"""Pre-run validation of a workflow (specification §6.2).

:func:`validate_workflow` loads the file, checks the schema, then checks everything that
spans several sections. It never reads the content of data files and never writes
anything: it only looks at the configuration and at which source files exist.

What is checked:

* schema (unknown keys, types, allowed values) - :mod:`data_automation.config`;
* unique identifiers; every step input produced by a source or an earlier step; every
  output fed by an existing dataset;
* run parameters: unknown, missing, malformed; undeclared placeholders in paths;
* paths: relative to the working root, never leaving it, wildcards only where allowed;
* sources: each input pattern matches files (or only warns, if configured), and no match
  leaves the root through a symbolic link;
* outputs: unique paths, never a source file and never matching an input pattern; their
  metadata files never collide with a source;
* steps: the type exists in the step registry, the number of inputs is accepted and the
  type-specific parameters are valid (strict, unknown keys refused);
* report: the run folder stays inside the root; summary datasets exist.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import WorkflowConfig, load_workflow
from .errors import WorkflowValidationError
from .parameters import parse_value, placeholders, render
from .paths import (
    PathRuleError,
    check_relative_path,
    escaping_matches,
    find_matches,
    relative_posix,
    resolve_in_root,
    resolve_root,
)
from .registry import validate_step

logger = logging.getLogger(__name__)

METADATA_SUFFIX = ".metadata.json"


@dataclass
class ValidationReport:
    """Result of :func:`validate_workflow`."""

    workflow_file: Path
    workflow_id: str | None = None
    root: Path | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # For the engine (not part of the printed report): parsed configuration and absolute paths.
    config: WorkflowConfig | None = None
    input_files: dict[str, list[Path]] = field(default_factory=dict)
    output_targets: dict[str, Path] = field(default_factory=dict)
    report_root: Path | None = None
    step_params: dict[str, Any] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "workflow_file": self.workflow_file.as_posix(),
            "workflow_id": self.workflow_id,
            "root": self.root.as_posix() if self.root else None,
            "parameters": dict(self.parameters),
            "inputs": self.inputs,
            "steps": self.steps,
            "outputs": self.outputs,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


def validate_workflow(path: Path, cli_parameters: dict[str, str] | None = None) -> ValidationReport:
    """Validate the workflow file at ``path`` with the given run parameters.

    Raises:
        WorkflowLoadError: The file cannot be read or is not valid YAML.
    Schema and cross-check problems do not raise: they are collected in the report.
    """
    report = ValidationReport(workflow_file=path)
    try:
        config = load_workflow(path)
    except WorkflowValidationError as exc:
        report.errors.extend(exc.issues)
        return report
    report.workflow_id = config.workflow.id
    report.config = config
    logger.info("Loaded workflow %r from %s", config.workflow.id, path)

    _check_identifiers(config, report)
    _check_steps(config, report)
    values = _check_parameters(config, cli_parameters or {}, report)
    try:
        report.root = resolve_root(path, config.workflow.root)
    except PathRuleError as exc:
        report.errors.append(f"workflow.root: {exc}")
    if report.root is not None and values is not None:
        _check_paths_and_sources(config, report.root, values, report)
    report.steps = [
        {"id": s.id, "type": s.type, "inputs": s.inputs, "output": s.output, "type_parameters": sorted(s.parameters)}
        for s in config.steps
    ]
    logger.info(
        "Validation of %r finished: %d error(s), %d warning(s)",
        config.workflow.id,
        len(report.errors),
        len(report.warnings),
    )
    return report


def _check_identifiers(config: WorkflowConfig, report: ValidationReport) -> None:
    def duplicates(values: list[str]) -> list[str]:
        return sorted({v for v in values if values.count(v) > 1})

    for section, ids in (
        ("inputs", [i.id for i in config.inputs]),
        ("steps", [s.id for s in config.steps]),
        ("outputs", [o.id for o in config.outputs]),
    ):
        for dup in duplicates(ids):
            report.errors.append(f"{section}: id {dup!r} is used more than once")

    available: dict[str, str] = {i.id: f"input {i.id!r}" for i in config.inputs}
    produced_later = {s.output: index for index, s in enumerate(config.steps)}
    for index, step in enumerate(config.steps):
        where = f"steps[{index}] ({step.id})"
        for name in step.inputs:
            if name in available:
                continue
            if name in produced_later and produced_later[name] >= index:
                producer = config.steps[produced_later[name]].id
                report.errors.append(f"{where}: input {name!r} is used before it is produced (by step {producer!r})")
            else:
                report.errors.append(f"{where}: input {name!r} is not an input or the output of an earlier step")
        if step.output in available:
            report.errors.append(f"{where}: output name {step.output!r} is already used by {available[step.output]}")
        else:
            available[step.output] = f"step {step.id!r}"

    used = {name for step in config.steps for name in step.inputs} | {o.input for o in config.outputs}
    for index, output in enumerate(config.outputs):
        if output.input not in available:
            report.errors.append(
                f"outputs[{index}] ({output.id}): dataset {output.input!r} is not produced by any input or step"
            )
    for name, origin in available.items():
        if name not in used:
            report.warnings.append(f"dataset {name!r} ({origin}) is never used")


def _check_steps(config: WorkflowConfig, report: ValidationReport) -> None:
    for index, step in enumerate(config.steps):
        params, problems = validate_step(step.type, len(step.inputs), step.parameters)
        report.errors.extend(f"steps[{index}] ({step.id}).{problem}" for problem in problems)
        if params is not None:
            report.step_params[step.id] = params
            for name in params.parameter_references():
                if name not in config.parameters:
                    report.errors.append(f"steps[{index}] ({step.id}): parameter {name!r} is not declared")
    if config.report.summary is not None:
        datasets = {i.id for i in config.inputs} | {s.output for s in config.steps}
        for name in config.report.summary.datasets:
            if name not in datasets:
                report.errors.append(f"report.summary.datasets: {name!r} is not produced by any input or step")


def _check_parameters(config: WorkflowConfig, given: dict[str, str], report: ValidationReport) -> dict[str, str] | None:
    """Return the final parameter values, or ``None`` if any parameter problem was found."""
    ok = True
    values: dict[str, str] = {}
    for name in sorted(set(given) - set(config.parameters)):
        report.errors.append(f"--param {name}: not declared in the workflow's parameters")
        ok = False
    for name, spec in config.parameters.items():
        if name in given:
            try:
                values[name] = parse_value(spec.type, given[name])
            except ValueError as exc:
                report.errors.append(f"--param {name}={given[name]!r}: {exc}")
                ok = False
        elif spec.default is not None:
            values[name] = parse_value(spec.type, spec.default)
        elif spec.is_required:
            report.errors.append(f"parameter {name!r} is required: pass --param {name}=<{spec.type}>")
            ok = False

    used: set[str] = set()
    paths = [(f"inputs[{i}] ({s.id}).path", s.path) for i, s in enumerate(config.inputs)]
    paths += [(f"outputs[{i}] ({o.id}).path", o.path) for i, o in enumerate(config.outputs)]
    for where, text in paths:
        for name in placeholders(text):
            used.add(name)
            if name not in config.parameters:
                report.errors.append(f"{where}: placeholder {{{name}}} is not a declared parameter")
                ok = False
    for name in sorted(set(config.parameters) - used):
        report.warnings.append(f"parameter {name!r} is declared but not used in any path")
    report.parameters = values
    return values if ok else None


def _check_paths_and_sources(
    config: WorkflowConfig, root: Path, values: dict[str, str], report: ValidationReport
) -> None:
    input_patterns: list[Path] = []
    source_files: set[str] = set()
    for index, spec in enumerate(config.inputs):
        where = f"inputs[{index}] ({spec.id}).path"
        entry: dict[str, Any] = {"id": spec.id, "type": spec.type, "path": spec.path}
        try:
            check_relative_path(spec.path, allow_wildcards=True)
            pattern = resolve_in_root(root, render(spec.path, values))
        except PathRuleError as exc:
            report.errors.append(f"{where}: {exc}")
            report.inputs.append(entry)
            continue
        input_patterns.append(pattern)
        matches = find_matches(root, pattern)
        escaping = escaping_matches(root, matches)
        for path in escaping:
            report.errors.append(
                f"{where}: {relative_posix(root, path)} resolves outside the working root (symbolic link)"
            )
        matches = [m for m in matches if m not in escaping]
        report.input_files[spec.id] = matches
        entry.update(resolved=relative_posix(root, pattern), matches=[relative_posix(root, m) for m in matches])
        report.inputs.append(entry)
        source_files.update(os.path.normcase(m.resolve()) for m in matches)
        logger.info("Input %r: %d file(s) match %s", spec.id, len(matches), entry["resolved"])
        if not matches:
            message = f"{where}: no file matches {entry['resolved']}"
            (report.errors if spec.on_empty_match == "fail" else report.warnings).append(message)

    seen_outputs: dict[str, str] = {}
    for index, spec in enumerate(config.outputs):
        where = f"outputs[{index}] ({spec.id}).path"
        entry = {"id": spec.id, "input": spec.input, "type": spec.type, "path": spec.path}
        try:
            check_relative_path(spec.path, allow_wildcards=False)
            target = resolve_in_root(root, render(spec.path, values))
        except PathRuleError as exc:
            report.errors.append(f"{where}: {exc}")
            report.outputs.append(entry)
            continue
        entry["resolved"] = relative_posix(root, target)
        entry["metadata"] = entry["resolved"] + METADATA_SUFFIX
        report.outputs.append(entry)
        report.output_targets[spec.id] = target
        key = os.path.normcase(target)
        if key in seen_outputs:
            report.errors.append(f"{where}: same file as output {seen_outputs[key]!r}")
        seen_outputs[key] = spec.id
        if os.path.normcase(target.resolve()) in source_files or any(
            os.path.normcase(target.parent) == os.path.normcase(p.parent) and fnmatch.fnmatch(target.name, p.name)
            for p in input_patterns
        ):
            report.errors.append(
                f"{where}: {entry['resolved']} is (or would be) a source file; sources are never overwritten"
            )
        if target.is_dir():
            report.errors.append(f"{where}: {entry['resolved']} is a folder")
        sidecar = Path(str(target) + METADATA_SUFFIX)
        if os.path.normcase(sidecar.resolve()) in source_files or os.path.normcase(sidecar) in seen_outputs:
            report.errors.append(
                f"{where}: its metadata file {entry['metadata']} would overwrite a source or an output"
            )

    where = "report.directory"
    try:
        check_relative_path(config.report.directory, allow_wildcards=False)
        report_root = resolve_in_root(root, render(config.report.directory, values)) / config.workflow.id
    except PathRuleError as exc:
        report.errors.append(f"{where}: {exc}")
        return
    if report_root.exists() and not report_root.is_dir():
        report.errors.append(f"{where}: {relative_posix(root, report_root)} exists and is not a folder")
    for file in source_files:
        if os.path.normcase(file).startswith(os.path.normcase(str(report_root)) + os.sep):
            report.errors.append(f"{where}: the run folder must not contain source files")
            break
    report.report_root = report_root
