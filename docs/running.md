# Running workflows

## Commands

| Command | What it does |
| --- | --- |
| `data-automate validate WORKFLOW [--param N=V ...] [--json]` | Checks the workflow (schema, parameters, references, paths, step parameters, matching files) without reading data or writing anything |
| `data-automate run WORKFLOW [--param N=V ...] [--overwrite] [--json]` | Runs it (below) |
| `data-automate steps` | Lists the registered step types |

Global options (before the command): `-v` progress, `-vv` details (on standard error, UTC
timestamps), `--version`. `python -m data_automation` is equivalent to `data-automate`.
Relative workflow paths are resolved from the current directory; every path *inside* the
workflow is resolved from its working root (`workflow.root`, relative to the workflow
file's folder), so the command works from any directory.

## What a run does

1. **Validate** the workflow exactly as `validate` does; any error refuses the run.
2. **Lock**: create `<report.directory>/<workflow id>/.lock`. If it exists, another run of
   the same workflow is in progress and the run is refused.
3. **Preflight**: every output and its `.metadata.json` must not exist, unless
   `--overwrite` is given. All blocked files are reported together; nothing has started.
4. **Fingerprint** every source file (SHA-256).
5. **Read** the inputs, then **run the steps** in their declared order.
6. **Write** each output under a temporary name next to its destination
   (`.name.tmp-<token>.csv`), **read it back** and compare it with the dataset value by
   value; write its metadata the same way.
7. **Check** that no source file changed since step 4 (same SHA-256).
8. **Publish** with `os.replace` (atomic on the same volume), only if the run succeeded
   (or, with `on_error: continue`, for the outputs whose data was produced).
9. **Report**: write the run folder; remove temporary files; release the lock.

There is no automatic retry or resume: to rerun after a failure, fix the cause and run the
same command again (add `--overwrite` if outputs were published).

## Statuses and exit codes

| Status | Exit | Meaning | Published |
| --- | --- | --- | --- |
| `success` | 0 | Every input, step and output succeeded | All outputs |
| `failed` | 1 | A source, step, export, verification or publication failed | Nothing (with `stop`) |
| — | 2 | Invalid command line (argparse) | Nothing; no report |
| — (`Result: REFUSED`) | 3 | Invalid workflow or parameters, existing outputs without `--overwrite`, lock held | Nothing; no run folder |
| `partial` | 4 | `on_error: continue` and something failed, but some outputs were published | The verified outputs whose data was produced |
| `interrupted` | 130 | Ctrl+C during the run | Nothing (unless publication had already started); temporary files removed |

A run is never reported as `success` if anything failed. If a file cannot be replaced
during publication (for example because it is open in Excel), the run fails; outputs
already replaced before it are listed in the report as published, with a warning.

## The run folder

`<report.directory>/<workflow id>/<run id>/` (default `runs/…`), created for every run that
passed the preflight — failed runs included:

| File | Content |
| --- | --- |
| `run_report.json` | Workflow, run id (UUID v4), UTC start/end, duration, status, exit code, `on_error`, `overwrite`, parameters, sources (path, input, SHA-256, unchanged), inputs (files, rows, duration, warnings), steps (inputs, rows in/out, status, duration, warnings, details, error), outputs (path, status, rows, columns, SHA-256, checks, write + verify duration), errors, warnings, environment (Python version, platform) |
| `run_report.md` | The same in readable tables (if `markdown` is in `report.formats`) |
| `run.log` | The log of the run, with UTC timestamps |
| `summary.md` | Business summary: the datasets listed in `report.summary` as tables (if configured and the datasets were produced) |

Reports contain relative paths only, no data rows (except in `summary.md`) and no
environment variables. Error messages may quote a few invalid values (at most five per
problem) to locate them.

Real examples: [reports/examples/](../reports/examples/sales-vs-targets/run/run_report.md).

## Export metadata

Each published file `F` has `F.metadata.json` beside it:

| Key | Content |
| --- | --- |
| `metadata_version` | `1` |
| `workflow_id`, `run_id`, `generated_at` | Which run produced the file, and when (UTC) |
| `parameters` | Run parameters |
| `output_id`, `dataset` | Output and dataset names |
| `file` | Path, type, SHA-256, rows, format (CSV: encoding, BOM, delimiter, decimal separator, line terminator; XLSX: sheet) |
| `columns` | Name, logical type and nullability of each column |
| `decimal_places` | For decimal columns: the largest number of decimal places present |
| `sources` | Every source file read by the run, with its SHA-256 |
| `checks` | The verifications done before publishing |

## Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `Result: INVALID` (validate) or `Result: REFUSED` (run), exit 3, with a list of problems | The workflow or parameters are wrong; each line gives the location (`steps[2] (join).relationship: …`). Run `validate` while editing. |
| `… already exists (use --overwrite to replace it)` | The period was already processed. Rerun with `--overwrite` to replace the outputs (only after the new ones are verified). |
| `another run of this workflow holds the lock .lock (run_id=… pid=…)` | A run is in progress. If none is (the computer crashed during a run), delete the `.lock` file named in the message. |
| `no file matches data/…/sales_*.csv` | Wrong period or folder. Set `on_empty_match: warn` only if an empty period is normal. |
| `column 'amount': 2 value(s) are not valid decimal … row 3: '1,5'` | The file uses another format: set `decimal_separator: ","` (or quote the field), or fix the file. |
| `… is not valid utf-8` | Set `encoding:` on the input (e.g. `cp1252` for files saved by older Excel versions). |
| `formula cell(s) … have no saved value` | The workbook was generated without being calculated: open and save it in Excel. |
| `relationship one_to_one violated: … appear more than once on the right side` | The reference data has duplicate keys; fix it or declare the real relationship. |
| `could not be published (is the file open in another program?)` | Close the file (Excel locks open files) and rerun with `--overwrite` if some outputs were published. |
| `a source file changed during the run` | A source was being written while the run read it; nothing was published. Rerun when the source is complete. |
| A PowerShell or console shows `?` instead of accented letters | Console encoding only; files are always UTF-8. Set `$env:PYTHONIOENCODING = "utf-8"`. |
