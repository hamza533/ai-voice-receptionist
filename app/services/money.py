"""Price formatting shared by the receptionist's tools and instructions."""

from __future__ import annotations

from decimal import Decimal


def format_money(currency: str, amount: object) -> str:
    """`GBP 25` for whole amounts, `GBP 12.50` otherwise: never round a price away."""
    value = Decimal(str(amount))
    digits = 0 if value == value.to_integral_value() else 2
    return f"{currency} {value:,.{digits}f}"
