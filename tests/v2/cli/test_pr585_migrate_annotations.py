"""PR585 migration regression: annotations change independently of names."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.testing import run_flow


@pytest.mark.parametrize("names", [("paths", "out"), ("src", "out"), ("paths", "resources")])
@pytest.mark.parametrize("annotations", [("", ""), (": object", ": object"), (": InputPaths", ": OutputContext")])
def test_annotation_only_edits_produce_runnable_flow__r585_mig_1(tmp_path: Path, names: tuple[str, str], annotations: tuple[str, str]) -> None:
    """R585-MIG-1: canonical parameter names still receive the reserved types."""
    # Given: a legacy callback with at least one already-canonical parameter
    first, second = names
    source = tmp_path / "source.py"
    source.write_text(
        'from rdetoolkit import workflows\n'
        'from rdetoolkit.types import InputPaths, OutputContext\n'
        f'def dataset({first}{annotations[0]}, {second}{annotations[1]}):\n'
        '    # Keep the measurement comment.\n'
        f'    assert {first}.inputdata.exists()\n'
        f'    ({second}.struct / "ready.txt").write_text("ready")\n'
        'workflows.run(custom_dataset_function=dataset)\n', encoding="utf-8",
    )
    output = tmp_path / "converted"
    # When: using the public migration command and importing its output
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"])
    assert result.exit_code == 0, result.output
    spec = importlib.util.spec_from_file_location(f"r585_migrate_{tmp_path.name}", output / source.name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = tmp_path / "input"
    fixture.mkdir()
    (fixture / "sample.txt").write_text("sample", encoding="utf-8")
    report = run_flow(module.pipeline, fixture)
    # Then: DI resolves both parameters and the migrated body executes
    assert report.status == "success", report.error
    assert list(inspect.signature(module.pipeline).parameters) == ["paths", "out"]
    assert "# Keep the measurement comment." in (output / source.name).read_text()
