"""Regenerate ``reports/examples/`` by really running the example workflows.

Each example runs in a temporary copy of ``config/`` and ``data/`` (so the repository's own
``output/`` and ``runs/`` folders are untouched); its outputs and its run folder are then
copied to ``reports/examples/<workflow id>/``. Nothing in ``reports/examples/`` is edited by
hand; ``tests/test_examples.py`` checks that it still matches a fresh run.

Usage (from the project root, with the package installed):
    python scripts/regenerate_examples.py --overwrite
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "reports" / "examples"
RUNS = [
    ("monthly-sales-report", "config/examples/monthly_sales.yaml"),
    ("sales-vs-targets", "config/examples/sales_vs_targets.yaml"),
    ("monthly-sales-by-category", "config/examples/monthly_sales_by_category.yaml"),
]
PARAMETERS = ["--param", "period=2026-09"]


def run_example(workflow_id: str, workflow: str, destination: Path) -> int:
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        shutil.copytree(ROOT / "config", work / "config")
        shutil.copytree(ROOT / "data", work / "data")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        completed = subprocess.run(  # noqa: S603 - fixed arguments, no shell
            [sys.executable, "-m", "data_automation", "run", workflow, *PARAMETERS],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        print(completed.stdout.rstrip())
        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
        run_dirs = list((work / "runs" / workflow_id).iterdir())
        shutil.copytree(work / "output", destination / "output")
        shutil.copytree(run_dirs[0], destination / "run")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overwrite", action="store_true", help="replace the existing examples")
    args = parser.parse_args()
    for workflow_id, workflow in RUNS:
        destination = EXAMPLES / workflow_id
        if destination.exists():
            if not args.overwrite:
                print(f"Error: {destination.relative_to(ROOT).as_posix()} exists; use --overwrite", file=sys.stderr)
                return 1
            shutil.rmtree(destination)
        code = run_example(workflow_id, workflow, destination)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
