"""Attribute mapping in ``migrate apply`` (Session RC1-INT-CLI, review item F08).

``migrate apply`` renamed ``(srcpaths, resource_paths)`` to
``(paths: InputPaths, out: OutputContext)`` but left attribute access alone,
so the standard v1 ``resource_paths.rawfiles`` became the non-existent
``out.rawfiles``: conversion exited 0 with no TODO and the flow failed with
``AttributeError`` under the Runner. Attributes on the renamed parameters are
now mapped onto the v2 bundle that owns them; anything without an equivalent,
and any bare use of a renamed parameter, is kept as-is and marked with one
``# TODO(rdetoolkit-migrate):`` line naming the original line and name
(Design §10: unsupported constructs are marked, not silently converted).

EP table:
    TC-RC1-F08-EP-001 | reviewer's ``resource_paths.rawfiles`` callback | ``paths.rawfiles``; flow succeeds under the real Runner
    TC-RC1-F08-EP-002 | each OutputContext field on the second param    | ``out.<same>``, no TODO
    TC-RC1-F08-EP-003 | ``smarttable_rawfile`` on the second param      | ``paths.smarttable_rawfile``, no TODO
    TC-RC1-F08-EP-004 | v1-only / unknown attribute on the second param | code kept + TODO with line and name
    TC-RC1-F08-EP-005 | ``helper(resource_paths)`` bare use             | renamed + TODO with line and name
    TC-RC1-F08-EP-006 | ``helper(srcpaths)`` bare use                   | renamed + TODO with line and name
    TC-RC1-F08-EP-007 | InputPaths field on the first param             | ``paths.<same>``, no TODO
    TC-RC1-F08-EP-008 | non-InputPaths attribute on the first param     | code kept + TODO with line and name

BV table:
    TC-RC1-F08-BV-001 | callback without parameter use        | no TODO line at all
    TC-RC1-F08-BV-002 | several findings on several lines    | one TODO line each, in source line order
    TC-RC1-F08-BV-003 | the same finding twice on one line   | a single TODO line
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.runner.lifecycle import Runner

_TODO = "# TODO(rdetoolkit-migrate): "
_OUTPUT_FIELDS = ("struct", "meta", "main_image", "other_image", "thumbnail", "raw", "logs", "attachment", "nonshared_raw", "invoice")
_UNMAPPED_FIELDS = ("invoice_schema_json", "invoice_org", "smarttable_row_data", "temp", "invoice_patch", "not_a_v1_field")


def _seed(data_root: Path) -> None:
    """Create a valid one-tile invoice-mode input tree."""
    for dirname in ("inputdata", "invoice", "tasksupport", "temp"):
        (data_root / dirname).mkdir(parents=True, exist_ok=True)
    (data_root / "inputdata" / "sample.txt").write_text("input", encoding="utf-8")
    invoice = {
        "datasetId": "rc1-f08-dataset",
        "basic": {"dateSubmitted": "2026-07-12", "dataOwnerId": "0" * 56, "dataName": "rc1"},
    }
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    (data_root / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text('{"constant": {}, "variable": []}', encoding="utf-8")


def _convert(tmp_path: Path, body: str) -> str:
    source = tmp_path / "legacy_callback.py"
    source.write_text(
        "from rdetoolkit.workflows import run\n"
        "def process(srcpaths, resource_paths):\n"
        f"{body}"
        "if __name__ == '__main__':\n"
        "    run(custom_dataset_function=process)\n",
        encoding="utf-8",
    )
    output = tmp_path / "migrated"
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "--output", str(output), "--no-dry-run"])
    assert result.exit_code == 0, result.output
    return (output / source.name).read_text(encoding="utf-8")


def _todo_lines(converted: str) -> list[str]:
    return [line for line in converted.splitlines() if line.startswith(_TODO)]


def _import(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_rawfiles_callback_runs_under_runner__tc_rc1_f08_ep_001(tmp_path: Path) -> None:
    """TC-RC1-F08-EP-001: the reviewer's rawfiles callback converts into a flow that runs."""
    # Given: the reviewer's valid two-argument callback reading rawfiles
    converted = _convert(tmp_path, "    assert len(resource_paths.rawfiles) == 1\n")
    # When: the converted flow runs under the real Runner on a valid one-tile input
    module = _import(tmp_path / "migrated" / "legacy_callback.py", "rc1_f08_rawfiles_migrated")
    root = tmp_path / "run_root"
    _seed(root / "data")
    report = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    ).run(module.pipeline)
    # Then: the run succeeds, rawfiles moved to the input bundle, and nothing is flagged
    assert report.status == "success", report.error
    assert "paths.rawfiles" in converted
    assert "out.rawfiles" not in converted
    assert _todo_lines(converted) == []


@pytest.mark.parametrize("field", _OUTPUT_FIELDS)
def test_output_fields_map_to_out__tc_rc1_f08_ep_002(tmp_path: Path, field: str) -> None:
    """TC-RC1-F08-EP-002: every OutputContext field keeps its name on ``out``."""
    # Given: a callback reading one output directory from the second parameter
    # When: it is converted
    converted = _convert(tmp_path, f"    target = resource_paths.{field}\n")
    # Then: the access moves to ``out`` and is not flagged
    assert f"target = out.{field}" in converted
    assert _todo_lines(converted) == []


def test_smarttable_rawfile_maps_to_paths__tc_rc1_f08_ep_003(tmp_path: Path) -> None:
    """TC-RC1-F08-EP-003: ``smarttable_rawfile`` belongs to InputPaths in v2."""
    # Given: a callback reading the SmartTable row file from the second parameter
    # When: it is converted
    converted = _convert(tmp_path, "    row = resource_paths.smarttable_rawfile\n")
    # Then: the access moves to ``paths``
    assert "row = paths.smarttable_rawfile" in converted
    assert _todo_lines(converted) == []


@pytest.mark.parametrize("field", _UNMAPPED_FIELDS)
def test_unmapped_output_attribute_is_kept_and_marked__tc_rc1_f08_ep_004(tmp_path: Path, field: str) -> None:
    """TC-RC1-F08-EP-004: a v1 field without a v2 home is left as written and flagged."""
    # Given: a callback reading a field neither v2 bundle has (line 3 of the source)
    # When: it is converted
    converted = _convert(tmp_path, f"    value = resource_paths.{field}\n")
    # Then: the original access is untouched and one TODO names its line and name
    assert f"value = resource_paths.{field}" in converted
    todos = _todo_lines(converted)
    assert len(todos) == 1
    assert "line 3" in todos[0]
    assert f"resource_paths.{field}" in todos[0]


def test_bare_output_parameter_use_is_marked__tc_rc1_f08_ep_005(tmp_path: Path) -> None:
    """TC-RC1-F08-EP-005: passing the renamed bundle on hands the callee a v2 object."""
    # Given: a callback passing the second parameter to a helper (line 3)
    # When: it is converted
    converted = _convert(tmp_path, "    helper(resource_paths)\n")
    # Then: the call uses the renamed parameter and is flagged with line and name
    assert "helper(out)" in converted
    todos = _todo_lines(converted)
    assert len(todos) == 1
    assert "line 3" in todos[0]
    assert "resource_paths" in todos[0]
    assert "OutputContext" in todos[0]


def test_bare_input_parameter_use_is_marked__tc_rc1_f08_ep_006(tmp_path: Path) -> None:
    """TC-RC1-F08-EP-006: the first parameter passed on is flagged the same way."""
    # Given: a callback passing the first parameter to a helper (line 3)
    # When: it is converted
    converted = _convert(tmp_path, "    helper(srcpaths)\n")
    # Then: the call uses the renamed parameter and is flagged with line and name
    assert "helper(paths)" in converted
    todos = _todo_lines(converted)
    assert len(todos) == 1
    assert "line 3" in todos[0]
    assert "srcpaths" in todos[0]
    assert "InputPaths" in todos[0]


@pytest.mark.parametrize("field", ("inputdata", "invoice", "tasksupport"))
def test_input_fields_stay_on_paths__tc_rc1_f08_ep_007(tmp_path: Path, field: str) -> None:
    """TC-RC1-F08-EP-007: InputPaths fields on the first parameter move to ``paths``."""
    # Given: a callback reading an input directory from the first parameter
    # When: it is converted
    converted = _convert(tmp_path, f"    source = srcpaths.{field}\n")
    # Then: the access is renamed and not flagged
    assert f"source = paths.{field}" in converted
    assert _todo_lines(converted) == []


def test_non_input_attribute_on_first_parameter_is_marked__tc_rc1_f08_ep_008(tmp_path: Path) -> None:
    """TC-RC1-F08-EP-008: ``srcpaths.config`` has no InputPaths equivalent."""
    # Given: a callback reading the v1 config from the first parameter (line 3)
    # When: it is converted
    converted = _convert(tmp_path, "    mode = srcpaths.config.system.extended_mode\n")
    # Then: the access is kept and flagged with line and name
    assert "mode = srcpaths.config.system.extended_mode" in converted
    todos = _todo_lines(converted)
    assert len(todos) == 1
    assert "line 3" in todos[0]
    assert "srcpaths.config" in todos[0]


def test_callback_without_parameter_use_has_no_todo__tc_rc1_f08_bv_001(tmp_path: Path) -> None:
    """TC-RC1-F08-BV-001: a callback that never touches its parameters is not flagged."""
    # Given: a callback whose body ignores both parameters
    # When: it is converted
    converted = _convert(tmp_path, "    return None\n")
    # Then: no TODO line is emitted
    assert "TODO(rdetoolkit-migrate)" not in converted


def test_findings_are_one_line_each_in_source_order__tc_rc1_f08_bv_002(tmp_path: Path) -> None:
    """TC-RC1-F08-BV-002: each finding gets its own TODO line, ordered by original line."""
    # Given: findings on lines 3, 4 and 5 beside mapped accesses
    body = (
        "    helper(resource_paths)\n"
        "    org = resource_paths.invoice_org\n"
        "    cfg = srcpaths.config\n"
        "    ok = resource_paths.struct\n"
    )
    # When: it is converted
    todos = _todo_lines(_convert(tmp_path, body))
    # Then: three TODO lines appear in line order
    assert len(todos) == 3
    assert ["line 3" in todos[0], "line 4" in todos[1], "line 5" in todos[2]] == [True, True, True]


def test_repeated_finding_on_one_line_is_reported_once__tc_rc1_f08_bv_003(tmp_path: Path) -> None:
    """TC-RC1-F08-BV-003: one line repeating the same unmapped access yields one TODO."""
    # Given: the same unmapped access twice on line 3
    # When: it is converted
    todos = _todo_lines(_convert(tmp_path, "    pair = (resource_paths.temp, resource_paths.temp)\n"))
    # Then: a single TODO line is emitted
    assert len(todos) == 1
