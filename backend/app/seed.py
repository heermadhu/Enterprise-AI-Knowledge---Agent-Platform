import asyncio
import calendar
import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.document_service import ingest_document
from app.models import Customer, Document, MonthlyRevenue, Order, Product, Sale

MONTHLY_PRODUCT_REVENUE = {
    1: (145000, 90000, 75000, 60000, 50000),
    2: (150000, 93000, 77000, 61000, 49000),
    3: (155000, 96000, 80000, 63000, 51000),
    4: (157000, 98000, 81000, 63000, 51000),
    5: (161000, 100000, 83000, 65000, 53000),
    6: (168000, 103000, 85000, 68000, 56000),
    7: (174000, 108000, 86000, 72000, 60000),
    8: (180000, 115000, 90000, 75000, 65000),
    9: (166000, 84000, 85000, 67000, 70000),
    10: (185000, 114000, 92000, 77000, 67000),
    11: (190000, 117000, 95000, 80000, 68000),
    12: (204000, 124000, 100000, 86000, 71000),
}
PRODUCT_NAMES = ["NovaCloud", "NovaSecure", "NovaAnalytics", "NovaFlow", "NovaAI"]
OTHER_PRODUCTS = [
    "NovaCloud Backup", "NovaCloud Edge", "NovaSecure Identity", "NovaSecure Audit",
    "NovaAnalytics BI", "NovaAnalytics Forecast", "NovaFlow Automate", "NovaFlow Connect",
    "NovaAI Assist", "NovaAI Studio", "NovaCloud Storage", "NovaSecure Endpoint",
    "NovaAnalytics Warehouse", "NovaFlow Approvals", "NovaAI Search",
]


async def seed_business_data(session: AsyncSession) -> None:
    counts = await session.execute(
        select(
            select(func.count()).select_from(Customer).scalar_subquery().label("customers"),
            select(func.count()).select_from(Product).scalar_subquery().label("products"),
            select(func.count()).select_from(Order).scalar_subquery().label("orders"),
            select(func.count()).select_from(Sale).scalar_subquery().label("sales"),
            select(func.count()).select_from(MonthlyRevenue).scalar_subquery().label("months"),
        )
    )
    current = counts.mappings().one()
    if any(current.values()):
        if (
            current["customers"] < 100
            or current["products"] < 20
            or current["orders"] < 1000
            or current["sales"] < 1000
            or current["months"] < 12
        ):
            raise RuntimeError("NovaTech business seed data is incomplete; refusing to start with partial records.")
        return

    products = [
        Product(name=name, category="Enterprise Software", unit_price=Decimal(price))
        for name, price in zip(PRODUCT_NAMES + OTHER_PRODUCTS, [129, 89, 99, 79, 149] + [49, 59, 69] * 5)
    ]
    customers = [
        Customer(
            name=f"{company} {index:03}",
            email=f"account{index:03}@{company.lower().replace(' ', '')}.example",
            industry=["Technology", "Healthcare", "Finance", "Retail", "Manufacturing"][index % 5],
            region=["North America", "EMEA", "APAC", "Latin America"][index % 4],
        )
        for index in range(1, 121)
        for company in [f"CustomerCo{index:03}"]
    ]
    session.add_all(products + customers)
    await session.flush()

    products_by_name = {product.name: product for product in products}
    orders: list[Order] = []
    sales: list[Sale] = []
    monthly: list[MonthlyRevenue] = []
    order_number = 0
    for month, product_amounts in MONTHLY_PRODUCT_REVENUE.items():
        month_order_count = 0
        for product_index, amount in enumerate(product_amounts):
            base, remainder = divmod(amount * 100, 20)
            for order_in_product in range(20):
                cents = base + (1 if order_in_product < remainder else 0)
                order_number += 1
                month_order_count += 1
                customer = customers[(order_number * 37) % len(customers)]
                order = Order(
                    customer_id=customer.id,
                    order_date=date(2025, month, min(3 + order_in_product, calendar.monthrange(2025, month)[1])),
                    status="completed",
                    order_total=Decimal(cents) / 100,
                )
                orders.append(order)
                sales.append(
                    Sale(
                        order=order,
                        product_id=products_by_name[PRODUCT_NAMES[product_index]].id,
                        units=1,
                        unit_price=Decimal(cents) / 100,
                        revenue=Decimal(cents) / 100,
                    )
                )
        monthly.append(
            MonthlyRevenue(
                month=date(2025, month, 1),
                revenue=Decimal(sum(product_amounts)),
                order_count=month_order_count,
            )
        )
    session.add_all(orders + sales + monthly)
    await session.commit()


async def seed_source_documents(session: AsyncSession) -> None:
    source_dir = Path(__file__).resolve().parents[2] / "data" / "documents"
    if not source_dir.is_dir():
        raise FileNotFoundError(f"NovaTech source document directory is missing: {source_dir}")
    stored_checksums = set((await session.scalars(select(Document.checksum))).all())
    for path in sorted(source_dir.glob("*.txt")):
        data = await asyncio.to_thread(path.read_bytes)
        checksum = hashlib.sha256(data).hexdigest()
        if checksum in stored_checksums:
            continue
        await ingest_document(session, path.name, "text/plain", data)
        stored_checksums.add(checksum)
