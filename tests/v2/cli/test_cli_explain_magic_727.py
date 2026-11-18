"""Default text output of ``run --explain`` shows the magic preview (#727)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from tests.v2.runner.test_magic_preview_727 import _project

ARGS = ["run", "missing:pipeline", "--validate-only", "--explain"]


def _text(root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 0, result.output
    return result.stdout


def test_text_shows_field_code_and_remedy__magic_t1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a template naming a missing invoice key.
    _project(tmp_path, "invoice", name="${invoice:custom:absent}")
    # When: explaining in the default text format.
    output = _text(tmp_path, monkeypatch)
    # Then: status, field, code, remedy and the unchecked areas are visible.
    assert "Magic preview: previewed (pre_flow_snapshot)" in output
    line = next(line for line in output.splitlines() if "basic.dataName" in line)
    assert "unavailable" in line
    assert "[4010]" in line
    assert "Remedy:" in line
    assert "Not checked: invoice_schema, invoice_standard_checks, flow_side_effects" in output


def test_text_shows_deferred_metadata__magic_t2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a metadata template the flow will satisfy.
    _project(tmp_path, "invoice", name="${metadata:constant:thickness}")
    # When: explaining in text.
    output = _text(tmp_path, monkeypatch)
    # Then: the field is reported as deferred without an error code.
    line = next(line for line in output.splitlines() if "basic.dataName" in line)
    assert "deferred" in line
    assert "[" not in line


def test_text_shows_disabled_policy__magic_t3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: interpolation disabled in configuration.
    _project(tmp_path, "invoice", name="${invoice:basic:dataOwnerId}", policy="disabled")
    # When: explaining in text.
    output = _text(tmp_path, monkeypatch)
    # Then: the disabled summary is visible.
    assert "Magic preview: disabled (policy_disabled)" in output


def test_text_summarizes_row_tiles__magic_t4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: SmartTable, whose row invoices are built at runtime.
    _project(tmp_path, "smarttable", name="plain")
    # When: explaining in text.
    output = _text(tmp_path, monkeypatch)
    # Then: one summary line per tile status, not one line per row.
    assert "Magic preview: deferred (row_invoice_built_at_runtime)" in output
    assert any(line.strip().startswith("deferred (row_invoice_built_at_runtime):") for line in output.splitlines())
