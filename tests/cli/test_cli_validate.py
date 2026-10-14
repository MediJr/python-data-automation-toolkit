"""The ``data-automate`` command line."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import VALID_WORKFLOW

from data_automation import __version__
from data_automation.cli import EXIT_INVALID_WORKFLOW, EXIT_OK, EXIT_USAGE, main

ROOT = Path(__file__).resolve().parents[2]


def test_help_and_version(capsys):
    for argv in (["--help"], ["validate", "--help"]):
        with pytest.raises(SystemExit) as info:
            main(argv)
        assert info.value.code == EXIT_OK
    out = capsys.readouterr().out
    assert "exit codes: 0 success, 1 run failed, 2 usage error, 3 refused before running," in out
    assert "4 partial run (on_error: continue), 130 interrupted" in out
    assert "--param NAME=VALUE" in out and "--json" in out
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == EXIT_OK and capsys.readouterr().out.strip() == f"data-automate {__version__}"


@pytest.mark.parametrize("argv", [[], ["validate"], ["execute", "x.yaml"], ["validate", "w.yaml", "--unknown"]])
def test_usage_errors_exit_2(argv, capsys):
    with pytest.raises(SystemExit) as info:
        main(argv)
    assert info.value.code == EXIT_USAGE


def test_valid_workflow_exit_0(workspace, capsys):
    assert main(["validate", str(workspace()), "--param", "period=2026-09"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Input sales_files: 1 file(s) match incoming/2026-09/sales_*.csv" in out
    assert "Output export: totals -> output/sales_2026-09.csv" in out
    assert "Note:" not in out  # step types and their parameters are validated since phase 2
    assert "Result: VALID (nothing was run)" in out


def test_invalid_workflow_exit_3_on_stderr(workspace, capsys):
    assert main(["validate", str(workspace())]) == EXIT_INVALID_WORKFLOW
    captured = capsys.readouterr()
    assert "Error: parameter 'period' is required" in captured.err
    assert "Result: INVALID (1 error(s); nothing was run)" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "argv_tail, message",
    [
        (["missing.yaml"], "Workflow file not found"),
        (["{wf}", "--param", "period"], "expected name=value"),
        (["{wf}", "--param", "period=1", "--param", "period=2"], "more than once"),
    ],
)
def test_load_and_parameter_errors_exit_3(workspace, capsys, argv_tail, message, monkeypatch, tmp_path):
    workflow = workspace()
    monkeypatch.chdir(tmp_path)
    assert main(["validate", *[a.format(wf=workflow) for a in argv_tail]]) == EXIT_INVALID_WORKFLOW
    assert message in capsys.readouterr().err


def test_python_tag_in_workflow_exit_3(workspace, capsys):
    workflow = workspace('workflow: !!python/object/apply:os.system ["echo hacked"]\n')
    assert main(["validate", str(workflow)]) == EXIT_INVALID_WORKFLOW
    assert "could not determine a constructor" in capsys.readouterr().err


def test_json_output(workspace, tmp_path, capsys):
    workflow = workspace()
    assert main(["validate", str(workflow), "--param", "period=2026-09", "--json"]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is True and data["errors"] == []
    assert data["inputs"][0]["matches"] == ["incoming/2026-09/sales_north.csv"]
    (tmp_path / "incoming" / "2026-09" / "sales_north.csv").unlink()
    assert main(["validate", str(workflow), "--param", "period=2026-09", "--json"]) == EXIT_INVALID_WORKFLOW
    data = json.loads(capsys.readouterr().out)
    assert data["valid"] is False
    assert data["errors"] == ["inputs[0] (sales_files).path: no file matches incoming/2026-09/sales_*.csv"]


def test_verbose_logging_goes_to_stderr_with_utc_timestamps(workspace, capsys):
    assert main(["-v", "validate", str(workspace()), "--param", "period=2026-09"]) == EXIT_OK
    err = capsys.readouterr().err
    assert "INFO data_automation.validation: Loaded workflow 'monthly-sales'" in err
    assert "Input 'sales_files': 1 file(s) match" in err
    first = err.splitlines()[0]
    assert first[:4].isdigit() and first.split(" ")[0].endswith("Z")
    logging.getLogger("data_automation").handlers.clear()


def test_quiet_by_default(workspace, capsys):
    main(["validate", str(workspace()), "--param", "period=2026-09"])
    assert capsys.readouterr().err == ""


def test_works_from_another_working_directory(workspace, tmp_path, monkeypatch, capsys):
    workflow = workspace(VALID_WORKFLOW.replace("root: .", "root: .."), name="config/workflow.yaml")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert main(["validate", os.path.relpath(workflow, elsewhere), "--param", "period=2026-09"]) == EXIT_OK
    assert "1 file(s) match incoming/2026-09/sales_*.csv" in capsys.readouterr().out


def test_module_entry_point_in_a_subprocess(workspace):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [sys.executable, "-m", "data_automation", "validate", str(workspace()), "--param", "period=2026-09"],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )
    assert completed.returncode == EXIT_OK, completed.stderr
    assert "Result: VALID" in completed.stdout


def test_example_workflow_of_the_repository_is_valid(capsys):
    example = ROOT / "config" / "examples" / "monthly_sales.yaml"
    assert main(["validate", str(example), "--param", "period=2026-09"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Input sales_files: 2 file(s) match data/sample/incoming/2026-09/sales_*.csv" in out
    assert "Output export_powerbi: kpis -> output/monthly_sales_2026-09.csv" in out
