"""Shared fixtures. Every test works in its own temporary folder."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

VALID_WORKFLOW = """\
workflow:
  id: monthly-sales
  schema_version: 1
  root: .
parameters:
  period: {type: month}
inputs:
  - id: sales_files
    type: csv
    path: "incoming/{period}/sales_*.csv"
    required_columns: [region, amount]
    types:
      amount: decimal
steps:
  - id: consolidate
    type: concatenate
    input: sales_files
    output: sales
  - id: kpis
    type: aggregate
    input: sales
    output: totals
    group_by: [region]
    metrics:
      total: {function: sum, column: amount}
outputs:
  - id: export
    input: totals
    type: csv
    path: "output/sales_{period}.csv"
"""


@pytest.fixture
def workspace(tmp_path: Path):
    """Create a workflow file (and optional data files) in a temporary root; return a factory."""

    def _make(text: str = VALID_WORKFLOW, files: dict[str, str] | None = None, name: str = "workflow.yaml") -> Path:
        files = {"incoming/2026-09/sales_north.csv": "region,amount\nNorth,1\n"} if files is None else files
        for relative, content in files.items():
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        workflow = tmp_path / name
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(textwrap.dedent(text), encoding="utf-8")
        return workflow

    return _make
