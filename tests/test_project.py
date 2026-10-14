"""Packaging, documentation and scope stay consistent with the code."""

from __future__ import annotations

import ast
import re
import shlex
import sys
import tomllib
from pathlib import Path

import pytest

import data_automation
from data_automation.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def _name(spec: str) -> str:
    return re.split(r"[<>=!~ ]", spec, maxsplit=1)[0].lower().replace("_", "-")


def test_version_and_entry_point():
    assert PYPROJECT["project"]["version"] == data_automation.__version__
    assert PYPROJECT["project"]["scripts"] == {"data-automate": "data_automation.cli:main"}
    assert PYPROJECT["project"]["license"] == "MIT"
    assert "LUMU BAMANA MANASSE" in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_runtime_dependencies_are_exactly_what_the_code_imports():
    declared = {_name(s) for s in PYPROJECT["project"]["dependencies"]}
    assert declared == {"defusedxml", "openpyxl", "pandas", "pydantic", "pyyaml"}
    imported = set()
    for path in (ROOT / "src" / "data_automation").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add(node.module.split(".")[0])
    third_party = imported - set(sys.stdlib_module_names) - {"__future__"}
    assert third_party == {"defusedxml", "openpyxl", "pandas", "pydantic", "yaml"}


def test_no_dependency_on_service_1():
    """ADR-0008: the package never imports or requires data_cleaning (service 1)."""
    code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))
    assert "data_cleaning" not in code
    assert not any("cleaning" in s for s in PYPROJECT["project"]["dependencies"])


def test_constraints_pin_every_declared_dependency():
    pinned = {}
    for line in (ROOT / "constraints.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split("==")
            pinned[_name(name)] = version
    for spec in PYPROJECT["project"]["dependencies"] + PYPROJECT["project"]["optional-dependencies"]["dev"]:
        assert _name(spec) in pinned, f"{spec} is not pinned in constraints.txt"


def test_package_modules():
    """The package contains exactly the documented modules (docs/architecture.md)."""
    package = ROOT / "src" / "data_automation"
    assert sorted(p.name for p in package.glob("*.py")) == [
        "__init__.py",
        "__main__.py",
        "cli.py",
        "config.py",
        "dataset.py",
        "engine.py",
        "errors.py",
        "log.py",
        "parameters.py",
        "paths.py",
        "readers.py",
        "registry.py",
        "reporting.py",
        "types.py",
        "validation.py",
        "writers.py",
        "yaml_loader.py",
    ]
    assert sorted(p.name for p in (package / "steps").glob("*.py")) == [
        "__init__.py",
        "_common.py",
        "aggregate.py",
        "columns.py",
        "combine.py",
        "rows.py",
    ]
    assert sorted(p.name for p in package.iterdir() if p.is_dir() and p.name != "__pycache__") == ["steps"]


def _slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_and_anchors_resolve(doc):
    text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://")):
            continue
        path, _, anchor = target.partition("#")
        dest = (doc.parent / path) if path else doc
        assert dest.exists(), f"{doc.name}: broken link {target}"
        if anchor:
            headings = re.findall(r"^#{1,6} (.+)$", dest.read_text(encoding="utf-8"), flags=re.M)
            assert anchor in {_slug(h) for h in headings}, f"{doc.name}: missing anchor #{anchor}"


def test_readme_commands_are_valid_for_the_real_parser():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    commands = [
        line
        for block in re.findall(r"```bash\n(.*?)```", text, flags=re.S)
        for line in block.splitlines()
        if line.startswith(("data-automate ", "python -m data_automation "))
    ]
    assert len(commands) == 4
    parser = build_parser()
    for line in commands:
        argv = shlex.split(line)
        argv = argv[1:] if argv[0] == "data-automate" else argv[3:]
        args = parser.parse_args(argv)
        if args.command != "steps":
            assert (ROOT / args.workflow).exists()


def test_readme_output_excerpt_matches_the_real_command(capsys):
    from data_automation.cli import main

    text = (ROOT / "README.md").read_text(encoding="utf-8")
    excerpt = re.search(r"```text\n(Workflow: .*?)```", text, flags=re.S).group(1).strip().splitlines()
    assert main(["validate", str(ROOT / "config/examples/monthly_sales.yaml"), "--param", "period=2026-09"]) == 0
    actual = capsys.readouterr().out.splitlines()
    for line in excerpt:
        if line.startswith("Workflow:"):
            assert line.split(" (")[0] in actual[0]
            continue
        assert line in actual, line
