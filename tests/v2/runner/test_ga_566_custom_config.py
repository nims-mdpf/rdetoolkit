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
    arguments = ["run", "ga566_flow:pipeline"]
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


_TEMPLATE_SECTION_YAML = (
    "system:\n  extended_mode: null\n  save_raw: true\n"
    "sem:\n  magnification_key: Mag\n  thumbnail: true\n"
)


def test_tasksupport_template_section_is_custom_without_warning__i624_ep_1(tmp_path: Path) -> None:
    """I624-EP-1: a v1 template section reaches config.custom silently."""
    # Given: an unchanged v1 template keeping its settings next to ``system:``
    data_root = tmp_path / "data"
    (data_root / "tasksupport").mkdir(parents=True)
    (data_root / "tasksupport/rdeconfig.yaml").write_text(_TEMPLATE_SECTION_YAML, encoding="utf-8")
    # When: the Runner discovers the tasksupport file through the v1 loader
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = ConfigNormalizer().normalize(None, root=tmp_path, origin="v2", data_root=data_root)
    # Then: the section is template settings under custom, and no warning fires
    assert result.custom == {"sem": {"magnification_key": "Mag", "thumbnail": True}}


def test_explicit_custom_wins_over_template_section__i624_bv_1(tmp_path: Path) -> None:
    """I624-BV-1: an explicit custom entry of the same name wins, silently."""
    # Given: a template section and an explicit custom entry with the same name
    source = {"sem": {"thumbnail": True}, "custom": {"sem": {"thumbnail": False}}}
    # When: converting at the legacy model boundary
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")
    # Then: explicit custom keeps priority
    assert result.custom == {"sem": {"thumbnail": False}}


def test_non_mapping_legacy_key_warns_with_remediation__i624_neg_1(tmp_path: Path) -> None:
    """I624-NEG-1: a top-level scalar is not a template section; the warning says what to do."""
    # Given / When: a v1 top-level scalar outside every known section
    with pytest.warns(UserWarning, match=r"'vendor'.*move it under `custom:`"):
        result = ConfigNormalizer().normalize({"vendor": "legacy"}, root=tmp_path, origin="v1")
    # Then: the value is still preserved
    assert result.custom == {"vendor": "legacy"}


@pytest.mark.parametrize(
    ("key", "section"),
    [("sytem", "system"), ("System", "system"), ("smartable", "smarttable"), ("multidata_tiles", "multidata_tile"), ("custm", "custom")],
)
def test_misspelled_v1_section_still_warns__i624_neg_3(tmp_path: Path, key: str, section: str) -> None:
    """I624-NEG-3: a mapping named like a v1 section is a likely typo and keeps warning."""
    # Given: a typo of a v1 section whose settings would otherwise fall back to defaults
    source = {key: {"extended_mode": "MultiDataTile"}}
    # When / Then: the warning names the intended section
    with pytest.warns(UserWarning, match=rf"{key!r} looks like the v1 section {section!r}"):
        result = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")
    # Then: the value is still preserved, not applied
    assert result.custom == {key: {"extended_mode": "MultiDataTile"}}
    assert result.system.extended_mode == "invoice"


@pytest.mark.parametrize("key", ["sem", "xps", "eis", "vsm", "analysis", "instrument"])
def test_template_section_names_do_not_warn__i624_bv_2(tmp_path: Path, key: str) -> None:
    """I624-BV-2: real template section names are not mistaken for v1 typos."""
    # Given / When: a template section with a name unlike every v1 section
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = ConfigNormalizer().normalize({key: {"enabled": True}}, root=tmp_path, origin="v1")
    # Then: it is template settings, silently
    assert result.custom == {key: {"enabled": True}}


def test_v2_form_rejects_template_section__i624_neg_2(tmp_path: Path) -> None:
    """I624-NEG-2: the v2 form keeps rejecting unknown sections so typos fail."""
    # Given: the same section in a project-root v2 rdeconfig.yaml
    (tmp_path / "rdeconfig.yaml").write_text(_TEMPLATE_SECTION_YAML, encoding="utf-8")
    # When / Then: discovery of the v2 form raises the configuration error
    with pytest.raises(RdeConfigError) as raised:
        ConfigNormalizer().normalize(None, root=tmp_path, origin="v2", data_root=tmp_path / "data")
    assert raised.value.code == 1002
