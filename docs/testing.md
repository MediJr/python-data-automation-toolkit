# Testing

```powershell
.venv\Scripts\python.exe -m pytest -q                       # whole suite
.venv\Scripts\python.exe -m pytest -q tests\unit            # one folder
.venv\Scripts\python.exe -m ruff check src tests scripts benchmarks
.venv\Scripts\python.exe -m ruff format --check src tests scripts benchmarks
.venv\Scripts\python.exe benchmarks\run_benchmark.py         # benchmark + independent check
```

All tests run on real files in temporary folders; nothing is mocked except the failures
that cannot be produced on demand (a full disk, a change of a source file at a precise
moment, Ctrl+C), which are injected by replacing one function during the test. Expected
results are written by hand in the tests (for example `162.50` = 120.50 + 42.00), never
computed with the code under test.

## Layout

| Folder | Content |
| --- | --- |
| `tests/unit/` | YAML loader, configuration models, parameters and paths, validation, types, readers, each step type, registry and writers |
| `tests/integration/` | Complete runs of the engine on real files, including every failure scenario |
| `tests/cli/` | Commands, options, exit codes, output streams, installed command and module in subprocesses, another working directory, the Task Scheduler wrapper |
| `tests/test_examples.py` | The committed examples (`reports/examples/`) equal a fresh run; the [demo](demo-monthly-sales.md) KPIs are recomputed with the standard library only and checked against the CSV, XLSX and recorded SHA-256; the sample workbook generator reproduces the committed file |
| `tests/test_project.py` | Packaging (version, entry point, dependencies = imports, pinned versions, no dependency on service 1), module list, documentation links and anchors, README commands and output |

## Acceptance criteria (specification §14)

| Criterion | Tests |
| --- | --- |
| AC-01 valid configuration loaded, invalid refused precisely | `unit/test_config_models.py`, `unit/test_validation.py`, `cli/test_cli_validate.py::test_invalid_workflow_exit_3_on_stderr` |
| AC-02 several CSV files consolidated | `unit/test_steps.py::test_concatenate_*`, `integration/test_engine.py::test_full_run_success` |
| AC-03 filter, join and aggregation applied | `unit/test_steps.py` (`test_filter_*`, `test_join_*`, `test_aggregate_*`), examples |
| AC-04 CSV and XLSX exports per the contract, verified, with metadata | `unit/test_registry_and_writers.py::test_csv_contract_exact_bytes`, `::test_xlsx_typed_cells_and_verification`, `integration/test_engine.py::test_metadata_describes_the_published_file`, `::test_verification_failure_is_not_published` |
| AC-05 run report with status, steps, volumes, durations, errors | `integration/test_engine.py::test_full_run_success`, `::test_step_failure_message_reaches_the_report` |
| AC-06 missing or invalid source fails explicitly, attached to its step | `cli/test_cli_run.py::test_run_refusals_and_failures_have_distinct_exit_codes`, `unit/test_readers.py`, `unit/test_validation.py::test_missing_sources_fail_or_warn` |
| AC-07 sources preserved | `integration/test_engine.py::test_full_run_success` (fingerprints), `::test_source_changed_during_the_run_blocks_publication` |
| AC-08 no overwrite without permission | `integration/test_engine.py::test_existing_outputs_are_never_overwritten_without_permission` |
| AC-09 repeated runs: no duplicates, no accidental overwrite | `integration/test_engine.py::test_runs_are_repeatable_without_duplicates`, `::test_stop_policy_publishes_nothing_and_keeps_previous_outputs` |
| AC-10 CLI documented and tested | `cli/` (help, usage errors, exit codes 0/1/2/3/4, JSON, verbosity), `test_project.py::test_readme_*` |
| AC-11 unit and integration tests pass on the supported environment | whole suite on Windows 11, Python 3.14.7 |
| AC-12 new step type without changing the engine | `unit/test_registry_and_writers.py::test_new_step_type_runs_through_the_unchanged_engine` |
| AC-13 complete example reproducible from a clean install | `test_examples.py`, plus the clean-install checks below |
| AC-14 installation, usage, configuration, troubleshooting documented | [README](../README.md), [configuration](configuration.md), [running](running.md#troubleshooting); links checked by `test_project.py` |
| AC-15 path outside the root and YAML execution tag refused | `unit/test_parameters_and_paths.py`, `unit/test_validation.py::test_input_path_rules`, `unit/test_yaml_loader.py::test_python_tags_are_refused`, `cli/test_cli_validate.py::test_python_tag_in_workflow_exit_3` |
| AC-16 join violating its relationship fails | `unit/test_steps.py::test_join_relationship_violation_fails_instead_of_multiplying_rows`, `integration/test_engine.py::test_join_relationship_violation_fails_the_run` |
| AC-17 Task Scheduler example documented, command tested | `cli/test_cli_run.py::test_task_scheduler_wrapper_script`, [scheduling.md](scheduling.md) |
| AC-18 period parameter selects files; missing or malformed parameter refused | `integration/test_engine.py::test_period_parameter_selects_only_that_period_files`, `unit/test_validation.py::test_parameter_problems` |

## Checks outside the test suite

Done before publication and reported in the release notes of the final phase:

- **Clean installs**: a new virtual environment with `pip install -e ".[dev]" -c constraints.txt`
  and the full suite; a regular `pip install .` in another environment and the example run
  from another directory; `pip check`.
- **Independent verification**: `benchmarks/verify_outputs.py` recomputes the benchmark
  outputs with the standard library only.
- **Mutation checks** (15): each safeguard was disabled one at a time and the suite was
  run; every time at least one test failed, and the code was restored afterwards. Disabled
  safeguards: overwrite protection, CSV read-back verification, XLSX read-back
  verification, join relationship check, `require_match`, path containment, link escape
  check, YAML safe loader, source fingerprint check, run lock, filter missing-value rule,
  filter `param` lookup, XLSX exact-number check, XLSX number-to-text conversion, LF line
  endings of `run.log`.

## Skipped test

`unit/test_parameters_and_paths.py::test_symbolic_link_escape_is_refused` is skipped when
the account cannot create symbolic links (the usual case on Windows without developer
mode). The same check is covered by `::test_directory_junction_escape_is_refused`.
