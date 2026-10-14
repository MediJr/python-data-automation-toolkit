"""The committed examples are real tool output and stay in sync with the code."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from data_automation.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "reports" / "examples"
VOLATILE = {"run_id", "started_at", "finished_at", "duration_s", "generated_at", "environment", "run_folder", "sha256"}


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stable(value, path=""):
    """Drop values that legitimately change between runs (ids, times, xlsx bytes)."""
    if isinstance(value, dict):
        return {k: _stable(v, f"{path}.{k}") for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_stable(v, path) for v in value]
    return value


_VOLATILE_TEXT = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}"), "<run id>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"), "<time>"),
    (re.compile(r"(?<=\| )[0-9a-f]{16}(?= \|)"), "<sha256>"),  # xlsx bytes include a timestamp
]


_SECONDS = re.compile(r"(?<=\| )\d+\.\d+(?= \|)")  # durations; run_report.md has no data values


def _masked(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for pattern, replacement in _VOLATILE_TEXT:
        text = pattern.sub(replacement, text)
    return _SECONDS.sub("<seconds>", text) if path.name == "run_report.md" else text


def _cells(path: Path):
    workbook = load_workbook(path, read_only=True)
    try:
        return {name: [list(r) for r in workbook[name].iter_rows(values_only=True)] for name in workbook.sheetnames}
    finally:
        workbook.close()


@pytest.mark.parametrize("workflow_id, workflow", _load_script("regenerate_examples").RUNS)
def test_committed_examples_match_a_fresh_run(tmp_path, monkeypatch, workflow_id, workflow):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    shutil.copytree(ROOT / "data", tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    assert main(["run", workflow, "--param", "period=2026-09"]) == 0
    committed = EXAMPLES / workflow_id
    fresh_run = next((tmp_path / "runs" / workflow_id).iterdir())
    fresh = {f"output/{p.name}": p for p in (tmp_path / "output").iterdir()} | {
        f"run/{p.name}": p for p in fresh_run.iterdir()
    }
    assert sorted(fresh) == sorted(p.relative_to(committed).as_posix() for p in committed.rglob("*") if p.is_file())
    for name, path in fresh.items():
        other = committed / name
        if name.endswith(".csv"):
            assert path.read_bytes() == other.read_bytes(), name
        elif name.endswith(".xlsx"):
            assert _cells(path) == _cells(other), name
        elif name.endswith(".json"):
            assert _stable(json.loads(path.read_text(encoding="utf-8"))) == _stable(
                json.loads(other.read_text(encoding="utf-8"))
            ), name
        else:  # Markdown reports and run.log: identical once run ids, times and durations are masked
            assert _masked(path) == _masked(other), name


def test_category_demo_results_are_correct_independently_of_the_engine():
    """docs/demo-monthly-sales.md: recompute the KPIs with csv + Decimal only and compare with the committed outputs."""
    import csv
    import hashlib
    import uuid
    from collections import defaultdict
    from decimal import ROUND_HALF_UP, Decimal

    def rows(path):
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    lines = [r for p in sorted((ROOT / "data/sample/order_lines/2026-09").glob("lines_*.csv")) for r in rows(p)]
    catalog = {r["sku"]: r for r in rows(ROOT / "data/sample/reference/products.csv")}
    completed = [r for r in lines if r["status"] == "completed" and int(r["quantity"]) >= 1]
    assert (len(lines), len(completed)) == (11, 9) and all(r["sku"] in catalog for r in completed)
    groups = defaultdict(list)
    for r in completed:
        groups[catalog[r["sku"]]["category"]].append(r)
    expected = []
    for category, items in groups.items():
        revenue = sum((Decimal(r["line_amount"]) for r in items), Decimal(0))
        mean = (revenue / len(items)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected.append(
            [category, str(revenue), str(sum(int(r["quantity"]) for r in items)), str(len(items)), str(mean)]
        )
    expected.sort(key=lambda row: Decimal(row[1]), reverse=True)
    # the values written in docs/demo-monthly-sales.md, computed by hand
    assert expected == [
        ["Furniture", "447.00", "3", "2", "223.50"],
        ["Lighting", "228.50", "6", "3", "76.17"],
        ["Stationery", "141.00", "14", "4", "35.25"],
    ]
    out = EXAMPLES / "monthly-sales-by-category" / "output"
    with (out / "sales_by_category_2026-09.csv").open(encoding="utf-8", newline="") as handle:
        assert list(csv.reader(handle)) == [["category", "revenue", "units", "order_lines", "average_line"], *expected]
    sheet = _cells(out / "sales_by_category_2026-09.xlsx")["Sales by category"]
    assert [[str(v) for v in row[:1]] + [Decimal(str(v)) for v in row[1:]] for row in sheet[1:]] == [
        [row[0], *(Decimal(v) for v in row[1:])] for row in expected
    ]
    with (out / "order_lines_enriched_2026-09.csv").open(encoding="utf-8", newline="") as handle:
        detail = list(csv.DictReader(handle))
    assert [(r["order_id"], r["category"]) for r in detail] == [
        (r["order_id"], catalog[r["sku"]]["category"]) for r in completed
    ]
    report = json.loads((EXAMPLES / "monthly-sales-by-category/run/run_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "success" and uuid.UUID(report["run_id"]).version == 4
    for name in ("order_lines_enriched_2026-09.csv", "sales_by_category_2026-09.csv", "sales_by_category_2026-09.xlsx"):
        metadata = json.loads((out / f"{name}.metadata.json").read_text(encoding="utf-8"))
        assert metadata["run_id"] == report["run_id"]
        assert metadata["file"]["sha256"] == hashlib.sha256((out / name).read_bytes()).hexdigest()
        for source in metadata["sources"]:
            assert source["sha256"] == hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest()


def test_sample_workbook_generator_reproduces_the_committed_file(tmp_path):
    _load_script("build_sample_data").build(tmp_path / "targets.xlsx")
    assert _cells(tmp_path / "targets.xlsx") == _cells(ROOT / "data/sample/reference/targets.xlsx")


def test_sample_data_is_synthetic_and_small():
    files = [p for p in (ROOT / "data").rglob("*") if p.is_file()]
    assert sum(p.stat().st_size for p in files) < 50_000
    text = "\n".join(p.read_text(encoding="utf-8") for p in files if p.suffix == ".csv")
    assert "@" not in text  # no e-mail addresses or other personal identifiers in the samples
