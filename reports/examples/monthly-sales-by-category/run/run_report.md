# Run report: monthly-sales-by-category

| Item | Value |
| --- | --- |
| Status | SUCCESS - every step ran and every output was verified and published |
| Exit code | 0 |
| Run id | a6979456-fd80-44b6-b836-5f4ec217f92c |
| Started (UTC) | 2026-10-14T16:11:12.078Z |
| Finished (UTC) | 2026-10-14T16:11:12.168Z |
| Duration (s) | 0.09 |
| Parameters | period=2026-09 |
| Error policy | stop |

## Sources

| File | Input | Unchanged during the run |
| --- | --- | --- |
| data/sample/order_lines/2026-09/lines_store_a.csv | order_lines | yes |
| data/sample/order_lines/2026-09/lines_store_b.csv | order_lines | yes |
| data/sample/reference/products.csv | products | yes |

## Inputs

| Input | Status | Files | Rows | Duration (s) |
| --- | --- | --- | --- | --- |
| order_lines | success | 2 | 11 | 0.006 |
| products | success | 1 | 6 | 0.001 |

## Steps

| Step | Type | Status | Rows in | Rows out | Duration (s) | Note |
| --- | --- | --- | --- | --- | --- | --- |
| consolidate | concatenate | success | order_lines: 11 | 11 | 0.006 |  |
| validate_lines | check | success | all_lines: 11 | 11 | 0.001 |  |
| completed_only | filter | success | valid_lines: 11 | 9 | 0.001 |  |
| add_products | join | success | completed_lines: 9, products: 6 | 9 | 0.021 |  |
| name_columns | rename | success | lines_with_products: 9 | 9 | 0.001 |  |
| detail_columns | select | success | renamed_lines: 9 | 9 | 0.001 |  |
| kpis_by_category | aggregate | success | enriched_lines: 9 | 3 | 0.002 |  |
| order_by_revenue | sort | success | kpis: 3 | 3 | 0.0 |  |

## Outputs

| Output | File | Status | Rows | Write + verify (s) | SHA-256 | Note |
| --- | --- | --- | --- | --- | --- | --- |
| lines_csv | output/order_lines_enriched_2026-09.csv | published | 9 | 0.005 | 6c7a9f71a2df4e3a |  |
| kpis_csv | output/sales_by_category_2026-09.csv | published | 3 | 0.005 | b8b683a63d0eaa66 |  |
| kpis_xlsx | output/sales_by_category_2026-09.xlsx | published | 3 | 0.024 | 99032b100b137147 |  |

## Errors

None.

## Warnings

None.

The complete report, including per-step details, is in `run_report.json`.
