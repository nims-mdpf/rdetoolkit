"""GA586 EP/BV: the v1 callback entry keeps v1's ``Config`` extras layout.

#566 flattened the ``custom:`` section into ``RdeConfig.custom`` for the flow
entry. The v1 callback entry must still hand its callback the extras v1.7.1
built from the same file: unknown top-level keys stay top-level and the
``custom:`` section stays ``Config.custom``.

| ID           | Kind     | Input                                                    | Expected (v1.7.1)                                |
|--------------|----------|----------------------------------------------------------|--------------------------------------------------|
| GA586-EP-1   | EP valid | tasksupport ``custom:`` section, ``config=None``          | ``config.custom == {...}``, extras ``{custom}``  |
| GA586-EP-2   | EP valid | ``custom:`` section and a top-level key of the same name | both kept where the file put them                |
| GA586-EP-3   | EP valid | explicit ``Config(custom=..., threshold=...)``            | extras equal the explicit ``Config``'s extras    |
| GA586-BV-1   | BV       | callback mutates ``config.custom`` on every tile          | the next tile and the caller's ``Config`` unchanged |
| GA586-EP-4   | EP valid | v2 ``RdeConfig`` source on the v1 entry                   | ``custom`` keys stay top-level (J-REVIEW #1)     |
"""

from __future__ import annotations

import copy
import warnings
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import workflows
from rdetoolkit.models.config import Config, SystemSettings
from rdetoolkit.types import RdeConfig
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


def _run_v1_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, rdeconfig: str | None = None, config: Any = None, files: int = 1) -> list[dict[str, Any]]:
    """Run the v1 callback entry and return what each tile's callback saw."""
    _build_tree(tmp_path / "data")
    for index in range(1, files):
        (tmp_path / "data/inputdata" / f"file_{index}.txt").write_text(f"data-{index}", encoding="utf-8")
    if rdeconfig is not None:
        (tmp_path / "data/tasksupport/rdeconfig.yaml").write_text(rdeconfig, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seen: list[dict[str, Any]] = []

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        del resource_paths
        legacy = srcpaths.config
        seen.append(
            {
                "has_custom": hasattr(legacy, "custom"),
                "custom": copy.deepcopy(getattr(legacy, "custom", None)),
                "extras": copy.deepcopy(legacy.model_extra),
            },
        )
        if isinstance(getattr(legacy, "custom", None), dict):
            legacy.custom["regular"] = "mutated"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        workflows.run(custom_dataset_function=callback, config=config)
    return seen


def test_tasksupport_custom_section_stays_config_custom__ga586_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA586-EP-1: the issue's reproduction prints v1.7.1's output."""
    # Given: the issue's tasksupport rdeconfig.yaml with a custom: section
    rdeconfig = 'custom:\n  regular: "Fm-3m"\nsystem:\n  save_raw: true\n'
    # When: the v1 entry discovers it (config=None)
    seen = _run_v1_entry(tmp_path, monkeypatch, rdeconfig=rdeconfig)
    # Then: True {'regular': 'Fm-3m'} {'custom': {'regular': 'Fm-3m'}}, as 1.7.1
    assert seen == [{"has_custom": True, "custom": {"regular": "Fm-3m"}, "extras": {"custom": {"regular": "Fm-3m"}}}]


def test_top_level_and_custom_section_keep_their_origin__ga586_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA586-EP-2: a top-level key and a custom: key of the same name both survive."""
    # Given: an unknown top-level key and a custom: section reusing its name
    rdeconfig = "threshold: 1\ncustom:\n  threshold: 2\n  regular: true\n"
    # When: the v1 entry discovers it
    seen = _run_v1_entry(tmp_path, monkeypatch, rdeconfig=rdeconfig)
    # Then: neither origin overwrites the other, exactly as v1 Config(**file)
    assert [entry["extras"] for entry in seen] == [{"threshold": 1, "custom": {"threshold": 2, "regular": True}}]


def test_explicit_v1_config_extras_reach_the_callback__ga586_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA586-EP-3: an explicit v1 Config's extras arrive unchanged."""
    # Given: an explicit v1 Config with a custom section and a top-level extra
    config = Config(system=SystemSettings(save_raw=True), custom={"regular": "Fm-3m"}, threshold=0.5)  # type: ignore[call-arg]
    # When: it is passed through the v1 entry
    seen = _run_v1_entry(tmp_path, monkeypatch, config=config)
    # Then: the callback sees the same extras the caller built
    assert [entry["extras"] for entry in seen] == [{"custom": {"regular": "Fm-3m"}, "threshold": 0.5}]


def test_callback_mutation_stays_inside_its_tile__ga586_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA586-BV-1: a tile mutating config.custom affects neither later tiles nor the caller."""
    # Given: an explicit Config and a MultiDataTile run with two tiles
    config = Config(system=SystemSettings(extended_mode="MultiDataTile"), custom={"regular": "Fm-3m"})  # type: ignore[call-arg]
    # When: every callback mutates its config.custom
    seen = _run_v1_entry(tmp_path, monkeypatch, config=config, files=2)
    # Then: each tile saw the original value and the caller's Config is untouched
    assert [entry["custom"] for entry in seen] == [{"regular": "Fm-3m"}, {"regular": "Fm-3m"}]
    assert config.model_extra == {"custom": {"regular": "Fm-3m"}}


def test_v2_config_source_keeps_the_flat_projection__ga586_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA586-EP-4: a v2 RdeConfig on the v1 entry keeps J-REVIEW ruling #1."""
    # Given: a canonical v2 config whose custom namespace is flat
    config = RdeConfig(custom={"regular": "Fm-3m"})
    # When: it is passed through the v1 entry
    seen = _run_v1_entry(tmp_path, monkeypatch, config=config)
    # Then: its custom keys are v1 top-level extras, as before #586
    assert [entry["extras"] for entry in seen] == [{"regular": "Fm-3m"}]
