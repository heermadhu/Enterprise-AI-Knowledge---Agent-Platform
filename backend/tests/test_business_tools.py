from app.agent import answer_query, select_tools
from app.business_tools import database_query, execute_sql, generate_sql
from app.seed import seed_business_data
from app.sql_safety import UnsafeQueryError
from decimal import Decimal


async def test_database_sql_returns_seeded_quarter_and_product_results(db_session) -> None:
    await seed_business_data(db_session)

    q3 = await database_query(db_session, "What was revenue in Q3 2025?")
    winner = await database_query(db_session, "Which product generated the most revenue?")

    assert Decimal(str(q3["rows"][0]["revenue"])) == Decimal("1497000")
    assert winner["rows"][0]["product"] == "NovaCloud"
    assert Decimal(str(winner["rows"][0]["revenue"])) == Decimal("2035000")
    assert "LIMIT 100" in q3["sql"]


async def test_month_comparison_matches_seeded_product_revenue(db_session) -> None:
    await seed_business_data(db_session)

    result = await database_query(
        db_session,
        "Why did September revenue fall compared with August in 2025?",
    )

    assert sum(Decimal(str(row["earlier_revenue"])) for row in result["rows"]) == Decimal("525000")
    assert sum(Decimal(str(row["later_revenue"])) for row in result["rows"]) == Decimal("472000")
    assert sum(Decimal(str(row["change"])) for row in result["rows"]) == Decimal("-53000")


async def test_quarter_comparison_returns_both_quarters(db_session) -> None:
    await seed_business_data(db_session)

    result = await database_query(db_session, "Compare Q3 to Q2 revenue in 2025.")

    assert {row["quarter"]: Decimal(str(row["revenue"])) for row in result["rows"]} == {
        "Q3": Decimal("1497000"),
        "Q2": Decimal("1392000"),
    }


async def test_monthly_order_volume_query_executes(db_session) -> None:
    await seed_business_data(db_session)

    result = await database_query(db_session, "Show the 2025 order volume by month.")

    assert result["row_count"] == 12
    assert result["rows"][0]["month"] == "2025-01"
    assert result["rows"][0]["order_count"] == 100


async def test_product_comparison_is_scoped_to_requested_quarter(db_session) -> None:
    await seed_business_data(db_session)

    result = await database_query(
        db_session,
        "Compare NovaCloud and NovaAI revenue performance in Q3 2025.",
    )

    revenue = {row["product"]: Decimal(str(row["revenue"])) for row in result["rows"]}
    assert revenue["NovaCloud"] == Decimal("520000")
    assert revenue["NovaAI"] == Decimal("195000")


async def test_unsupported_year_returns_no_seeded_revenue(db_session) -> None:
    await seed_business_data(db_session)

    result = await database_query(db_session, "What was NovaTech's exact 2024 annual revenue?")

    assert result["row_count"] == 0
    assert "2024-01-01" in result["sql"]


async def test_sql_executor_revalidates_before_execution(db_session) -> None:
    try:
        await execute_sql(db_session, "DELETE FROM customers")
    except UnsafeQueryError:
        pass
    else:
        raise AssertionError("The SQL executor must reject mutations.")


def test_agent_routes_multi_source_and_document_questions() -> None:
    assert select_tools("Why did September revenue fall compared with August?") == [
        "database_query",
        "document_search",
        "calculator",
    ]
    assert select_tools("What risks are mentioned in the Q3 report?") == ["document_search"]
    assert select_tools("What was revenue in Q3?") == ["database_query"]
