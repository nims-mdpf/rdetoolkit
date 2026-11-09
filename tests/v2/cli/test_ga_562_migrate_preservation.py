"""GA562 EP/BV: unsupported migrations retain executable sources and comments."""

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.testing import run_flow


@pytest.mark.parametrize("target", ["datasets_process.dataset", "getattr(datasets_process, 'dataset')", "missing"])
def test_unresolved_callback_keeps_whole_project__ga562_neg_1(tmp_path: Path, target: str) -> None:
    """GA562-NEG-1: a manual migration keeps run(), comments and unrelated bytes."""
    # Given: the standard cross-module template layout with helper files
    source = tmp_path / "container"
    (source / "modules").mkdir(parents=True)
    files = {
        "main.py": f"# Copyright header\nimport rdetoolkit.workflows\nfrom modules import datasets_process\nrdetoolkit.workflows.run(custom_dataset_function={target})  # register\n",
        "modules/datasets_process.py": '# reader comment\ndef dataset(srcpaths, resource_paths):\n    # copy the first raw file\n    (resource_paths.struct / "x.txt").write_text(resource_paths.rawfiles[0].read_text())\n',
        "modules/__init__.py": "# Package license\n",
        "helpers.py": "# unrelated helper\nVALUE = 'quoted'\n",
    }
    for name, content in files.items():
        (source / name).write_text(content, encoding="utf-8")
    output = tmp_path / "migrated"
    # When: the public tool cannot resolve a callback within its source file
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"])
    # Then: it explains the manual step and every original file remains intact
    assert result.exit_code == 0, result.output
    assert "manual" in result.output.lower()
    assert target in result.output
    for name, content in files.items():
        assert (output / name).read_text() == content
        assert (source / name).read_text() == content


@pytest.mark.parametrize("encoding", ["utf-8", "cp932"])
def test_supported_conversion_preserves_comments__ga562_ep_1(tmp_path: Path, encoding: str) -> None:
    """GA562-EP-1: local callbacks preserve comments and quoted strings while mapping paths."""
    # Given: a directly convertible callback with Unicode and inline comments
    source = tmp_path / "source.py"
    text = f'''# coding: {encoding}
# Copyright header 日本語
from rdetoolkit import workflows

def dataset(srcpaths, resource_paths):
    # copy the first raw file
    content = resource_paths.rawfiles[0].read_text()  # preserve this comment
    (resource_paths.struct / "x.txt").write_text(content)

workflows.run(custom_dataset_function=dataset)  # entry comment
'''
    source.write_bytes(text.encode(encoding))
    output = tmp_path / "converted"
    # When: converting and importing the resulting UTF-8 flow module
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"])
    assert result.exit_code == 0, result.output
    converted = (output / source.name).read_text(encoding="utf-8")
    for comment in ["# Copyright header 日本語", "# copy the first raw file", "# preserve this comment", "# entry comment"]:
        assert comment in converted
    spec = importlib.util.spec_from_file_location(f"ga562_{encoding.replace('-', '_')}", output / source.name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = tmp_path / "input"
    fixture.mkdir()
    (fixture / "a.txt").write_text("measured", encoding="utf-8")
    report = run_flow(module.pipeline, fixture)
    # Then: public v2 execution produces the same measured artifact
    assert report.status == "success", report.error
    assert "paths.rawfiles" in converted and "out.struct" in converted


def test_mixed_callbacks_are_not_partially_converted__ga562_neg_2(tmp_path: Path) -> None:
    """GA562-NEG-2: a local callback must not hide a second unresolved entry."""
    # Given: one local and one foreign callback in the same file
    source = tmp_path / "mixed.py"
    text = "from rdetoolkit import workflows\ndef local(src, out):\n    pass\nworkflows.run(custom_dataset_function=local)\nworkflows.run(custom_dataset_function=foreign.dataset)  # preserve\n"
    source.write_text(text, encoding="utf-8")
    output = tmp_path / "output"
    # When: applying migration with an unsupported sibling entry
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"])
    # Then: the whole module is left intact and the unresolved target is reported
    assert result.exit_code == 0, result.output
    assert "foreign.dataset" in result.output and "manual" in result.output.lower()
    assert (output / source.name).read_text() == text


@pytest.mark.parametrize("prefix", ["", '"""Module documentation."""\nfrom __future__ import annotations\n', 'def identity(fn):\n    return fn\n\n@identity\n'])
def test_source_edit_boundaries__ga562_bv_2(tmp_path: Path, prefix: str) -> None:
    """GA562-BV-2: headers, decorators and Unicode cannot corrupt token offsets."""
    # Given: a callback with a cookie-like string and non-ASCII text before a mapped name
    source = tmp_path / "boundary.py"
    text = prefix + '''def dataset(src, resources):
    marker = """literal
# coding: cp932
"""
    label = "測定"; value = resources.rawfiles[0]
    return marker
run(custom_dataset_function=dataset)
'''
    source.write_text(text, encoding="utf-8")
    output = tmp_path / "output"
    # When: editing source rather than regenerating the complete AST
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"])
    # Then: the flow is importable, its literal content stays intact and its path is mapped
    assert result.exit_code == 0, result.output
    converted = (output / source.name).read_text()
    compile(converted, str(output / source.name), "exec")
    assert "# coding: cp932" in converted
    assert 'label = "測定"; value = paths.rawfiles[0]' in converted


def test_main_guard_retains_other_statements__ga562_neg_2(tmp_path: Path) -> None:
    """GA562-NEG-2: converting an entry cannot delete neighboring main logic."""
    # Given: a convertible callback and useful code in both main guard branches
    source = tmp_path / "guarded.py"
    text = '''from rdetoolkit import workflows
def dataset(src, resources):
    pass
if __name__ == "__main__":
    print("keep the setup")  # retain setup
    workflows.run(custom_dataset_function=dataset)
else:
    print("keep the import hook")
'''
    source.write_text(text, encoding="utf-8")
    output = tmp_path / "output"
    # When: removing the converted callback's legacy entry
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"])
    # Then: only that call changes and its removal is explicitly reported
    assert result.exit_code == 0, result.output
    converted = (output / source.name).read_text()
    assert 'print("keep the setup")  # retain setup' in converted
    assert 'print("keep the import hook")' in converted
    assert "removed legacy entry" in result.output
    compile(converted, str(output / source.name), "exec")


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(label=st.text(alphabet=["x", "測", "定", "μ", "🙂", "é"], max_size=12))
def test_unicode_edits_are_idempotent__ga562_bv_3(tmp_path: Path, label: str) -> None:
    """GA562-BV-3: UTF-8 byte offsets preserve arbitrary literals across two passes."""
    # Given: arbitrary measured text before a resource reference on the same line
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        root = Path(directory)
        source = root / "source.py"
        literal = json.dumps(label, ensure_ascii=False)
        source.write_text(f"def dataset(src, resources):\n    label = {literal}; value = resources.rawfiles[0]\nrun(custom_dataset_function=dataset)\n", encoding="utf-8")
        first, second = root / "first", root / "second"
        # When: applying the public tool twice
        for input_path, output in [(source, first), (first / source.name, second)]:
            result = CliRunner().invoke(app, ["migrate", "apply", str(input_path), "--out", str(output), "--no-dry-run"])
            assert result.exit_code == 0, result.output
        # Then: the literal remains verbatim, the mapping is valid and no second edit occurs
        converted = (first / source.name).read_text()
        assert f"label = {literal}; value = paths.rawfiles[0]" in converted
        compile(converted, "converted.py", "exec")
        assert (second / source.name).read_bytes() == (first / source.name).read_bytes()
