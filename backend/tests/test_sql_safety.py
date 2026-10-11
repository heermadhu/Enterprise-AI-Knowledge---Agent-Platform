import pytest

from app.sql_safety import UnsafeQueryError, validate_read_only_sql


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "UPDATE customers SET name = 'x'",
        "INSERT INTO customers (name) VALUES ('x')",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD COLUMN x TEXT",
        "TRUNCATE customers",
        "SELECT * FROM secrets",
        "SELECT pg_sleep(10) FROM customers",
        "SELECT * FROM customers; DROP TABLE customers",
        "SELECT * INTO archived_customers FROM customers",
    ],
)
def test_unsafe_sql_is_rejected(sql: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql(sql)


def test_select_is_limited_and_allowed() -> None:
    safe = validate_read_only_sql("SELECT name FROM products ORDER BY name LIMIT 10000")

    assert safe.endswith("LIMIT 100")
    assert validate_read_only_sql("SELECT COUNT(*) AS customers FROM customers").endswith("LIMIT 100")
    assert "SUBSTRING(" in validate_read_only_sql(
        "SELECT SUBSTRING(CAST(order_date AS TEXT), 1, 7) AS month FROM orders"
    )
