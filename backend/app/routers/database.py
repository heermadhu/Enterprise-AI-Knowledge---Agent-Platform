from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_tools import SQLGenerationError, database_query
from app.db import SessionLocal, get_session
from app.models import Customer, MonthlyRevenue, Order, Product, Sale
from app.telemetry import elapsed_ms, record_metric

router = APIRouter(prefix="/api/database", tags=["database"])


class DatabaseQueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


@router.get("/overview")
async def database_overview(session: AsyncSession = Depends(get_session)) -> dict:
    result = await session.execute(
        select(
            select(func.count()).select_from(Customer).scalar_subquery().label("customers"),
            select(func.count()).select_from(Product).scalar_subquery().label("products"),
            select(func.count()).select_from(Order).scalar_subquery().label("orders"),
            select(func.count()).select_from(Sale).scalar_subquery().label("sales"),
            select(func.coalesce(func.sum(MonthlyRevenue.revenue), 0))
            .select_from(MonthlyRevenue)
            .scalar_subquery()
            .label("revenue"),
        )
    )
    row = result.mappings().one()
    monthly = (
        await session.execute(
            select(MonthlyRevenue.month, MonthlyRevenue.revenue)
            .order_by(MonthlyRevenue.month)
        )
    ).all()
    return {
        "customers": row["customers"],
        "products": row["products"],
        "orders": row["orders"],
        "sales": row["sales"],
        "recognized_revenue": str(row["revenue"]),
        "monthly_revenue": [{"month": month.isoformat(), "revenue": str(revenue)} for month, revenue in monthly],
    }


@router.post("/query")
async def query_database(
    body: DatabaseQueryRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    started = __import__("time").perf_counter()
    result = None
    error = None
    status_code = 200
    try:
        result = await database_query(session, body.question)
        return result
    except (SQLGenerationError, ValueError) as exc:
        error = type(exc).__name__
        status_code = 422
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        error = type(exc).__name__
        status_code = 500
        raise
    finally:
        await session.rollback()
        async with SessionLocal() as metrics_session:
            await record_metric(
                metrics_session,
                request_id=request.state.request_id,
                query=body.question,
                status_code=status_code,
                result=result,
                error=error,
                total_latency_ms=elapsed_ms(started),
            )
