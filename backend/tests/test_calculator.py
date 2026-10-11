from decimal import Decimal

import pytest

from app.calculator import CalculatorInputError, calculate


def test_calculator_evaluates_basic_arithmetic() -> None:
    assert calculate("(525000 - 472000) / 525000 * 100") == Decimal("10.09523809523809523809523810")


@pytest.mark.parametrize("expression", ["__import__('os').system('whoami')", "2 ** 1000", "1 / 0", "nan"])
def test_calculator_rejects_unsafe_or_invalid_expression(expression: str) -> None:
    with pytest.raises(CalculatorInputError):
        calculate(expression)
