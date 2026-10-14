"""The ``run`` and ``steps`` commands, and the scheduling wrapper (AC-10, AC-17)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from data_automation.cli import main

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = "config/examples/monthly_sales.yaml"
EXPECTED = "region,total_sales,order_count\nNorth,162.50,2\nSouth,200.00,1\n"


@pytest.fixture
def copy_of_project(tmp_path, monkeypatch):
    """The example workflow and its sample data, copied so that runs never write into the repository."""
    for folder in ("config", "data", "scripts"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_run_example_end_to_end(copy_of_project, capsys):
    assert main(["run", EXAMPLE, "--param", "period=2026-09"]) == 0
    out = capsys.readouterr().out
    assert "Input sales_files: success, 5 row(s) from 2 file(s)" in out
    assert "Step calculate_kpis (aggregate): success, 2 row(s)" in out
    assert "Output export_powerbi: published, 2 row(s) -> output/monthly_sales_2026-09.csv" in out
    assert "Result: SUCCESS (exit code 0)" in out
    assert (copy_of_project / "output/monthly_sales_2026-09.csv").read_text(encoding="utf-8") == EXPECTED


def test_run_refusals_and_failures_have_distinct_exit_codes(copy_of_project, capsys):
    assert main(["run", EXAMPLE]) == 3  # missing parameter: refused before running
    assert "parameter 'period' is required" in capsys.readouterr().err
    assert main(["run", EXAMPLE, "--param", "period=2026-09"]) == 0
    assert main(["run", EXAMPLE, "--param", "period=2026-09"]) == 3  # outputs exist
    assert "already exists (use --overwrite to replace it)" in capsys.readouterr().err
    bad = copy_of_project / "data/sample/incoming/2026-09/sales_north.csv"
    bad.write_text("region,order_id,status,amount\nNorth,SO-1,closed,12,5\n", encoding="utf-8")
    assert main(["run", EXAMPLE, "--param", "period=2026-09", "--overwrite"]) == 1
    err = capsys.readouterr().err
    assert "Result: FAILED (exit code 1)" in err and "line 2 (5 fields)" in err
    assert (copy_of_project / "output/monthly_sales_2026-09.csv").read_text(encoding="utf-8") == EXPECTED  # kept


def test_run_json_output(copy_of_project, capsys):
    assert main(["run", EXAMPLE, "--param", "period=2026-09", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "success" and report["exit_code"] == 0
    assert report["outputs"][0]["status"] == "published"


def test_steps_command_lists_the_registry(capsys):
    assert main(["steps"]) == 0
    names = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
    assert names == ["aggregate", "cast", "check", "concatenate", "filter", "join", "rename", "select", "sort"]


def test_installed_command_in_a_subprocess(copy_of_project):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [sys.executable, "-m", "data_automation", "run", EXAMPLE, "--param", "period=2026-09"],
        capture_output=True,
        text=True,
        env=env,
        cwd=copy_of_project,
    )
    assert completed.returncode == 0, completed.stderr
    assert (copy_of_project / "output/monthly_sales_2026-09.csv").read_text(encoding="utf-8") == EXPECTED


@pytest.mark.skipif(os.name != "nt" or shutil.which("powershell.exe") is None, reason="Windows PowerShell")
def test_task_scheduler_wrapper_script(copy_of_project):
    """AC-17: the command documented for the Windows Task Scheduler runs and returns the exit code."""
    script = copy_of_project / "scripts/scheduling/run_monthly_sales.ps1"
    exe = Path(sys.executable).with_name("data-automate.exe")
    if not exe.exists():
        pytest.skip("data-automate.exe is not installed in this environment")
    base = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-DataAutomate",
        str(exe),
        "-Period",
        "2026-09",
    ]
    first = subprocess.run(base, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    assert (copy_of_project / "output/monthly_sales_2026-09.csv").read_text(encoding="utf-8") == EXPECTED
    assert subprocess.run(base, capture_output=True).returncode == 3  # already processed: refused
    assert subprocess.run([*base, "-Overwrite"], capture_output=True).returncode == 0
