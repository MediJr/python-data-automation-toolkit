"""Workflow configuration models (schema version 1), validated with Pydantic.

The models describe the *structure* of a workflow. They are strict: unknown keys are
rejected, values must already have the right type (YAML ``007`` is the integer 7 and will
not be accepted where text is expected), and each field is checked independently.

Cross-references (datasets used before they are produced, paths outside the root, run
parameters...) are checked afterwards in :mod:`data_automation.validation`.

Type-specific step parameters are kept in :attr:`StepSpec.parameters` and are validated
by the step registry in phase 2; phase 1 only checks the step envelope.
"""

from __future__ import annotations

import codecs
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator, model_validator

from .errors import WorkflowValidationError
from .parameters import NAME_PATTERN, parse_value
from .yaml_loader import load_yaml_mapping

SCHEMA_VERSION = 1
IDENTIFIER_PATTERN = r"[a-z][a-z0-9_-]{0,63}"
Identifier = Annotated[str, StringConstraints(pattern=rf"^{IDENTIFIER_PATTERN}$")]
StepType = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
ColumnName = Annotated[str, StringConstraints(min_length=1, max_length=255)]
FileType = Literal["csv", "xlsx"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class WorkflowInfo(_Strict):
    """The ``workflow`` section."""

    id: Identifier
    schema_version: Literal[1]
    description: str | None = None
    root: str = Field(default=".", min_length=1, description="Working root, relative to the workflow file's folder.")


class ParameterSpec(_Strict):
    """One entry of the ``parameters`` section."""

    type: Literal["string", "integer", "date", "month"]
    required: bool | None = None
    default: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _default_matches_type(self) -> ParameterSpec:
        if self.default is not None:
            if self.required:
                raise ValueError("a parameter with a default cannot be required")
            try:
                parse_value(self.type, self.default)
            except ValueError as exc:
                raise ValueError(f"default {self.default!r} {exc}") from None
        return self

    @property
    def is_required(self) -> bool:
        return self.default is None if self.required is None else self.required


class ColumnType(_Strict):
    """Declared logical type of an input column (ADR-0007)."""

    type: Literal["string", "integer", "decimal", "date", "datetime", "boolean"]
    format: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _format(self) -> ColumnType:
        if self.format is not None and self.type not in ("date", "datetime"):
            raise ValueError("format only applies to date and datetime")
        if self.format is not None and "%" not in self.format:
            raise ValueError(f"{self.format!r} is not a strptime format (e.g. %d/%m/%Y)")
        return self


class InputSpec(_Strict):
    """One entry of the ``inputs`` section (a set of source files)."""

    id: Identifier
    type: FileType
    path: str = Field(
        min_length=1, description="File or pattern relative to the root; the last part may contain * ? [ ]."
    )
    required_columns: list[ColumnName] = Field(default_factory=list)
    types: dict[ColumnName, ColumnType] = Field(default_factory=dict)
    decimal_separator: Literal[".", ","] = "."
    on_empty_match: Literal["fail", "warn"] = "fail"
    on_empty_file: Literal["fail", "skip"] = "fail"
    encoding: str = "utf-8"
    delimiter: str = ","
    sheet: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _short_type_form(cls, data: Any) -> Any:
        """Allow ``amount: decimal`` as a short form of ``amount: {type: decimal}``."""
        if isinstance(data, dict) and isinstance(data.get("types"), dict):
            data = dict(data)
            data["types"] = {k: {"type": v} if isinstance(v, str) else v for k, v in data["types"].items()}
        return data

    @model_validator(mode="after")
    def _format_options(self) -> InputSpec:
        if (
            self.delimiter == self.decimal_separator
            and self.type == "csv"
            and "decimal" in {t.type for t in self.types.values()}
        ):
            raise ValueError("the decimal separator cannot be the CSV delimiter")
        given = self.model_fields_set
        if self.type == "xlsx" and given & {"encoding", "delimiter"}:
            raise ValueError("encoding and delimiter only apply to csv inputs")
        if self.type == "csv" and "sheet" in given:
            raise ValueError("sheet only applies to xlsx inputs")
        if len(self.delimiter) != 1:
            raise ValueError("delimiter must be a single character")
        try:
            codecs.lookup(self.encoding)
        except LookupError:
            raise ValueError(f"unknown encoding {self.encoding!r}") from None
        if len(set(self.required_columns)) != len(self.required_columns):
            raise ValueError("required_columns lists a column more than once")
        return self


class StepSpec(BaseModel):
    """One entry of the ``steps`` section.

    Only the envelope is defined here; any other key is a type-specific parameter,
    collected in :attr:`parameters` and validated by the step registry (phase 2).
    """

    model_config = ConfigDict(extra="allow", strict=True, frozen=True)

    id: Identifier
    type: StepType
    input: Identifier | list[Identifier]
    output: Identifier
    description: str | None = None

    @field_validator("input")
    @classmethod
    def _non_empty_inputs(cls, value: str | list[str]) -> str | list[str]:
        if isinstance(value, list) and (not value or len(set(value)) != len(value)):
            raise ValueError("input list must be non-empty and without duplicates")
        return value

    @property
    def inputs(self) -> list[str]:
        return [self.input] if isinstance(self.input, str) else list(self.input)

    @property
    def parameters(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class OutputSpec(_Strict):
    """One entry of the ``outputs`` section (an exported file)."""

    id: Identifier
    input: Identifier
    type: FileType
    path: str = Field(min_length=1)
    expected_columns: list[ColumnName] | None = None
    sheet_name: str | None = None

    @model_validator(mode="after")
    def _format_options(self) -> OutputSpec:
        if self.type == "csv" and self.sheet_name is not None:
            raise ValueError("sheet_name only applies to xlsx outputs")
        if self.sheet_name is not None and not 1 <= len(self.sheet_name) <= 31:
            raise ValueError("sheet_name must be 1-31 characters")
        suffix = Path(self.path).suffix.lower()
        if suffix != f".{self.type}":
            raise ValueError(f"path must end with .{self.type} for a {self.type} output")
        if self.expected_columns is not None and len(set(self.expected_columns)) != len(self.expected_columns):
            raise ValueError("expected_columns lists a column more than once")
        return self


class SummarySpec(_Strict):
    """Business summary (C-06): the listed datasets, as Markdown tables."""

    datasets: list[Identifier] = Field(min_length=1)
    max_rows: int = Field(default=50, ge=1, le=1000)
    title: str | None = None


class ReportSpec(_Strict):
    """The ``report`` section."""

    formats: list[Literal["json", "markdown"]] = Field(default_factory=lambda: ["json", "markdown"], min_length=1)
    directory: str = Field(default="runs", min_length=1, description="Run folders, relative to the root.")
    summary: SummarySpec | None = None

    @field_validator("formats")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("formats lists a value more than once")
        return value


class WorkflowConfig(_Strict):
    """A complete workflow file."""

    workflow: WorkflowInfo
    parameters: dict[Annotated[str, StringConstraints(pattern=rf"^{NAME_PATTERN}$")], ParameterSpec] = Field(
        default_factory=dict
    )
    inputs: list[InputSpec] = Field(min_length=1)
    steps: list[StepSpec] = Field(default_factory=list)
    outputs: list[OutputSpec] = Field(min_length=1)
    on_error: Literal["stop", "continue"] = "stop"
    report: ReportSpec = Field(default_factory=ReportSpec)


def format_validation_error(error: ValidationError) -> list[str]:
    """Turn a Pydantic error into one readable message per problem, with its location."""
    messages = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "(top level)"
        message = item["msg"].removeprefix("Value error, ")
        received = item.get("input")
        if item["type"] == "extra_forbidden":
            message = "unknown key (check the spelling; unknown keys are never ignored)"
        elif item["type"] != "missing" and not isinstance(received, dict | list):
            message += f" (got {received!r})"
        messages.append(f"{location}: {message}")
    return messages


def parse_workflow(data: dict[str, Any]) -> WorkflowConfig:
    """Validate a loaded mapping against the schema.

    Raises:
        WorkflowValidationError: With one message per problem.
    """
    try:
        return WorkflowConfig.model_validate(data)
    except ValidationError as exc:
        raise WorkflowValidationError(format_validation_error(exc)) from exc


def load_workflow(path: Path) -> WorkflowConfig:
    """Load and validate a workflow file (YAML schema check only, no cross-checks)."""
    return parse_workflow(load_yaml_mapping(path))
