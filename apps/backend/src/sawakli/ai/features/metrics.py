"""Deterministic metric primitives shared by all AI-01 features."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

Numeric = Decimal | int

# Pin precision and rounding so process-global Decimal changes cannot alter AI output.
FEATURE_DECIMAL_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)


def safe_divide(numerator: Numeric, denominator: Numeric) -> Decimal | None:
    """Divide finite values, returning ``None`` when the denominator is zero.

    ``None`` is the single missing-value representation used by AI-01. Inputs to
    this primitive come from validated canonical records, so non-finite Decimals
    are rejected before feature engineering.
    """

    decimal_numerator = _as_decimal(numerator)
    decimal_denominator = _as_decimal(denominator)
    if not decimal_numerator.is_finite() or not decimal_denominator.is_finite():
        raise ValueError("safe_divide requires finite operands")
    if decimal_denominator == 0:
        return None
    with localcontext(FEATURE_DECIMAL_CONTEXT):
        return decimal_numerator / decimal_denominator


def relative_change(current: Numeric, previous: Numeric) -> Decimal | None:
    """Return ``(current - previous) / previous`` using safe division."""

    with localcontext(FEATURE_DECIMAL_CONTEXT):
        difference = _as_decimal(current) - _as_decimal(previous)
    return safe_divide(difference, previous)


def decimal_sum(values: Iterable[Numeric]) -> Decimal:
    """Return a deterministic sum using the feature Decimal context."""

    with localcontext(FEATURE_DECIMAL_CONTEXT):
        return sum((_as_decimal(value) for value in values), start=Decimal(0))


def _as_decimal(value: Numeric) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(value)
