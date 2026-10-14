"""Logical types: parsing, literal coercion and canonical text."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from data_automation.types import coerce_literal, format_text, parse_text, python_values, to_series


@pytest.mark.parametrize(
    "kind, text, expected",
    [
        ("integer", " 42 ", 42),
        ("integer", "-7", -7),
        ("decimal", "120.50", Decimal("120.50")),
        ("decimal", ".5", Decimal("0.5")),
        ("decimal", "-3", Decimal("-3")),
        ("date", "2026-02-28", dt.date(2026, 2, 28)),
        ("datetime", "2026-09-30T14:05:00", dt.datetime(2026, 9, 30, 14, 5)),
        ("datetime", "2026-09-30 14:05", dt.datetime(2026, 9, 30, 14, 5)),
        ("boolean", "TRUE", True),
        ("boolean", "false", False),
        ("string", "  kept as is ", "  kept as is "),
    ],
)
def test_parse_valid_values(kind, text, expected):
    assert parse_text(kind, text) == expected


@pytest.mark.parametrize(
    "kind, text",
    [
        ("integer", "4.0"),
        ("integer", "1e3"),
        ("integer", "12 000"),
        ("integer", str(2**63)),
        ("decimal", "1,5"),
        ("decimal", "1.234,5"),
        ("decimal", "1e5"),
        ("decimal", "NaN"),
        ("decimal", "12 €"),
        ("date", "2026-02-30"),
        ("date", "30/09/2026"),
        ("date", "2026-9-1"),
        ("datetime", "yesterday"),
        ("datetime", "2026-09-30T25:00:00"),
        ("boolean", "yes"),
        ("boolean", "1"),
    ],
)
def test_invalid_values_are_errors_never_guesses(kind, text):
    with pytest.raises(ValueError):
        parse_text(kind, text)


def test_decimal_comma_and_custom_date_formats():
    assert parse_text("decimal", "1234,50", decimal_separator=",") == Decimal("1234.50")
    with pytest.raises(ValueError):
        parse_text("decimal", "1234.50", decimal_separator=",")
    assert parse_text("date", "30/09/2026", date_format="%d/%m/%Y") == dt.date(2026, 9, 30)
    with pytest.raises(ValueError):
        parse_text("date", "09/30/2026", date_format="%d/%m/%Y")


@pytest.mark.parametrize(
    "kind, value, text",
    [
        ("decimal", Decimal("162.50"), "162.50"),
        ("decimal", Decimal("1E+2"), "100"),
        ("decimal", Decimal("-0"), "0"),
        ("integer", 7, "7"),
        ("date", dt.date(2026, 9, 1), "2026-09-01"),
        ("datetime", dt.datetime(2026, 9, 1, 8, 30), "2026-09-01T08:30:00"),
        ("boolean", True, "true"),
        ("string", "=SUM(A1)", "=SUM(A1)"),
        ("decimal", None, ""),
    ],
)
def test_canonical_text(kind, value, text):
    assert format_text(kind, value) == text


def test_literal_coercion_is_strict():
    assert coerce_literal("decimal", 120) == Decimal(120)
    assert coerce_literal("decimal", "120.5") == Decimal("120.5")
    assert coerce_literal("date", dt.date(2026, 9, 1)) == dt.date(2026, 9, 1)  # YAML already parsed the date
    assert coerce_literal("date", "2026-09-01") == dt.date(2026, 9, 1)
    for kind, value in (("integer", True), ("string", 7), ("boolean", "yes"), ("date", 20260901), ("integer", 4.5)):
        with pytest.raises(ValueError):
            coerce_literal(kind, value)


def test_series_storage_and_python_values():
    assert str(to_series("integer", [1, None]).dtype) == "Int64"
    assert str(to_series("string", ["a", None]).dtype) == "string"
    assert python_values(to_series("decimal", [Decimal("1.10"), None])) == [Decimal("1.10"), None]
    assert python_values(to_series("integer", [3, None])) == [3, None]
