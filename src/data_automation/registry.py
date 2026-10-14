"""Step registry and step contract (ADR-0004).

A step type is a :class:`StepType`: a name, a Pydantic model for its type-specific
parameters (strict, unknown keys refused), the number of input datasets it accepts, and
a ``run`` function. Adding a type means implementing one and calling :func:`register`;
the engine never needs to change (FR-15, AC-12).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from .dataset import Dataset


class StepParams(BaseModel):
    """Base class for step parameter models: strict, unknown keys are errors."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    def parameter_references(self) -> list[str]:
        """Names of the run parameters these settings use; validation checks they are declared."""
        return []


class StepFailure(Exception):
    """A step could not produce its output; the message explains why, for the run report."""


@dataclass
class StepContext:
    """What a step may know about the run (it never sees paths outside the root)."""

    run_id: str
    workflow_id: str
    step_id: str
    parameters: dict[str, str]
    logger: logging.Logger


@dataclass
class StepResult:
    """Output of a step plus anything worth reporting."""

    dataset: Dataset
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


RunFunction = Callable[[Any, list[Dataset], StepContext], StepResult]


@dataclass(frozen=True)
class StepType:
    name: str
    description: str
    params_model: type[StepParams]
    run: RunFunction
    min_inputs: int = 1
    max_inputs: int | None = 1


_REGISTRY: dict[str, StepType] = {}


def register(step_type: StepType) -> StepType:
    """Add a step type to the registry.

    Raises:
        ValueError: A type with the same name is already registered.
    """
    if step_type.name in _REGISTRY:
        raise ValueError(f"step type {step_type.name!r} is already registered")
    _REGISTRY[step_type.name] = step_type
    return step_type


def unregister(name: str) -> None:
    """Remove a step type (used by tests that register temporary types)."""
    _REGISTRY.pop(name, None)


def get(name: str) -> StepType | None:
    _load_builtin_steps()
    return _REGISTRY.get(name)


def available() -> dict[str, StepType]:
    _load_builtin_steps()
    return dict(sorted(_REGISTRY.items()))


def validate_step(step_type: str, n_inputs: int, raw_params: dict[str, Any]) -> tuple[StepParams | None, list[str]]:
    """Check a step's type, number of inputs and parameters.

    Returns:
        The parsed parameters (or ``None``) and a list of problems, each prefixed with the
        parameter it concerns.
    """
    definition = get(step_type)
    if definition is None:
        return None, [f"type: unknown step type {step_type!r} (available: {', '.join(available())})"]
    problems = []
    if n_inputs < definition.min_inputs or (definition.max_inputs is not None and n_inputs > definition.max_inputs):
        expected = (
            f"exactly {definition.min_inputs}"
            if definition.min_inputs == definition.max_inputs
            else f"at least {definition.min_inputs}"
            if definition.max_inputs is None
            else f"{definition.min_inputs} to {definition.max_inputs}"
        )
        problems.append(f"input: a {step_type} step takes {expected} input dataset(s), got {n_inputs}")
    try:
        params = definition.params_model.model_validate(raw_params)
    except ValidationError as exc:
        from .config import format_validation_error

        problems.extend(format_validation_error(exc))
        params = None
    return params, problems


def _load_builtin_steps() -> None:
    from . import steps  # noqa: F401  (importing the package registers the built-in types)
