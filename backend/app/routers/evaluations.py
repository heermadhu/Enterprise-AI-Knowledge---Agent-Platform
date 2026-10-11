import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import answer_query
from app.db import SessionLocal, get_session
from app.models import EvaluationRun
from app.sql_safety import UnsafeQueryError, validate_read_only_sql

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])
CASE_FILE = Path(__file__).resolve().parents[3] / "evaluation" / "cases.json"


def load_cases() -> list[dict]:
    with CASE_FILE.open(encoding="utf-8") as file:
        cases = json.load(file)
    if not isinstance(cases, list) or len(cases) < 40:
        raise RuntimeError("The evaluation suite must contain at least 40 cases.")
    return cases


class EvaluationRunRequest(BaseModel):
    limit: int = Field(default=48, ge=1, le=100)


@router.get("/cases")
async def evaluation_cases() -> dict:
    cases = load_cases()
    categories: dict[str, int] = {}
    for case in cases:
        categories[case["category"]] = categories.get(case["category"], 0) + 1
    return {"count": len(cases), "categories": categories, "cases": cases}


def _contains_expected_keyword(answer: str, keyword: str) -> bool:
    normalized_keyword = keyword.lower()
    if normalized_keyword in answer:
        return True
    try:
        expected_number = Decimal(keyword.replace(",", ""))
    except InvalidOperation:
        return False
    tolerance = Decimal("0.005") if expected_number.as_tuple().exponent < 0 else Decimal(0)
    for number in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?", answer):
        try:
            if abs(Decimal(number.replace(",", "")) - expected_number) <= tolerance:
                return True
        except InvalidOperation:
            continue
    return False


def _case_result(case: dict, result: dict) -> dict[str, Any]:
    answer = result["answer"].lower()
    expected_keywords = case.get("keywords", [])
    keyword_matches = sum(_contains_expected_keyword(answer, keyword) for keyword in expected_keywords)
    answer_correctness = keyword_matches / len(expected_keywords) if expected_keywords else None
    sources = result["citations"]
    expected_sources = case.get("sources", [])
    retrieval_relevance = None
    citation_correctness = None
    if expected_sources:
        relevant = [
            source
            for source in sources
            if any(term.lower() in source["filename"].lower() for term in expected_sources)
        ]
        retrieval_relevance = min(1.0, len(relevant) / max(len(sources), 1))
        citation_correctness = min(
            1.0,
            sum(
                any(term.lower() in source["filename"].lower() for term in expected_sources)
                and bool(source["snippet"].strip())
                for source in sources
            )
            / len(expected_sources),
        )
    sql_correctness = None
    if case.get("sql"):
        try:
            sql_correctness = 1.0 if result["sql"] and validate_read_only_sql(result["sql"]) else 0.0
        except UnsafeQueryError:
            sql_correctness = 0.0
    expected_tools = set(case.get("tools", []))
    actual_tools = set(result["selected_tools"])
    tool_selection_correctness = (
        len(expected_tools & actual_tools) / len(expected_tools) if expected_tools else None
    )
    return {
        "case_id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "answer": result["answer"],
        "answer_correctness": answer_correctness,
        "retrieval_relevance": retrieval_relevance,
        "citation_correctness": citation_correctness,
        "sql_correctness": sql_correctness,
        "tool_selection_correctness": tool_selection_correctness,
        "latency_ms": result["total_latency_ms"],
        "token_usage": result["token_usage"],
        "citations": result["citations"],
        "selected_tools": result["selected_tools"],
    }


def _mean(results: list[dict], key: str) -> float | None:
    values = [result[key] for result in results if result[key] is not None]
    return round(sum(values) / len(values), 4) if values else None


@router.post("/runs", status_code=201)
async def run_evaluation(
    body: EvaluationRunRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    cases = load_cases()[: body.limit]
    run = EvaluationRun(status="running", total_cases=len(cases), results=[])
    session.add(run)
    await session.commit()
    await session.refresh(run)

    results: list[dict] = []
    try:
        for case in cases:
            response = await answer_query(case["question"], session)
            results.append(_case_result(case, response))
            await session.rollback()
        run.results = results
        run.status = "completed"
        run.finished_at = datetime.utcnow()
        await session.commit()
    except Exception as error:
        await session.rollback()
        run.status = "failed"
        run.results = results
        run.finished_at = datetime.utcnow()
        await session.commit()
        raise HTTPException(status_code=500, detail="Evaluation run failed. See request monitoring for details.") from error

    summary = {
        "answer_correctness": _mean(results, "answer_correctness"),
        "retrieval_relevance": _mean(results, "retrieval_relevance"),
        "citation_correctness": _mean(results, "citation_correctness"),
        "sql_correctness": _mean(results, "sql_correctness"),
        "tool_selection_correctness": _mean(results, "tool_selection_correctness"),
        "average_latency_ms": _mean(results, "latency_ms"),
        "average_token_usage": _mean(results, "token_usage"),
    }
    return {"id": run.id, "status": run.status, "total_cases": len(results), "summary": summary, "results": results}


@router.get("/runs")
async def list_evaluation_runs(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.scalars(
            select(EvaluationRun).order_by(EvaluationRun.started_at.desc()).limit(20)
        )
    ).all()
    return [
        {
            "id": run.id,
            "status": run.status,
            "total_cases": run.total_cases,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "summary": {
                "answer_correctness": _mean(run.results, "answer_correctness"),
                "retrieval_relevance": _mean(run.results, "retrieval_relevance"),
                "citation_correctness": _mean(run.results, "citation_correctness"),
                "sql_correctness": _mean(run.results, "sql_correctness"),
                "average_latency_ms": _mean(run.results, "latency_ms"),
            },
        }
        for run in rows
    ]


@router.get("/runs/{run_id}")
async def get_evaluation_run(run_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found.")
    summary = {
        "answer_correctness": _mean(run.results, "answer_correctness"),
        "retrieval_relevance": _mean(run.results, "retrieval_relevance"),
        "citation_correctness": _mean(run.results, "citation_correctness"),
        "sql_correctness": _mean(run.results, "sql_correctness"),
        "tool_selection_correctness": _mean(run.results, "tool_selection_correctness"),
        "average_latency_ms": _mean(run.results, "latency_ms"),
        "average_token_usage": _mean(run.results, "token_usage"),
    }
    return {
        "id": run.id,
        "status": run.status,
        "total_cases": run.total_cases,
        "summary": summary,
        "results": run.results,
    }
