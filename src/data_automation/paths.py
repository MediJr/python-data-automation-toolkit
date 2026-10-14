"""Working root and path safety (ADR-0006).

Rules:

* the root is declared relative to the workflow file's folder and must be an existing
  directory;
* every path in the workflow is relative to the root; absolute paths, drive letters and
  UNC paths are refused;
* after placeholders are replaced, a path must stay inside the root once normalized and
  once symbolic links are resolved;
* wildcards (``*``, ``?``, ``[...]``) are allowed only in the last part of an input path;
  ``**`` (recursive search) is not supported.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path, PurePath, PureWindowsPath

GLOB_CHARACTERS = frozenset("*?[")


class PathRuleError(ValueError):
    """A configured path breaks one of the path rules."""


def has_wildcard(text: str) -> bool:
    return any(ch in GLOB_CHARACTERS for ch in text)


def _is_absolute(text: str) -> bool:
    return (
        PurePath(text).is_absolute()
        or PureWindowsPath(text).is_absolute()
        or bool(PureWindowsPath(text).drive)
        or text.startswith(("/", "\\"))
    )


def resolve_root(workflow_file: Path, root: str) -> Path:
    """Return the absolute working root for ``workflow_file``.

    Raises:
        PathRuleError: The root is absolute, contains a wildcard, or is not an existing directory.
    """
    if _is_absolute(root):
        raise PathRuleError("the root must be relative to the workflow file's folder (absolute paths are not portable)")
    if has_wildcard(root):
        raise PathRuleError("the root must not contain wildcards")
    resolved = (workflow_file.resolve().parent / root).resolve()
    if not resolved.is_dir():
        raise PathRuleError(f"the root folder does not exist: {resolved}")
    return resolved


def inside(root: Path, candidate: Path) -> bool:
    """True if ``candidate`` is ``root`` or below it (both must be absolute)."""
    try:
        return os.path.commonpath([os.path.normcase(root), os.path.normcase(candidate)]) == os.path.normcase(root)
    except ValueError:  # different drives on Windows
        return False


def check_relative_path(text: str, *, allow_wildcards: bool) -> None:
    """Check the shape of a configured path before placeholders are replaced.

    Raises:
        PathRuleError: Absolute path, ``**``, or a wildcard where it is not allowed.
    """
    if _is_absolute(text):
        raise PathRuleError("absolute paths are not allowed; use a path relative to the root")
    parts = text.replace("\\", "/").split("/")
    if "**" in text:
        raise PathRuleError("recursive patterns (**) are not supported")
    if any(has_wildcard(part) for part in parts[:-1]):
        raise PathRuleError("wildcards are only allowed in the last part of a path")
    if has_wildcard(parts[-1]) and not allow_wildcards:
        raise PathRuleError("wildcards are not allowed in output paths")


def resolve_in_root(root: Path, text: str) -> Path:
    """Join ``text`` to ``root`` and check that the result stays inside the root.

    The folder part is resolved (symbolic links followed); the last part may be a pattern.

    Raises:
        PathRuleError: The path leaves the root.
    """
    joined = Path(os.path.normpath(root / text))
    if not inside(root, joined):
        raise PathRuleError("the path leaves the working root")
    folder = joined.parent.resolve()
    if not inside(root, folder):
        raise PathRuleError("the path leaves the working root through a symbolic link")
    return folder / joined.name


def find_matches(root: Path, pattern_path: Path) -> list[Path]:
    """Files matching ``pattern_path`` (last part may contain wildcards), sorted by name.

    Matches whose real location is outside the root (symbolic links) are excluded and
    returned separately by :func:`escaping_matches`.
    """
    folder = pattern_path.parent
    if not folder.is_dir():
        return []
    if not has_wildcard(pattern_path.name):
        return [pattern_path] if pattern_path.is_file() else []
    names = sorted(entry.name for entry in folder.iterdir() if entry.is_file())
    return [folder / name for name in names if fnmatch.fnmatch(name, pattern_path.name)]


def escaping_matches(root: Path, matches: list[Path]) -> list[Path]:
    """Matches whose resolved location is outside the root (e.g. symbolic links)."""
    return [path for path in matches if not inside(root, path.resolve())]


def relative_posix(root: Path, path: Path) -> str:
    """``path`` relative to ``root``, with forward slashes (for reports)."""
    return Path(os.path.relpath(path, root)).as_posix()
