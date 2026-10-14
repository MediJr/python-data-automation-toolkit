"""Command-line interface: ``data-automate`` (also ``python -m data_automation``).

Commands: ``validate`` (check without running), ``run`` (execute a workflow) and ``steps``
(list the available step types).

Exit codes (stable, for schedulers):
    0    success (valid workflow, or run completed and every output published)
    1    the run failed (see its report)
    2    invalid command-line usage
    3    refused before anything ran: invalid workflow or parameters, missing sources,
         outputs that would be overwritten without --overwrite, or another run in progress
    4    partial run (on_error: continue): some outputs published, some steps or outputs failed
    130  the run was interrupted
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .engine import EXIT_FAILED, RunRejected, run_workflow
from .errors import AutomationError
from .log import configure_logging
from .parameters import parse_cli_parameters
from .registry import available
from .validation import validate_workflow

PROG = "data-automate"
EXIT_OK = 0
EXIT_RUN_FAILED = EXIT_FAILED
EXIT_USAGE = 2
EXIT_INVALID_WORKFLOW = 3
EXIT_PARTIAL = 4
EXIT_INTERRUPTED = 130

_EXAMPLES = f"""\
examples:
  {PROG} validate config/examples/monthly_sales.yaml --param period=2026-09
  {PROG} run config/examples/monthly_sales.yaml --param period=2026-09
  {PROG} run config/examples/monthly_sales.yaml --param period=2026-09 --overwrite
  {PROG} -v run config/examples/monthly_sales.yaml --param period=2026-09 --json
  {PROG} steps

exit codes: 0 success, 1 run failed, 2 usage error, 3 refused before running,
            4 partial run (on_error: continue), 130 interrupted
"""


def _add_workflow_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("workflow", type=Path, help="workflow file (.yaml or .yml)")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="run parameter, e.g. period=2026-09 (repeatable)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Declarative, validated and traceable automation of data-processing workflows.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="show progress (-v) or details (-vv) on stderr"
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    validate = commands.add_parser(
        "validate",
        help="check a workflow file without running it",
        description="Check a workflow file: schema, step types and parameters, references between sections, run "
        "parameters, paths and sources. Data files are not read and nothing is written.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_workflow_arguments(validate)
    validate.add_argument("--json", action="store_true", help="print the validation report as JSON on stdout")

    run = commands.add_parser(
        "run",
        help="run a workflow: read the sources, run the steps, write and verify the outputs",
        description="Run a workflow. Every output is written to a temporary file, read back and compared before it "
        "is published; source files are never modified; a run report is written for every run that starts.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_workflow_arguments(run)
    run.add_argument(
        "--overwrite", action="store_true", help="allow replacing existing output files (after verification)"
    )
    run.add_argument("--json", action="store_true", help="print the run report as JSON on stdout")

    commands.add_parser("steps", help="list the available step types", description="List the available step types.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")  # never crash on a legacy console encoding
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    try:
        if args.command == "steps":
            return _steps()
        if args.command == "validate":
            return _validate(args)
        return _run(args)
    except RunRejected as exc:
        for problem in exc.problems:
            print(f"Error: {problem}", file=sys.stderr)
        print(f"Result: REFUSED ({len(exc.problems)} problem(s); nothing was run)", file=sys.stderr)
        return EXIT_INVALID_WORKFLOW
    except AutomationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INVALID_WORKFLOW
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_RUN_FAILED


def _steps() -> int:
    for name, step_type in available().items():
        inputs = (
            f"{step_type.min_inputs}"
            if step_type.min_inputs == step_type.max_inputs
            else f"{step_type.min_inputs}+"
            if step_type.max_inputs is None
            else f"{step_type.min_inputs}-{step_type.max_inputs}"
        )
        print(f"{name:<12} inputs: {inputs:<3} {step_type.description}")
    return EXIT_OK


def _validate(args: argparse.Namespace) -> int:
    report = validate_workflow(args.workflow, parse_cli_parameters(args.param))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return EXIT_OK if report.valid else EXIT_INVALID_WORKFLOW
    out = sys.stdout if report.valid else sys.stderr
    print(f"Workflow: {report.workflow_id or '(unreadable)'} ({args.workflow.as_posix()})", file=out)
    if report.root is not None:
        print(f"Root: {report.root.as_posix()}", file=out)
    if report.parameters:
        print("Parameters: " + ", ".join(f"{k}={v}" for k, v in report.parameters.items()), file=out)
    for entry in report.inputs:
        if "matches" in entry:
            print(f"Input {entry['id']}: {len(entry['matches'])} file(s) match {entry['resolved']}", file=out)
    for entry in report.steps:
        print(f"Step {entry['id']}: type {entry['type']}, {', '.join(entry['inputs'])} -> {entry['output']}", file=out)
    for entry in report.outputs:
        if "resolved" in entry:
            print(f"Output {entry['id']}: {entry['input']} -> {entry['resolved']}", file=out)
    for warning in report.warnings:
        print(f"Warning: {warning}", file=out)
    if report.valid:
        print("Result: VALID (nothing was run)", file=out)
        return EXIT_OK
    for error in report.errors:
        print(f"Error: {error}", file=out)
    print(f"Result: INVALID ({len(report.errors)} error(s); nothing was run)", file=out)
    return EXIT_INVALID_WORKFLOW


def _run(args: argparse.Namespace) -> int:
    result = run_workflow(args.workflow, parse_cli_parameters(args.param), overwrite=args.overwrite)
    report = result.report
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return result.exit_code
    out = sys.stdout if result.status == "success" else sys.stderr
    print(f"Run {result.run_id} of workflow {report['workflow']['id']}", file=out)
    for entry in report["inputs"]:
        print(
            f"Input {entry['id']}: {entry['status']}, {entry['rows']} row(s) from {len(entry['files'])} file(s)",
            file=out,
        )
    for entry in report["steps"]:
        detail = (
            f"{entry.get('rows_out', '-')} row(s)"
            if entry["status"] == "success"
            else entry.get("error") or entry.get("reason")
        )
        print(f"Step {entry['id']} ({entry['type']}): {entry['status']}, {detail}", file=out)
    for entry in report["outputs"]:
        detail = (
            f"{entry.get('rows')} row(s) -> {entry['path']}"
            if entry["status"] == "published"
            else entry.get("error") or entry.get("reason")
        )
        print(f"Output {entry['id']}: {entry['status']}, {detail}", file=out)
    for warning in report["warnings"]:
        print(f"Warning: {warning}", file=out)
    for error in report["errors"]:
        print(f"Error: {error}", file=out)
    reports = ", ".join(p.name for p in result.report_files)
    print(f"Report: {report['run_folder']}/ ({reports})", file=out)
    print(f"Result: {result.status.upper()} (exit code {result.exit_code})", file=out)
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
