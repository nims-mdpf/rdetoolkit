"""GA565 EP/BV: unrelated build configuration cannot hide tasksupport."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit import flow, workflows
from rdetoolkit.cli.app import app
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.types import RdeConfig
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


@pytest.mark.parametrize("entry", ["v1", "v2", "cli"])
@pytest.mark.parametrize("toml", ['[project]\nname="x"\nversion="0"\n', '[tool.ruff]\nline-length=120\n'])
def test_unrelated_pyproject_preserves_artifacts__ga565_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str, toml: str) -> None:
    """GA565-NEG-1: implicit flow and CLI config match the frozen v1 artifact."""
    # Given: tasksupport owns raw-copy settings alongside an unrelated build file
    _build_tree(tmp_path / "data")
    (tmp_path / "pyproject.toml").write_text(toml, encoding="utf-8")
    (tmp_path / "data/tasksupport/rdeconfig.yaml").write_text(
        "system:\n  save_raw: true\n  save_nonshared_raw: false\n  save_thumbnail_image: true\n", encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    seen: list[bool] = []

    @flow
    def pipeline(config: RdeConfig) -> None:
        seen.append(config.system.save_thumbnail_image)

    # When: executing the actual selected entry without an explicit config
    if entry == "cli":
        monkeypatch.syspath_prepend(str(tmp_path))
        (tmp_path / "ga565_flow.py").write_text("from rdetoolkit import flow\n@flow\ndef pipeline() -> None:\n    pass\n", encoding="utf-8")
        result = CliRunner().invoke(app, ["run", "--flow", "ga565_flow:pipeline"])
        assert result.exit_code == 0, result.output
    elif entry == "v1":
        workflows.run()
    else:
        report = workflows.run(flow=pipeline)
        assert report.status == "success", report.error
        assert seen == [True]
    # Then: the same input is saved as raw, without the default nonshared copy
    assert (tmp_path / "data/raw/file_0.txt").read_text(encoding="utf-8") == "data-0"
    assert not (tmp_path / "data/nonshared_raw/file_0.txt").exists()


@pytest.mark.parametrize("content, expected", [(None, True), ("[tool.rdetoolkit]\n", False), ("[tool.rdetoolkit.system]\nsave_raw=true\n", True)])
def test_present_empty_table_keeps_precedence__ga565_bv_1(tmp_path: Path, content: str | None, expected: bool) -> None:
    """GA565-BV-1: only an absent table falls through; an empty table is explicit."""
    # Given: tasksupport config and an optional project-level table
    task = tmp_path / "data/tasksupport"
    task.mkdir(parents=True)
    (task / "rdeconfig.yaml").write_text("system:\n  save_raw: true\n", encoding="utf-8")
    if content is not None:
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
    # When: normalizing an implicit v2 configuration
    config = ConfigNormalizer().normalize(None, root=tmp_path, data_root=tmp_path / "data", origin="v2")
    # Then: a present configuration retains its declared priority
    assert config.system.save_raw is expected


@pytest.mark.parametrize("content", ["[broken", '[tool]\nrdetoolkit="bad"\n'])
def test_invalid_project_config_is_not_ignored__ga565_neg_2(tmp_path: Path, content: str) -> None:
    """GA565-NEG-2: malformed or nonmapping TOML is a catalogued input error."""
    # Given: an invalid configuration candidate
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
    # When / Then: discovery reports the existing configuration error
    with pytest.raises(RdeConfigError) as raised:
        ConfigNormalizer().normalize(None, root=tmp_path, data_root=tmp_path / "data", origin="v2")
    assert raised.value.code == 1002
