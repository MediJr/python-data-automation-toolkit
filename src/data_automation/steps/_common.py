"""Helpers shared by the built-in step types."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from ..dataset import Dataset, DatasetError
from ..registry import StepFailure

MAX_EXAMPLES = 5


def single_frame(dataset: Dataset) -> pd.DataFrame:
    try:
        return dataset.frame()
    except DatasetError as exc:
        raise StepFailure(str(exc)) from None


def require_columns(dataset: Dataset, columns: Iterable[str], what: str) -> None:
    missing = [c for c in columns if c not in dataset.types]
    if missing:
        raise StepFailure(
            f"{what}: column(s) {', '.join(repr(c) for c in missing)} not found in dataset {dataset.name!r} "
            f"(available: {', '.join(repr(c) for c in dataset.columns)})"
        )


def examples(rows: list[int], values: list[Any] | None = None) -> str:
    """Human description of failing data rows (1-based), with values when given."""
    shown = rows[:MAX_EXAMPLES]
    if values is None:
        listed = ", ".join(str(r) for r in shown)
    else:
        listed = ", ".join(f"row {r}: {v!r}" for r, v in zip(shown, values[:MAX_EXAMPLES], strict=False))
    more = f" and {len(rows) - MAX_EXAMPLES} more" if len(rows) > MAX_EXAMPLES else ""
    return f"{listed}{more}"
