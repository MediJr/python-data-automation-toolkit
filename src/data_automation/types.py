"""Logical column types (ADR-0007) and their exact text forms.

Every column of a dataset has one logical type. Values are held as:

========== ======================== =============================================
type       Python value             canonical text (CSV export)
========== ======================== =============================================
string     ``str``                  the text itself
integer    ``int``                  ``-42``
decimal    ``decimal.Decimal``      ``1234.50`` (point, no exponent, no grouping)
date       ``datetime.date``        ``2026-09-30`` (ISO 8601)
datetime   ``datetime.datetime``    ``2026-09-30T14:05:00`` (ISO 8601)
boolean    ``bool``                 ``true`` / ``false``
========== ======================== =============================================

Missing values are ``None`` in Python lists and ``pd.NA`` in frames; they are written
as empty cells. Decimals are exact (no binary floating point), so sums of amounts do
not drift. Nothing is ever guessed: a value that does not match its declared type is
an error, never a silent conversion.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

LOGICAL_TYPES = ("string", "integer", "decimal", "date", "datetime", "boolean")
_INTEGER = re.compile(r"[+-]?\d+")
_DECIMAL = re.compile(r"[+-]?(\d+([.,]\d*)?|[.,]\d+)")
_INT64 = (-(2**63), 2**63 - 1)


def is_missing(value: Any) -> bool:
    """True for ``None``, ``pd.NA`` and float NaN."""
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value)) if not isinstance(value, str | Decimal | dt.date) else False
    except TypeError, ValueError:
        return False


def parse_text(kind: str, text: str, *, date_format: str | None = None, decimal_separator: str = ".") -> Any:
    """Convert the text of one cell to a value of type ``kind``.

    Surrounding spaces are ignored for every type except ``string``. Empty text must be
    handled by the caller (it means "missing").

    Raises:
        ValueError: The text is not a valid value of that type.
    """
    if kind == "string":
        return text
    value = text.strip()
    if kind == "integer":
        if not _INTEGER.fullmatch(value):
            raise ValueError("not an integer")
        number = int(value)
        if not _INT64[0] <= number <= _INT64[1]:
            raise ValueError("integer out of the 64-bit range")
        return number
    if kind == "decimal":
        other = "," if decimal_separator == "." else "."
        if other in value or not _DECIMAL.fullmatch(value):
            raise ValueError(f"not a decimal number with '{decimal_separator}' as decimal separator")
        try:
            return Decimal(value.replace(decimal_separator, "."))
        except InvalidOperation:
            raise ValueError("not a decimal number") from None
    if kind == "date":
        try:
            if date_format:
                return dt.datetime.strptime(value, date_format).date()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError
            return dt.date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"not a date in the form {date_format or 'YYYY-MM-DD'}") from None
    if kind == "datetime":
        try:
            if date_format:
                return dt.datetime.strptime(value, date_format)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?)?(Z|[+-]\d{2}:\d{2})?", value):
                raise ValueError
            return dt.datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"not a date-time in the form {date_format or 'YYYY-MM-DDTHH:MM:SS'}") from None
    if kind == "boolean":
        lowered = value.lower()
        if lowered in ("true", "false"):
            return lowered == "true"
        raise ValueError("not a boolean (true or false)")
    raise ValueError(f"unknown type {kind!r}")


def coerce_literal(kind: str, value: Any) -> Any:
    """Convert a value written in the workflow file (e.g. a filter value) to type ``kind``.

    YAML may already have produced an ``int``, ``bool`` or ``date``; strings are parsed
    with :func:`parse_text`. A value of the wrong kind is an error (``True`` is not the
    integer 1, a date is not a string).

    Raises:
        ValueError: The value cannot represent type ``kind`` without guessing.
    """
    if kind == "string":
        if isinstance(value, str):
            return value
        raise ValueError(f"{value!r} is not text (quote it in the workflow file)")
    if isinstance(value, bool):
        if kind == "boolean":
            return value
        raise ValueError(f"{value!r} is a boolean, not {kind}")
    if kind == "boolean":
        raise ValueError(f"{value!r} is not a boolean (use true or false)")
    if kind == "integer" and isinstance(value, int):
        return value
    if kind == "decimal" and isinstance(value, int | float):
        return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
    if kind == "date" and isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if kind == "datetime" and isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        return parse_text(kind, value)
    raise ValueError(f"{value!r} cannot be used as a {kind} value")


def format_text(kind: str, value: Any) -> str:
    """Canonical text of a value (ADR-0007); missing values give an empty string."""
    if is_missing(value):
        return ""
    if kind == "decimal":
        text = format(value, "f")
        return "0" if text in ("-0", "+0") else text
    if kind == "date":
        return value.isoformat()
    if kind == "datetime":
        return value.isoformat(timespec="seconds" if value.microsecond == 0 else "microseconds")
    if kind == "boolean":
        return "true" if value else "false"
    return str(value)


def to_series(kind: str, values: Iterable[Any], index: Any = None) -> pd.Series:
    """Build a pandas Series holding ``values`` with the storage used for ``kind``."""
    items = [pd.NA if is_missing(v) else v for v in values]
    if kind == "string":
        return pd.Series(items, index=index, dtype="string")
    if kind == "integer":
        return pd.Series(items, index=index, dtype="Int64")
    return pd.Series(items, index=index, dtype="object")


def python_values(series: pd.Series) -> list[Any]:
    """Values of a series as plain Python objects (``None`` for missing)."""
    out = []
    for value in series.tolist():
        if is_missing(value):
            out.append(None)
        elif hasattr(value, "item") and not isinstance(value, Decimal | dt.date):
            out.append(value.item())
        else:
            out.append(value)
    return out
