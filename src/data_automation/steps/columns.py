"""Column steps: ``select`` (projection), ``rename`` and ``cast`` (explicit type conversion)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..dataset import Dataset
from ..registry import StepContext, StepFailure, StepParams, StepResult, StepType, register
from ..types import format_text, parse_text, python_values, to_series
from ._common import examples, require_columns, single_frame

# --------------------------------------------------------------------------- select


class SelectParams(StepParams):
    columns: list[str] = Field(min_length=1)

    @field_validator("columns")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("columns lists a column more than once")
        return value


def run_select(params: SelectParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    dataset = inputs[0]
    frame = single_frame(dataset)
    require_columns(dataset, params.columns, "select")
    types = {c: dataset.types[c] for c in params.columns}
    dropped = [c for c in dataset.columns if c not in types]
    return StepResult(Dataset.from_frame(ctx.step_id, frame[params.columns], types), [], {"dropped_columns": dropped})


register(StepType("select", "Keep only the listed columns, in the listed order.", SelectParams, run_select))

# --------------------------------------------------------------------------- rename


class RenameParams(StepParams):
    columns: dict[str, str] = Field(min_length=1)

    @field_validator("columns")
    @classmethod
    def _targets(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not new for new in value.values()):
            raise ValueError("new column names cannot be empty")
        if len(set(value.values())) != len(value):
            raise ValueError("two columns cannot get the same new name")
        return value


def run_rename(params: RenameParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    dataset = inputs[0]
    frame = single_frame(dataset)
    require_columns(dataset, params.columns, "rename")
    names = [params.columns.get(c, c) for c in dataset.columns]
    if len(set(names)) != len(names):
        clash = sorted({n for n in names if names.count(n) > 1})
        raise StepFailure(f"rename would create duplicate column(s) {clash}")
    types = {params.columns.get(c, c): kind for c, kind in dataset.types.items()}
    result = frame.rename(columns=params.columns)
    return StepResult(Dataset.from_frame(ctx.step_id, result, types), [], {"renamed": dict(params.columns)})


register(StepType("rename", "Rename columns; a clash with an existing name is an error.", RenameParams, run_rename))

# --------------------------------------------------------------------------- cast


class CastSpec(StepParams):
    type: Literal["string", "integer", "decimal", "date", "datetime", "boolean"]
    format: str | None = Field(default=None, min_length=1)
    decimal_separator: Literal[".", ","] = "."

    @model_validator(mode="after")
    def _options(self) -> CastSpec:
        if self.format is not None and self.type not in ("date", "datetime"):
            raise ValueError("format only applies to date and datetime")
        if self.format is not None and "%" not in self.format:
            raise ValueError(f"{self.format!r} is not a strptime format (e.g. %d/%m/%Y)")
        if "decimal_separator" in self.model_fields_set and self.type != "decimal":
            raise ValueError("decimal_separator only applies to decimal")
        return self


class CastParams(StepParams):
    columns: dict[str, CastSpec] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _short_form(cls, data: object) -> object:
        """Allow ``amount: decimal`` as a short form of ``amount: {type: decimal}``."""
        if isinstance(data, dict) and isinstance(data.get("columns"), dict):
            data = dict(data)
            data["columns"] = {k: {"type": v} if isinstance(v, str) else v for k, v in data["columns"].items()}
        return data


def convert_column(values: list, source_kind: str, spec: CastSpec) -> tuple[list, list[int], list]:
    """Convert values to ``spec.type``. Returns converted values, failing rows (1-based) and their values."""
    converted, bad_rows, bad_values = [], [], []
    for index, value in enumerate(values, start=1):
        if value is None:
            converted.append(None)
            continue
        text = value if source_kind == "string" else format_text(source_kind, value)
        if source_kind == "string" and text.strip() == "" and spec.type != "string":
            converted.append(None)  # empty text is a missing value, never zero or a default
            continue
        try:
            converted.append(
                parse_text(spec.type, text, date_format=spec.format, decimal_separator=spec.decimal_separator)
            )
        except ValueError:
            bad_rows.append(index)
            bad_values.append(value)
            converted.append(None)
    return converted, bad_rows, bad_values


def run_cast(params: CastParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    dataset = inputs[0]
    frame = single_frame(dataset).copy()
    require_columns(dataset, params.columns, "cast")
    types = dict(dataset.types)
    problems = []
    for column, spec in params.columns.items():
        values, bad_rows, bad_values = convert_column(python_values(frame[column]), dataset.types[column], spec)
        if bad_rows:
            problems.append(
                f"{len(bad_rows)} value(s) of {column!r} are not valid {spec.type} ({examples(bad_rows, bad_values)})"
            )
            continue
        frame[column] = to_series(spec.type, values, index=frame.index)
        types[column] = spec.type
    if problems:
        raise StepFailure("cast failed: " + "; ".join(problems))
    return StepResult(
        Dataset.from_frame(ctx.step_id, frame, types), [], {"converted": {c: s.type for c, s in params.columns.items()}}
    )


register(
    StepType(
        "cast", "Convert columns to a declared type; any value that does not convert is an error.", CastParams, run_cast
    )
)
