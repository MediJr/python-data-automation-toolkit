# Architecture

A workflow is an **ordered list of steps exchanging named datasets** (ADR-0004). There is
no dependency graph, no parallelism and no plugin loading: the order of the file is the
order of execution.

```text
              ┌────────────── validate (no data read, nothing written) ──────────────┐
workflow.yaml │ yaml_loader ─► config (Pydantic) ─► parameters ─► paths ─► registry │
              └───────────────────────────────────┬──────────────────────────────────┘
                                                  ▼
 engine:  lock ─► preflight outputs ─► SHA-256 sources ─► readers ─► steps (in order)
          ─► writers: temp file ─► read back + compare ─► sources unchanged? ─► os.replace
          ─► reporting (run_report.json / .md, run.log, summary.md) ─► unlock
```

## Modules (`src/data_automation/`)

| Module | Responsibility |
| --- | --- |
| `cli.py`, `__main__.py` | argparse commands `validate`, `run`, `steps`; exit codes; console output |
| `log.py` | Logging with UTC timestamps; verbosity |
| `errors.py` | Exceptions shared by the modules |
| `yaml_loader.py` | Safe YAML loading with extra refusals (duplicates, anchors, aliases, non-text keys, size) |
| `config.py` | Strict Pydantic models of the workflow file; readable error messages |
| `parameters.py` | Typed run parameters (`string`, `integer`, `date`, `month`) and `{name}` substitution |
| `paths.py` | Working root, path shape rules, pattern matching, containment checks (including links) |
| `validation.py` | Everything checked before a run: parameters, references, paths, sources, outputs, step parameters |
| `types.py` | Logical types: strict parsing, literal coercion, canonical text, pandas storage |
| `dataset.py` | `Dataset` (name, columns, types, parts) and `Part` (a frame and its origin) |
| `readers.py` | CSV (`csv` module) and XLSX (openpyxl read-only, defusedxml) readers |
| `registry.py` | Step contract (`StepParams`, `StepType`, `StepContext`, `StepResult`, `StepFailure`) and registry |
| `steps/` | Built-in step types: `combine.py` (concatenate, join), `rows.py` (filter, sort, check), `columns.py` (select, rename, cast), `aggregate.py` |
| `writers.py` | CSV/XLSX export contract, read-back verification, metadata helpers |
| `engine.py` | Run order, lock, statuses, error policy, publication, run folder |
| `reporting.py` | Markdown run report and business summary |

Specification §12 grouped readers and writers in an `io.py` module and parameters in
`config.py`; they were split into the smaller modules above as the code grew (C-14 allows
it; recorded in [ADR-0009](decisions/0009-choix-de-realisation.md)).

## Data model

- A **dataset** has a name, ordered columns, a logical type per column and one or more
  **parts**. An input matching three files is one dataset with three parts (one per file,
  with the file as origin), so per-file information is never lost before `concatenate`.
- Values are stored in pandas columns chosen per logical type: `string` dtype for text,
  nullable `Int64` for integers, and `object` columns holding Python `Decimal`,
  `datetime.date`, `datetime.datetime` and `bool` values for the other types. Decimals stay exact `Decimal` objects end to end; nothing goes through
  floats except XLSX cells.
- Steps work on Python values where exactness matters (filters, aggregations, joins'
  checks) and on pandas for bulk operations (concatenation, merge, sort).

## Extending the step registry

```python
from data_automation.dataset import Dataset
from data_automation.registry import StepParams, StepResult, StepType, register


class UpperParams(StepParams):          # strict: unknown keys and wrong types are errors
    column: str


def run_upper(params, inputs, ctx):
    frame = inputs[0].frame().copy()
    frame[params.column] = frame[params.column].str.upper()
    return StepResult(Dataset.from_frame(ctx.step_id, frame, inputs[0].types), [], {})


register(StepType("upper", "Upper-case one text column.", UpperParams, run_upper))
```

After registration, `type: upper` is validated, run, timed and reported like a built-in
type; the engine is not changed (AC-12, tested in
`tests/unit/test_registry_and_writers.py`). A step raises `StepFailure` with a message
for the report; any other exception is recorded as an internal error of that step. A
`StepParams` subclass can override `parameter_references()` to have validation check that
the run parameters it uses are declared. Registration happens in code (the module must be
imported before the run); there is no plugin discovery.

## Design decisions

The decisions and their alternatives are recorded in French in
[docs/decisions/](decisions/README.md): argparse (0001), YAML + Pydantic (0002), atomic
runs (0003), execution model (0004), declarative filters (0005), working root (0006),
export contract (0007), independence from service 1 (0008), implementation choices (0009).
