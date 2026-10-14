# Run report: sales-vs-targets

| Item | Value |
| --- | --- |
| Status | SUCCESS - every step ran and every output was verified and published |
| Exit code | 0 |
| Run id | 4b7bd482-f725-4a12-b0d4-053b69d0532c |
| Started (UTC) | 2026-10-14T03:18:57.504Z |
| Finished (UTC) | 2026-10-14T03:18:57.577Z |
| Duration (s) | 0.072 |
| Parameters | period=2026-09 |
| Error policy | stop |

## Sources

| File | Input | Unchanged during the run |
| --- | --- | --- |
| data/sample/incoming/2026-09/sales_north.csv | sales_files | yes |
| data/sample/incoming/2026-09/sales_south.csv | sales_files | yes |
| data/sample/reference/targets.xlsx | targets | yes |

## Inputs

| Input | Status | Files | Rows | Duration (s) |
| --- | --- | --- | --- | --- |
| sales_files | success | 2 | 5 | 0.004 |
| targets | success | 1 | 3 | 0.009 |

## Steps

| Step | Type | Status | Rows in | Rows out | Duration (s) | Note |
| --- | --- | --- | --- | --- | --- | --- |
| consolidate_sales | concatenate | success | sales_files: 5 | 5 | 0.005 |  |
| closed_orders | filter | success | sales: 5 | 3 | 0.001 |  |
| totals_per_region | aggregate | success | closed_sales: 3 | 2 | 0.001 |  |
| add_targets | join | success | totals: 2, targets: 3 | 2 | 0.01 |  |
| keep_report_columns | select | success | totals_with_targets: 2 | 2 | 0.001 |  |
| controls | check | success | report_columns: 2 | 2 | 0.001 |  |
| order_by_sales | sort | success | checked: 2 | 2 | 0.001 |  |

## Outputs

| Output | File | Status | Rows | Write + verify (s) | SHA-256 | Note |
| --- | --- | --- | --- | --- | --- | --- |
| powerbi_csv | output/sales_vs_targets_2026-09.csv | published | 2 | 0.004 | f6e94179c7cc1457 |  |
| powerbi_xlsx | output/sales_vs_targets_2026-09.xlsx | published | 2 | 0.024 | 106b21b09eeff2f0 |  |

## Errors

None.

## Warnings

None.

The complete report, including per-step details, is in `run_report.json`.
