"""PR585 package discovery regression: import each initializer by package name."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("command", ["list", "init", "explicit_then_auto"])
def test_package_initializer_registers_once__r585_pkg_1(tmp_path: Path, nested: bool, command: str) -> None:
    """R585-PKG-1: package skeletons remain unambiguous by their short names."""
    # Given: a skeleton declared in a conventional package initializer
    package = tmp_path / "modules"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    module_name = "modules"
    if nested:
        package = package / "nested"
        package.mkdir()
        module_name += ".nested"
    (package / "__init__.py").write_text('''from typing import final
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths
class PackageSkeleton(ProcessingTemplate):
    @slot
    def read(self, paths: InputPaths) -> None: ...
    @final
    def __flow__(self, paths: InputPaths) -> None:
        self.read(paths)
''', encoding="utf-8")
    arguments = ["skeletons", "list", "--json"] if command == "list" else ["new", "processing", "PackageSkeleton"]
    # When: invoking the installed CLI in a fresh production-like process
    invocation = [sys.executable, "-m", "rdetoolkit", *arguments]
    if command == "explicit_then_auto":
        script = (
            "from typer.testing import CliRunner\n"
            "from rdetoolkit.cli.app import app\n"
            f"first = CliRunner().invoke(app, ['templates', 'list', '--json', '--module', {module_name!r}])\n"
            "assert first.exit_code == 0, first.output\n"
            "second = CliRunner().invoke(app, ['templates', 'list', '--json'])\n"
            "assert second.exit_code == 0, second.output\n"
            "print(second.output)\n"
        )
        invocation = [sys.executable, "-c", script]
    result = subprocess.run(invocation, cwd=tmp_path, capture_output=True, text=True, check=False, timeout=60)
    # Then: canonical package identity is unique and short-name generation works
    assert result.returncode == 0, result.stdout + result.stderr
    if command != "init":
        entries = json.loads(result.stdout)
        assert [entry["id"] for entry in entries if entry["name"] == "PackageSkeleton"] == [f"{module_name}.PackageSkeleton"]
    else:
        assert f"from {module_name} import PackageSkeleton" in (tmp_path / "processing.py").read_text()
        assert (tmp_path / "main.py").is_file()
