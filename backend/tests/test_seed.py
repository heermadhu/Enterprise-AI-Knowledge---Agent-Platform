from sqlalchemy import func, select

from app.models import Customer, MonthlyRevenue, Order, Product, Sale
from app.seed import seed_business_data


async def test_seed_is_consistent_and_idempotent(db_session) -> None:
    await seed_business_data(db_session)
    await seed_business_data(db_session)

    assert await db_session.scalar(select(func.count()).select_from(Customer)) == 120
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 20
    assert await db_session.scalar(select(func.count()).select_from(Order)) == 1200
    assert await db_session.scalar(select(func.count()).select_from(Sale)) == 1200
    assert await db_session.scalar(select(func.count()).select_from(MonthlyRevenue)) == 12

    august = await db_session.scalar(select(MonthlyRevenue.revenue).where(MonthlyRevenue.month == "2025-08-01"))
    september = await db_session.scalar(select(MonthlyRevenue.revenue).where(MonthlyRevenue.month == "2025-09-01"))
    assert float(august) - float(september) == 53000
