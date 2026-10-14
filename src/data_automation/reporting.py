"""Run reports (C-06).

* Technical report: ``run_report.json`` (complete, for programs) and ``run_report.md``
  (for people), written for every run that started, including failed ones.
* Business summary (optional, ``report.summary``): ``summary.md`` with the listed datasets
  as tables, e.g. the indicators computed by the workflow.

Reports contain paths relative to the working root only (no machine-specific paths) and
never the content of environment variables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .types import format_text, python_values

if TYPE_CHECKING:  # pragma: no cover
    from .engine import _Run

_STATUS_TEXT = {
    "success": "SUCCESS - every step ran and every output was verified and published",
    "partial": "PARTIAL - some steps or outputs failed; the outputs listed as published are complete",
    "failed": "FAILED - see the errors; outputs were not published unless listed as published",
    "interrupted": "INTERRUPTED - the run was stopped; outputs not listed as published were not changed",
}


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    return lines + ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Run report: {report['workflow']['id']}",
        "",
        *_table(
            ["Item", "Value"],
            [
                ["Status", _STATUS_TEXT[report["status"]]],
                ["Exit code", report["exit_code"]],
                ["Run id", report["run_id"]],
                ["Started (UTC)", report["started_at"]],
                ["Finished (UTC)", report["finished_at"]],
                ["Duration (s)", report["duration_s"]],
                ["Parameters", ", ".join(f"{k}={v}" for k, v in report["parameters"].items()) or "none"],
                ["Error policy", report["on_error"]],
            ],
        ),
        "",
        "## Sources",
        "",
    ]
    lines += (
        _table(
            ["File", "Input", "Unchanged during the run"],
            [[s["path"], s["input"], "yes" if s["unchanged"] else "NO"] for s in report["sources"]],
        )
        if report["sources"]
        else ["No source file."]
    )
    lines += ["", "## Inputs", ""]
    lines += _table(
        ["Input", "Status", "Files", "Rows", "Duration (s)"],
        [[i["id"], i["status"], len(i["files"]), i["rows"], i.get("duration_s", "")] for i in report["inputs"]],
    )
    lines += ["", "## Steps", ""]
    lines += (
        _table(
            ["Step", "Type", "Status", "Rows in", "Rows out", "Duration (s)", "Note"],
            [
                [
                    s["id"],
                    s["type"],
                    s["status"],
                    ", ".join(f"{k}: {v}" for k, v in s.get("rows_in", {}).items()),
                    s.get("rows_out", ""),
                    s.get("duration_s", ""),
                    s.get("error") or s.get("reason") or "",
                ]
                for s in report["steps"]
            ],
        )
        if report["steps"]
        else ["No step."]
    )
    lines += ["", "## Outputs", ""]
    lines += _table(
        ["Output", "File", "Status", "Rows", "Write + verify (s)", "SHA-256", "Note"],
        [
            [
                o["id"],
                o["path"],
                o["status"],
                o.get("rows", ""),
                o.get("duration_s", ""),
                (o.get("sha256") or "")[:16],
                o.get("error") or o.get("reason") or "",
            ]
            for o in report["outputs"]
        ],
    )
    lines += ["", "## Errors", ""] + ([f"- {e}" for e in report["errors"]] or ["None."])
    lines += ["", "## Warnings", ""] + ([f"- {w}" for w in report["warnings"]] or ["None."])
    lines += ["", "The complete report, including per-step details, is in `run_report.json`.", ""]
    return "\n".join(lines)


def render_summary(run: _Run) -> str | None:
    spec = run.config.report.summary
    if spec is None:
        return None
    lines = [f"# {spec.title or run.config.workflow.description or run.config.workflow.id}", ""]
    if run.validation.parameters:
        lines += ["Parameters: " + ", ".join(f"{k}={v}" for k, v in run.validation.parameters.items()), ""]
    lines += [f"Run {run.run_id}, status: {run.status()}.", ""]
    for name in spec.datasets:
        lines += [f"## {name}", ""]
        dataset = run.datasets.get(name)
        if dataset is None or len(dataset.parts) != 1:
            lines += ["Not available in this run (see the run report).", ""]
            continue
        frame = dataset.frame()
        kinds = [dataset.types[c] for c in dataset.columns]
        columns = [python_values(frame[c]) for c in dataset.columns]
        rows = [[format_text(k, v) for k, v in zip(kinds, row, strict=True)] for row in zip(*columns, strict=True)]
        lines += _table(dataset.columns, rows[: spec.max_rows])
        if len(rows) > spec.max_rows:
            lines += ["", f"_{spec.max_rows} of {len(rows)} rows shown._"]
        lines.append("")
    return "\n".join(lines)


def write_reports(report: dict[str, Any], run: _Run, run_dir: Path) -> list[Path]:
    """Write the technical report (and the business summary, if configured) into ``run_dir``."""
    written = []
    formats = run.config.report.formats
    if "json" in formats:
        path = run_dir / "run_report.json"
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n"
        )
        written.append(path)
    if "markdown" in formats:
        path = run_dir / "run_report.md"
        path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
        written.append(path)
    summary = render_summary(run)
    if summary is not None:
        path = run_dir / "summary.md"
        path.write_text(summary, encoding="utf-8", newline="\n")
        written.append(path)
    return written
