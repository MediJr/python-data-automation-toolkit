"""Run parameters and working-root path rules."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from data_automation.errors import ParameterError
from data_automation.parameters import parse_cli_parameters, parse_value, placeholders, render
from data_automation.paths import (
    PathRuleError,
    check_relative_path,
    escaping_matches,
    find_matches,
    inside,
    resolve_in_root,
    resolve_root,
)


@pytest.mark.parametrize(
    "kind, raw, expected",
    [
        ("month", "2026-09", "2026-09"),
        ("date", "2026-02-28", "2026-02-28"),
        ("integer", "+42", "42"),
        ("string", "north", "north"),
    ],
)
def test_parameter_values_are_parsed(kind, raw, expected):
    assert parse_value(kind, raw) == expected


@pytest.mark.parametrize(
    "kind, raw",
    [
        ("month", "2026-13"),
        ("month", "2026-9"),
        ("month", "09-2026"),
        ("date", "2026-02-30"),
        ("date", "2026-2-1"),
        ("date", "01/02/2026"),
        ("integer", "4.2"),
        ("integer", ""),
        ("string", ""),
        ("string", "../x"),
        ("string", "a/b"),
        ("string", "a\\b"),
        ("string", " padded"),
    ],
)
def test_malformed_parameter_values_are_refused(kind, raw):
    with pytest.raises(ValueError):
        parse_value(kind, raw)


def test_cli_parameter_parsing():
    assert parse_cli_parameters(["period=2026-09", "region=north"]) == {"period": "2026-09", "region": "north"}
    assert parse_cli_parameters(["note=a=b"]) == {"note": "a=b"}
    for bad, message in (
        (["period"], "expected name=value"),
        (["Period=1"], "invalid parameter name"),
        (["p=1", "p=2"], "more than once"),
    ):
        with pytest.raises(ParameterError, match=message):
            parse_cli_parameters(bad)


def test_placeholders_are_substituted_without_format_semantics():
    assert placeholders("in/{period}/x_{region}.csv") == ["period", "region"]
    assert render("in/{period}/x.csv", {"period": "2026-09"}) == "in/2026-09/x.csv"
    # str.format would resolve attributes; plain substitution only knows declared names
    assert placeholders("{period.__class__}") == ["period.__class__"]
    with pytest.raises(KeyError):
        render("{period.__class__}", {"period": "x"})


def test_root_is_relative_and_must_exist(tmp_path):
    workflow = tmp_path / "config" / "w.yaml"
    workflow.parent.mkdir()
    workflow.write_text("x", encoding="utf-8")
    assert resolve_root(workflow, "..") == tmp_path.resolve()
    assert resolve_root(workflow, ".") == (tmp_path / "config").resolve()
    with pytest.raises(PathRuleError, match="relative"):
        resolve_root(workflow, str(tmp_path))
    with pytest.raises(PathRuleError, match="does not exist"):
        resolve_root(workflow, "missing")
    with pytest.raises(PathRuleError, match="wildcards"):
        resolve_root(workflow, "*")


@pytest.mark.parametrize(
    "text, allow, message",
    [
        ("C:/data/x.csv", True, "absolute"),
        ("C:x.csv", True, "absolute"),
        ("/etc/x.csv", True, "absolute"),
        ("\\\\server\\share\\x.csv", True, "absolute"),
        ("in/**/x.csv", True, "recursive"),
        ("in*/x.csv", True, "last part"),
        ("out/x_*.csv", False, "not allowed in output paths"),
    ],
)
def test_path_shape_rules(text, allow, message):
    with pytest.raises(PathRuleError, match=message):
        check_relative_path(text, allow_wildcards=allow)


def test_relative_paths_with_wildcards_in_last_part_are_accepted():
    check_relative_path("in/2026-09/sales_*.csv", allow_wildcards=True)
    check_relative_path("out/result.csv", allow_wildcards=False)


def test_traversal_outside_the_root_is_refused(tmp_path):
    root = tmp_path.resolve()
    assert resolve_in_root(root, "a/../b/x.csv") == root / "b" / "x.csv"
    # leaving and re-entering the same folder is allowed: the normalized path is inside
    assert inside(root, resolve_in_root(root, "a/../../" + tmp_path.name + "/x.csv"))
    for text in ("../x.csv", "a/../../x.csv", "../" + tmp_path.name + "_other/x.csv"):
        # the message must name the real cause, not a symbolic link
        with pytest.raises(PathRuleError, match=r"^the path leaves the working root$"):
            resolve_in_root(root, text)


def test_symbolic_link_escape_is_refused(tmp_path):
    root = (tmp_path / "root").resolve()
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.csv").write_text("x", encoding="utf-8")
    try:
        os.symlink(outside, root / "link", target_is_directory=True)
    except OSError:
        pytest.skip("creating symbolic links is not permitted in this environment")
    with pytest.raises(PathRuleError, match="symbolic link"):
        resolve_in_root(root, "link/secret.csv")


@pytest.mark.skipif(os.name != "nt", reason="directory junctions are a Windows feature")
def test_directory_junction_escape_is_refused(tmp_path):
    """Junctions need no special privilege on Windows, so the link check is always exercised there."""
    import _winapi

    root = (tmp_path / "root").resolve()
    outside = (tmp_path / "outside").resolve()
    root.mkdir()
    outside.mkdir()
    (outside / "secret.csv").write_text("x", encoding="utf-8")
    _winapi.CreateJunction(str(outside), str(root / "link"))
    with pytest.raises(PathRuleError, match="symbolic link"):
        resolve_in_root(root, "link/secret.csv")
    assert escaping_matches(root, [root / "link" / "secret.csv"]) == [root / "link" / "secret.csv"]


def test_find_matches_sorted_and_files_only(tmp_path):
    root = tmp_path.resolve()
    folder = root / "in"
    folder.mkdir()
    for name in ("sales_b.csv", "sales_a.csv", "other.csv"):
        (folder / name).write_text("x", encoding="utf-8")
    (folder / "sales_dir.csv").mkdir()
    assert [p.name for p in find_matches(root, folder / "sales_*.csv")] == ["sales_a.csv", "sales_b.csv"]
    assert [p.name for p in find_matches(root, folder / "other.csv")] == ["other.csv"]
    assert find_matches(root, root / "missing" / "*.csv") == []
    assert find_matches(root, folder / "nothing_*.csv") == []
    assert isinstance(find_matches(root, folder / "other.csv")[0], Path)
