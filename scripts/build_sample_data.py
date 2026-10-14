"""Build the synthetic Excel sample ``data/sample/reference/targets.xlsx``.

An .xlsx file mixes typed cells and cannot be written by hand, so it is generated here.
All values are fictional. The cell content is reproducible; the file bytes are not
(openpyxl stores the save time inside the file).

Usage (from the project root):
    python scripts/build_sample_data.py            # refuses to replace an existing file
    python scripts/build_sample_data.py --overwrite
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

TARGET = Path(__file__).resolve().parents[1] / "data" / "sample" / "reference" / "targets.xlsx"
HEADER = ["region", "target", "manager"]
ROWS = [
    ["North", Decimal("150.00"), "A. Martin"],
    ["South", Decimal("250.00"), "B. Diallo"],
    ["East", Decimal("100.00"), "C. Novak"],
]


def build(path: Path) -> None:
    """Write the workbook to ``path``: a notes sheet, then the 'Targets' sheet."""
    workbook = Workbook()
    notes = workbook.active
    notes.title = "Read me"
    notes.append(["Synthetic monthly sales targets per region (fictional names). Data on sheet 'Targets'."])
    sheet = workbook.create_sheet("Targets")
    sheet.append(HEADER)
    for row in ROWS:
        sheet.append(row)
    workbook.properties.creator = "python-data-automation-toolkit sample generator"
    workbook.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overwrite", action="store_true", help="replace an existing file")
    args = parser.parse_args()
    if TARGET.exists() and not args.overwrite:
        print(f"Error: {TARGET.name} already exists; use --overwrite to rebuild it.", file=sys.stderr)
        return 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    build(TARGET)
    print(f"Wrote {TARGET.relative_to(TARGET.parents[3]).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
