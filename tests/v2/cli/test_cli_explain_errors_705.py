"""Error partitions for the versioned read-only explanation workflow."""

import json
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from tests.v2.cli.test_cli_explain_705 import _schema
from tests.v2.contract.fixtures import _generate


@pytest.mark.parametrize("artifact,expected", [("data/invoice/invoice.json", 4003), ("data/tasksupport/invoice.schema.json", 4003)])
def test_missing_source_artifact_is_structured__explain_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str, expected: int) -> None:
    # Given: one of the required source artifacts is missing.
    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)
    (tmp_path / artifact).unlink()
    monkeypatch.chdir(tmp_path)
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    # When: explaining validation failure.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: the versioned catalogued error does not publish failure artifacts.
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["error"]["code"] == expected
    assert before == sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))


def test_invalid_schema_is_structured__explain_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the schema itself has an invalid type declaration.
    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)
    (tmp_path / "data/tasksupport/invoice.schema.json").write_text('{"type": "unsupported"}')
    monkeypatch.chdir(tmp_path)
    # When: validating the current source snapshot.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: source schema validation uses the same catalog code as execution.
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["error"]["code"] == 4001


@pytest.mark.parametrize("explicit,expected", [(False, 1007), (True, 1005)])
def test_mode_conflicts_are_structured__explain_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit: bool, expected: int) -> None:
    # Given: incompatible special evidence or an explicitly conflicting invoice.
    inputdata = tmp_path / "data/inputdata"
    inputdata.mkdir(parents=True)
    (inputdata / "smarttable_batch.csv").touch()
    if explicit:
        (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: invoice\n")
    else:
        (inputdata / "batch_excel_invoice.xlsx").touch()
    monkeypatch.chdir(tmp_path)
    # When: explaining before source validation and registration.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: the error includes inspectable file evidence in the checked schema.
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["error"]["code"] == expected
    assert not (tmp_path / "data/logs").exists()


@pytest.mark.parametrize("reference", [":pipeline", "module:", "module:pipeline:extra"])
def test_invalid_reference_is_rejected_without_import__explain_n3(reference: str) -> None:
    # Given: a malformed flow reference for the read-only route.
    # When: validating its syntax without user imports.
    result = CliRunner().invoke(app, ["run", reference, "--validate-only", "--explain"])
    # Then: a usage error leaves the missing module untouched.
    assert result.exit_code == 3


def test_legacy_explanation_is_usage_error__explain_n3() -> None:
    # Given: explanation is defined only for the v2 registration contract.
    # When: requesting it for a legacy callback reference.
    result = CliRunner().invoke(app, ["run", "--legacy", "missing.py::dataset", "--validate-only", "--explain"])
    # Then: the callback module is never loaded.
    assert result.exit_code == 3
