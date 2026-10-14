# Workflow configuration (schema version 1)

This page describes every section of a workflow file and what `data-automate validate`
checks before a run. The step types and their parameters are described in
[steps.md](steps.md); what a run does with the file is described in [running.md](running.md).

A workflow file is YAML, UTF-8, at most 1 MB. It is loaded with PyYAML's safe loader plus
extra rules: duplicate keys, anchors (`&name`), aliases (`*name`) and keys that are not text
are refused. (YAML 1.1 reads unquoted `on`, `off`, `yes`, `no` as booleans; as keys they are
refused with a message asking to quote them.)
Every section is validated strictly: **unknown keys are errors** and values must already have
the right type.

> YAML 1.1 converts some unquoted values: `007` becomes the number 7, `NO` becomes `false`,
> `2026-09-01` becomes a date. Strict validation reports such values instead of accepting
> them; quote them (`"007"`) when you mean text.

## `workflow` (required)

| Key | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Lower-case identifier: letters, digits, `_`, `-`; starts with a letter |
| `schema_version` | yes | Must be `1` |
| `description` | no | Free text |
| `root` | no (default `.`) | Working root, **relative to the folder of the workflow file**; must exist; absolute paths and wildcards are refused |

## `parameters` (optional)

A mapping from parameter name (lower case, letters, digits, `_`) to:

| Key | Default | Meaning |
| --- | --- | --- |
| `type` | required | `string`, `integer`, `date` (`YYYY-MM-DD`, a real date) or `month` (`YYYY-MM`) |
| `default` | none | Text value, checked against `type`; a parameter with a default is optional |
| `required` | `true` without default | Cannot be `true` when a default is given |
| `description` | none | Free text |

Values are given with `--param name=value`. Unknown names, repeated names, missing required
parameters and malformed values are errors. `string` values may not contain `/`, `\` or
`..`, because they can be used in paths.

Parameters are used in two places:

- in paths (input, output and `report.directory`) as `{name}`: plain text replacement of
  declared names only; nothing is evaluated;
- in filter conditions, with `param: name` instead of `value:` (see
  [steps.md](steps.md#filter)): the parameter's value is converted to the column's type,
  exactly like a literal value.

A parameter that is declared but never used produces a warning; a `param:` naming an
undeclared parameter is an error.

## `inputs` (required, at least one)

| Key | Default | Meaning |
| --- | --- | --- |
| `id` | required | Dataset name (identifier) |
| `type` | required | `csv` or `xlsx` |
| `path` | required | File or pattern relative to the root; `*`, `?` and `[...]` are allowed in the **last part only**; `**` is not supported |
| `required_columns` | `[]` | Columns each file must contain |
| `types` | `{}` | Logical type per column (see below); undeclared columns are `string` |
| `decimal_separator` | `.` | `.` or `,`: how `decimal` values are written in the file (CSV text and text cells) |
| `on_empty_match` | `fail` | `fail`: no matching file is an error; `warn`: a warning, and the input is an empty dataset with the declared columns |
| `on_empty_file` | `fail` | `fail`: an empty file (no header) is an error; `skip`: it is skipped with a warning (but not if every file is empty) |
| `encoding` | `utf-8` | CSV only; must be a known Python codec; a UTF-8 BOM is accepted |
| `delimiter` | `,` | CSV only; one character |
| `sheet` | first sheet | XLSX only |

### Column types

`types` maps a column to a logical type, either in short form (`amount: decimal`) or with
options (`day: {type: date, format: "%d/%m/%Y"}`):

| Type | Accepted text | Notes |
| --- | --- | --- |
| `string` | anything | Default; kept as is (leading zeros, spaces) |
| `integer` | `42`, `-7` | No decimals, exponents or thousands separators; 64-bit range |
| `decimal` | `120.50`, `.5`, `-3` (or with `,` if `decimal_separator: ","`) | Exact (Python `Decimal`), never a float; no exponents, `NaN` or currency signs |
| `date` | `2026-09-30`, or the `format` given | A datetime with a time of day is refused, not truncated |
| `datetime` | `2026-09-30T14:05:00`, `2026-09-30 14:05`, or the `format` | Without time zone |
| `boolean` | `true` / `false` (any case) | `yes`, `1`… are refused |

An empty cell is a **missing value**, never 0 or an empty text. A value that does not
match its type fails the input, with the file, the row and the value in the message (up to
five examples). Every file of an input becomes one **part** of the input dataset; use a
`concatenate` step to combine them.

XLSX cells: numbers, dates and booleans are read from the typed cells; a formula without a
saved value is refused (open and save the file in Excel first); values outside the header
columns are refused.

## `steps` (optional)

An ordered list. Each step has:

| Key | Meaning |
| --- | --- |
| `id` | Unique step identifier |
| `type` | Step type name; must be registered (`data-automate steps` lists them) |
| `input` | One dataset name, or a non-empty list of names |
| `output` | Name of the dataset the step produces; must be new |
| `description` | Optional |

Every other key is a **type-specific parameter**, validated strictly by the step type's own
model (unknown keys and wrong types are errors), together with the number of inputs the
type accepts. See [steps.md](steps.md).

Rules checked now: step ids are unique; every input is a source or the output of an
**earlier** step (using a dataset before it is produced is an error); an output name cannot
reuse an existing dataset name. Datasets that are never used produce a warning.

## `outputs` (required, at least one)

| Key | Default | Meaning |
| --- | --- | --- |
| `id` | required | Unique output identifier |
| `input` | required | Dataset to export (a source or a step output) |
| `type` | required | `csv` or `xlsx`; the path must end with the matching extension |
| `path` | required | Relative to the root; no wildcards |
| `expected_columns` | none | Exact list and order of columns the dataset must have; checked before writing |
| `sheet_name` | none | XLSX only, 1–31 characters |

Two outputs cannot write the same file; an output can never be a source file or match an
input pattern; an existing folder at the output path is an error.

A dataset exported to a file must have a single part (combine multi-file inputs with
`concatenate` first).

## `on_error`

| Value | Behaviour |
| --- | --- |
| `stop` (default) | The first failure stops the run; nothing is published |
| `continue` | A step whose input was not produced (its producer failed or was skipped) is skipped; the other steps still run. Outputs whose dataset was produced are written, verified and published; the others are skipped. The status is `partial` (exit 4) if at least one output was published, otherwise `failed` — never `success` |

With `continue`, previous files of the skipped outputs stay as they were, so the output
folder can hold files from different runs: the run report lists which outputs were
published (see [running.md](running.md#statuses-and-exit-codes)).

## `report`

| Key | Default | Meaning |
| --- | --- | --- |
| `formats` | `[json, markdown]` | Which of `run_report.json` / `run_report.md` to write; non-empty, no duplicates |
| `directory` | `runs` | Folder of the run reports, relative to the root (parameters allowed); each run writes `<directory>/<workflow id>/<run id>/` |
| `summary.datasets` | — | Datasets to show in `summary.md` (business summary); must exist |
| `summary.max_rows` | `50` | Rows shown per dataset (1–1000); the summary says when rows are left out |
| `summary.title` | workflow id | Title of the summary |

The report folder can never contain a source file, and an output's `.metadata.json` file
can never be a source.

## Path rules

All paths are relative to the working root. After `{name}` placeholders are replaced, a path
must stay inside the root once normalized (`a/../../x` is refused) and once symbolic links
are resolved. Matches that point outside the root through a symbolic link are errors.
