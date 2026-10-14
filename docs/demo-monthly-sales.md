# Demo: monthly sales by product category

A complete, reproducible workflow on **synthetic data**: the order lines of two stores for
September 2026 are consolidated, checked, filtered, joined with a product catalog and
aggregated per category, then exported to CSV and Excel with metadata and run reports.

Every value on this page comes from a real run. The outputs are committed, unedited, in
[reports/examples/monthly-sales-by-category/](../reports/examples/monthly-sales-by-category/run/run_report.md),
and two tests guard them:

- `tests/test_examples.py::test_committed_examples_match_a_fresh_run` reruns the workflow
  and compares every file with the committed one (ids, times and durations excepted);
- `tests/test_examples.py::test_category_demo_results_are_correct_independently_of_the_engine`
  recomputes the KPIs from the raw files with the standard library only (`csv`,
  `Decimal`), compares them with the hand-computed values below, and checks the XLSX
  cells, the UUID v4 and every SHA-256 recorded in the metadata.

## Files

| Role | File |
| --- | --- |
| Workflow | [config/examples/monthly_sales_by_category.yaml](../config/examples/monthly_sales_by_category.yaml) (commented) |
| Order lines, one file per store | [data/sample/order_lines/2026-09/](../data/sample/order_lines/2026-09/lines_store_a.csv) (`lines_store_a.csv`: 6 lines, `lines_store_b.csv`: 5 lines) |
| Product catalog | [data/sample/reference/products.csv](../data/sample/reference/products.csv) (6 products) |

Input excerpt (`lines_store_a.csv`):

```text
order_id,order_date,store,sku,quantity,line_amount,status
A-1001,2026-09-02,Store A,P-100,2,59.80,completed
A-1002,2026-09-05,Store A,P-200,1,149.00,completed
A-1004,2026-09-15,Store A,P-100,1,29.90,cancelled
```

Catalog excerpt (`products.csv`):

```text
sku,product_name,category
P-100,Desk lamp,Lighting
P-200,Office chair,Furniture
P-300,Notebook pack,Stationery
```

## The workflow

```text
order_lines (2 files, 11 rows) ── consolidate (concatenate) ── 11 rows
  ── validate_lines (check: no missing key fields, unique order_id + sku, known status) ── 11 rows
  ── completed_only (filter: status = completed, quantity >= 1) ── 9 rows
  ── add_products (join on sku, many_to_one, every SKU must exist) ◄── products (6 rows)
  ── name_columns (rename product_name → product) ── detail_columns (select 8 columns) ── 9 rows ──► order_lines_enriched_2026-09.csv
  ── kpis_by_category (aggregate: revenue, units, order lines, average line) ── 3 rows
  ── order_by_revenue (sort, revenue descending) ──► sales_by_category_2026-09.csv and .xlsx
```

If a check fails (for example a duplicated order line or an unknown status), if a sold SKU
is missing from the catalog, or if the catalog lists a SKU twice, the run stops with exit
code 1 and nothing is published.

## Commands

From the project folder, after [installation](../README.md#installation):

```bash
data-automate validate config/examples/monthly_sales_by_category.yaml --param period=2026-09
```

```bash
data-automate run config/examples/monthly_sales_by_category.yaml --param period=2026-09
```

Output of the run (the run id changes every time):

```text
Run a6979456-fd80-44b6-b836-5f4ec217f92c of workflow monthly-sales-by-category
Input order_lines: success, 11 row(s) from 2 file(s)
Input products: success, 6 row(s) from 1 file(s)
Step consolidate (concatenate): success, 11 row(s)
Step validate_lines (check): success, 11 row(s)
Step completed_only (filter): success, 9 row(s)
Step add_products (join): success, 9 row(s)
Step name_columns (rename): success, 9 row(s)
Step detail_columns (select): success, 9 row(s)
Step kpis_by_category (aggregate): success, 3 row(s)
Step order_by_revenue (sort): success, 3 row(s)
Output lines_csv: published, 9 row(s) -> output/order_lines_enriched_2026-09.csv
Output kpis_csv: published, 3 row(s) -> output/sales_by_category_2026-09.csv
Output kpis_xlsx: published, 3 row(s) -> output/sales_by_category_2026-09.xlsx
Report: runs/monthly-sales-by-category/a6979456-fd80-44b6-b836-5f4ec217f92c/ (run_report.json, run_report.md, summary.md)
Result: SUCCESS (exit code 0)
```

Running the same command again is refused with exit code 3 (the outputs exist); add
`--overwrite` to replace them after the new files are verified.

## Result

`output/sales_by_category_2026-09.csv` (UTF-8 without BOM, LF):

```text
category,revenue,units,order_lines,average_line
Furniture,447.00,3,2,223.50
Lighting,228.50,6,3,76.17
Stationery,141.00,14,4,35.25
```

Hand check: Furniture = 149.00 + 298.00 (lines A-1002, A-1006); Lighting = 59.80 + 89.70
+ 79.00 (A-1001, B-2002, B-2005), average 228.50 / 3 = 76.1667 → 76.17; Stationery =
23.85 + 51.60 + 39.75 + 25.80. The two cancelled lines (A-1004, B-2004) are excluded.

## Measured results

From the committed [run report](../reports/examples/monthly-sales-by-category/run/run_report.md):

| Measure | Value |
| --- | --- |
| Rows read | 11 order lines from 2 files; 6 catalog rows |
| Rows after validation | 11 (all rules passed) |
| Rows after the filter | 9 (2 cancelled lines removed) |
| Lines matched with a product | 9 of 9 (`require_match`), 5 distinct SKUs; 1 catalog product (P-600) unsold |
| Indicators | 3 categories; total revenue 816.50 |
| Files published | `order_lines_enriched_2026-09.csv` (9 rows), `sales_by_category_2026-09.csv` (3 rows), `sales_by_category_2026-09.xlsx` (3 rows), each with a `.metadata.json` |
| Verification | each file read back and compared value by value before publication; 3 source files unchanged (SHA-256 before = after) |
| Run id | `a6979456-fd80-44b6-b836-5f4ec217f92c` (UUID v4, also in every metadata file) |
| SHA-256 of `sales_by_category_2026-09.csv` | `b8b683a63d0eaa6621e19a1b5eb7fdf7cfded6c121ce284d176465bb63385da2` |
| Status | `success`, exit code 0 |
| Duration | 0.09 s inside the run (Windows 11, Python 3.14.7; excludes Python start-up) |

The XLSX file holds the same values in typed cells (numbers, text); Excel shows `447`
instead of `447.00` because Excel numbers do not keep trailing zeros
([limitations](limitations.md#data-and-formats)).

## Produced files

```text
output/
  order_lines_enriched_2026-09.csv            + .metadata.json
  sales_by_category_2026-09.csv               + .metadata.json
  sales_by_category_2026-09.xlsx              + .metadata.json
runs/monthly-sales-by-category/<run id>/
  run_report.json   run_report.md   run.log   summary.md
```

The [summary](../reports/examples/monthly-sales-by-category/run/summary.md) is the business
view (the KPI table); the run report is the technical view (status, every input, step and
output with rows, durations and checks). The fields of each file are described in
[running.md](running.md#the-run-folder).

## Regenerate and verify

```powershell
.venv\Scripts\python.exe scripts\regenerate_examples.py --overwrite
.venv\Scripts\python.exe -m pytest -q tests\test_examples.py
```

The script runs every example workflow in a temporary copy of `config/` and `data/` and
copies the results to `reports/examples/`; the tests fail if the committed files no longer
match a fresh run or the independent computation.
