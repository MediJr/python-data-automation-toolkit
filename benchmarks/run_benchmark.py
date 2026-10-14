"""Run the benchmark: 1 warm-up run, then 3 measured runs of the real CLI, then verify.

Each run starts from an empty ``benchmarks/work/output`` and ``runs`` folder (a fresh,
complete run, as a scheduler would start it). The results are printed and written to
``benchmarks/results.json``; ``benchmarks/verify_outputs.py`` then checks the outputs
independently.

Usage (from the project root, with the package installed):
    python benchmarks/run_benchmark.py
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate_data import WORK, generate  # noqa: E402
from measure import run_measured  # noqa: E402

MEASURED_RUNS = 3


def _one_run() -> dict:
    for folder in ("output", "runs"):
        shutil.rmtree(WORK / folder, ignore_errors=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = run_measured([sys.executable, "-m", "data_automation", "run", str(HERE / "benchmark.yaml")], env=env)
    if result["exit_code"] != 0:
        raise SystemExit(f"benchmark run failed (exit {result['exit_code']}):\n{result['stdout']}\n{result['stderr']}")
    return result


def main() -> int:
    generate(rows_per_file=10_000, files=12)
    inputs = sorted((WORK / "data").rglob("*.csv"))
    _one_run()  # warm-up: file cache, .pyc files
    runs = [_one_run() for _ in range(MEASURED_RUNS)]
    walls = [r["wall_seconds"] for r in runs]
    peaks = [r["peak_job_commit_bytes"] / 2**20 for r in runs]
    report = json.loads(next((WORK / "runs" / "benchmark").glob("*/run_report.json")).read_text(encoding="utf-8"))
    import data_automation  # only for the version number

    results = {
        "workload": {
            "input_files": len(inputs),
            "input_rows": sum(i["rows"] for i in report["inputs"]),
            "input_bytes": sum(p.stat().st_size for p in inputs),
            "steps": [f"{s['id']} ({s['type']}): {s['rows_out']} rows" for s in report["steps"]],
            "outputs": {o["path"]: o["rows"] for o in report["outputs"]},
        },
        "method": "1 warm-up + 3 measured runs of 'python -m data_automation run'; wall time from process start "
        "to exit; memory = peak committed private memory of the process (Windows Job Object)",
        "wall_seconds": [round(w, 2) for w in walls],
        "wall_seconds_median": round(statistics.median(walls), 2),
        "peak_commit_mib": [round(p, 1) for p in peaks],
        "peak_commit_mib_max": round(max(peaks), 1),
        "step_durations_s_last_run": {s["id"]: s["duration_s"] for s in report["steps"]},
        "input_durations_s_last_run": {i["id"]: i["duration_s"] for i in report["inputs"]},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "data_automation": data_automation.__version__,
        },
    }
    (HERE / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(results, indent=2))
    return subprocess.call([sys.executable, str(HERE / "verify_outputs.py")])  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
