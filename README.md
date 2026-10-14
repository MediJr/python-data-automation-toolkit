# Python Data Automation Toolkit

Declarative, validated and traceable automation of recurring data-processing workflows:
consolidate CSV and Excel files, filter, join and aggregate them, and publish verified
CSV/XLSX datasets ready to import into Power BI — with a run report for every run.

> Personal portfolio project (service 2 of a three-part data portfolio), built and tested on
> **Windows 11 with Python 3.14.7 only**. Other systems, other Python versions and the
> import into Power BI Desktop have **not** been tested; see [limitations](docs/limitations.md).
> It is independent of
> [python-data-cleaning-toolkit](https://github.com/MediJr/python-data-cleaning-toolkit)
> (service 1) and does not depend on it.

## The problem

Monthly reporting often means the same manual routine: collect one file per branch, paste
them together, filter, look up targets, compute totals, save a file for Power BI — and hope
nothing was pasted twice or overwritten. A one-off script automates the routine but rarely
says *what it did*, refuses bad input, or protects last month's output.

This toolkit describes the routine once, in a YAML **workflow file**, and runs it from the
command line or a scheduler. Every run is checked before it starts, either completes and
publishes verified files or publishes nothing, and leaves a report.

## Features

- **Workflow files** in YAML, validated strictly before anything runs (unknown keys, wrong
  types, undeclared datasets and unsafe paths are all reported at once).
- **Run parameters** such as `--param period=2026-09`, used in file paths and filter
  conditions; required and malformed parameters are refused before running.
- **Readers** for CSV (encoding, delimiter, decimal comma) and XLSX (sheet selection), with
  declared column types: `string`, `integer`, `decimal` (exact), `date`, `datetime`,
  `boolean`. Invalid values fail with file, row and value — they are never guessed.
- **Nine step types**: `concatenate`, `filter`, `join`, `aggregate`, `select`, `rename`,
  `cast`, `sort`, `check`. Filters are declarative data (no `eval`, `exec` or
  `DataFrame.query`); joins declare their relationship (`one_to_one`, `many_to_one`,
  `one_to_many`) and fail if the data violates it.
- **Extensible**: a new step type is a parameter model plus a function, registered with
  `register()`; the engine does not change ([docs/architecture.md](docs/architecture.md)).
- **Verified exports** for Power BI: CSV in UTF-8 without BOM with ISO dates and `.` as the
  decimal separator, or typed XLSX; each file is written to a temporary name, read back and
  compared value by value before it is published, with a `.metadata.json` file beside it.
- **Safe repeated runs**: existing outputs are never replaced without `--overwrite`;
  publication happens only when every output is verified; sources are fingerprinted
  (SHA-256) and must not change during the run; a lock prevents concurrent runs.
- **Reports** for every run: `run_report.json`, `run_report.md`, `run.log`, and an optional
  business summary in Markdown.
- **Scheduler-friendly**: documented exit codes and a tested PowerShell wrapper for the
  Windows Task Scheduler ([docs/scheduling.md](docs/scheduling.md)).

## Use cases

- Monthly consolidation of branch sales files into KPIs per region
  ([config/examples/monthly_sales.yaml](config/examples/monthly_sales.yaml)).
- Recurring preparation of a dataset for Power BI, joined with reference data from Excel
  ([config/examples/sales_vs_targets.yaml](config/examples/sales_vs_targets.yaml)).
- A periodic report: indicator files plus a Markdown summary, with an audit trail.
- Explicit failure: a missing file, an invalid value or a broken control stops the run with
  a clear message attached to its step, and nothing is published.

## What it is not

Not an orchestrator (no scheduler, no dependency graph, no parallelism), not a database, not
a data-cleaning tool (that is service 1), not connected to Power BI Service. There is no
automatic resume: a failed run is simply run again. Data is processed in memory. Details in
[docs/limitations.md](docs/limitations.md).

## Technologies

Python 3.14 · pandas 3 · openpyxl · Pydantic 2 · PyYAML · defusedxml · argparse ·
pytest · Ruff. Exact tested versions are pinned in [constraints.txt](constraints.txt).

## Architecture

```text
workflow.yaml ──► yaml_loader + config (strict YAML, Pydantic models)
              ──► validation (parameters, references, paths, step parameters via registry)
              ──► engine: lock ► fingerprint sources ► read inputs ► run steps in order
                          ► write outputs to temporary files ► read back and verify
                          ► check sources unchanged ► publish (os.replace) ► reports
```

Each step receives named datasets and produces one new named dataset. More in
[docs/architecture.md](docs/architecture.md) and the
[architecture decisions](docs/decisions/README.md) (in French).

## Requirements

- Windows 11 (the only tested system) and Python 3.14 (the only tested version;
  `requires-python >= 3.14`).
- Runtime dependencies: pandas, openpyxl, pydantic, PyYAML, defusedxml (numpy comes with
  pandas).

## Installation

For development (editable, with the exact tested versions), in PowerShell from the project
folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]" -c constraints.txt
```

As a user (regular install from the folder or from a clone):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install . -c constraints.txt
```

Both give the `data-automate` command (also available as `python -m data_automation`).

## Usage

Check a workflow without running it (nothing is read or written except listing the
matching files):

```bash
data-automate validate config/examples/monthly_sales.yaml --param period=2026-09
```

```text
Workflow: monthly-sales-report (config/examples/monthly_sales.yaml)
Parameters: period=2026-09
Input sales_files: 2 file(s) match data/sample/incoming/2026-09/sales_*.csv
Step consolidate_sales: type concatenate, sales_files -> sales
Step only_closed_orders: type filter, sales -> closed_sales
Step calculate_kpis: type aggregate, closed_sales -> kpis
Output export_powerbi: kpis -> output/monthly_sales_2026-09.csv
Result: VALID (nothing was run)
```

(The real output also prints the absolute working root on a `Root:` line.)

Run it:

```bash
data-automate run config/examples/monthly_sales.yaml --param period=2026-09
```

Run the CSV + Excel example (join with targets, CSV and XLSX outputs, summary):

```bash
data-automate run config/examples/sales_vs_targets.yaml --param period=2026-09
```

List the step types:

```bash
data-automate steps
```

Options: `--overwrite` replaces outputs of a period already processed (only after the new
files are verified); `--json` prints the run report as JSON; `-v` / `-vv` show progress on
standard error. Running the same command twice without `--overwrite` is refused with exit
code 3 and touches nothing.

| Exit code | Meaning |
| --- | --- |
| 0 | Success: every step ran, every output was verified and published |
| 1 | The run failed: nothing was published |
| 2 | Invalid command-line usage |
| 3 | Refused before running: invalid workflow or parameters, existing output without `--overwrite`, another run in progress |
| 4 | Partial run (`on_error: continue`): the outputs that could be produced were verified and published, the others were not |
| 130 | Interrupted (Ctrl+C): nothing was published |

## Example: input and output

Input (two branch files for September 2026, [data/sample/incoming/2026-09](data/sample/incoming/2026-09/sales_north.csv)):

```text
region,order_id,status,amount
North,SO-0001,closed,120.50
North,SO-0002,open,80.00
North,SO-0003,closed,42.00
```

Output `output/monthly_sales_2026-09.csv` (UTF-8 without BOM, LF line endings):

```text
region,total_sales,order_count
North,162.50,2
South,200.00,1
```

The second example also reads `data/sample/reference/targets.xlsx` and writes
`output/sales_vs_targets_2026-09.csv` and `.xlsx`. All the files produced by the examples —
outputs, metadata, reports and logs — are committed, unedited, in
[reports/examples/](reports/examples/sales-vs-targets/run/run_report.md); a test checks
that they still match a fresh run.

## Demo: monthly sales by product category

A reproducible end-to-end scenario on synthetic data, documented step by step in
[docs/demo-monthly-sales.md](docs/demo-monthly-sales.md):

```text
lines_store_a.csv ┐
lines_store_b.csv ┴─ concatenate ─ check ─ filter (completed) ─ join on sku ◄─ products.csv
   ─ rename + select ──────────────────────────────► order_lines_enriched_2026-09.csv
   ─ aggregate per category ─ sort by revenue ─────► sales_by_category_2026-09.csv / .xlsx
```

```bash
data-automate run config/examples/monthly_sales_by_category.yaml --param period=2026-09
```

Observed results (real run, committed in
[reports/examples/monthly-sales-by-category/](reports/examples/monthly-sales-by-category/run/run_report.md)):

| Measure | Value |
| --- | --- |
| Rows read | 11 order lines (2 files) + 6 catalog rows |
| After validation / filter | 11 / 9 (2 cancelled lines excluded) |
| Lines matched with a product | 9 of 9 |
| KPIs | Furniture 447.00 · Lighting 228.50 · Stationery 141.00 (total 816.50) |
| Files | 2 CSV + 1 XLSX, each read back and verified, each with metadata (UUID v4 run id, SHA-256) |
| Status / duration | `success`, exit code 0, 0.09 s inside the run |

The KPIs are also recomputed by a test that uses only the standard library (`csv`,
`Decimal`) and checks the CSV, the XLSX cells and every recorded SHA-256.

## Workflow configuration

A workflow file declares *what* to do; the engine decides nothing on its own. Commented
excerpt of [config/examples/monthly_sales_by_category.yaml](config/examples/monthly_sales_by_category.yaml):

```yaml
workflow:
  id: monthly-sales-by-category    # names the run folder: runs/monthly-sales-by-category/<run id>/
  schema_version: 1
  root: ../..                      # working root; no path may leave it
parameters:
  period: {type: month}            # required: --param period=2026-09
inputs:
  - id: order_lines                # every matching file becomes one part of the dataset
    type: csv
    path: "data/sample/order_lines/{period}/lines_*.csv"
    required_columns: [order_id, order_date, store, sku, quantity, line_amount, status]
    types: {order_date: date, quantity: integer, line_amount: decimal}   # strict, exact decimals
  - {id: products, type: csv, path: data/sample/reference/products.csv}
steps:                             # run in this order; each one creates a new named dataset
  - {id: consolidate, type: concatenate, input: order_lines, output: all_lines}
  - id: validate_lines             # controls: the run fails if a rule is broken
    type: check
    input: all_lines
    output: valid_lines
    not_null: [order_id, sku, quantity, line_amount, status]
    unique: [order_id, sku]
  - id: completed_only             # declarative condition, never evaluated as code
    type: filter
    input: valid_lines
    output: completed_lines
    where: [{column: status, op: eq, value: completed}]
  - id: add_products               # relationship checked before joining: rows cannot multiply
    type: join
    input: [completed_lines, products]
    output: lines_with_products
    keys: [sku]
    relationship: many_to_one
    require_match: true            # every sold SKU must be in the catalog
  - id: kpis_by_category
    type: aggregate
    input: lines_with_products
    output: kpis
    group_by: [category]
    metrics:
      revenue: {function: sum, column: line_amount}
      average_line: {function: mean, column: line_amount, round: 2}
outputs:                           # written to a temporary file, read back, verified, then published
  - {id: kpis_csv, input: kpis, type: csv, path: "output/sales_by_category_{period}.csv"}
  - {id: kpis_xlsx, input: kpis, type: xlsx, path: "output/sales_by_category_{period}.xlsx"}
```

The complete file also renames and selects columns, sorts the result and adds a
`summary`.

Full reference: [docs/configuration.md](docs/configuration.md) (all sections and path
rules) and [docs/steps.md](docs/steps.md) (every step type and its parameters).

## Outputs and reports

Each run writes, under `runs/<workflow id>/<run id>/` (the run id is a UUID v4):

- `run_report.json` — status, exit code, parameters, sources with SHA-256, inputs, steps
  (rows in/out, duration, details), outputs, errors, warnings, environment;
- `run_report.md` — the same, readable; `run.log` — the log with UTC timestamps;
- `summary.md` — optional business summary of chosen datasets.

Each published file has a `<file>.metadata.json` beside it: workflow and run ids,
parameters, column schema (logical types and nullability), decimal places, file format,
sources with SHA-256 and the checks done. See [docs/running.md](docs/running.md) and
[docs/powerbi.md](docs/powerbi.md).

## Safety and reliability

- YAML is loaded with a safe loader; Python tags, duplicate keys, anchors/aliases,
  non-text keys and files over 1 MB are refused.
- Nothing from the configuration is evaluated as code.
- All paths are relative to a declared working root; absolute paths, `..` escapes and links
  leading outside it are refused; an output can never be a source.
- Untrusted XLSX files are parsed with defusedxml protections; formulas without a saved
  value are refused rather than read as empty.
- Outputs are atomic: temporary file → read back and compare → `os.replace`; a failure
  leaves previous outputs untouched and removes temporary files.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests scripts benchmarks
.venv\Scripts\python.exe -m ruff format --check src tests scripts benchmarks
```

Unit, integration and CLI tests cover each step type against hand-computed results, every
failure scenario (missing or changed sources, failed verification, disk errors, locks,
interruption), the export contract byte by byte, path and YAML attacks, and the Task
Scheduler wrapper. One test (symbolic link escaping the root) is skipped on Windows without
the privilege to create links. See [docs/testing.md](docs/testing.md) for the mapping from
acceptance criteria to tests.

## Performance

On a synthetic 120,000-row workload (12 CSV files, 5 MB), a complete run — consolidate,
filter, aggregate, join, sort, three verified exports — took a median of about **7 s**
with a peak memory of about **570 MiB**, on one Windows 11 computer. Method, details and
caveats: [docs/performance.md](docs/performance.md).

## Project structure

```text
src/data_automation/   package: cli, config, validation, engine, registry, readers,
                       writers, reporting, types, paths, parameters, steps/
config/examples/       example workflows
data/sample/           small synthetic input files
reports/examples/      real outputs and reports of the examples
scripts/               example regeneration, sample data, Task Scheduler wrapper
benchmarks/            reproducible benchmark and independent output check
tests/                 unit/, integration/, cli/ and project-level tests
docs/                  documentation (English) and specification + decisions (French)
```

## Known limitations

- Tested only on Windows 11 with Python 3.14.7; Linux, macOS and other Python versions are
  not verified.
- Import into Power BI Desktop has **not** been tested; the import settings are documented
  as untested recommendations.
- Data is processed in memory (about 110 times the input size in the benchmark).
- No automatic resume, no internal scheduler, no parallel steps, CSV and XLSX only.
- Excel numbers lose trailing zeros (`250.00` shows as `250`).
- One test is skipped on Windows without the symbolic-link privilege (the same check is
  covered by a directory-junction test).

Full list: [docs/limitations.md](docs/limitations.md).

## Documentation

- [Demo: monthly sales by category](docs/demo-monthly-sales.md)
- [Configuration reference](docs/configuration.md) · [Step reference](docs/steps.md)
- [Running workflows, reports and troubleshooting](docs/running.md)
- [Power BI import](docs/powerbi.md) · [Scheduling](docs/scheduling.md)
- [Architecture](docs/architecture.md) · [Testing](docs/testing.md) ·
  [Performance](docs/performance.md) · [Limitations](docs/limitations.md)
- [Specification](docs/specification.md) and [decisions](docs/decisions/README.md) (French)

## Contributing

Issues and pull requests are welcome. Set up the development environment, then run the
same checks as before a release:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]" -c constraints.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests scripts benchmarks
.venv\Scripts\python.exe -m ruff format --check src tests scripts benchmarks
```

- A new transformation is a new step type registered with `register()`
  ([architecture](docs/architecture.md#extending-the-step-registry)); the engine should not
  need changes.
- Expected values in tests are computed by hand, never copied from the tool's output.
- If outputs change, run `scripts/regenerate_examples.py --overwrite` and review the diff;
  `tests/test_examples.py` fails when the committed examples are stale.
- Use synthetic data only.

## License

[MIT](LICENSE) — Copyright (c) 2026 LUMU BAMANA MANASSE.
