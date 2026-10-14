"""Strict, safe YAML loading for workflow files.

Built on PyYAML's ``SafeLoader`` (never the full loader), with three extra rules that
prevent silent surprises:

* duplicate keys are rejected (PyYAML would silently keep the last value);
* aliases and anchors are rejected (workflows do not need them, and alias expansion can
  be abused to build huge documents);
* files larger than :data:`MAX_FILE_BYTES` are rejected.

Python-specific tags such as ``!!python/object`` are refused by ``SafeLoader`` itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import WorkflowLoadError

MAX_FILE_BYTES = 1024 * 1024


class _StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys and aliases."""

    def compose_node(self, parent: Any, index: Any) -> Any:  # type: ignore[override]
        # Checked on the parser event, before any node is built or any alias expanded.
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent):
            raise yaml.constructor.ConstructorError(
                None, None, "YAML aliases (*name) are not allowed in workflow files", event.start_mark
            )
        if getattr(event, "anchor", None) is not None:
            raise yaml.constructor.ConstructorError(
                None, None, "YAML anchors (&name) are not allowed in workflow files", event.start_mark
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: dict[Any, Any] = {}
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"key {key!r} is not text: YAML reads on/off/yes/no/true/false as booleans and digits as numbers; "
                    "put the key in quotes",
                    key_node.start_mark,
                )
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark, f"duplicate key {key!r}", key_node.start_mark
                )
            seen[key] = True
        return super().construct_mapping(node, deep=deep)


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Load a workflow file and return its top-level mapping.

    Raises:
        WorkflowLoadError: The file is missing, too large, not UTF-8, not valid YAML,
            uses a forbidden YAML feature, or does not contain a mapping.
    """
    if not path.exists():
        raise WorkflowLoadError(f"Workflow file not found: {path}")
    if not path.is_file():
        raise WorkflowLoadError(f"Workflow path is not a file: {path}")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise WorkflowLoadError(f"{path.name} is {size} bytes; workflow files are limited to {MAX_FILE_BYTES} bytes.")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise WorkflowLoadError(f"{path.name} is not valid UTF-8 (byte {exc.start}).") from exc
    except OSError as exc:
        raise WorkflowLoadError(f"Cannot read {path}: {exc}") from exc
    try:
        data = yaml.load(text, Loader=_StrictSafeLoader)  # noqa: S506 - _StrictSafeLoader derives from SafeLoader
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark is not None else ""
        raise WorkflowLoadError(f"{path.name}: {exc.problem}{where}") from exc
    except yaml.YAMLError as exc:
        raise WorkflowLoadError(f"{path.name}: invalid YAML: {exc}") from exc
    if data is None:
        raise WorkflowLoadError(f"{path.name} is empty.")
    if not isinstance(data, dict):
        raise WorkflowLoadError(f"{path.name} must contain a mapping (key: value) at the top level.")
    return data
