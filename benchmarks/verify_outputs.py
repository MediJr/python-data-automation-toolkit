"""Independent check of the benchmark outputs.

Recomputes the expected results from the generated source files with the standard library
only (``csv`` and ``decimal``); it deliberately does **not** import ``data_automation``, so a
bug in the package cannot hide itself. Exits with 1 on the first difference.

Usage: python benchmarks/verify_outputs.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

WORK = Path(__file__).resolve().parent / "work"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def expected() -> tuple[list[list[str]], list[list[str]]]:
    closed = []
    for path in sorted((WORK / "data/incoming/2026-09").glob("sales_*.csv")):
        closed += [r for r in _rows(path) if r["status"] == "closed" and Decimal(r["amount"]) > 0]
    totals: dict[str, list[Decimal]] = defaultdict(list)
    for row in closed:
        totals[row["region"]].append(Decimal(row["amount"]))
    targets = {r["region"]: r["target"] for r in _rows(WORK / "data/reference/targets.csv")}
    kpis = [["region", "total_sales", "order_count", "average_order", "target"]]
    for region in sorted(totals):
        amounts = totals[region]
        mean = (sum(amounts) / len(amounts)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        kpis.append([region, str(sum(amounts)), str(len(amounts)), str(mean), targets[region]])
    detail = [["region", "order_id", "status", "order_date", "amount"]]
    detail += [[r[c] for c in detail[0]] for r in sorted(closed, key=lambda r: r["order_id"])]
    return kpis, detail


def main() -> int:
    kpis, detail = expected()
    problems = []
    for name, rows in (("kpis.csv", kpis), ("closed_orders.csv", detail)):
        path = WORK / "output" / name
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw:
            problems.append(f"{name}: BOM or CRLF found")
        with path.open(encoding="utf-8", newline="") as handle:
            actual = list(csv.reader(handle))
        if actual != rows:
            first = next(
                (i for i, (a, b) in enumerate(zip(actual, rows, strict=False)) if a != b), min(len(actual), len(rows))
            )
            problems.append(f"{name}: differs from the independent computation at line {first + 1}")
        else:
            print(f"{name}: {len(rows) - 1} data rows identical to the independent computation")
    for problem in problems:
        print(f"ERROR {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
