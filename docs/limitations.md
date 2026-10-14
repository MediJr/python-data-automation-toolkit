# Limitations

What this version does not do, and what has not been verified. Nothing below is hidden
behind a "should work".

## Verified environment

| Verified | Not verified |
| --- | --- |
| Windows 11 (build 26300), Python 3.14.7, the versions in [constraints.txt](../constraints.txt) | Linux, macOS, other Windows versions, Python 3.13 or older (excluded by `requires-python`), Python 3.15, other dependency versions |
| Editable install with pinned versions; regular (non-editable) install; running from another directory | Installation from PyPI (the package is not published there) |
| Windows Task Scheduler wrapper script (run by the tests) | Creating a real scheduled task (`schtasks` command documented, not executed); cron and other schedulers |
| Export format (bytes, typed cells, read-back) | **Import into Power BI Desktop** (no import was performed; the [settings and M query](powerbi.md) are untested recommendations); Power BI Service |

The source code avoids Windows-only behaviour except the Task Scheduler script and the
benchmark's memory measurement, but that is not a substitute for testing on other systems.

## Functional scope (MVP)

- **No automatic resume or retry.** A failed run publishes nothing (with `on_error: stop`);
  fix the cause and run again. Steps are never re-run individually.
- **No scheduler, no daemon, no parallelism, no dependency graph**: steps run one after the
  other in the file's order.
- **Only CSV and XLSX** sources and outputs. No databases, APIs, Parquet, JSON or `.xls`.
- **No append mode**: every run writes complete outputs. History is kept by putting a
  parameter in the output path (e.g. `{period}`), not by appending.
- **Multi-output publication is not all-or-nothing**: outputs are replaced one by one
  after all are verified. If a replacement fails (a file open in Excel), outputs replaced
  before it stay published; the report says which (ADR-0003).
- **Nine step types**; no expressions or computed columns (deliberately: nothing from the
  configuration is evaluated). New logic needs a new step type in Python.
- **Run parameters** are `string`, `integer`, `date` or `month`; filters use them by name
  (`param:`) with single-value operators only.
- **No notifications** (e-mail, Teams…); the scheduler reads the exit code.
- **Reports are never deleted** by the tool; `runs/` grows with every run.

## Data and formats

- **In-memory processing**: memory use was about 110 times the input size in the
  [benchmark](performance.md) (5 MB → 570 MiB). Large inputs (millions of rows) were not
  tested.
- **XLSX numbers lose trailing zeros**: `250.00` in a decimal column is written as the Excel
  number 250 and reads back as `250` (same value). The CSV keeps `250.00` only if the value
  came with those places: a value read from an Excel number cell (as in the example
  targets) is `250`.
- **XLSX numeric limits**: decimals that an Excel number cannot hold exactly and integers
  above 2^53 make an XLSX export fail (use CSV).
- **Time zones**: datetimes are read and written without time zone; values with a time zone
  cannot be exported to XLSX. All report and log timestamps are UTC.
- **XLSX reading** uses the saved values of formulas (`data_only`); formulas never
  calculated by Excel are refused. Merged cells, hidden rows and several header rows are
  not interpreted; the first row of the sheet is the header.
- **CSV**: one header row, one delimiter character, standard quoting. No automatic
  detection of encoding, delimiter or decimal separator: they are declared.
- **Mean** without `round` keeps 28 significant digits (Python `Decimal` precision).

## Security model

The workflow file is trusted to be *written by the user*, but is still validated as if
it were not: no code execution, no paths outside the working root. Source files are
untrusted data (strict parsing, defusedxml for XLSX). The tool does not sandbox the
process, does not encrypt anything and does not manage secrets (there is no secret in a
workflow file). It protects against mistakes and malformed files, not against a user with
write access to the working folder.

## Tests

- One test is skipped on Windows: the escape of the working root through a **symbolic
  link** needs the privilege to create links, which the test account does not have. The
  same check is exercised by a test with a **directory junction** (no privilege needed),
  which passes.
- The PowerShell wrapper test needs Windows PowerShell and the `data-automate.exe` launcher
  in the active environment.
