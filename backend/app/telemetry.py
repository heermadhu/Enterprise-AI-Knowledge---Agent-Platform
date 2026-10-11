import re
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RequestMetric

SECRET_PATTERNS = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|password|secret|token)\b\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED]"),
)


def redact_query(query: str) -> str:
    redacted = query
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted[:4000]


async def record_metric(
    session: AsyncSession,
    *,
    request_id: str,
    query: str,
    status_code: int,
    result: dict[str, Any] | None,
    error: str | None,
    total_latency_ms: float,
) -> None:
    session.add(
        RequestMetric(
            request_id=request_id,
            status_code=status_code,
            query=redact_query(query),
            selected_tools=(result or {}).get("selected_tools", []),
            retrieval_latency_ms=(result or {}).get("retrieval_latency_ms", 0),
            llm_latency_ms=(result or {}).get("llm_latency_ms", 0),
            total_latency_ms=total_latency_ms,
            retrieved_chunks=len((result or {}).get("citations", [])),
            token_usage=(result or {}).get("token_usage"),
            error=error,
        )
    )
    await session.commit()


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)
