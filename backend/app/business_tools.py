import calendar
import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.llm import LLMProviderError, chat_completion
from app.sql_safety import validate_read_only_sql

MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}


class SQLGenerationError(ValueError):
    pass


def _deterministic_sql(question: str) -> str:
    query = question.lower()
    year_match = re.search(r"\b(20\d{2})\b", query)
    year = int(year_match.group(1)) if year_match else 2025

    matched_months = [(name, month) for name, month in MONTHS.items() if re.search(rf"\b{name}\b", query)]
    if len(matched_months) >= 2:
        first, second = matched_months[:2]
        start_month, end_month = sorted([first[1], second[1]])
        start = date(year, start_month, 1).isoformat()
        following = date(year + 1, 1, 1) if end_month == 12 else date(year, end_month + 1, 1)
        if "product" in query or "why" in query or "compare" in query or "fall" in query or "declin" in query:
            return f"""
                SELECT p.name AS product,
                       SUM(CASE WHEN o.order_date < '{date(year, end_month, 1).isoformat()}' THEN s.revenue ELSE 0 END) AS earlier_revenue,
                       SUM(CASE WHEN o.order_date >= '{date(year, end_month, 1).isoformat()}' THEN s.revenue ELSE 0 END) AS later_revenue,
                       SUM(CASE WHEN o.order_date >= '{date(year, end_month, 1).isoformat()}' THEN s.revenue ELSE -s.revenue END) AS change
                FROM sales s
                JOIN products p ON p.id = s.product_id
                JOIN orders o ON o.id = s.order_id
                WHERE o.order_date >= '{start}' AND o.order_date < '{following.isoformat()}'
                GROUP BY p.name ORDER BY change
            """
        return f"""
            SELECT month, revenue, order_count FROM monthly_revenue
            WHERE month IN ('{date(year, start_month, 1)}', '{date(year, end_month, 1)}')
            ORDER BY month
        """

    quarter_matches = list(dict.fromkeys(re.findall(r"\bq([1-4])\b", query)))
    if len(quarter_matches) >= 2 and ("revenue" in query or "sales" in query):
        queries = []
        for quarter_text in quarter_matches[:4]:
            quarter = int(quarter_text)
            first_month = (quarter - 1) * 3 + 1
            last_month = first_month + 3
            last_date = date(year, last_month, 1) if last_month <= 12 else date(year + 1, 1, 1)
            queries.append(
                f"SELECT 'Q{quarter}' AS quarter, SUM(revenue) AS revenue FROM monthly_revenue "
                f"WHERE month >= '{date(year, first_month, 1)}' AND month < '{last_date}'"
            )
        return "SELECT quarter, revenue FROM (" + " UNION ALL ".join(queries) + ") AS quarter_totals"

    quarter_match = re.search(r"\bq([1-4])\b", query)
    known_products = ("novacloud", "novasecure", "novaanalytics", "novaflow", "novaai")
    product_question = "product" in query or any(name in query for name in known_products)
    if quarter_match and product_question and any(
        word in query for word in ("revenue", "sales", "compare", "performance")
    ):
        quarter = int(quarter_match.group(1))
        first_month = (quarter - 1) * 3 + 1
        last_month = first_month + 3
        return (
            "SELECT p.name AS product, SUM(s.revenue) AS revenue "
            "FROM sales s JOIN products p ON p.id = s.product_id "
            "JOIN orders o ON o.id = s.order_id "
            f"WHERE o.order_date >= '{date(year, first_month, 1)}' "
            f"AND o.order_date < '{date(year, last_month, 1) if last_month <= 12 else date(year + 1, 1, 1)}' "
            "GROUP BY p.name ORDER BY revenue DESC"
        )

    if quarter_match and ("revenue" in query or "sales" in query or "order" in query):
        quarter = int(quarter_match.group(1))
        first_month = (quarter - 1) * 3 + 1
        last_month = first_month + 3
        return (
            "SELECT SUM(revenue) AS revenue, SUM(order_count) AS order_count "
            "FROM monthly_revenue "
            f"WHERE month >= '{date(year, first_month, 1)}' AND month < '{date(year, last_month, 1) if last_month <= 12 else date(year + 1, 1, 1)}'"
        )

    if "product" in query and any(word in query for word in ("most", "top", "highest", "best", "revenue", "sales")):
        return (
            "SELECT p.name AS product, SUM(s.revenue) AS revenue "
            "FROM sales s JOIN products p ON p.id = s.product_id "
            "JOIN orders o ON o.id = s.order_id "
            f"WHERE o.order_date >= '{date(year, 1, 1)}' AND o.order_date < '{date(year + 1, 1, 1)}' "
            "GROUP BY p.name ORDER BY revenue DESC LIMIT 5"
        )

    if matched_months and any(word in query for word in ("revenue", "sales", "month", "fall", "declin")):
        month = matched_months[0][1]
        first_day = date(year, month, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return (
            "SELECT month, revenue, order_count FROM monthly_revenue "
            f"WHERE month >= '{first_day}' AND month < '{next_month}' ORDER BY month"
        )

    if any(word in query for word in ("customer", "account")) and any(word in query for word in ("count", "how many", "total")):
        return "SELECT COUNT(*) AS customer_count FROM customers"
    if any(word in query for word in ("order", "orders")) and any(word in query for word in ("count", "how many", "total")):
        return "SELECT COUNT(*) AS order_count FROM orders"
    if any(word in query for word in ("order", "orders")) and any(word in query for word in ("month", "monthly")):
        return (
            "SELECT SUBSTRING(CAST(order_date AS TEXT), 1, 7) AS month, COUNT(*) AS order_count "
            "FROM orders GROUP BY SUBSTRING(CAST(order_date AS TEXT), 1, 7) ORDER BY month"
        )
    if any(word in query for word in ("revenue", "sales", "business")):
        return (
            "SELECT month, revenue FROM monthly_revenue "
            f"WHERE month >= '{date(year, 1, 1)}' AND month < '{date(year + 1, 1, 1)}' "
            "ORDER BY month DESC LIMIT 12"
        )
    raise SQLGenerationError("The local SQL generator does not support this business-data question.")


async def generate_sql(question: str) -> str:
    settings = get_settings()
    if settings.llm_provider != "openai":
        return validate_read_only_sql(_deterministic_sql(question))
    try:
        response = await chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Translate the business question into one PostgreSQL SELECT statement only. "
                        "Available tables: customers(id,name,email,industry,region,created_at), "
                        "products(id,name,category,unit_price,active), orders(id,customer_id,order_date,status,order_total), "
                        "sales(id,order_id,product_id,units,unit_price,revenue), "
                        "monthly_revenue(id,month,revenue,order_count). Use explicit joins and aliases. "
                        "Never use mutation, DDL, system tables, comments, or non-read-only functions. "
                        "Return SQL only, without markdown."
                    ),
                },
                {"role": "user", "content": question},
            ]
        )
    except LLMProviderError as error:
        raise SQLGenerationError(str(error)) from error
    statement = response.content.strip().removeprefix("```sql").removesuffix("```").strip()
    return validate_read_only_sql(statement)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


async def execute_sql(session: AsyncSession, statement: str) -> dict:
    safe_statement = validate_read_only_sql(statement)
    dialect = session.get_bind().dialect.name
    executable_statement = safe_statement
    if dialect == "postgresql":
        await session.execute(text("SET TRANSACTION READ ONLY"))
    elif dialect == "sqlite":
        executable_statement = sqlglot.transpile(
            safe_statement, read="postgres", write="sqlite"
        )[0]
    result = await session.execute(text(executable_statement))
    columns = list(result.keys())
    rows = [
        {key: _serialize_value(value) for key, value in row.items()}
        for row in result.mappings().all()
    ]
    return {"sql": safe_statement, "columns": columns, "rows": rows, "row_count": len(rows)}


async def database_query(session: AsyncSession, question: str) -> dict:
    statement = await generate_sql(question)
    return await execute_sql(session, statement)
