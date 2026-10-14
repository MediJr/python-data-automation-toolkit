"""Row steps: ``filter`` (declarative conditions), ``sort`` and ``check`` (controls).

Conditions are data, never code (ADR-0005): an operator is chosen from a closed list and
evaluated in Python. No text from the workflow is passed to ``eval``, ``exec`` or
``DataFrame.query``.

A condition compares with either a literal ``value`` or a run parameter (``param``, FR-19);
a parameter is looked up by name in the run's parameters, never substituted into text.

Missing values follow SQL-like rules: a comparison with a missing value is never true,
so such rows are excluded by every operator except ``is_null``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from ..dataset import Dataset
from ..registry import StepContext, StepFailure, StepParams, StepResult, StepType, register
from ..types import coerce_literal, python_values
from ._common import examples, require_columns, single_frame

# --------------------------------------------------------------------------- filter

Operator = Literal["eq", "ne", "lt", "le", "gt", "ge", "in", "not_in", "between", "contains", "is_null", "not_null"]
_NO_VALUE = {"is_null", "not_null"}
_LIST_VALUE = {"in", "not_in"}
_ORDERED = {"lt", "le", "gt", "ge", "between"}


class Condition(StepParams):
    column: str = Field(min_length=1)
    op: Operator
    value: Any = None
    param: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")

    @model_validator(mode="after")
    def _value_shape(self) -> Condition:
        has_value = "value" in self.model_fields_set
        if self.param is not None:
            if has_value:
                raise ValueError("give either value or param, not both")
            if self.op in _NO_VALUE | _LIST_VALUE | {"between"}:
                raise ValueError(f"operator {self.op} cannot take a param (only single-value operators can)")
            return self
        if self.op in _NO_VALUE and has_value:
            raise ValueError(f"operator {self.op} takes no value")
        if self.op not in _NO_VALUE and not has_value:
            raise ValueError(f"operator {self.op} needs a value or a param")
        if self.op in _LIST_VALUE and (not isinstance(self.value, list) or not self.value):
            raise ValueError(f"operator {self.op} needs a non-empty list of values")
        if self.op == "between" and (not isinstance(self.value, list) or len(self.value) != 2):
            raise ValueError("operator between needs a list of two values [low, high]")
        if self.op not in _LIST_VALUE | {"between"} | _NO_VALUE and isinstance(self.value, list | dict):
            raise ValueError(f"operator {self.op} needs a single value")
        return self


class FilterParams(StepParams):
    where: list[Condition] = Field(min_length=1)

    def parameter_references(self) -> list[str]:
        return [c.param for c in self.where if c.param is not None]


def _predicate(condition: Condition, kind: str, parameters: dict[str, str]):
    op = condition.op
    literal = condition.value
    if condition.param is not None:
        if condition.param not in parameters:
            raise StepFailure(f"condition on {condition.column!r}: parameter {condition.param!r} has no value")
        literal = parameters[condition.param]
    if op == "is_null":
        return lambda v: v is None
    if op == "not_null":
        return lambda v: v is not None
    if op == "contains":
        if kind != "string":
            raise StepFailure(f"operator contains only applies to string columns ({condition.column!r} is {kind})")
        needle = coerce_literal("string", literal)
        return lambda v: v is not None and needle in v
    if kind == "boolean" and op in _ORDERED:
        raise StepFailure(f"operator {op} cannot compare booleans ({condition.column!r})")
    try:
        if op in _LIST_VALUE:
            allowed = {coerce_literal(kind, item) for item in condition.value}
            return (
                (lambda v: v is not None and v in allowed)
                if op == "in"
                else (lambda v: v is not None and v not in allowed)
            )
        if op == "between":
            low, high = (coerce_literal(kind, item) for item in condition.value)
            return lambda v: v is not None and low <= v <= high
        target = coerce_literal(kind, literal)
    except ValueError as exc:
        source = f" (parameter {condition.param!r})" if condition.param is not None else ""
        raise StepFailure(f"condition on {condition.column!r} ({kind}){source}: {exc}") from None
    compare = {
        "eq": lambda v: v == target,
        "ne": lambda v: v != target,
        "lt": lambda v: v < target,
        "le": lambda v: v <= target,
        "gt": lambda v: v > target,
        "ge": lambda v: v >= target,
    }[op]
    return lambda v: v is not None and compare(v)


def run_filter(params: FilterParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    dataset = inputs[0]
    frame = single_frame(dataset)
    require_columns(dataset, [c.column for c in params.where], "filter")
    keep = [True] * len(frame)
    for condition in params.where:
        predicate = _predicate(condition, dataset.types[condition.column], ctx.parameters)
        values = python_values(frame[condition.column])
        try:
            keep = [k and predicate(v) for k, v in zip(keep, values, strict=True)]
        except TypeError as exc:
            raise StepFailure(f"condition on {condition.column!r} cannot be evaluated: {exc}") from None
    result = frame[keep]
    details = {"rows_in": len(frame), "rows_out": len(result), "rows_removed": len(frame) - len(result)}
    return StepResult(Dataset.from_frame(ctx.step_id, result, dataset.types), [], details)


register(StepType("filter", "Keep the rows that satisfy all declared conditions.", FilterParams, run_filter))

# --------------------------------------------------------------------------- sort


class SortKey(StepParams):
    column: str = Field(min_length=1)
    descending: bool = False


class SortParams(StepParams):
    by: list[SortKey] = Field(min_length=1)


def run_sort(params: SortParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    dataset = inputs[0]
    frame = single_frame(dataset)
    require_columns(dataset, [k.column for k in params.by], "sort")
    order = list(range(len(frame)))
    for key in reversed(params.by):  # successive stable sorts, last key first
        values = python_values(frame[key.column])
        present = [i for i in order if values[i] is not None]
        missing = [i for i in order if values[i] is None]
        try:
            present.sort(key=lambda i: values[i], reverse=key.descending)
        except TypeError as exc:
            raise StepFailure(f"cannot sort on {key.column!r}: {exc}") from None
        order = present + missing  # missing values always last
    result = frame.iloc[order]
    return StepResult(Dataset.from_frame(ctx.step_id, result, dataset.types), [], {"rows": len(result)})


register(StepType("sort", "Sort rows by one or more columns (stable; missing values last).", SortParams, run_sort))

# --------------------------------------------------------------------------- check


class CheckParams(StepParams):
    min_rows: int | None = Field(default=None, ge=0)
    max_rows: int | None = Field(default=None, ge=0)
    not_null: list[str] = Field(default_factory=list)
    unique: list[str] = Field(default_factory=list)
    allowed_values: dict[str, list[Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _at_least_one_rule(self) -> CheckParams:
        if not (
            self.min_rows is not None
            or self.max_rows is not None
            or self.not_null
            or self.unique
            or self.allowed_values
        ):
            raise ValueError("a check step needs at least one rule")
        if self.min_rows is not None and self.max_rows is not None and self.min_rows > self.max_rows:
            raise ValueError("min_rows cannot be greater than max_rows")
        return self


def run_check(params: CheckParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    """Pass the data through unchanged if every rule holds; otherwise fail with the reasons."""
    dataset = inputs[0]
    frame = single_frame(dataset)
    require_columns(dataset, [*params.not_null, *params.unique, *params.allowed_values], "check")
    problems: list[str] = []
    rows = len(frame)
    if params.min_rows is not None and rows < params.min_rows:
        problems.append(f"{rows} row(s), at least {params.min_rows} expected")
    if params.max_rows is not None and rows > params.max_rows:
        problems.append(f"{rows} row(s), at most {params.max_rows} expected")
    for column in params.not_null:
        bad = [i + 1 for i, v in enumerate(python_values(frame[column])) if v is None]
        if bad:
            problems.append(f"{len(bad)} missing value(s) in {column!r} (data rows {examples(bad)})")
    if params.unique:
        duplicated = frame.duplicated(params.unique, keep=False).tolist()
        bad = [i + 1 for i, flag in enumerate(duplicated) if flag]
        if bad:
            problems.append(f"{len(bad)} row(s) share the same {params.unique} (data rows {examples(bad)})")
    for column, allowed_raw in params.allowed_values.items():
        kind = dataset.types[column]
        try:
            allowed = {coerce_literal(kind, v) for v in allowed_raw}
        except ValueError as exc:
            raise StepFailure(f"allowed_values for {column!r} ({kind}): {exc}") from None
        values = python_values(frame[column])
        bad = [i + 1 for i, v in enumerate(values) if v is not None and v not in allowed]
        if bad:
            problems.append(
                f"{len(bad)} value(s) of {column!r} not allowed ({examples(bad, [values[i - 1] for i in bad])})"
            )
    if problems:
        raise StepFailure("check failed: " + "; ".join(problems))
    return StepResult(Dataset.from_frame(ctx.step_id, frame, dataset.types), [], {"rows": rows, "rules_passed": True})


register(
    StepType(
        "check",
        "Verify row counts, missing values, uniqueness and allowed values; fail if a rule is broken.",
        CheckParams,
        run_check,
    )
)
