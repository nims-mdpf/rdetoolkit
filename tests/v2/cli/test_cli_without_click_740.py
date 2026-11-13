"""The CLI works with a typer that vendors click and no ``click`` package (#740).

typer 0.26 and later no longer depend on ``click``: they ship a copy as
``typer._click``. rdetoolkit must therefore reach click only through typer.

| Test ID | Target | Condition | Expected |
|---|---|---|---|
| TC-740-SRC-001 | every module and stub under ``src/rdetoolkit`` | parse imports | none imports ``click`` |
| TC-740-RUN-001 | ``rdetoolkit --help`` | ``click`` unimportable, typer vendors click | exit 0, root help printed |
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "rdetoolkit"

#: Runs ``rdetoolkit --help`` with every ``click`` import failing.
_HELP_WITHOUT_CLICK = """
import importlib.abc
import runpy
import sys


class _BlockClick(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "click" or name.startswith("click."):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None


sys.meta_path.insert(0, _BlockClick())
sys.argv = ["rdetoolkit", "--help"]
runpy.run_module("rdetoolkit", run_name="__main__", alter_sys=True)
"""


def _imports_click(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == "click" or alias.name.startswith("click.") for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.level == 0 and node.module is not None and (node.module == "click" or node.module.startswith("click."))
    return False


def test_no_module_imports_click_directly__tc_740_src_001() -> None:
    # Given: every Python module and type stub of the package
    sources = sorted([*SRC_ROOT.rglob("*.py"), *SRC_ROOT.rglob("*.pyi")])
    assert sources

    # When: collecting the imports of click
    offenders = [
        f"{path.relative_to(SRC_ROOT.parent)}:{node.lineno}"
        for path in sources
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        if _imports_click(node)
    ]

    # Then: there are none; click is reached through typer only
    assert offenders == []


@pytest.mark.skipif(
    importlib.util.find_spec("typer._click") is None,
    reason="this typer depends on the click package (typer < 0.26)",
)
def test_root_help_runs_without_click__tc_740_run_001() -> None:
    # When: running the CLI where no click package can be imported
    result = subprocess.run(
        [sys.executable, "-c", _HELP_WITHOUT_CLICK],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={**os.environ, "COLUMNS": "200", "NO_COLOR": "1"},
    )

    # Then: the root help is printed
    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout
    assert "Build, run, and package RDE" in result.stdout
