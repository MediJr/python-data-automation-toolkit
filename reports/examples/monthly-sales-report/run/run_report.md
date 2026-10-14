# Run report: monthly-sales-report

| Item | Value |
| --- | --- |
| Status | SUCCESS - every step ran and every output was verified and published |
| Exit code | 0 |
| Run id | 047ee7f7-a7a4-4025-85a3-c98300c06773 |
| Started (UTC) | 2026-10-14T03:18:54.304Z |
| Finished (UTC) | 2026-10-14T03:18:54.328Z |
| Duration (s) | 0.024 |
| Parameters | period=2026-09 |
| Error policy | stop |

## Sources

| File | Input | Unchanged during the run |
| --- | --- | --- |
| data/sample/incoming/2026-09/sales_north.csv | sales_files | yes |
| data/sample/incoming/2026-09/sales_south.csv | sales_files | yes |

## Inputs

| Input | Status | Files | Rows | Duration (s) |
| --- | --- | --- | --- | --- |
| sales_files | success | 2 | 5 | 0.004 |

## Steps

| Step | Type | Status | Rows in | Rows out | Duration (s) | Note |
| --- | --- | --- | --- | --- | --- | --- |
| consolidate_sales | concatenate | success | sales_files: 5 | 5 | 0.005 |  |
| only_closed_orders | filter | success | sales: 5 | 3 | 0.001 |  |
| calculate_kpis | aggregate | success | closed_sales: 3 | 2 | 0.001 |  |

## Outputs

| Output | File | Status | Rows | Write + verify (s) | SHA-256 | Note |
| --- | --- | --- | --- | --- | --- | --- |
| export_powerbi | output/monthly_sales_2026-09.csv | published | 2 | 0.004 | 946f8c278a42e6c9 |  |

## Errors

None.

## Warnings

None.

The complete report, including per-step details, is in `run_report.json`.
