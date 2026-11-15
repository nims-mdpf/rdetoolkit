"""Additional EP/BV partitions found by independent review.

| ID | Partition | Expected |
|----|-----------|----------|
| PR-N1 | invalid field or malformed YAML containing private values | safe 1002 JSON |
| PR-N2 | declared directory/file collision | 4006 before extraction |
| PR-N3 | case-colliding archive directories | 4006 before extraction |
| PR-N4 | a suffix lacking a full path-component match | missing reference 4006 |
| PR-B1 | uppercase ZIP extension | same RDEFormat decision |
| PR-B2 | rawless SmartTable with an unused archive | extract archive and clean system files |
"""

from pathlib import Path
from zipfile import ZipFile

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.runner.input_snapshot import discover_input_snapshot, materialize_input_snapshot
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import RdeConfig


@pytest.mark.parametrize("text", ["system:\n  save_raw: SECRET_INVALID_VALUE\n", "system: [SECRET_VALUE\n", "multidata_tile:\n  order: SECRET_INVALID_VALUE\n"])
def test_config_error_output_redacts_values__pr_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    # Given: invalid configuration whose rejected payload must stay private.
    (tmp_path / "rdeconfig.yaml").write_text(text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: emitting machine-readable explanation errors.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: a catalogued error identifies the field or file without exposing the value.
    import json

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"]["code"] == 1002
    assert "SECRET" not in result.stdout


@pytest.mark.parametrize("members", [["a/", "a"], ["Foo/a.txt", "foo/b.txt"], ["a", "A/child.txt"]])
def test_archive_layout_collision_rejected__pr_n2_n3(tmp_path: Path, members: list[str]) -> None:
    # Given: archive identities that cannot be materialized consistently.
    with ZipFile(tmp_path / "input.zip", "w") as archive:
        for name in members:
            archive.writestr(name, "content")
    # When: describing groups without extraction.
    with pytest.raises(RdeValidationError) as caught:
        discover_input_snapshot(ModeKind.rdeformat, tmp_path, RdeConfig())
    # Then: ambiguity fails with a catalogued error before touching output paths.
    assert caught.value.code == 4006
    assert [p.name for p in tmp_path.iterdir()] == ["input.zip"]


def test_smarttable_file_reference_respects_components__pr_n4(tmp_path: Path) -> None:
    # Given: a suffix resembling but not matching an archive-relative component path.
    (tmp_path / "smarttable_case.csv").write_text("File\ninputdata1\na/raw.txt\n", encoding="utf-8")
    with ZipFile(tmp_path / "input.zip", "w") as archive:
        archive.writestr("ba/raw.txt", "content")
    # When: planning that row's raw-file group.
    with pytest.raises(RdeValidationError) as caught:
        discover_input_snapshot(ModeKind.smarttable, tmp_path, RdeConfig())
    # Then: the misleading suffix is a missing reference rather than a selected file.
    assert caught.value.code == 4006
    assert "missing_file_reference" in str(caught.value)


def test_uppercase_archive_extension_is_supported__pr_b1(tmp_path: Path) -> None:
    # Given: an existing valid RDEFormat fixture using the legacy-supported extension case.
    from tests.v2.contract.fixtures import _generate
    from rdetoolkit.runner.preview import preview_registration

    _generate.materialize_case(_generate.oracle_case("v1/rdeformat/ok"), tmp_path)
    (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: rdeformat\n", encoding="utf-8")
    archives = list((tmp_path / "data" / "inputdata").glob("*.zip"))
    archives[0].rename(archives[0].with_suffix(".ZIP"))
    # When: explaining the same format without extraction.
    preview = preview_registration(tmp_path)
    # Then: extension case does not change the selected mode.
    assert preview.decision.chosen_mode is ModeKind.rdeformat


def test_rawless_rows_keep_archive_materialization__pr_b2(tmp_path: Path) -> None:
    # Given: a SmartTable row with no raw reference and an otherwise valid unused archive.
    (tmp_path / "smarttable_case.csv").write_text("Name\nbasic/dataName\nexample\n", encoding="utf-8")
    with ZipFile(tmp_path / "input.zip", "w") as archive:
        archive.writestr("raw/unused.txt", "content")
        archive.writestr(".DS_Store", "system")
    snapshot = discover_input_snapshot(ModeKind.smarttable, tmp_path, RdeConfig())
    # When: materializing the accepted snapshot as actual execution does.
    output = tmp_path / "output"
    materialize_input_snapshot(snapshot, output)
    # Then: legacy extraction artifacts and system-file cleanup remain compatible.
    assert (output / "raw" / "unused.txt").read_text() == "content"
    assert not (output / ".DS_Store").exists()


def test_invoice_validation_output_redacts_values__pr_n5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a valid project with a private value that violates its invoice schema.
    import json
    from tests.v2.contract.fixtures import _generate

    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)
    invoice_path = tmp_path / "data/invoice/invoice.json"
    schema_path = tmp_path / "data/tasksupport/invoice.schema.json"
    invoice = json.loads(invoice_path.read_text())
    schema = json.loads(schema_path.read_text())
    schema["properties"].setdefault("custom", {"type": "object", "properties": {}})["properties"]["private_count"] = {"type": "integer", "label": {"ja": "private", "en": "private"}}
    invoice.setdefault("custom", {})["private_count"] = "LEAK_INVOICE_VALUE"
    invoice_path.write_text(json.dumps(invoice), encoding="utf-8")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: read-only explanation encounters the schema failure.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: the failure retains its catalog identity and corrective advice, without raw values.
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"]["code"] == 4001
    assert "LEAK_INVOICE_VALUE" not in result.stdout
    assert "Remediation" in result.stdout


@pytest.mark.parametrize("relative", ["invoice/invoice.json", "tasksupport/invoice.schema.json"])
def test_missing_source_identifies_safe_path__pr_n6(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str) -> None:
    # Given: a source artifact is missing from an otherwise valid project.
    import json
    from tests.v2.contract.fixtures import _generate
    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)
    (tmp_path / "data" / relative).unlink()
    monkeypatch.chdir(tmp_path)
    # When: inspecting the project without running the flow.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: the safe relative path identifies the input the user must supply.
    payload = json.loads(result.stdout)
    assert result.exit_code == 1
    assert payload["error"]["code"] == 4003
    assert payload["error"]["detail"] == {"artifact": relative}
    assert relative in payload["error"]["message"]
