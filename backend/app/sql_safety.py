import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ALLOWED_TABLES = {"customers", "products", "orders", "sales", "monthly_revenue"}
ALLOWED_FUNCTIONS = {
    "AVG", "CAST", "COALESCE", "COUNT", "EXTRACT", "LOWER", "MAX", "MIN",
    "ROUND", "SUBSTRING", "SUM", "UPPER",
}
STRUCTURAL_FUNCTION_NODES = {
    "And", "Or", "Not", "EQ", "NEQ", "GT", "GTE", "LT", "LTE",
    "Is", "In", "Between", "Like", "ILike", "Case", "If",
}
MAX_ROWS = 100


class UnsafeQueryError(ValueError):
    pass


def validate_read_only_sql(statement: str) -> str:
    if not statement or len(statement) > 10000:
        raise UnsafeQueryError("SQL must contain between 1 and 10,000 characters.")
    try:
        parsed_statements = sqlglot.parse(statement, read="postgres")
    except ParseError as error:
        raise UnsafeQueryError("The generated SQL could not be parsed.") from error
    if len(parsed_statements) != 1 or parsed_statements[0] is None:
        raise UnsafeQueryError("Only one SQL statement is allowed.")

    query = parsed_statements[0]
    if not isinstance(query, exp.Select):
        raise UnsafeQueryError("Only read-only SELECT queries are allowed.")
    if query.args.get("into") is not None or query.args.get("locks"):
        raise UnsafeQueryError("SELECT INTO and locking queries are not allowed.")

    tables = {table.name.lower() for table in query.find_all(exp.Table)}
    if not tables or not tables.issubset(ALLOWED_TABLES):
        raise UnsafeQueryError("The query references a table that is not available.")

    for function in query.find_all(exp.Func):
        if type(function).__name__ in STRUCTURAL_FUNCTION_NODES:
            continue
        function_name = function.sql_name().upper()
        if function_name not in ALLOWED_FUNCTIONS:
            raise UnsafeQueryError(f"The SQL function {function_name} is not allowed.")

    limit = query.args.get("limit")
    if limit is None:
        query = query.limit(MAX_ROWS)
    else:
        expression = limit.expression
        if isinstance(expression, exp.Literal) and expression.is_number:
            requested_limit = int(expression.this)
            if requested_limit < 1:
                raise UnsafeQueryError("The row limit must be at least 1.")
            if requested_limit > MAX_ROWS:
                limit.set("expression", exp.Literal.number(MAX_ROWS))
    return query.sql(dialect="postgres")
