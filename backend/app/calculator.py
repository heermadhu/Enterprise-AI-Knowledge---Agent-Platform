import ast
import math
from decimal import Decimal, DivisionByZero, InvalidOperation


class CalculatorInputError(ValueError):
    pass


def calculate(expression: str) -> Decimal:
    if not expression or len(expression) > 200:
        raise CalculatorInputError("Enter an arithmetic expression of at most 200 characters.")
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise CalculatorInputError("The calculator accepts arithmetic only.") from error

    def evaluate(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            value = Decimal(str(node.value))
            if not value.is_finite():
                raise CalculatorInputError("The value must be finite.")
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise CalculatorInputError("Division by zero is not allowed.")
            return left / right
        raise CalculatorInputError("Only numeric values and +, -, *, /, and parentheses are allowed.")

    try:
        result = evaluate(parsed)
    except (InvalidOperation, DivisionByZero) as error:
        raise CalculatorInputError("The arithmetic expression is invalid.") from error
    if not math.isfinite(float(result)):
        raise CalculatorInputError("The result is outside the supported numeric range.")
    return result
