"""CLI explanation is JSON-safe and never imports the user's flow module."""

import json
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from tests.v2.contract.fixtures import _generate


def _schema() -> dict[str, object]:
    return json.loads((Path(__file__).parents[3] / "src/rdetoolkit/static/registration-explain.schema.json").read_text())


def test_explain_json_skips_user_import__explain_n2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: importing the selected module would fail, and inputs are valid.
    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)
    (tmp_path / "must_not_import.py").write_text("raise RuntimeError('user module imported')\n")
    monkeypatch.chdir(tmp_path)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # When: the CLI explains the current input snapshot.
    result = CliRunner().invoke(app, ["run", "must_not_import:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: JSON is uncontaminated and no user code or output publication occurs.
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["preparation"]["status"] == "not_invoked"
    assert before == {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("options", [["--explain"], ["--validate-only", "--explain", "--format", "yaml"], ["--format", "json"]])
def test_inapplicable_explain_options__explain_n3(options: list[str]) -> None:
    # Given: options outside the documented explain contract.
    # When: the CLI parses their combination.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", *options])
    # Then: a usage error occurs without importing the flow.
    assert result.exit_code == 3


def test_invalid_config_produces_schema_valid_error__explain_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: an invalid mode setting and an import that must never happen.
    (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: typo\n")
    monkeypatch.chdir(tmp_path)
    # When: explanation encounters invalid configuration.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: one versioned failure envelope carries the catalogued code.
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["error"]["code"] == 1002


@pytest.mark.parametrize("mode", ["invoice", "multidatatile", "smarttable", "excelinvoice", "rdeformat"])
def test_explain_five_modes__explain_p1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    # Given: one valid fixture for each supported registration mode.
    _generate.materialize_case(_generate.oracle_case(f"v1/{mode}/ok"), tmp_path)
    (tmp_path / "rdeconfig.yaml").write_text(f"system:\n  extended_mode: {mode}\n")
    monkeypatch.chdir(tmp_path)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # When: requesting a machine-readable explanation twice.
    args = ["run", "must_not_import:pipeline", "--validate-only", "--explain", "--format", "json"]
    result = CliRunner().invoke(app, args)
    repeated = CliRunner().invoke(app, args)
    # Then: all modes emit schema-valid reproducible output without mutations.
    assert result.exit_code == 0, result.output
    assert result.stdout == repeated.stdout
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["decision"]["chosen_mode"] == mode
    expected = {"rdeformat": "not_applicable", "smarttable": "deferred", "excelinvoice": "deferred"}.get(mode, "no_templates")
    assert payload["magic_preview"]["status"] == expected
    assert payload["graph_preview"]["status"] == ("deferred" if mode == "rdeformat" else "no_tabular_inputs")
    assert before == {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("contents", ["- one\n- two\n", "system: [unterminated\n"])
def test_invalid_override_is_structured__explain_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contents: str) -> None:
    # Given: malformed override material that previously bypassed JSON diagnostics.
    override = tmp_path / "override.yaml"
    override.write_text(contents)
    monkeypatch.chdir(tmp_path)
    # When: explaining with that override.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json", "--config", str(override)])
    # Then: exactly one error envelope follows the checked-in schema.
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["error"]["code"] == 1002
