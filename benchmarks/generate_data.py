"""Generate the deterministic synthetic benchmark data set.

12 monthly branch files x 10,000 orders = 120,000 rows, plus a targets file. The same seed
always gives the same bytes, so measurements can be repeated on the same input.

Usage: python benchmarks/generate_data.py [--rows-per-file N] [--files N]
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
import shutil
from pathlib import Path

WORK = Path(__file__).resolve().parent / "work"
REGIONS = ["North", "South", "East", "West", "Centre", "Coast", "Mountain", "Islands"]
STATUSES = ["closed"] * 15 + ["open"] * 3 + ["cancelled"] * 2


def generate(rows_per_file: int, files: int, seed: int = 2026) -> Path:
    rng = random.Random(seed)  # noqa: S311 - reproducible synthetic data, not security
    incoming = WORK / "data" / "incoming" / "2026-09"
    if WORK.joinpath("data").exists():
        shutil.rmtree(WORK / "data")
    incoming.mkdir(parents=True)
    order = 0
    for branch in range(1, files + 1):
        lines = ["region,order_id,status,order_date,amount"]
        for _ in range(rows_per_file):
            order += 1
            day = dt.date(2026, 9, rng.randint(1, 30))
            cents = rng.randint(100, 500_000)
            amount = f"{cents // 100}.{cents % 100:02d}"
            lines.append(f"{rng.choice(REGIONS)},SO-{order:07d},{rng.choice(STATUSES)},{day.isoformat()},{amount}")
        (incoming / f"sales_branch{branch:02d}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    reference = WORK / "data" / "reference"
    reference.mkdir(parents=True)
    targets = ["region,target"] + [f"{r},{(i + 1) * 1_000_000}.00" for i, r in enumerate(REGIONS)]
    (reference / "targets.csv").write_text("\n".join(targets) + "\n", encoding="utf-8", newline="\n")
    return WORK


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows-per-file", type=int, default=10_000)
    parser.add_argument("--files", type=int, default=12)
    args = parser.parse_args()
    work = generate(args.rows_per_file, args.files)
    print(f"{args.files * args.rows_per_file} rows in {args.files} files under {work}")


if __name__ == "__main__":
    main()
