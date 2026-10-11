from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import RequestMetric

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/summary")
async def monitoring_summary(session: AsyncSession = Depends(get_session)) -> dict:
    aggregate = await session.execute(
        select(
            func.count(RequestMetric.id).label("requests"),
            func.sum(case((RequestMetric.status_code >= 400, 1), else_=0)).label("errors"),
            func.avg(RequestMetric.total_latency_ms).label("average_latency_ms"),
            func.sum(RequestMetric.retrieved_chunks).label("retrieved_chunks"),
            func.sum(RequestMetric.token_usage).label("tokens"),
        )
    )
    row = aggregate.mappings().one()
    return {
        "requests": row["requests"] or 0,
        "errors": row["errors"] or 0,
        "average_latency_ms": round(float(row["average_latency_ms"] or 0), 2),
        "retrieved_chunks": row["retrieved_chunks"] or 0,
        "token_usage": row["tokens"] or 0,
    }


@router.get("/requests")
async def monitoring_requests(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    if limit < 1 or limit > 200:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Limit must be between 1 and 200.")
    rows = (
        await session.scalars(
            select(RequestMetric)
            .order_by(RequestMetric.timestamp.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "request_id": row.request_id,
            "timestamp": row.timestamp,
            "status_code": row.status_code,
            "query": row.query,
            "selected_tools": row.selected_tools,
            "retrieval_latency_ms": row.retrieval_latency_ms,
            "llm_latency_ms": row.llm_latency_ms,
            "total_latency_ms": row.total_latency_ms,
            "retrieved_chunks": row.retrieved_chunks,
            "token_usage": row.token_usage,
            "error": row.error,
        }
        for row in rows
    ]
