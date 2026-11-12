"""Issue #597 typing: the config models' stubs allow default construction.

Every settings model builds with no arguments at runtime, so a consumer type
checking against the installed stubs must be able to write the same call.
``model_config`` is a class attribute (``ClassVar`` on ``BaseModel``); declared
as a plain annotation in a stub it became a required constructor argument.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-597-TYPE-EP-1 | default construction | every v2 settings model, ``RdeConfig()``, ``MultiDataTileSettings()`` | mypy --strict clean |

Negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-597-TYPE-NG-1 | v2 invalid order | ``V2MultiDataTileSettings(order="random")`` | ``[arg-type]`` |
| TC-597-TYPE-NG-2 | v1 invalid order | ``MultiDataTileSettings(order="random")`` | ``[arg-type]`` |
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _check(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_config_models_build_with_defaults__tc_597_type_ep_1(tmp_path: Path) -> None:
    """TC-597-TYPE-EP-1: runtime-valid default construction type checks."""
    source = """from typing import Literal
from rdetoolkit.models.config import MultiDataTileSettings
from rdetoolkit.types import (
    RdeConfig,
    V2ExecutionSettings,
    V2MultiDataTileSettings,
    V2RecordingSettings,
    V2SmartTableSettings,
    V2SystemSettings,
)

V2SystemSettings()
V2ExecutionSettings()
V2RecordingSettings()
V2SmartTableSettings()
v2_order: Literal["name", "filesystem"] = V2MultiDataTileSettings().order
config = RdeConfig()
config_order: Literal["name", "filesystem"] = config.multidata_tile.order
V2MultiDataTileSettings(order="filesystem")
v1_order: Literal["name", "filesystem"] = MultiDataTileSettings().order
MultiDataTileSettings(ignore_errors=True, order="filesystem")
"""
    result = _check(tmp_path, source)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            'from rdetoolkit.types import V2MultiDataTileSettings\nV2MultiDataTileSettings(order="random")\n',
            id="tc_597_type_ng_1",
        ),
        pytest.param(
            'from rdetoolkit.models.config import MultiDataTileSettings\nMultiDataTileSettings(order="random")\n',
            id="tc_597_type_ng_2",
        ),
    ],
)
def test_invalid_order_is_rejected__tc_597_type_ng(tmp_path: Path, source: str) -> None:
    """TC-597-TYPE-NG-1/2: the stubs keep ``order`` a two-value Literal."""
    result = _check(tmp_path, source)
    assert result.returncode != 0
    assert "[arg-type]" in result.stdout, result.stdout + result.stderr
