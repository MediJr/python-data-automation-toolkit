"""Schema validation of workflow files (Pydantic models)."""

from __future__ import annotations

import copy

import pytest
import yaml
from conftest import VALID_WORKFLOW

from data_automation.config import parse_workflow
from data_automation.errors import WorkflowValidationError

BASE = yaml.safe_load(VALID_WORKFLOW)


def _with(changes):
    data = copy.deepcopy(BASE)
    changes(data)
    return data


def _issues(data):
    with pytest.raises(WorkflowValidationError) as info:
        parse_workflow(data)
    return info.value.issues


def test_valid_workflow_and_defaults():
    config = parse_workflow(copy.deepcopy(BASE))
    assert config.workflow.id == "monthly-sales" and config.workflow.root == "."
    assert config.on_error == "stop"
    assert config.report.formats == ["json", "markdown"]
    assert config.inputs[0].on_empty_match == "fail" and config.inputs[0].encoding == "utf-8"
    assert config.parameters["period"].is_required is True
    assert config.steps[1].parameters == {
        "group_by": ["region"],
        "metrics": {"total": {"function": "sum", "column": "amount"}},
    }
    assert config.steps[0].inputs == ["sales_files"]


@pytest.mark.parametrize(
    "change, expected",
    [
        (lambda d: d.update(on_eror="stop"), "on_eror: unknown key"),
        (lambda d: d["workflow"].update(schema_version=2), "workflow.schema_version: Input should be 1"),
        (lambda d: d["workflow"].update(schema_version="1"), "workflow.schema_version: Input should be 1"),
        (lambda d: d["workflow"].update(id="Monthly Sales"), "workflow.id: String should match pattern"),
        (lambda d: d.update(on_error="retry"), "on_error: Input should be 'stop' or 'continue'"),
        (lambda d: d.update(inputs=[]), "inputs: List should have at least 1 item"),
        (lambda d: d.pop("outputs"), "outputs: Field required"),
        (lambda d: d["inputs"][0].update(type="parquet"), "inputs.0.type: Input should be 'csv' or 'xlsx'"),
        (lambda d: d["inputs"][0].update(sheet="Data"), "sheet only applies to xlsx inputs"),
        (lambda d: d["inputs"][0].update(delimiter=";;"), "delimiter must be a single character"),
        (lambda d: d["inputs"][0].update(encoding="klingon"), "unknown encoding 'klingon'"),
        (lambda d: d["inputs"][0].update(required_columns=["a", "a"]), "lists a column more than once"),
        (lambda d: d["inputs"][0].update(on_empty_match="ignore"), "on_empty_match: Input should be 'fail' or 'warn'"),
        (lambda d: d["outputs"][0].update(path="output/sales.xlsx"), "path must end with .csv"),
        (lambda d: d["outputs"][0].update(sheet_name="S"), "sheet_name only applies to xlsx outputs"),
        (lambda d: d["outputs"][0].update(colour="red"), "outputs.0.colour: unknown key"),
        (lambda d: d["steps"][0].update(input=[]), "input list must be non-empty"),
        (lambda d: d["steps"][0].update(type="Concat-Files"), "steps.0.type: String should match pattern"),
        (lambda d: d["parameters"]["period"].update(type="week"), "parameters.period.type"),
        (lambda d: d["parameters"]["period"].update(default="2026-13"), "default '2026-13' must be a month"),
        (lambda d: d["parameters"]["period"].update(default="2026-09", required=True), "cannot be required"),
        (lambda d: d.update(report={"formats": ["json", "json"]}), "report.formats: formats lists a value"),
        (lambda d: d.update(report={"formats": []}), "report.formats: List should have at least 1 item"),
    ],
)
def test_invalid_values_are_rejected_with_their_location(change, expected):
    issues = _issues(_with(change))
    assert any(expected in issue for issue in issues), issues


def test_yaml_coercions_are_not_silently_accepted():
    """YAML 1.1 reads 007 as the integer 7 and NO as False: strict models refuse them."""
    issues = _issues(_with(lambda d: d["outputs"][0].update(sheet_name=7)))
    assert any("outputs.0.sheet_name: Input should be a valid string (got 7)" in i for i in issues)
    issues = _issues(_with(lambda d: d["parameters"]["period"].update(default=False)))
    assert any("parameters.period.default" in i for i in issues)


@pytest.mark.parametrize("value", ["no", "yes", "true", 1, 0])
def test_booleans_must_be_real_booleans(value):
    """Lax validation would turn "no" into False or 1 into True; strict mode refuses."""
    issues = _issues(_with(lambda d: d["parameters"]["period"].update(required=value)))
    assert any(i.startswith("parameters.period.required: Input should be a valid boolean") for i in issues), issues


def test_all_problems_are_reported_at_once():
    data = _with(lambda d: (d.update(on_eror="x"), d["inputs"][0].update(type="txt"), d["workflow"].pop("id")))
    issues = _issues(data)
    assert len(issues) == 3
    assert {i.split(":")[0] for i in issues} == {"on_eror", "inputs.0.type", "workflow.id"}


def test_xlsx_input_rejects_csv_only_options():
    issues = _issues(_with(lambda d: d["inputs"][0].update(type="xlsx", delimiter=";")))
    assert any("encoding and delimiter only apply to csv inputs" in i for i in issues)


def test_parameter_with_default_is_optional():
    data = _with(lambda d: d["parameters"]["period"].update(default="2026-09"))
    assert parse_workflow(data).parameters["period"].is_required is False
