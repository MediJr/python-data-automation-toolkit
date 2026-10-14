"""``aggregate``: group rows and compute indicators (sum, count, mean, min, max).

Semantics (documented, deterministic):

* groups are sorted by their key values, missing keys forming their own group, last;
* ``count`` without a column counts rows; with a column, it counts non-missing values;
* ``sum``, ``mean``, ``min`` and ``max`` ignore missing values; if a group has no value
  at all, the result is missing (never a fabricated 0);
* sums and means are exact decimals; ``round`` uses half-up rounding;
* without ``group_by``, one row is produced, even for an empty dataset.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import Field, model_validator

from ..dataset import Dataset
from ..registry import StepContext, StepFailure, StepParams, StepResult, StepType, register
from ..types import python_values
from ._common import require_columns, single_frame

_NUMERIC = {"integer", "decimal"}
_ORDERED = {"integer", "decimal", "date", "datetime", "string"}


class Metric(StepParams):
    function: Literal["sum", "count", "mean", "min", "max"]
    column: str | None = Field(default=None, min_length=1)
    round: int | None = Field(default=None, ge=0, le=12)

    @model_validator(mode="after")
    def _column(self) -> Metric:
        if self.function != "count" and self.column is None:
            raise ValueError(f"function {self.function} needs a column")
        return self


class AggregateParams(StepParams):
    group_by: list[str] = Field(default_factory=list)
    metrics: dict[str, Metric] = Field(min_length=1)

    @model_validator(mode="after")
    def _names(self) -> AggregateParams:
        if len(set(self.group_by)) != len(self.group_by):
            raise ValueError("group_by lists a column more than once")
        clash = set(self.group_by) & set(self.metrics)
        if clash:
            raise ValueError(f"metric names clash with group_by columns: {sorted(clash)}")
        return self


def _result_type(metric: Metric, source: str | None) -> str:
    if metric.function == "count":
        return "integer"
    if metric.function == "mean":
        return "decimal"
    return source or "integer"


def _compute(metric: Metric, values: list, rows: int):
    if metric.function == "count":
        return rows if metric.column is None else sum(1 for v in values if v is not None)
    present = [v for v in values if v is not None]
    if not present:
        return None
    if metric.function == "sum":
        return sum(present, Decimal(0)) if isinstance(present[0], Decimal) else sum(present)
    if metric.function == "mean":
        return sum((Decimal(v) for v in present), Decimal(0)) / Decimal(len(present))
    return min(present) if metric.function == "min" else max(present)


def run_aggregate(params: AggregateParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    dataset = inputs[0]
    frame = single_frame(dataset)
    columns = [m.column for m in params.metrics.values() if m.column]
    require_columns(dataset, [*params.group_by, *columns], "aggregate")
    for name, metric in params.metrics.items():
        kind = dataset.types.get(metric.column) if metric.column else None
        if metric.function in ("sum", "mean") and kind not in _NUMERIC:
            raise StepFailure(
                f"metric {name!r}: {metric.function} needs an integer or decimal column "
                f"({metric.column!r} is {kind}; use a cast step or declare its type)"
            )
        if metric.function in ("min", "max") and kind not in _ORDERED:
            raise StepFailure(f"metric {name!r}: {metric.function} cannot be computed on a {kind} column")
        if metric.round is not None and _result_type(metric, kind) != "decimal":
            raise StepFailure(f"metric {name!r}: round only applies to decimal results")

    keys = [python_values(frame[c]) for c in params.group_by]
    metric_values = {c: python_values(frame[c]) for c in set(columns)}
    groups: dict[tuple, list[int]] = {}
    for i in range(len(frame)):
        groups.setdefault(tuple(k[i] for k in keys), []).append(i)
    if not params.group_by and not groups:
        groups[()] = []
    try:
        ordered = sorted(groups, key=lambda key: tuple((v is None, v) if v is not None else (True, 0) for v in key))
    except TypeError as exc:
        raise StepFailure(f"cannot order groups: {exc}") from None

    out: dict[str, list] = {c: [] for c in params.group_by} | {name: [] for name in params.metrics}
    for key in ordered:
        rows = groups[key]
        for column, value in zip(params.group_by, key, strict=True):
            out[column].append(value)
        for name, metric in params.metrics.items():
            values = [metric_values[metric.column][i] for i in rows] if metric.column else []
            result = _compute(metric, values, len(rows))
            if metric.round is not None and result is not None:
                result = result.quantize(Decimal(1).scaleb(-metric.round), rounding=ROUND_HALF_UP)
            out[name].append(result)
    types = {c: dataset.types[c] for c in params.group_by}
    types |= {n: _result_type(m, dataset.types.get(m.column) if m.column else None) for n, m in params.metrics.items()}
    result = Dataset.from_columns(ctx.step_id, out, types)
    return StepResult(result, [], {"rows_in": len(frame), "groups": len(ordered)})


register(
    StepType(
        "aggregate", "Group rows and compute sum, count, mean, min or max per group.", AggregateParams, run_aggregate
    )
)
