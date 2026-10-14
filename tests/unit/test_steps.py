"""Built-in step types: real transformations on data, checked against hand-computed results."""

from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

import pandas as pd
import pytest

from data_automation import registry
from data_automation.dataset import Dataset, Part
from data_automation.registry import StepContext, StepFailure
from data_automation.types import python_values, to_series


def ds(name, columns, types, origin=None):
    return Dataset.from_columns(name, columns, types, origin)


def run(step_type, params, *inputs):
    parsed, problems = registry.validate_step(step_type, len(inputs), params)
    assert not problems, problems
    ctx = StepContext("run", "wf", "step_out", {}, logging.getLogger("test"))
    return registry.get(step_type).run(parsed, list(inputs), ctx)


def values(result, column):
    return python_values(result.dataset.frame()[column])


SALES = ds(
    "sales",
    {
        "region": ["North", "North", "South", "North", None],
        "status": ["closed", "open", "closed", "closed", "closed"],
        "amount": [Decimal("120.50"), Decimal("80"), Decimal("200.00"), Decimal("42.00"), Decimal("5")],
        "day": [dt.date(2026, 9, 1), dt.date(2026, 9, 2), dt.date(2026, 9, 3), None, dt.date(2026, 9, 30)],
    },
    {"region": "string", "status": "string", "amount": "decimal", "day": "date"},
)


# --------------------------------------------------------------------------- concatenate


def _multi_part(frames):
    parts = [Part(pd.DataFrame({c: to_series(t, v) for c, (t, v) in f.items()}), origin) for origin, f in frames]
    types = {c: t for _, f in frames for c, (t, _) in f.items()}
    return Dataset("files", list(frames[0][1]), types, parts)


def test_concatenate_aligns_columns_and_records_the_source():
    files = _multi_part(
        [
            ("in/a.csv", {"x": ("integer", [1, 2]), "y": ("string", ["a", "b"])}),
            ("in/b.csv", {"y": ("string", ["c"]), "x": ("integer", [3])}),
        ]
    )
    result = run("concatenate", {"add_source_column": "source"}, files)
    assert result.dataset.columns == ["x", "y", "source"]
    assert values(result, "x") == [1, 2, 3] and values(result, "y") == ["a", "b", "c"]
    assert values(result, "source") == ["in/a.csv", "in/a.csv", "in/b.csv"]
    assert result.details["rows_by_part"] == {"in/a.csv": 2, "in/b.csv": 1}


def test_concatenate_same_policy_refuses_different_columns_union_fills():
    files = _multi_part(
        [("a.csv", {"x": ("integer", [1])}), ("b.csv", {"x": ("integer", [2]), "z": ("string", ["q"])})]
    )
    with pytest.raises(StepFailure, match="b.csv has column 'z' that a.csv does not have"):
        run("concatenate", {}, files)
    result = run("concatenate", {"columns": "union"}, files)
    assert values(result, "z") == [None, "q"]
    assert "a.csv: column(s) z absent, filled with missing values" in result.warnings


def test_concatenate_refuses_type_conflicts():
    files = _multi_part([("a.csv", {"x": ("integer", [1])})])
    other = ds("other", {"x": ["1"]}, {"x": "string"})
    with pytest.raises(StepFailure, match="column 'x' is integer in a.csv but string in other"):
        run("concatenate", {}, files, other)


# --------------------------------------------------------------------------- filter


def test_filter_and_semantics_with_missing_values():
    result = run(
        "filter",
        {"where": [{"column": "status", "op": "eq", "value": "closed"}, {"column": "amount", "op": "ge", "value": 42}]},
        SALES,
    )
    assert values(result, "amount") == [Decimal("120.50"), Decimal("200.00"), Decimal("42.00")]
    assert result.details == {"rows_in": 5, "rows_out": 3, "rows_removed": 2}
    # a missing value never satisfies a comparison, not even 'ne'
    result = run("filter", {"where": [{"column": "region", "op": "ne", "value": "North"}]}, SALES)
    assert values(result, "region") == ["South"]
    result = run("filter", {"where": [{"column": "region", "op": "is_null"}]}, SALES)
    assert values(result, "amount") == [Decimal("5")]


@pytest.mark.parametrize(
    "condition, expected_amounts",
    [
        ({"column": "region", "op": "in", "value": ["South", "West"]}, ["200.00"]),
        ({"column": "region", "op": "not_in", "value": ["North"]}, ["200.00"]),
        ({"column": "day", "op": "between", "value": ["2026-09-02", "2026-09-30"]}, ["80", "200.00", "5"]),
        ({"column": "day", "op": "lt", "value": dt.date(2026, 9, 2)}, ["120.50"]),  # a date already parsed by YAML
        ({"column": "status", "op": "contains", "value": "pe"}, ["80"]),
        ({"column": "day", "op": "not_null"}, ["120.50", "80", "200.00", "5"]),
    ],
)
def test_filter_operators(condition, expected_amounts):
    result = run("filter", {"where": [condition]}, SALES)
    assert [str(v) for v in values(result, "amount")] == expected_amounts


@pytest.mark.parametrize(
    "condition, message",
    [
        ({"column": "amount", "op": "eq", "value": "lots"}, "condition on 'amount' \\(decimal\\)"),
        ({"column": "status", "op": "gt", "value": 3}, "is not text"),
        ({"column": "amount", "op": "contains", "value": "1"}, "only applies to string columns"),
        ({"column": "missing", "op": "eq", "value": 1}, "column\\(s\\) 'missing' not found"),
    ],
)
def test_filter_runtime_errors(condition, message):
    with pytest.raises(StepFailure, match=message):
        run("filter", {"where": [condition]}, SALES)


def test_filter_compares_with_a_run_parameter_by_name():
    """FR-19: a condition may take its value from a run parameter (looked up, never substituted)."""
    parsed, problems = registry.validate_step("filter", 1, {"where": [{"column": "day", "op": "ge", "param": "start"}]})
    assert not problems and parsed.parameter_references() == ["start"]
    ctx = StepContext("run", "wf", "step_out", {"start": "2026-09-03"}, logging.getLogger("test"))
    result = registry.get("filter").run(parsed, [SALES], ctx)
    assert values(result, "day") == [dt.date(2026, 9, 3), dt.date(2026, 9, 30)]
    ctx = StepContext("run", "wf", "step_out", {"start": "September"}, logging.getLogger("test"))
    with pytest.raises(StepFailure, match=r"condition on 'day' \(date\) \(parameter 'start'\)"):
        registry.get("filter").run(parsed, [SALES], ctx)


@pytest.mark.parametrize(
    "where, message",
    [
        ([{"column": "a", "op": "eq"}], "needs a value"),
        ([{"column": "a", "op": "is_null", "value": 1}], "takes no value"),
        ([{"column": "a", "op": "in", "value": "x"}], "non-empty list"),
        ([{"column": "a", "op": "between", "value": [1]}], "two values"),
        ([{"column": "a", "op": "query", "value": "a > 1"}], "where.0.op"),
        ([{"column": "a", "op": "eq", "value": 1, "expr": "__import__('os')"}], "unknown key"),
        ([{"column": "a", "op": "eq", "value": 1, "param": "p"}], "either value or param"),
        ([{"column": "a", "op": "in", "param": "p"}], "cannot take a param"),
        ([{"column": "a", "op": "eq", "param": "{p}"}], "where.0.param"),
    ],
)
def test_filter_definitions_are_validated_and_never_evaluated(where, message):
    _, problems = registry.validate_step("filter", 1, {"where": where})
    assert any(message in p for p in problems), problems


# --------------------------------------------------------------------------- columns


def test_select_rename_cast():
    selected = run("select", {"columns": ["amount", "region"]}, SALES)
    assert selected.dataset.columns == ["amount", "region"]
    renamed = run("rename", {"columns": {"amount": "revenue"}}, SALES)
    assert renamed.dataset.columns == ["region", "status", "revenue", "day"]
    assert renamed.dataset.types["revenue"] == "decimal"
    with pytest.raises(StepFailure, match="duplicate column"):
        run("rename", {"columns": {"amount": "region"}}, SALES)
    text = ds("t", {"n": ["1", " 2 ", "", None], "d": ["30/09/2026", None, None, None]}, {"n": "string", "d": "string"})
    cast = run("cast", {"columns": {"n": "integer", "d": {"type": "date", "format": "%d/%m/%Y"}}}, text)
    assert values(cast, "n") == [1, 2, None, None]  # empty text becomes missing, never 0
    assert values(cast, "d")[0] == dt.date(2026, 9, 30)
    assert cast.dataset.types == {"n": "integer", "d": "date"}


def test_cast_failures_are_reported_with_rows():
    text = ds("t", {"n": ["1", "x", "2.5"]}, {"n": "string"})
    with pytest.raises(StepFailure, match=r"2 value\(s\) of 'n' are not valid integer \(row 2: 'x', row 3: '2.5'\)"):
        run("cast", {"columns": {"n": "integer"}}, text)


def test_sort_is_stable_with_missing_last():
    result = run("sort", {"by": [{"column": "region"}, {"column": "amount", "descending": True}]}, SALES)
    assert values(result, "region") == ["North", "North", "North", "South", None]
    assert values(result, "amount")[:3] == [Decimal("120.50"), Decimal("80"), Decimal("42.00")]


# --------------------------------------------------------------------------- aggregate


def test_aggregate_hand_computed_kpis():
    result = run(
        "aggregate",
        {
            "group_by": ["region"],
            "metrics": {
                "total": {"function": "sum", "column": "amount"},
                "orders": {"function": "count"},
                "average": {"function": "mean", "column": "amount", "round": 2},
                "first_day": {"function": "min", "column": "day"},
                "days_known": {"function": "count", "column": "day"},
            },
        },
        SALES,
    )
    assert values(result, "region") == ["North", "South", None]  # sorted, missing key last
    assert values(result, "total") == [Decimal("242.50"), Decimal("200.00"), Decimal("5")]
    assert values(result, "orders") == [3, 1, 1]
    assert values(result, "average") == [Decimal("80.83"), Decimal("200.00"), Decimal("5.00")]  # 242.50 / 3, half-up
    assert values(result, "first_day") == [dt.date(2026, 9, 1), dt.date(2026, 9, 3), dt.date(2026, 9, 30)]
    assert values(result, "days_known") == [2, 1, 1]
    assert result.dataset.types == {
        "region": "string",
        "total": "decimal",
        "orders": "integer",
        "average": "decimal",
        "first_day": "date",
        "days_known": "integer",
    }


def test_aggregate_never_fabricates_zero():
    empty = ds("e", {"amount": []}, {"amount": "decimal"})
    result = run(
        "aggregate", {"metrics": {"n": {"function": "count"}, "total": {"function": "sum", "column": "amount"}}}, empty
    )
    assert values(result, "n") == [0] and values(result, "total") == [None]


def test_aggregate_type_errors():
    with pytest.raises(StepFailure, match="sum needs an integer or decimal column"):
        run("aggregate", {"metrics": {"t": {"function": "sum", "column": "status"}}}, SALES)
    _, problems = registry.validate_step(
        "aggregate", 1, {"group_by": ["total"], "metrics": {"total": {"function": "count"}}}
    )
    assert any("clash" in p for p in problems)


# --------------------------------------------------------------------------- join (AC-16)

ORDERS = ds(
    "orders",
    {"region": ["North", "South", "East", None], "amount": [Decimal(1), Decimal(2), Decimal(3), Decimal(4)]},
    {"region": "string", "amount": "decimal"},
)
TARGETS = ds(
    "targets",
    {"region": ["North", "South", None], "target": [Decimal(10), Decimal(20), Decimal(99)]},
    {"region": "string", "target": "decimal"},
)


def test_join_many_to_one_left_keeps_rows_and_never_matches_missing_keys():
    result = run("join", {"keys": ["region"], "relationship": "many_to_one", "how": "left"}, ORDERS, TARGETS)
    assert values(result, "region") == ["North", "South", "East", None]
    assert values(result, "target") == [Decimal(10), Decimal(20), None, None]  # NA key did not match NA key
    assert result.details["unmatched_left"] == 2


def test_join_inner_and_require_match():
    inner = run("join", {"keys": ["region"], "relationship": "many_to_one"}, ORDERS, TARGETS)
    assert values(inner, "region") == ["North", "South"]
    with pytest.raises(StepFailure, match=r"require_match: 2 left row\(s\) have no matching row"):
        run("join", {"keys": ["region"], "relationship": "many_to_one", "require_match": True}, ORDERS, TARGETS)


def test_join_relationship_violation_fails_instead_of_multiplying_rows():
    duplicated = ds(
        "t",
        {"region": ["North", "North"], "target": [Decimal(1), Decimal(2)]},
        {"region": "string", "target": "decimal"},
    )
    with pytest.raises(
        StepFailure,
        match=r"relationship many_to_one violated: 1 key value\(s\) appear more than once on the right side",
    ):
        run("join", {"keys": ["region"], "relationship": "many_to_one"}, ORDERS, duplicated)


def test_join_overlapping_columns_get_suffixes_and_key_types_must_match():
    other = ds("o", {"region": ["North"], "amount": [Decimal(9)]}, {"region": "string", "amount": "decimal"})
    result = run("join", {"keys": ["region"], "relationship": "one_to_one"}, ORDERS, other)
    assert result.dataset.columns == ["region", "amount_left", "amount_right"]
    numeric = ds("n", {"region": [1]}, {"region": "integer"})
    with pytest.raises(StepFailure, match="key 'region' is string on the left but integer on the right"):
        run("join", {"keys": ["region"], "relationship": "many_to_one"}, ORDERS, numeric)


# --------------------------------------------------------------------------- check


def test_check_passes_data_through_or_fails_with_reasons():
    ok = run("check", {"min_rows": 1, "not_null": ["status"], "allowed_values": {"status": ["open", "closed"]}}, SALES)
    assert ok.dataset.rows == 5
    with pytest.raises(StepFailure) as info:
        run("check", {"max_rows": 3, "not_null": ["region"], "unique": ["region"]}, SALES)
    message = str(info.value)
    assert "5 row(s), at most 3 expected" in message
    assert "1 missing value(s) in 'region' (data rows 5)" in message
    assert "3 row(s) share the same ['region']" in message


def test_multi_part_dataset_must_be_concatenated_first():
    files = _multi_part([("a.csv", {"x": ("integer", [1])}), ("b.csv", {"x": ("integer", [2])})])
    with pytest.raises(StepFailure, match="has 2 parts"):
        run("sort", {"by": [{"column": "x"}]}, files)
