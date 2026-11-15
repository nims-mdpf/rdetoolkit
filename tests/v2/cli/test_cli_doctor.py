"""Doctor EP/BV table, written before implementation.

| ID | Partition / boundary | Expected |
| D01 | nested / flat / explicit data root | same resolved paths, clean |
| D02 | missing invoice / schema / metadata / input directory | error, exit 1 |
| D03 | malformed invoice / schema / metadata / config | safe error, exit 1 |
| D04 | mismatched invoice | 4001, exit 1 |
| D05 | mode detected despite explicit config | W1001, warning, exit 0 |
| D06 | flow with body and preparation | neither invoked |
| D07 | missing / noncallable / invalid flow reference | error, exit 1 |
| D08 | unresolved / duplicate reserved parameters | 2003 / 2006 |
| D09 | remote schema reference | no retrieval, error |
| D10 | absent root / invalid format | usage, exit 3 |
| D11 | existing outputs / diagnostics | byte-identical after doctor |
| D12 | repeated diagnostic command | deterministic JSON |
| D13 | null / list / scalar document | schema error, exit 1 |
| D14 | import noise / exception | values suppressed, no bytecode writes |
| D15 | nested external reference | offline failure |
| D16 | standard invoice mismatch | Runner 4001 |
| D17 | skeleton / concrete template | reject skeleton, inspect concrete without constructing |
| D18 | temporary-copy IO failure | structured failure, inputs preserved |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app

runner = CliRunner()


def _project(root: Path, layout: str = "nested") -> Path:
    data = root / "data" if layout == "nested" else root
    for name in ("inputdata", "invoice", "tasksupport"):
        (data / name).mkdir(parents=True, exist_ok=True)
    (data / "inputdata" / "sample.txt").write_text("sample", encoding="utf-8")
    (data / "invoice" / "invoice.json").write_text(json.dumps({
        "datasetId": "dataset", "basic": {
            "dateSubmitted": "2026-11-12", "dataOwnerId": "0" * 56, "dataName": "example",
        },
    }), encoding="utf-8")
    (data / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (data / "tasksupport" / "metadata-def.json").write_text('{}', encoding="utf-8")
    return data


def _invoke(root: Path, *args: str):
    return runner.invoke(app, ["doctor", str(root), "--format", "json", *args])


@pytest.mark.parametrize("layout", ["nested", "flat", "data"])
def test_clean_layouts_d01(tmp_path, layout):
    # Given: a clean project in each Runner-supported layout
    data = _project(tmp_path, "nested" if layout == "data" else layout)
    root = data if layout == "data" else tmp_path
    # When: preflighting the project
    result = _invoke(root)
    # Then: the reported data root matches Runner resolution
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1"
    assert payload["status"] == "passed"
    assert payload["data_root"] == ("." if root == data else "data")
    assert payload["mode"] == "invoice"
    assert payload["diagnostics"] == []


@pytest.mark.parametrize("relative", ["invoice/invoice.json", "tasksupport/invoice.schema.json", "inputdata"])
def test_missing_inputs_d02(tmp_path, relative):
    # Given: one missing input the Runner cannot run without
    data = _project(tmp_path)
    path = data / relative
    if path.is_dir():
        (path / "sample.txt").unlink()
        path.rmdir()
    else:
        path.unlink()
    # When: requesting JSON diagnostics
    result = _invoke(tmp_path)
    # Then: a structured failure names the Runner's own code and the project-relative path
    payload = json.loads(result.stdout)
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert any(d["code"] == 4003 and d["location"]["path"] == f"data/{relative}" for d in payload["diagnostics"])


def test_missing_metadata_definition_is_a_warning_d02(tmp_path):
    # Given: a project without metadata-def.json, which a run does not require
    data = _project(tmp_path)
    (data / "tasksupport/metadata-def.json").unlink()
    # When: requesting JSON diagnostics
    result = _invoke(tmp_path)
    # Then: it is reported, but the project still passes like the Runner would
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, result.output
    assert payload["status"] == "warning"
    assert payload["mode"] == "invoice"
    assert [d["name"] for d in payload["diagnostics"]] == ["MetadataDefinitionMissing"]


@pytest.mark.parametrize("relative,content,code", [
    ("invoice/invoice.json", "not json SECRET", 4001),
    ("tasksupport/invoice.schema.json", "not json SECRET", 4001),
    ("tasksupport/metadata-def.json", "not json SECRET", 4002),
    ("tasksupport/metadata-def.json", '{"bad": {"name": "SECRET"}}', 4002),
    ("../rdeconfig.yaml", "unknown_option: SECRET", 1002),
    ("../rdeconfig.yaml", "system: [SECRET", 1002),
])
def test_malformed_inputs_safe_d03(tmp_path, relative, content, code):
    # Given: an input containing invalid data and a secret sentinel
    data = _project(tmp_path)
    (data / relative).write_text(content, encoding="utf-8")
    # When: preflighting that input
    result = _invoke(tmp_path)
    # Then: a stable catalog code is returned without exposing input values
    payload = json.loads(result.stdout)
    assert result.exit_code == 1, result.output
    assert any(d["code"] == code for d in payload["diagnostics"])
    assert "SECRET" not in result.output


def test_mismatched_invoice_d04(tmp_path):
    # Given: an invoice that violates the project's schema
    data = _project(tmp_path)
    (data / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}, "required": ["missing"]}', encoding="utf-8")
    # When: doctor reuses Runner preflight
    result = _invoke(tmp_path)
    # Then: catalog remediation is provided
    findings = json.loads(result.stdout)["diagnostics"]
    assert result.exit_code == 1
    assert any(d["code"] == 4001 and d["remediation"] for d in findings)


def test_file_mode_override_d05(tmp_path):
    # Given: SmartTable input and an explicitly configured MultiDataTile mode
    data = _project(tmp_path)
    (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: MultiDataTile\n", encoding="utf-8")
    (data / "inputdata" / "smarttable_sample.csv").write_text("x\n1\n", encoding="utf-8")
    # When: mode detection runs without executing processing
    result = _invoke(tmp_path)
    # Then: the Runner's override is visible and warning-only is successful
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, result.output
    assert payload["mode"] == "smarttable"
    assert payload["status"] == "warning"
    assert any(d["code"] == 1001 and d["severity"] == "warning" for d in payload["diagnostics"])


def test_no_flow_or_prepare_execution_d06(tmp_path, monkeypatch):
    # Given: a flow whose prepare and body would leave an external sentinel
    _project(tmp_path)
    sentinel = tmp_path / "executed"
    module = tmp_path / "doctor_side_effect_flow.py"
    module.write_text("from pathlib import Path\nfrom rdetoolkit import flow\n"
                      f"def prepare(*args): Path({str(sentinel)!r}).write_text('prepare')\n"
                      "@flow(prepare=prepare)\n"
                      f"def main(): Path({str(sentinel)!r}).write_text('body')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    # When: checking a supplied flow
    result = _invoke(tmp_path, "--ref", "doctor_side_effect_flow:main")
    # Then: importing is allowed, but neither user callback is executed
    assert result.exit_code == 0, result.output
    assert not sentinel.exists()
    assert "flow.signature" in [c["check_id"] for c in json.loads(result.stdout)["checks"]]


@pytest.mark.parametrize("reference", ["missing_doctor_module:main", "json:missing", "json:__doc__", "invalid-reference"])
def test_invalid_flow_d07(tmp_path, reference):
    # Given: an invalid flow reference
    _project(tmp_path)
    # When: checking it
    result = _invoke(tmp_path, "--ref", reference)
    # Then: failure is structured independently of run's exit contract
    assert result.exit_code == 1
    assert any(d["check_id"] == "flow.import" for d in json.loads(result.stdout)["diagnostics"])


@pytest.mark.parametrize("signature,code", [("required", 2003), ("a: InputPaths, b: InputPaths", 2006)])
def test_flow_annotations_d08(tmp_path, monkeypatch, signature, code):
    # Given: a flow requiring unsupported or duplicate reserved injection
    _project(tmp_path)
    name = f"doctor_invalid_flow_{code}"
    (tmp_path / f"{name}.py").write_text(f"from rdetoolkit.types import InputPaths\ndef main({signature}): pass\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    # When: preflighting signature injection
    result = _invoke(tmp_path, "--ref", f"{name}:main")
    # Then: the existing injection error code is preserved
    assert result.exit_code == 1
    assert any(d["code"] == code for d in json.loads(result.stdout)["diagnostics"])


def test_no_remote_schema_resolution_d09(tmp_path, monkeypatch):
    # Given: a schema containing an external reference
    data = _project(tmp_path)
    (data / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}, "$ref": "https://example.invalid/SECRET"}', encoding="utf-8")
    # When: preflighting offline
    result = _invoke(tmp_path)
    # Then: no URI is retrieved or disclosed and the limitation is explicit
    assert result.exit_code == 1
    assert "SECRET" not in result.output
    assert any(d["name"] == "ExternalSchemaReference" for d in json.loads(result.stdout)["diagnostics"])


@pytest.mark.parametrize("args", [["nonexistent-doctor-root"], ["--format", "xml"]])
def test_usage_errors_d10(tmp_path, args):
    # Given: an absent root or unsupported output format
    # When: invoking doctor
    result = runner.invoke(app, ["doctor", *args])
    # Then: it is the v2 invalid-input status, with remediation on stderr
    assert result.exit_code == 3
    assert "Remediation:" in result.stderr
    assert result.stdout == ""


def test_unknown_option_is_click_usage_d10(tmp_path):
    # Given/When: an option doctor does not have (the retired run spelling)
    result = runner.invoke(app, ["doctor", str(tmp_path), "--flow", "m:f"])
    # Then: the parser rejects it with Click's usage status
    assert result.exit_code == 2


def test_preserves_project_d11(tmp_path):
    # Given: previous diagnostic and output artifacts
    data = _project(tmp_path)
    for relative in ("logs/run_report_old.json", "logs/iterations/iteration_0.json", "structured/output.csv", "job.failed", "temp/old.txt"):
        path = data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"previous artifact")
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # When: doctor performs Runner validation
    result = _invoke(tmp_path)
    # Then: no source or output files are added, removed, or rewritten
    after = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert result.exit_code == 0, result.output
    assert before == after


def test_repeatable_text_and_json_d12(tmp_path):
    # Given: a clean project
    _project(tmp_path)
    # When: doctor is run repeatedly in both formats
    first, second = _invoke(tmp_path), _invoke(tmp_path)
    text_result = runner.invoke(app, ["doctor", str(tmp_path)])
    # Then: output excludes transient run IDs/times and text stays available
    assert first.stdout == second.stdout
    assert text_result.exit_code == 0
    assert "passed" in text_result.stdout


@pytest.mark.parametrize("relative,code", [("invoice/invoice.json", 4001), ("tasksupport/invoice.schema.json", 4001), ("tasksupport/metadata-def.json", 4002)])
@pytest.mark.parametrize("content", ["null", "[]", "42", '"SECRET"'])
def test_nonobject_documents_d13(tmp_path, relative, code, content):
    # Given: a well-formed JSON value that is not a project input object
    data = _project(tmp_path)
    (data / relative).write_text(content, encoding="utf-8")
    # When: requesting diagnostics
    result = _invoke(tmp_path)
    # Then: the structural failure cannot be mistaken for a clean project
    assert result.exit_code == 1
    assert any(d["code"] == code for d in json.loads(result.stdout)["diagnostics"])
    assert "SECRET" not in result.output


@pytest.mark.parametrize("raises", [False, True])
def test_import_output_is_suppressed_d14(tmp_path, monkeypatch, raises):
    # Given: an imported module that prints a secret and may fail
    _project(tmp_path)
    name = f"doctor_noisy_module_{raises}"
    content = "print('SECRET')\n"
    content += "raise ImportError('SECRET')\n" if raises else "def main(): pass\n"
    (tmp_path / f"{name}.py").write_text(content, encoding="utf-8")
    # When: doctor imports that module from its explicit project root
    result = _invoke(tmp_path, "--ref", f"{name}:main")
    # Then: JSON stays parseable and no import output or bytecode is exposed
    assert result.exit_code == int(raises)
    json.loads(result.stdout)
    assert "SECRET" not in result.output
    assert not (tmp_path / "__pycache__").exists()


@pytest.mark.parametrize("definition", [{"allOf": [{"$ref": "https://example.invalid/SECRET"}]}, {"properties": {"x": {"$ref": "local.json"}}}])
def test_nested_external_reference_d15(tmp_path, definition):
    # Given: a schema whose external reference is nested below applicators
    data = _project(tmp_path)
    definition.setdefault("properties", {})
    (data / "tasksupport/invoice.schema.json").write_text(json.dumps(definition), encoding="utf-8")
    # When: checking offline
    result = _invoke(tmp_path)
    # Then: recursive references are rejected before Runner validation
    assert result.exit_code == 1
    assert any(d["name"] == "ExternalSchemaReference" for d in json.loads(result.stdout)["diagnostics"])


def test_runner_invoice_failure_d16(tmp_path):
    # Given: an invoice object missing system-required basic fields
    data = _project(tmp_path)
    (data / "invoice/invoice.json").write_text('{"basic": {"dataName": "SECRET"}}', encoding="utf-8")
    # When: the existing Runner validates the source invoice
    result = _invoke(tmp_path)
    # Then: its catalog outcome is kept, without the failing data values
    assert result.exit_code == 1
    assert any(d["check_id"] == "runner.preflight" and d["code"] == 4001 for d in json.loads(result.stdout)["diagnostics"])
    assert "SECRET" not in result.output


@pytest.mark.parametrize("class_name,expected", [("Skeleton", 1), ("Concrete", 0)])
def test_template_signature_without_constructor_d17(tmp_path, class_name, expected):
    # Given: a skeleton and a concrete template counting import-time constructions
    _project(tmp_path)
    name = f"doctor_template_{class_name}"
    (tmp_path / f"{name}.py").write_text(
        "from typing import final\nfrom rdetoolkit.templates import ProcessingTemplate\n"
        "from rdetoolkit.types import InputPaths\n"
        "class Skeleton(ProcessingTemplate):\n"
        "    @final\n    def __flow__(self, paths: InputPaths) -> None: raise AssertionError('body')\n"
        "construction_count = 0\nclass Concrete(Skeleton):\n"
        "    def __init__(self):\n        global construction_count\n        construction_count += 1\n", encoding="utf-8")
    # When: doctor inspects a class accepted as a flow target
    result = _invoke(tmp_path, "--ref", f"{name}:{class_name}")
    # Then: only a concrete signature passes; there is no extra construction or body call
    assert result.exit_code == expected, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == ("failed" if expected else "passed")
    import sys
    assert sys.modules[name].construction_count == 1


def test_copy_io_failure_d18(tmp_path, monkeypatch):
    # Given: valid project inputs and a temporary-copy failure
    _project(tmp_path)
    def fail_copy(*args, **kwargs):
        raise OSError("SECRET")
    monkeypatch.setattr("rdetoolkit.cli.doctor_cmd.shutil.copytree", fail_copy)
    # When: isolation cannot be established
    result = _invoke(tmp_path)
    # Then: failure is explicit and no raw exception value is emitted
    assert result.exit_code == 1
    assert any(d["name"] == "PreflightUnavailable" for d in json.loads(result.stdout)["diagnostics"])
    assert "SECRET" not in result.output


def test_text_findings_are_actionable(tmp_path):
    # Given: a project with a missing schema
    data = _project(tmp_path)
    (data / "tasksupport/invoice.schema.json").unlink()
    # When: using the default text format
    result = runner.invoke(app, ["doctor", str(tmp_path)])
    # Then: the same failure and correction are available to a human
    assert result.exit_code == 1
    assert "Remediation:" in result.stdout


@pytest.mark.parametrize("depth", [400, 10000])
def test_deep_schema_fails_as_json(tmp_path, depth):
    # Given: a deeply nested JSON schema exceeding normal schema limits
    data = _project(tmp_path)
    (data / "tasksupport/invoice.schema.json").write_text('{"allOf":' + '[' * depth + '0' + ']' * depth + '}', encoding="utf-8")
    # When: parsing or validating reaches recursion limits
    result = _invoke(tmp_path)
    # Then: the failure still uses the structured JSON contract
    assert result.exit_code == 1
    assert any(d["code"] == 4001 for d in json.loads(result.stdout)["diagnostics"])


@pytest.mark.parametrize("smarttable", [False, True])
def test_matches_run_validate_only_d19(tmp_path, monkeypatch, smarttable):
    # Given: a project, and an identical copy checked by `rdetoolkit run --validate-only`
    import shutil

    project = tmp_path / "project"
    data = _project(project)
    (project / "rdeconfig.yaml").write_text("system:\n  extended_mode: MultiDataTile\n", encoding="utf-8")
    if smarttable:
        (data / "inputdata" / "smarttable_sample.csv").write_text("x\n1\n", encoding="utf-8")
    reference = tmp_path / "reference"
    shutil.copytree(project, reference)
    module = f"doctor_parity_flow_{smarttable}"
    (reference / f"{module}.py").write_text("def main() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(reference)
    run = runner.invoke(app, ["run", f"{module}:main", "--validate-only"])
    assert run.exit_code == 0, run.output
    (expected_path,) = (reference / "data/logs").glob("run_report_*.json")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    # When: doctor checks the original project
    payload = json.loads(_invoke(project).stdout)
    # Then: it reports the same mode and effective-config digest as the run
    assert (payload["mode"], payload["config"]["digest"]) == (expected["mode"], expected["config_digest"])
    assert ("mode.selection" in {d["check_id"] for d in payload["diagnostics"]}) is smarttable


def test_temporary_copy_is_removed_d20(tmp_path, monkeypatch):
    # Given: temporary directories created under a known location
    import tempfile

    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    project = tmp_path / "project"
    _project(project)
    # When: doctor runs its isolated preflight, successfully and after a copy failure
    assert _invoke(project).exit_code == 0
    monkeypatch.setattr("rdetoolkit.cli.doctor_cmd.shutil.copytree", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    assert _invoke(project).exit_code == 1
    # Then: no copy is left behind
    assert list(scratch.iterdir()) == []
