"""Cross-section validation (specification §6.2)."""

from __future__ import annotations

import pytest
from conftest import VALID_WORKFLOW

from data_automation.errors import WorkflowLoadError
from data_automation.validation import validate_workflow


def _errors(report):
    return "\n".join(report.errors)


def test_valid_workflow_report(workspace):
    report = validate_workflow(workspace(), {"period": "2026-09"})
    assert report.valid, report.errors
    assert report.workflow_id == "monthly-sales"
    assert report.parameters == {"period": "2026-09"}
    assert report.inputs[0]["matches"] == ["incoming/2026-09/sales_north.csv"]
    assert report.outputs[0]["resolved"] == "output/sales_2026-09.csv"
    assert [s["id"] for s in report.steps] == ["consolidate", "kpis"]
    assert report.steps[1]["type_parameters"] == ["group_by", "metrics"]
    assert report.notes == []
    assert set(report.step_params) == {"consolidate", "kpis"}
    assert report.warnings == []


def test_validation_never_writes_anything(workspace, tmp_path):
    workflow = workspace()
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    validate_workflow(workflow, {"period": "2026-09"})
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before


def test_schema_problems_are_collected_not_raised(workspace):
    report = validate_workflow(
        workspace(VALID_WORKFLOW.replace("on_error", "x").replace("root: .", "root: .\n  colour: red"))
    )
    assert not report.valid
    assert any("workflow.colour: unknown key" in e for e in report.errors)


def test_unreadable_file_raises_load_error(tmp_path):
    with pytest.raises(WorkflowLoadError):
        validate_workflow(tmp_path / "missing.yaml")


@pytest.mark.parametrize(
    "params, message",
    [
        ({}, "parameter 'period' is required: pass --param period=<month>"),
        ({"period": "2026-9"}, "--param period='2026-9': must be a month"),
        ({"period": "2026-09", "region": "x"}, "--param region: not declared"),
    ],
)
def test_parameter_problems(workspace, params, message):
    report = validate_workflow(workspace(), params)
    assert message in _errors(report)


def test_undeclared_placeholder_and_unused_parameter(workspace):
    text = VALID_WORKFLOW.replace("output/sales_{period}.csv", "output/sales_{region}.csv")
    text = text.replace("  period: {type: month}", "  period: {type: month}\n  spare: {type: string, default: x}")
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "outputs[0] (export).path: placeholder {region} is not a declared parameter" in _errors(report)
    assert "parameter 'spare' is declared but not used in any path" in report.warnings


def test_filter_parameter_must_be_declared(workspace):
    step = "  - {id: recent, type: filter, input: sales_files, output: recent, where: [{column: region, op: eq, param: zone}]}"
    text = VALID_WORKFLOW.replace("steps:\n", f"steps:\n{step}\n", 1)
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "steps[0] (recent): parameter 'zone' is not declared" in _errors(report)


def test_dataset_references(workspace):
    text = VALID_WORKFLOW.replace("    input: sales\n", "    input: totals\n")  # kpis uses its own output
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "steps[1] (kpis): input 'totals' is used before it is produced (by step 'kpis')" in _errors(report)

    text = VALID_WORKFLOW.replace("    input: sales\n", "    input: salez\n")
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "input 'salez' is not an input or the output of an earlier step" in _errors(report)
    assert "dataset 'sales' (step 'consolidate') is never used" in report.warnings

    text = VALID_WORKFLOW.replace("    input: totals\n    type: csv", "    input: total\n    type: csv")
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "outputs[0] (export): dataset 'total' is not produced by any input or step" in _errors(report)


def test_duplicate_ids_and_dataset_names(workspace):
    text = VALID_WORKFLOW.replace("  - id: kpis", "  - id: consolidate").replace("output: totals", "output: sales")
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    errors = _errors(report)
    assert "steps: id 'consolidate' is used more than once" in errors
    assert "output name 'sales' is already used by step 'consolidate'" in errors


def test_input_output_name_clash(workspace):
    text = VALID_WORKFLOW.replace("output: sales\n", "output: sales_files\n")
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "output name 'sales_files' is already used by input 'sales_files'" in _errors(report)


def test_missing_sources_fail_or_warn(workspace):
    report = validate_workflow(workspace(files={}), {"period": "2026-09"})
    assert "inputs[0] (sales_files).path: no file matches incoming/2026-09/sales_*.csv" in _errors(report)
    text = VALID_WORKFLOW.replace(
        "required_columns: [region, amount]", "required_columns: [region, amount]\n    on_empty_match: warn"
    )
    report = validate_workflow(workspace(text, files={}), {"period": "2026-09"})
    assert report.valid
    assert "inputs[0] (sales_files).path: no file matches incoming/2026-09/sales_*.csv" in report.warnings


@pytest.mark.parametrize(
    "replacement, message",
    [
        ('path: "../incoming/{period}/sales_*.csv"', "leaves the working root"),
        ('path: "C:/incoming/sales.csv"', "absolute paths are not allowed"),
        ('path: "incoming/**/sales.csv"', "recursive patterns"),
    ],
)
def test_input_path_rules(workspace, replacement, message):
    text = VALID_WORKFLOW.replace('path: "incoming/{period}/sales_*.csv"', replacement)
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert message in _errors(report)


def test_output_must_never_be_a_source(workspace):
    text = VALID_WORKFLOW.replace('path: "output/sales_{period}.csv"', 'path: "incoming/{period}/sales_north.csv"')
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "is (or would be) a source file; sources are never overwritten" in _errors(report)
    # also when the file does not exist yet but matches the input pattern
    text = VALID_WORKFLOW.replace('path: "output/sales_{period}.csv"', 'path: "incoming/{period}/sales_new.csv"')
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "is (or would be) a source file" in _errors(report)


def test_outputs_must_not_collide_or_be_folders(workspace, tmp_path):
    text = VALID_WORKFLOW + '  - id: export2\n    input: totals\n    type: csv\n    path: "output/sales_{period}.csv"\n'
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert "outputs[1] (export2).path: same file as output 'export'" in _errors(report)
    (tmp_path / "output" / "sales_2026-09.csv").mkdir(parents=True)
    report = validate_workflow(workspace(), {"period": "2026-09"})
    assert "output/sales_2026-09.csv is a folder" in _errors(report)


def test_root_problems(workspace):
    report = validate_workflow(workspace(VALID_WORKFLOW.replace("root: .", "root: missing")), {"period": "2026-09"})
    assert "workflow.root: the root folder does not exist" in _errors(report)


def test_workflow_in_subfolder_with_parent_root(workspace):
    text = VALID_WORKFLOW.replace("root: .", "root: ..")
    report = validate_workflow(workspace(text, name="config/workflow.yaml"), {"period": "2026-09"})
    assert report.valid, report.errors
    assert report.inputs[0]["matches"] == ["incoming/2026-09/sales_north.csv"]


def test_no_steps_note_when_there_are_no_steps(workspace):
    text = (
        VALID_WORKFLOW.split("steps:")[0]
        + 'outputs:\n  - id: export\n    input: sales_files\n    type: csv\n    path: "o.csv"\n'
    )
    report = validate_workflow(workspace(text), {"period": "2026-09"})
    assert report.valid and report.steps == []
