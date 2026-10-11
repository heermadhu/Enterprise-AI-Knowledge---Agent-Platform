import json
import re
import time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_tools import SQLGenerationError, database_query
from app.calculator import CalculatorInputError, calculate
from app.llm import LLMProviderError, chat_completion
from app.models import Document
from app.document_service import retrieve_chunks

TOOL_NAMES = {
    "document_search",
    "database_query",
    "calculator",
    "document_metadata_search",
}
MIN_DOCUMENT_EVIDENCE_SCORE = 0.18

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "document_search",
            "description": "Search indexed source documents and return evidence snippets with citations.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 8}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "database_query",
            "description": "Answer a business-data question using a validated, read-only SQL query.",
            "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a numeric arithmetic expression using only +, -, *, /, and parentheses.",
            "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "document_metadata_search",
            "description": "Find indexed documents by filename or title.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
        },
    },
]


class DocumentSearchArgs(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=6, ge=1, le=8)


class DatabaseQueryArgs(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class CalculatorArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=200)


class MetadataSearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)


def select_tools(query: str) -> list[str]:
    normalized = query.lower()
    tools: list[str] = []
    direct_business_terms = ("revenue", "sales", "order", "customer", "database")
    top_product_question = "product" in normalized and any(
        term in normalized for term in ("most", "top", "highest", "best", "revenue", "sales")
    )
    if any(term in normalized for term in direct_business_terms) or top_product_question:
        tools.append("database_query")
    if any(term in normalized for term in ("document", "report", "policy", "risk", "why", "explain", "both", "source", "cite")):
        tools.append("document_search")
    if "document" in normalized and any(term in normalized for term in ("list", "find", "uploaded", "file")):
        tools.append("document_metadata_search")
    if any(term in normalized for term in ("change", "compare", "compared", "difference", "decline", "declined", "fall", "fell", "percent", "percentage", "calculate")):
        tools.append("calculator")
    if not tools:
        tools.append("document_search")
    if "database_query" in tools and not any(term in normalized for term in ("why", "explain", "report", "both", "source")):
        tools = [tool for tool in tools if tool != "document_search"]
    return list(dict.fromkeys(tools))


async def _metadata_search(session: AsyncSession, query: str) -> list[dict]:
    rows = (
        await session.scalars(
            select(Document)
            .where(Document.filename.ilike(f"%{query}%"))
            .order_by(Document.uploaded_at.desc())
            .limit(20)
        )
    ).all()
    return [{"id": row.id, "filename": row.filename, "status": row.status} for row in rows]


async def _invoke_tool(
    name: str,
    arguments: dict,
    session: AsyncSession,
    source_cache: list[dict],
) -> dict:
    try:
        if name == "document_search":
            args = DocumentSearchArgs.model_validate(arguments)
            sources = await retrieve_chunks(args.query, args.limit)
            sources = [source for source in sources if source["score"] >= MIN_DOCUMENT_EVIDENCE_SCORE]
            source_cache.extend(sources)
            return {"citations": sources}
        if name == "database_query":
            args = DatabaseQueryArgs.model_validate(arguments)
            return await database_query(session, args.question)
        if name == "calculator":
            args = CalculatorArgs.model_validate(arguments)
            return {"expression": args.expression, "result": str(calculate(args.expression))}
        if name == "document_metadata_search":
            args = MetadataSearchArgs.model_validate(arguments)
            return {"documents": await _metadata_search(session, args.query)}
    except (ValidationError, SQLGenerationError, CalculatorInputError) as error:
        return {"error": str(error)}
    raise ValueError(f"Unsupported agent tool: {name}")


def _fallback_calculation(tool_results: list[dict], query: str) -> dict | None:
    database = next((result for result in tool_results if result.get("tool") == "database_query"), None)
    if database:
        rows = database["result"].get("rows", [])
        if rows and all("earlier_revenue" in row and "later_revenue" in row for row in rows):
            product_match = re.search(
                r"\b(NovaCloud|NovaSecure|NovaAnalytics|NovaFlow|NovaAI)\b",
                query,
                re.IGNORECASE,
            )
            if product_match:
                rows = [
                    row for row in rows
                    if row["product"].lower() == product_match.group(1).lower()
                ]
                if not rows:
                    return None
            earlier = sum((Decimal(row["earlier_revenue"]) for row in rows), Decimal(0))
            later = sum((Decimal(row["later_revenue"]) for row in rows), Decimal(0))
            difference = calculate(f"{earlier} - {later}")
            percent = calculate(f"{difference} / {earlier} * 100") if earlier else Decimal(0)
            return {
                "expression": f"{earlier} - {later}",
                "result": str(difference),
                "percent_change": str(percent),
                "comparison_base": str(earlier),
            }
    expression_match = re.search(r"(?:calculate|compute)\s+([0-9\s().,+*/-]{3,200})", query, re.IGNORECASE)
    if expression_match:
        expression = expression_match.group(1).strip()
        return {"expression": expression, "result": str(calculate(expression))}
    return None


def _format_fallback_answer(
    tool_results: list[dict],
    citations: list[dict],
    calculation: dict | None,
) -> str:
    parts: list[str] = []
    if citations:
        parts.append("Based on the indexed evidence:")
        for index, citation in enumerate(citations[:3], 1):
            excerpt = citation["snippet"].strip().replace("\n", " ")
            parts.append(f"\n[{index}] {excerpt[:1000]}")
    database = next((result for result in tool_results if result.get("tool") == "database_query"), None)
    if database:
        result = database["result"]
        if result.get("error"):
            parts.append(f"\nThe business-data query could not be completed: {result['error']}")
        elif result.get("rows"):
            parts.append(f"\nBusiness data returned {result['row_count']} row(s):")
            headers = result["columns"]
            parts.append("\n| " + " | ".join(headers) + " |")
            parts.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in result["rows"][:12]:
                parts.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
        else:
            parts.append("\nThe business-data query returned no matching records.")
    if calculation:
        parts.append(
            f"\nCalculation from the returned values: {calculation['expression']} = {calculation['result']}."
        )
        if "percent_change" in calculation:
            parts.append(
                f" That is a {calculation['percent_change']}% change against {calculation['comparison_base']}."
            )
    if not citations and not database:
        calculator = next((result for result in tool_results if result.get("tool") == "calculator"), None)
        if calculator:
            return (
                f"Calculation: {calculator['result']['expression']} = "
                f"{calculator['result']['result']}."
            )
    errors = [result["result"]["error"] for result in tool_results if result["result"].get("error")]
    if errors and not database:
        parts.append("\nA selected tool could not complete the request: " + "; ".join(errors))
    if not citations and not database and not tool_results:
        return "I don't have enough indexed evidence or business data to answer that question."
    if database and not citations and not database["result"].get("rows") and not database["result"].get("error"):
        return "I don't have enough matching business data to answer that question."
    if not citations and not database:
        return "I don't have enough indexed evidence to answer that question. Try uploading a relevant source document."
    return "\n".join(parts)


async def answer_query(
    query: str,
    session: AsyncSession,
    history: list[dict] | None = None,
) -> dict:
    started = time.perf_counter()
    retrieval_latency = 0.0
    llm_latency = 0.0
    token_usage = 0
    tool_results: list[dict] = []
    source_cache: list[dict] = []
    settings_provider_enabled = False
    from app.config import get_settings

    settings_provider_enabled = get_settings().llm_provider == "openai"
    resolved_query = query
    if history:
        previous_question = next(
            (message["content"] for message in reversed(history) if message["role"] == "user"),
            None,
        )
        if previous_question and re.match(
            r"^\s*(?:and\b|what about\b|how about\b|then\b|compare that\b)",
            query,
            re.IGNORECASE,
        ):
            resolved_query = f"{previous_question}\nFollow-up: {query}"
    if settings_provider_enabled:
        planner_messages = [
            {
                "role": "system",
                "content": (
                    "Select the minimum tools needed to answer the question using evidence. "
                    "Use multiple tools for cross-source questions; calculations must use calculator. "
                    "Never answer from memory. You may call only the provided tools."
                ),
            },
        ] + (history or [])[-8:] + [{"role": "user", "content": query}]
        plan = await chat_completion(planner_messages, TOOL_DEFINITIONS)
        llm_latency += plan.latency_ms
        token_usage += (plan.prompt_tokens or 0) + (plan.completion_tokens or 0)
        selected_calls = plan.tool_calls
        if selected_calls:
            for call in selected_calls[:6]:
                name = call.get("function", {}).get("name", "")
                if name not in TOOL_NAMES:
                    raise ValueError("The agent attempted to call an unavailable tool.")
                try:
                    args = json.loads(call.get("function", {}).get("arguments", "{}"))
                except json.JSONDecodeError as error:
                    raise ValueError("The agent returned invalid tool arguments.") from error
                tool_started = time.perf_counter()
                result = await _invoke_tool(name, args, session, source_cache)
                if name == "document_search":
                    retrieval_latency += (time.perf_counter() - tool_started) * 1000
                tool_results.append({"tool": name, "result": result})
            final_messages = [
                {"role": "system", "content": (
                    "Answer only from the supplied tool results. If evidence is insufficient, say so. "
                    "Cite document claims with [1], [2], etc. Do not reveal chain-of-thought; provide only "
                    "the answer and a concise description of sources/tools used."
                )},
                {"role": "user", "content": query},
                {"role": "assistant", "tool_calls": selected_calls[:6]},
            ]
            for call, output in zip(selected_calls[:6], tool_results):
                final_messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(output["result"], default=str)}
                )
            final = await chat_completion(final_messages)
            llm_latency += final.latency_ms
            token_usage += (final.prompt_tokens or 0) + (final.completion_tokens or 0)
            answer = final.content.strip()
            selected_tools = list(dict.fromkeys(item["tool"] for item in tool_results))
        else:
            selected_tools = select_tools(resolved_query)
    else:
        selected_tools = select_tools(resolved_query)

    if not settings_provider_enabled or not tool_results:
        for tool in selected_tools:
            tool_started = time.perf_counter()
            arguments: dict[str, Any]
            if tool == "database_query":
                arguments = {"question": resolved_query}
            elif tool == "calculator":
                calculation = _fallback_calculation(tool_results, resolved_query)
                if calculation:
                    tool_results.append({"tool": "calculator", "result": calculation})
                continue
            else:
                arguments = {"query": resolved_query}
            result = await _invoke_tool(tool, arguments, session, source_cache)
            if tool == "document_search":
                retrieval_latency += (time.perf_counter() - tool_started) * 1000
            tool_results.append({"tool": tool, "result": result})
        calculation = _fallback_calculation(tool_results, resolved_query) if "calculator" in selected_tools else None
        if calculation and not any(result["tool"] == "calculator" for result in tool_results):
            tool_results.append({"tool": "calculator", "result": calculation})
        answer = _format_fallback_answer(tool_results, source_cache, calculation)

    unique_sources: list[dict] = []
    seen: set[tuple] = set()
    for source in source_cache:
        key = (source["document_id"], source["chunk_index"])
        if key not in seen:
            seen.add(key)
            unique_sources.append(source)
    return {
        "answer": answer,
        "citations": unique_sources,
        "selected_tools": selected_tools,
        "tool_results": tool_results,
        "sql": next(
            (item["result"].get("sql") for item in tool_results if item["tool"] == "database_query"),
            None,
        ),
        "retrieval_latency_ms": round(retrieval_latency, 2),
        "llm_latency_ms": round(llm_latency, 2),
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "token_usage": token_usage or None,
    }
