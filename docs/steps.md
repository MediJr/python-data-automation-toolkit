# Step reference

Steps run **in the order of the file**. Each step reads one or more named datasets
(`input`) and produces one new named dataset (`output`); the datasets it reads are not
changed. Parameters are validated strictly before the run (unknown keys and wrong types are
errors); problems that depend on the data (a missing column, a value of the wrong type) fail
the step during the run, with the step named in the error.

`data-automate steps` lists the registered types. Common keys (`id`, `type`, `input`,
`output`, `description`) are described in [configuration.md](configuration.md#steps-optional).

| Type | Inputs | Purpose |
| --- | --- | --- |
| [`concatenate`](#concatenate) | 1 or more | Stack rows (all files of a multi-file input, or several datasets) |
| [`filter`](#filter) | 1 | Keep rows matching all conditions |
| [`join`](#join) | 2 | Match rows of two datasets on keys, with a declared relationship |
| [`aggregate`](#aggregate) | 1 | Group and compute sum, count, mean, min, max |
| [`select`](#select) | 1 | Keep and order columns |
| [`rename`](#rename) | 1 | Rename columns |
| [`cast`](#cast) | 1 | Convert columns to a type |
| [`sort`](#sort) | 1 | Sort rows |
| [`check`](#check) | 1 | Controls: row counts, missing values, uniqueness, allowed values |

**Missing values.** An empty cell is a missing value. Comparisons with a missing value are
never true (as in SQL), aggregations ignore missing values, and a group with no value gives
a missing result — never 0.

**Multi-file inputs.** An input whose pattern matches several files is a dataset with one
part per file. Only `concatenate` accepts it; every other step (and every output) needs a
single part.

## concatenate

| Parameter | Default | Meaning |
| --- | --- | --- |
| `columns` | `same` | `same`: every file/dataset must have exactly the same columns (order may differ; the first one's order is kept). `union`: all columns are kept, absent ones are filled with missing values (with a warning per file) |
| `add_source_column` | none | Name of a new text column holding each row's origin (the file path relative to the root, or the dataset name) |

A column must have the same type everywhere; otherwise the step fails and names both
origins. Zero-row files are allowed.

```yaml
- {id: consolidate, type: concatenate, input: sales_files, output: sales, add_source_column: source_file}
```

## filter

`where` is a non-empty list of conditions; a row is kept when **all** conditions are true.
Each condition is `{column, op, value}` or `{column, op, param}`:

| `op` | Value | True when |
| --- | --- | --- |
| `eq`, `ne` | one value | equal / not equal |
| `lt`, `le`, `gt`, `ge` | one value | less / less or equal / greater / greater or equal (not for booleans) |
| `between` | `[low, high]` | `low <= value <= high` |
| `in`, `not_in` | non-empty list | in / not in the list |
| `contains` | text | the text column contains the value (case-sensitive) |
| `is_null`, `not_null` | none | missing / present |

The value is converted to the **column's type** with the same strict rules as input files:
for a `decimal` column write `100` or `"99.90"`, for a `date` column `2026-09-01`, for a
`string` column quote numbers (`"007"`). A value that cannot be converted fails the step.

`param: name` takes the value from a run parameter instead (single-value operators only;
the parameter must be declared). The value is looked up by name, never substituted into
text. Example with `--param start=2026-09-15` and a parameter `start: {type: date}`:

```yaml
- id: second_half
  type: filter
  input: sales
  output: late_sales
  where:
    - {column: status, op: in, value: [closed, shipped]}
    - {column: order_date, op: ge, param: start}
```

Conditions are data: the operator comes from the closed list above and is evaluated in
Python. Nothing is passed to `eval`, `exec` or `DataFrame.query`.

## join

`input` is a list of two datasets: left, right.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `relationship` | required | `one_to_one`, `many_to_one` (right keys unique) or `one_to_many` (left keys unique) |
| `keys` | — | Key columns with the same name on both sides (kept once in the result) |
| `left_keys`, `right_keys` | — | Instead of `keys`, when names differ (same length; both kept) |
| `how` | `inner` | `inner`, `left`, `right` or `outer` |
| `require_match` | `false` | Fail if any left row has no match on the right |
| `suffixes` | `[_left, _right]` | Added to non-key columns present on both sides (with a warning) |

The relationship is **checked before joining**: if a key that should be unique appears more
than once, the step fails with examples of the duplicated keys, so rows can never multiply
silently. Key columns must have the same type on both sides. Rows whose key is missing
never match (they are kept by `left`/`right`/`outer` joins on their side, with a warning).
Result columns: left columns, then right columns.

```yaml
- {id: add_targets, type: join, input: [totals, targets], output: with_targets,
   keys: [region], relationship: one_to_one, how: left, require_match: true}
```

## aggregate

| Parameter | Default | Meaning |
| --- | --- | --- |
| `group_by` | `[]` | Grouping columns; without them, the result is one row for the whole dataset |
| `metrics` | required | Mapping `result name: {function, column, round}` |

| `function` | `column` | Result type |
| --- | --- | --- |
| `count` | optional: without it counts rows, with it counts present values | integer |
| `sum` | integer or decimal column | type of the column |
| `mean` | integer or decimal column | decimal |
| `min`, `max` | integer, decimal, date, datetime or string column | type of the column |

`round: n` (0–12) rounds a decimal result half-up to `n` places; without it a mean keeps
full precision (28 significant digits). Sums of decimals are exact. Groups are sorted by
the `group_by` values, with missing keys last (they form their own group). Result names
must not repeat a `group_by` column.

```yaml
metrics:
  total_sales: {function: sum, column: amount}
  order_count: {function: count}
  average_order: {function: mean, column: amount, round: 2}
```

## select

`columns`: non-empty list; the result has exactly these columns in this order. Unknown or
repeated names fail.

## rename

`columns`: mapping `old name: new name`. Unknown columns and names that would clash fail.

## cast

`columns`: mapping `column: type` or `column: {type, format, decimal_separator}`. Converts
`string` columns with the same strict rules as the readers (empty text becomes missing);
converting between other types goes through their canonical text (`decimal` →
`string` gives `162.50`). Any value that does not convert fails the step with up to five
examples.

```yaml
columns:
  quantity: integer
  delivered: {type: date, format: "%d/%m/%Y"}
```

## sort

`by`: non-empty list of `{column, descending}` (`descending` defaults to `false`). The sort
is stable (equal rows keep their order) and missing values are always last.

## check

A control step: the data passes through unchanged if every rule holds, otherwise the step
fails and lists every broken rule (with up to five example rows each). At least one rule:

| Rule | Meaning |
| --- | --- |
| `min_rows`, `max_rows` | Row count bounds |
| `not_null` | Columns that must have no missing value |
| `unique` | Columns whose combined values must be unique |
| `allowed_values` | Mapping `column: [values]`; missing values are not checked (use `not_null`) |

```yaml
- {id: controls, type: check, input: report, output: checked,
   min_rows: 1, not_null: [region, total_sales], unique: [region]}
```

## Adding a step type

A step type is a Pydantic parameter model (subclass of `StepParams`) and a function
`run(params, inputs, context) -> StepResult`, registered with
`data_automation.registry.register(StepType(...))`. Validation, reporting and the engine
use it without change; see [architecture.md](architecture.md#extending-the-step-registry).
