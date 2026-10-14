"""Strict, safe YAML loading."""

from __future__ import annotations

import pytest

from data_automation.errors import WorkflowLoadError
from data_automation.yaml_loader import MAX_FILE_BYTES, load_yaml_mapping


def _write(tmp_path, text, encoding="utf-8"):
    path = tmp_path / "w.yaml"
    path.write_bytes(text.encode(encoding))
    return path


def test_plain_mapping_is_loaded(tmp_path):
    assert load_yaml_mapping(_write(tmp_path, "a: 1\nb: [x, y]\n")) == {"a": 1, "b": ["x", "y"]}


def test_utf8_bom_is_accepted(tmp_path):
    assert load_yaml_mapping(_write(tmp_path, "a: é\n", encoding="utf-8-sig")) == {"a": "é"}


@pytest.mark.parametrize(
    "text",
    [
        '!!python/object/apply:os.system ["echo hacked"]',
        "a: !!python/name:os.system\n",
        "a: !!python/object:builtins.dict {}\n",
    ],
)
def test_python_tags_are_refused(tmp_path, text):
    with pytest.raises(WorkflowLoadError, match="could not determine a constructor"):
        load_yaml_mapping(_write(tmp_path, text))


def test_duplicate_keys_are_refused_with_line(tmp_path):
    """Regression guard: PyYAML alone silently keeps the last value."""
    with pytest.raises(WorkflowLoadError, match=r"duplicate key 'on_error' \(line 2, column 1\)"):
        load_yaml_mapping(_write(tmp_path, "on_error: stop\non_error: continue\n"))


def test_nested_duplicate_keys_are_refused(tmp_path):
    with pytest.raises(WorkflowLoadError, match="duplicate key 'id'"):
        load_yaml_mapping(_write(tmp_path, "workflow:\n  id: a\n  id: b\n"))


def test_aliases_and_anchors_are_refused(tmp_path):
    with pytest.raises(WorkflowLoadError, match="anchors"):
        load_yaml_mapping(_write(tmp_path, "a: &x [1]\nb: 2\n"))
    with pytest.raises(WorkflowLoadError, match="anchors|aliases"):
        load_yaml_mapping(_write(tmp_path, "a: &x [1]\nb: *x\n"))


def test_alias_bomb_is_refused_without_expansion(tmp_path):
    bomb = "a: &a [x, x]\nb: &b [*a, *a]\nc: &c [*b, *b]\nd: [*c, *c, *c, *c]\n"
    with pytest.raises(WorkflowLoadError):
        load_yaml_mapping(_write(tmp_path, bomb))


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "is empty"),
        ("# only a comment\n", "is empty"),
        ("- a\n- b\n", "must contain a mapping"),
        ("just text\n", "must contain a mapping"),
        ("a: [1, 2\n", r"line \d+"),
    ],
)
def test_malformed_or_non_mapping_content(tmp_path, text, message):
    with pytest.raises(WorkflowLoadError, match=message):
        load_yaml_mapping(_write(tmp_path, text))


def test_missing_file_folder_size_and_encoding(tmp_path):
    with pytest.raises(WorkflowLoadError, match="not found"):
        load_yaml_mapping(tmp_path / "missing.yaml")
    with pytest.raises(WorkflowLoadError, match="not a file"):
        load_yaml_mapping(tmp_path)
    big = tmp_path / "big.yaml"
    big.write_bytes(b"a: 1\n" + b"#" * MAX_FILE_BYTES)
    with pytest.raises(WorkflowLoadError, match="limited to"):
        load_yaml_mapping(big)
    with pytest.raises(WorkflowLoadError, match="not valid UTF-8"):
        load_yaml_mapping(_write(tmp_path, "a: é\n", encoding="cp1252"))
