"""Privacy and diagnostic partitions for rejected configuration values.

| ID | Partition | Expected |
|----|-----------|----------|
| CP-N1 | rejected literal through a mapping | 1002, allowed values, no payload |
| CP-N2 | rejected literal through CLI YAML | 1002 JSON, allowed values, no payload |
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.errors import RdeConfigError


def _assert_safe_diagnostic(message: str) -> None:
    assert "execution.type_check" in message
    assert all(repr(value) in message for value in ("off", "warn", "strict"))
    assert "SECRET" not in message


def test_literal_error_preserves_choices_without_input__cp_n1(tmp_path: Path) -> None:
    """CP-N1: normalizer errors retain safe choices without private input."""
    # Given: a private string that is not a supported type-check policy.
    source = {"execution": {"type_check": "SECRET_INVALID_VALUE"}}
    # When: normalizing configuration through the public boundary.
    with pytest.raises(RdeConfigError) as caught:
        ConfigNormalizer().normalize(source, root=tmp_path, origin="v2")
    # Then: the catalogued error lists choices without the rejected payload.
    assert caught.value.code == 1002
    _assert_safe_diagnostic(str(caught.value))


def test_explain_literal_error_preserves_choices_without_input__cp_n2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CP-N2: explanation JSON retains safe choices without private input."""
    # Given: a discovered YAML configuration containing a private invalid policy.
    (tmp_path / "rdeconfig.yaml").write_text("execution:\n  type_check: SECRET_INVALID_VALUE\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: explaining the rejected configuration without loading user code.
    result = CliRunner().invoke(app, ["run", "missing:pipeline", "--validate-only", "--explain", "--format", "json"])
    # Then: JSON retains corrective choices and excludes the private input.
    assert result.exit_code == 1, result.output
    error = json.loads(result.stdout)["error"]
    assert error["code"] == 1002
    _assert_safe_diagnostic(result.stdout)
