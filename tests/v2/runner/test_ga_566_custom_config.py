"""GA566 EP/BV: implicit and explicit custom configuration are equivalent."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.errors import RdeConfigError


@pytest.mark.parametrize("explicit", [False, True])
def test_cli_custom_is_flat_without_warning__ga566_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit: bool) -> None:
    """GA566-EP-1: real CLI config discovery and --config produce equal output."""
    from tests.v2.runner.test_event_log_robustness_k4 import _build_tree

    # Given: a production-shaped tasksupport configuration and a public flow
    _build_tree(tmp_path / "data")
    path = tmp_path / "data/tasksupport/rdeconfig.yaml"
    path.write_text("system:\n  save_thumbnail_image: false\ncustom:\n  regular: true\n  inverse: false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "ga566_flow.py").write_text(
        'from rdetoolkit import flow\nfrom rdetoolkit.types import RdeConfig, OutputContext\n'
        'from rdetoolkit.nodes import save_json\n@flow\ndef pipeline(config: RdeConfig, out: OutputContext) -> None:\n'
        '    save_json(config.custom, out, "custom.json")\n', encoding="utf-8",
    )
    arguments = ["run", "--flow", "ga566_flow:pipeline"]
    if explicit:
        arguments += ["--config", str(path)]
    # When: executing the actual CLI boundary
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = CliRunner().invoke(app, arguments)
    # Then: measured config has no extra custom wrapper or misleading warning
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "data/structured/custom.json").read_text()) == {"regular": True, "inverse": False}
    assert not any("Legacy configuration key 'custom'" in str(item.message) for item in caught)


def test_legacy_extras_merge_without_mutating_source__ga566_bv_1(tmp_path: Path) -> None:
    """GA566-BV-1: explicit custom wins collisions while unknown extras survive."""
    # Given: an old extension alongside an explicit custom namespace
    source = {"custom": {"regular": True, "vendor": "explicit"}, "vendor": "legacy"}
    # When: converting at the legacy model boundary
    with pytest.warns(UserWarning, match="vendor"):
        result = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")
    # Then: custom stays flat and the caller's mapping stays unchanged
    assert result.custom == {"regular": True, "vendor": "explicit"}
    assert source["vendor"] == "legacy"


@pytest.mark.parametrize("custom", [None, [], 7, "bad"])
def test_invalid_custom_rejected__ga566_neg_1(tmp_path: Path, custom: Any) -> None:
    """GA566-NEG-1: malformed custom sections never become nested valid data."""
    # Given: an invalid user custom section
    # When / Then: normalizing the legacy form keeps strict mapping validation
    with pytest.raises(RdeConfigError) as raised:
        ConfigNormalizer().normalize({"custom": custom}, root=tmp_path, origin="v1")
    assert raised.value.code == 1002
