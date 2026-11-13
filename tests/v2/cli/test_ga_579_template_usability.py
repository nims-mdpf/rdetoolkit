"""GA579 EP/BV: templates are diagnosable, discoverable and wired on init."""

from __future__ import annotations

import importlib
import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit import workflows
from rdetoolkit.cli.app import app
from rdetoolkit.errors import RdeRegistryError
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


def _provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, package: bool = False) -> str:
    name = 'ga579_' + tmp_path.name.replace('-', '_')
    directory = tmp_path
    if package:
        directory = tmp_path / "modules"
        directory.mkdir()
        (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / f"{name}.py").write_text('''from pathlib import Path
from typing import final
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths
class Measurement:
    pass
class Ga579Skeleton(ProcessingTemplate):
    @slot
    def read(self, path: Path) -> Measurement:
        """Read a measured domain object from a source file."""
    @final
    def __flow__(self, paths: InputPaths) -> None:
        self.read(paths.rawfiles[0])
class FirstProcessing(Ga579Skeleton):
    def read(self, path: Path) -> Measurement:
        return Measurement()
class SecondProcessing(Ga579Skeleton):
    def read(self, path: Path) -> Measurement:
        return Measurement()
''', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    if package:
        monkeypatch.delitem(sys.modules, "modules", raising=False)
    return ("modules." if package else "") + name


@pytest.mark.parametrize("signature", ["self", "self, wrong: Path", "self, path: str", "self, path: Path, extra: int = 0", "self, *, path: Path"])
def test_signature_error_shows_both_sides__ga579_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signature: str) -> None:
    """GA579-NEG-1: mismatches remain import errors and show a repairable signature."""
    # Given: an imported skeleton and a mismatching concrete slot
    module = importlib.import_module(_provider(tmp_path, monkeypatch))
    namespace = dict(vars(module))
    # When: defining the incompatible subclass
    with pytest.raises(RdeRegistryError) as raised:
        exec(f"class InvalidProcessing(Ga579Skeleton):\n    def read({signature}) -> Measurement:\n        pass\n", namespace)
    # Then: the catalogued diagnostic includes both declared and supplied forms
    assert raised.value.code == 2102
    message = str(raised.value).lower()
    assert "expected" in message and "actual" in message
    assert "path" in message and "read" in message


@pytest.mark.parametrize("package", [False, True])
def test_project_templates_discovered_without_module__ga579_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, package: bool) -> None:
    """GA579-EP-1: root and conventional modules packages can supply skeletons."""
    # Given: an unimported local skeleton
    name = _provider(tmp_path, monkeypatch, package)
    # When: listing then describing without --module
    result = CliRunner().invoke(app, ["skeletons", "list", "--json"])
    assert result.exit_code == 0, result.output
    assert any(item["id"] == f"{name}.Ga579Skeleton" for item in json.loads(result.output))
    described = CliRunner().invoke(app, ["skeletons", "show", f"{name}.Ga579Skeleton", "--json"])
    # Then: documentation names real domain types and omits stdlib Path
    assert described.exit_code == 0, described.output
    value = json.loads(described.output)
    assert value["slots"][0]["docstring"] == "Read a measured domain object from a source file."
    assert "pathlib.Path" not in value["domain_types"]
    assert f"{name}.Measurement" in value["domain_types"]


def test_init_generates_wired_main_and_usable_sample__ga579_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA579-BV-1: generated main calls the concrete class and reports failure."""
    # Given: a skeleton whose first slot accepts Path, not InputPaths
    name = _provider(tmp_path, monkeypatch)
    result = CliRunner().invoke(app, ["new", "processing", f"{name}.Ga579Skeleton", "--module", name])
    assert result.exit_code == 0, result.output
    sample = (tmp_path / "tests/test_processing.py").read_text()
    assert "read(rde_paths)" not in sample
    called: list[Any] = []

    def run(**kwargs: Any) -> Any:
        from types import SimpleNamespace
        called.append(kwargs["flow"])
        return SimpleNamespace(status=status, exit_code=exit_code)

    monkeypatch.setattr(workflows, "run", run)
    monkeypatch.delitem(sys.modules, "processing", raising=False)
    # When: executing the generated production entry
    for status, exit_code in [("success", 0), ("failed", 1), ("partial", 2)]:
        with pytest.raises(SystemExit) as raised:
            runpy.run_path(str(tmp_path / "main.py"), run_name="__main__")
        # Then: the concrete template is selected and the result controls the exit
        assert raised.value.code == exit_code
        assert called[-1].__name__ == "Ga579SkeletonProcessing"
    assert len(called) == 3


def test_existing_main_rejected_before_other_writes__ga579_neg_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA579-NEG-2: generation preflights the new entry file too."""
    # Given: a user-owned production entry
    name = _provider(tmp_path, monkeypatch)
    (tmp_path / "main.py").write_text("# user-owned entry\n", encoding="utf-8")
    # When: generating without the explicit force option
    result = CliRunner().invoke(app, ["new", "processing", f"{name}.Ga579Skeleton", "--module", name])
    # Then: every output remains untouched
    assert result.exit_code == 3
    assert (tmp_path / "main.py").read_text() == "# user-owned entry\n"
    assert not (tmp_path / "processing.py").exists()


def test_sibling_reports_have_concrete_identity__ga579_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA579-EP-2: existing concrete identity stays distinct across siblings."""
    # Given: two concrete implementations of one skeleton and a valid dataset
    module = importlib.import_module(_provider(tmp_path, monkeypatch))
    _build_tree(tmp_path / "data")
    # When: running the concrete classes through the public v2 entry
    first = workflows.run(flow=module.FirstProcessing)
    second = workflows.run(flow=module.SecondProcessing)
    # Then: the reports and node parents name the selected class
    assert first.status == second.status == "success"
    assert first.flow_id != second.flow_id
    for report in [first, second]:
        assert all(call["node_id"].startswith(report.flow_id + ".") for call in report.iterations[0]["node_calls"])


def test_alias_discovery_skips_unrelated_and_broken_sources__ga579_neg_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA579-NEG-3: provider aliases work without executing unrelated sources."""
    # Given: an aliased skeleton alongside scripts that must never be imported
    name = _provider(tmp_path, monkeypatch)
    path = tmp_path / f"{name}.py"
    source = path.read_text().replace("ProcessingTemplate, slot", "ProcessingTemplate as TemplateBase, slot").replace("(ProcessingTemplate):", "(TemplateBase):")
    path.write_text(source, encoding="utf-8")
    (tmp_path / "unrelated.py").write_text("raise RuntimeError('do not import')\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    # When: discovering project providers
    result = CliRunner().invoke(app, ["skeletons", "list", "--json"])
    # Then: only the declared template provider runs
    assert result.exit_code == 0, result.output
    assert any(item["id"] == f"{name}.Ga579Skeleton" for item in json.loads(result.output))


def test_broken_provider_is_a_usage_error__ga579_neg_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA579-NEG-3: explicit imports still surface provider errors with exit 3."""
    # Given: a template module whose import fails
    name = _provider(tmp_path, monkeypatch)
    with (tmp_path / f"{name}.py").open("a", encoding="utf-8") as target:
        target.write("raise RuntimeError('broken provider')\n")
    # When: an explicit module import is requested
    result = CliRunner().invoke(app, ["skeletons", "list", "--module", name])
    # Then: the existing usage-error path explains the import failure
    assert result.exit_code == 3
    assert "broken provider" in result.output
