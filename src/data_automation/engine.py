"""Workflow execution engine (phases 2, 4 and 5).

Order of a run (ADR-0003, ADR-0004):

1. validate the workflow; any problem rejects the run before anything starts;
2. take the workflow lock (one run of a workflow at a time);
3. check every output and metadata file: an existing one is never replaced without
   ``overwrite`` (all problems reported together, nothing started);
4. fingerprint the source files (SHA-256);
5. read the inputs, then run the steps in their declared order. A step whose input was not
   produced is skipped; with ``on_error: stop`` the first failure stops the run, with
   ``continue`` the independent steps go on;
6. write every output to a temporary file next to its destination, read it back and compare
   it with the dataset, then check that no source file changed;
7. only then publish the outputs (atomic replacement). With ``stop``, nothing is published
   unless everything succeeded; with ``continue``, verified outputs whose data was fully
   produced are published and the run is "partial";
8. write the run report (always, even after a failure) and release the lock.

Each run has a UUID v4 and its own folder ``<report.directory>/<workflow id>/<run id>/``.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import platform
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .dataset import Dataset
from .errors import AutomationError
from .log import LOGGER_NAME, LfFileHandler, UtcFormatter
from .paths import relative_posix
from .readers import InputReadError, read_input
from .registry import StepContext, StepFailure, get
from .validation import METADATA_SUFFIX, ValidationReport, validate_workflow
from .writers import (
    CSV_FORMAT,
    ExportError,
    check_columns,
    column_schema,
    decimal_places,
    sha256,
    verify_csv,
    verify_xlsx,
    write_csv,
    write_xlsx,
)

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_REJECTED = 3
EXIT_PARTIAL = 4
EXIT_INTERRUPTED = 130
STATUS_EXIT = {"success": EXIT_SUCCESS, "partial": EXIT_PARTIAL, "failed": EXIT_FAILED, "interrupted": EXIT_INTERRUPTED}
LOCK_NAME = ".lock"
DEFAULT_SHEET = "data"


class RunRejected(AutomationError):
    """The run was refused before anything started; ``problems`` lists every reason."""

    def __init__(self, problems: list[str], validation: ValidationReport | None = None) -> None:
        self.problems = list(problems)
        self.validation = validation
        super().__init__(f"run refused ({len(self.problems)} problem(s)):\n  - " + "\n  - ".join(self.problems))


@dataclass
class RunResult:
    run_id: str
    status: str
    exit_code: int
    run_dir: Path
    report: dict[str, Any]
    report_files: list[Path] = field(default_factory=list)


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class _Run:
    """State of one run; kept in one object so that the report can always be written."""

    def __init__(self, validation: ValidationReport, workflow_file: Path, overwrite: bool) -> None:
        self.validation = validation
        self.config = validation.config
        self.root: Path = validation.root
        self.workflow_file = workflow_file
        self.overwrite = overwrite
        self.run_id = str(uuid.uuid4())
        self.started = _now()
        self.clock = time.perf_counter()
        self.datasets: dict[str, Dataset] = {}
        self.sources: dict[str, dict[str, Any]] = {}
        self.inputs: list[dict[str, Any]] = []
        self.steps: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.warnings: list[str] = list(validation.warnings)
        self.failed = False
        self.sources_changed = False
        self.interrupted = False
        self.temporaries: list[Path] = []
        self.published: list[str] = []
        self.run_dir: Path = validation.report_root / self.run_id

    # ------------------------------------------------------------------ helpers

    def rel(self, path: Path) -> str:
        return relative_posix(self.root, path)

    def fail(self, message: str) -> None:
        self.failed = True
        self.errors.append(message)
        logger.error(message)

    @property
    def stop_on_error(self) -> bool:
        return self.config.on_error == "stop"

    @property
    def stopped(self) -> bool:
        return self.interrupted or (self.failed and self.stop_on_error)

    # ------------------------------------------------------------------ phases

    def fingerprint_sources(self) -> None:
        for input_id, files in self.validation.input_files.items():
            for path in files:
                self.sources[self.rel(path)] = {"input": input_id, "sha256_before": sha256(path), "path": path}

    def read_inputs(self) -> None:
        for spec in self.config.inputs:
            entry: dict[str, Any] = {"id": spec.id, "status": "skipped", "files": [], "rows": 0, "warnings": []}
            self.inputs.append(entry)
            if self.stopped:
                entry["reason"] = "run stopped"
                continue
            started = time.perf_counter()
            try:
                result = read_input(spec, self.validation.input_files.get(spec.id, []), self.root)
            except InputReadError as exc:
                entry.update(status="failed", error=str(exc))
                self.fail(f"input {spec.id!r}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 - an unexpected bug must not hide the report
                entry.update(status="failed", error=f"internal error: {exc!r}")
                self.fail(f"input {spec.id!r}: internal error {exc!r}")
                logger.debug("Traceback:\n%s", traceback.format_exc())
                continue
            finally:
                entry["duration_s"] = round(time.perf_counter() - started, 3)
            self.datasets[spec.id] = result.dataset
            entry.update(status="success", files=result.files, rows=result.dataset.rows, warnings=result.warnings)
            self.warnings.extend(f"input {spec.id!r}: {w}" for w in result.warnings)
            logger.info("Input %r: %d row(s) from %d file(s)", spec.id, result.dataset.rows, len(result.files))

    def run_steps(self) -> None:
        for step in self.config.steps:
            entry: dict[str, Any] = {"id": step.id, "type": step.type, "inputs": step.inputs, "output": step.output}
            self.steps.append(entry)
            if self.stopped:
                entry.update(status="skipped", reason="run stopped")
                continue
            missing = [name for name in step.inputs if name not in self.datasets]
            if missing:
                entry.update(status="skipped", reason=f"input(s) not available: {', '.join(missing)}")
                self.warnings.append(f"step {step.id!r} skipped: input(s) {missing} not available")
                continue
            inputs = [self.datasets[name] for name in step.inputs]
            entry["rows_in"] = {d.name: d.rows for d in inputs}
            context = StepContext(
                self.run_id, self.config.workflow.id, step.id, dict(self.validation.parameters), logger
            )
            started = time.perf_counter()
            try:
                result = get(step.type).run(self.validation.step_params[step.id], inputs, context)
            except StepFailure as exc:
                entry.update(status="failed", error=str(exc))
                self.fail(f"step {step.id!r} ({step.type}): {exc}")
            except Exception as exc:  # noqa: BLE001 - an unexpected bug must not hide the report
                entry.update(status="failed", error=f"internal error: {exc!r}")
                self.fail(f"step {step.id!r} ({step.type}): internal error {exc!r}")
                logger.debug("Traceback:\n%s", traceback.format_exc())
            else:
                result.dataset.name = step.output
                self.datasets[step.output] = result.dataset
                entry.update(
                    status="success", rows_out=result.dataset.rows, warnings=result.warnings, details=result.details
                )
                self.warnings.extend(f"step {step.id!r}: {w}" for w in result.warnings)
                logger.info("Step %r (%s): %s -> %d row(s)", step.id, step.type, entry["rows_in"], result.dataset.rows)
            finally:
                entry["duration_s"] = round(time.perf_counter() - started, 3)

    def prepare_outputs(self) -> list[tuple[dict[str, Any], Path, Path, Path, Path]]:
        """Write and verify every output under temporary names; nothing is published here."""
        prepared = []
        for spec in self.config.outputs:
            target = self.validation.output_targets[spec.id]
            entry: dict[str, Any] = {
                "id": spec.id,
                "input": spec.input,
                "type": spec.type,
                "path": self.rel(target),
                "metadata": self.rel(target) + METADATA_SUFFIX,
                "status": "not_published",
            }
            self.outputs.append(entry)
            if self.stopped:
                entry["reason"] = "run stopped"
                continue
            dataset = self.datasets.get(spec.input)
            if dataset is None:
                entry.update(status="skipped", reason=f"dataset {spec.input!r} was not produced")
                self.warnings.append(f"output {spec.id!r} skipped: dataset {spec.input!r} was not produced")
                continue
            token = uuid.uuid4().hex[:8]
            # temporary names keep the real extension (openpyxl only opens .xlsx names)
            temp = target.with_name(f".{target.stem}.tmp-{token}{target.suffix}")
            temp_meta = target.with_name(f".{target.name}.tmp-{token}{METADATA_SUFFIX}")
            sheet = spec.sheet_name or DEFAULT_SHEET
            started = time.perf_counter()
            try:
                if len(dataset.parts) != 1:
                    raise ExportError(
                        f"dataset {spec.input!r} still has {len(dataset.parts)} parts; concatenate it first"
                    )
                check_columns(dataset, spec.expected_columns)
                target.parent.mkdir(parents=True, exist_ok=True)
                self.temporaries += [temp, temp_meta]
                if spec.type == "csv":
                    write_csv(dataset, temp)
                    verify_csv(dataset, temp)
                else:
                    write_xlsx(dataset, temp, sheet)
                    verify_xlsx(dataset, temp, sheet)
                checks = [
                    "columns" + (" match expected_columns" if spec.expected_columns else " recorded"),
                    "file read back and compared value by value",
                    f"{dataset.rows} row(s) read back",
                ]
                metadata = self.metadata(spec, dataset, temp, checks, sheet)
                temp_meta.write_text(
                    json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
                )
                entry.update(
                    status="verified",
                    rows=dataset.rows,
                    columns=dataset.columns,
                    sha256=metadata["file"]["sha256"],
                    checks=checks,
                    duration_s=round(time.perf_counter() - started, 3),
                )
                prepared.append((entry, temp, target, temp_meta, Path(str(target) + METADATA_SUFFIX)))
                logger.info("Output %r written and verified (%d row(s))", spec.id, dataset.rows)
            except (ExportError, OSError) as exc:
                entry.update(status="failed", error=str(exc))
                self.fail(f"output {spec.id!r}: {exc}")
            except Exception as exc:  # noqa: BLE001 - an unexpected bug must not hide the report
                entry.update(status="failed", error=f"internal error: {exc!r}")
                self.fail(f"output {spec.id!r}: internal error {exc!r}")
                logger.debug("Traceback:\n%s", traceback.format_exc())
        return prepared

    def metadata(self, spec: Any, dataset: Dataset, temp: Path, checks: list[str], sheet: str) -> dict[str, Any]:
        file_format = (
            dict(CSV_FORMAT) if spec.type == "csv" else {"sheet_name": sheet, "dates": "date cells (yyyy-mm-dd)"}
        )
        return {
            "metadata_version": 1,
            "workflow_id": self.config.workflow.id,
            "run_id": self.run_id,
            "generated_at": _now(),
            "parameters": dict(self.validation.parameters),
            "output_id": spec.id,
            "dataset": spec.input,
            "file": {
                "path": self.rel(self.validation.output_targets[spec.id]),
                "type": spec.type,
                "sha256": sha256(temp),
                "rows": dataset.rows,
                "format": file_format,
            },
            "columns": column_schema(dataset),
            "decimal_places": decimal_places(dataset),
            "sources": [{"path": path, "sha256": info["sha256_before"]} for path, info in self.sources.items()],
            "checks": checks,
        }

    def check_sources_unchanged(self) -> None:
        for path, info in self.sources.items():
            try:
                info["sha256_after"] = sha256(info["path"])
            except OSError as exc:
                info["sha256_after"] = None
                self.fail(f"source {path} could not be read again after the run: {exc}")
                continue
            if info["sha256_after"] != info["sha256_before"]:
                self.sources_changed = True
                self.fail(f"source {path} changed during the run; outputs are not published")

    def publish(self, prepared: list[tuple[dict[str, Any], Path, Path, Path, Path]]) -> None:
        if self.sources_changed or self.stopped or (self.failed and self.stop_on_error):
            reason = (
                "a source file changed during the run"
                if self.sources_changed
                else "the run did not succeed (on_error: stop)"
            )
            for entry, *_ in prepared:
                entry.update(status="not_published", reason=reason)
            return
        for entry, temp, target, temp_meta, meta_target in prepared:
            try:
                os.replace(temp, target)
                os.replace(temp_meta, meta_target)
            except OSError as exc:
                entry.update(status="failed", error=f"could not be published: {exc}")
                self.fail(
                    f"output {entry['id']!r} could not be published (is the file open in another program?): {exc}"
                )
                if self.stop_on_error:
                    break
                continue
            entry["status"] = "published"
            self.published.append(entry["id"])
        if self.failed and self.published:
            self.warnings.append(f"outputs already published before the failure: {self.published}")

    def status(self) -> str:
        if self.interrupted:
            return "interrupted"
        if not self.failed:
            return "success"
        if not self.stop_on_error and self.published:
            return "partial"
        return "failed"

    def cleanup(self) -> None:
        for temp in self.temporaries:
            try:
                temp.unlink(missing_ok=True)
            except OSError as exc:
                self.warnings.append(f"temporary file {self.rel(temp)} could not be removed: {exc}")

    def _complete_entries(self) -> None:
        """After an interruption, give every input, step and output an explicit status."""
        for entry in self.inputs + self.steps:
            entry.setdefault("status", "interrupted")
        seen_inputs = {e["id"] for e in self.inputs}
        for spec in self.config.inputs:
            if spec.id not in seen_inputs:
                self.inputs.append(
                    {"id": spec.id, "status": "skipped", "files": [], "rows": 0, "reason": "run interrupted"}
                )
        seen_steps = {e["id"] for e in self.steps}
        for step in self.config.steps:
            if step.id not in seen_steps:
                self.steps.append(
                    {
                        "id": step.id,
                        "type": step.type,
                        "inputs": step.inputs,
                        "output": step.output,
                        "status": "skipped",
                        "reason": "run interrupted",
                    }
                )
        seen_outputs = {e["id"] for e in self.outputs}
        for spec in self.config.outputs:
            if spec.id not in seen_outputs:
                target = self.validation.output_targets[spec.id]
                self.outputs.append(
                    {
                        "id": spec.id,
                        "input": spec.input,
                        "type": spec.type,
                        "path": self.rel(target),
                        "status": "not_published",
                        "reason": "run interrupted",
                    }
                )
        for entry in self.outputs:
            if entry["status"] == "verified":  # interrupted before publication
                entry.update(status="not_published", reason="the run was interrupted before publication")

    def report(self, finished: str) -> dict[str, Any]:
        self._complete_entries()
        status = self.status()
        return {
            "report_version": 1,
            "tool": {"name": "python-data-automation-toolkit", "version": __version__},
            "workflow": {
                "id": self.config.workflow.id,
                "file": self.workflow_file.name,
                "description": self.config.workflow.description,
            },
            "run_id": self.run_id,
            "started_at": self.started,
            "finished_at": finished,
            "duration_s": round(time.perf_counter() - self.clock, 3),
            "status": status,
            "exit_code": STATUS_EXIT[status],
            "on_error": self.config.on_error,
            "overwrite": self.overwrite,
            "parameters": dict(self.validation.parameters),
            "run_folder": self.rel(self.run_dir),
            "sources": [
                {
                    "path": p,
                    "input": i["input"],
                    "sha256_before": i["sha256_before"],
                    "sha256_after": i.get("sha256_after"),
                    "unchanged": i.get("sha256_after") == i["sha256_before"],
                }
                for p, i in self.sources.items()
            ],
            "inputs": self.inputs,
            "steps": self.steps,
            "outputs": self.outputs,
            "errors": self.errors,
            "warnings": self.warnings,
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
        }


def _acquire_lock(report_root: Path, run_id: str) -> Path:
    report_root.mkdir(parents=True, exist_ok=True)
    lock = report_root / LOCK_NAME
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            holder = lock.read_text(encoding="utf-8").strip()
        except OSError:
            holder = "unknown"
        raise RunRejected(
            [
                f"another run of this workflow holds the lock {lock.name} ({holder}); if no run is active "
                f"(e.g. after a crash), delete {lock}"
            ]
        ) from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"run_id={run_id} pid={os.getpid()} started={_now()}\n")
    return lock


def run_workflow(
    workflow_file: Path, parameters: dict[str, str] | None = None, *, overwrite: bool = False
) -> RunResult:
    """Run a workflow. See the module documentation for the exact order and guarantees.

    Raises:
        WorkflowLoadError: The file cannot be read (nothing started).
        RunRejected: Invalid workflow, lock held, or outputs that would be overwritten without
            permission (nothing started, no report written).
    """
    from .reporting import write_reports

    validation = validate_workflow(workflow_file, parameters or {})
    if not validation.valid:
        raise RunRejected(validation.errors, validation)
    run = _Run(validation, workflow_file, overwrite)
    lock = _acquire_lock(validation.report_root, run.run_id)
    file_handler: logging.Handler | None = None
    package_logger = logging.getLogger(LOGGER_NAME)
    try:
        blocked = []
        for output_id, target in validation.output_targets.items():
            for path in (target, Path(str(target) + METADATA_SUFFIX)):
                if path.exists() and not overwrite:
                    blocked.append(
                        f"output {output_id!r}: {run.rel(path)} already exists (use --overwrite to replace it)"
                    )
        if blocked:
            raise RunRejected(blocked, validation)
        run.run_dir.mkdir(parents=True, exist_ok=False)
        file_handler = LfFileHandler(run.run_dir / "run.log", encoding="utf-8")
        file_handler.setFormatter(UtcFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        file_handler.setLevel(logging.INFO)
        package_logger.addHandler(file_handler)
        previous_level = package_logger.level
        if package_logger.getEffectiveLevel() > logging.INFO:  # library use without configure_logging()
            package_logger.setLevel(logging.INFO)
        logger.info(
            "Run %s of workflow %r started (parameters %s)", run.run_id, run.config.workflow.id, validation.parameters
        )
        try:
            run.fingerprint_sources()
            run.read_inputs()
            run.run_steps()
            prepared = run.prepare_outputs()
            run.check_sources_unchanged()
            run.publish(prepared)
        except KeyboardInterrupt:
            run.interrupted = True
            run.errors.append("the run was interrupted; no further output was published")
            logger.error("Run %s interrupted", run.run_id)
        finally:
            run.cleanup()
        finished = _now()
        report = run.report(finished)
        logger.info("Run %s finished: %s", run.run_id, report["status"])
        files = write_reports(report, run, run.run_dir)
        return RunResult(run.run_id, report["status"], report["exit_code"], run.run_dir, report, files)
    finally:
        if file_handler is not None:
            package_logger.removeHandler(file_handler)
            package_logger.setLevel(previous_level)
            file_handler.close()
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove the lock file %s", lock)
