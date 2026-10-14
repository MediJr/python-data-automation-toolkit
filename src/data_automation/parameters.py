"""Run parameters (FR-19): declared in the workflow, supplied with ``--param name=value``.

Values are typed and checked before anything runs. Placeholders such as ``{period}`` in
paths are replaced by a plain regular-expression substitution: no ``str.format`` (which
would allow attribute access such as ``{x.__class__}``) and no evaluation of any kind.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping

from .errors import ParameterError

PARAMETER_TYPES = ("string", "integer", "date", "month")
NAME_PATTERN = r"[a-z][a-z0-9_]{0,63}"
PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_NAME = re.compile(NAME_PATTERN)


def parse_value(kind: str, raw: str) -> str:
    """Check ``raw`` against a parameter type and return its canonical text.

    * ``string``: any non-empty text without ``/``, ``\\`` or ``..`` (it may end up in a path);
    * ``integer``: optional sign and digits;
    * ``date``: ``YYYY-MM-DD`` (a real calendar date);
    * ``month``: ``YYYY-MM``.

    Raises:
        ValueError: The value does not match the type.
    """
    if kind == "string":
        if raw == "" or any(part in raw for part in ("/", "\\", "..")) or raw != raw.strip():
            raise ValueError("must be non-empty, without surrounding spaces, '/', '\\' or '..'")
        return raw
    if kind == "integer":
        if not re.fullmatch(r"[+-]?\d+", raw):
            raise ValueError("must be an integer")
        return str(int(raw))
    if kind == "date":
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            try:
                return dt.date.fromisoformat(raw).isoformat()
            except ValueError:
                pass
        raise ValueError("must be a real date in the form YYYY-MM-DD")
    if kind == "month":
        match = re.fullmatch(r"(\d{4})-(\d{2})", raw)
        if not match or not 1 <= int(match.group(2)) <= 12:
            raise ValueError("must be a month in the form YYYY-MM")
        return raw
    raise ValueError(f"unknown parameter type {kind!r}")


def parse_cli_parameters(pairs: Iterable[str]) -> dict[str, str]:
    """Parse ``name=value`` strings from the command line.

    Raises:
        ParameterError: Malformed pair, invalid name, or the same name given twice.
    """
    values: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise ParameterError(f"--param {pair!r}: expected name=value")
        if not _NAME.fullmatch(name):
            raise ParameterError(f"--param {pair!r}: invalid parameter name {name!r}")
        if name in values:
            raise ParameterError(f"--param {name!r} is given more than once")
        values[name] = value
    return values


def placeholders(text: str) -> list[str]:
    """Return the placeholder names used in ``text`` (in order, with duplicates)."""
    return PLACEHOLDER.findall(text)


def render(text: str, values: Mapping[str, str]) -> str:
    """Replace ``{name}`` placeholders by their values; unknown names raise ``KeyError``."""
    return PLACEHOLDER.sub(lambda match: values[match.group(1)], text)
