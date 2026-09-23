"""Shared helpers for the real-canary mode parity cells.

Sessions I6-A/B/C grew one copy of ``_canary_flow`` / ``_frozen_canary`` /
``_discovered_config`` / ``_run_canary`` per mode module. The four bodies were
byte-identical apart from the mode name, which made them a three-way drift
risk: a ruling that changed how a canary is run had to be applied three times
or the modes would silently stop testing the same thing. Session I-REVIEW-A
recorded the triplication as debt 3; this module settles it.

The behavior is deliberately unchanged. In particular :func:`run_canary` still
accepts no configuration argument, because ruling #4 makes
``data_root/tasksupport/rdeconfig.yaml`` the one configuration source a canary
cell may use — a cell that could pass overrides would be able to reintroduce
the bypass review F2 found.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.config_loader import load_config
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, InvoiceData, RdeConfig
from tests.v2.contract.fixtures import _generate


@flow
def canary_flow(paths: InputPaths, invoice: InvoiceData) -> None:
    """Consume one tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()
    assert invoice.raw


def frozen_canary(mode: str) -> dict[str, Any]:
    """Return the frozen v1 canary snapshot for one mode.

    Args:
        mode: One of the five canary mode families.

    Returns:
        The parsed snapshot, including its ``case`` provenance.
    """
    path = _generate.CANARY_EXPECTED_ROOT / mode / "ok.json"
    return json.loads(path.read_text(encoding="utf-8"))


def discovered_config(mode: str) -> RdeConfig:
    """Load the canary's configuration exactly as a production run does.

    Args:
        mode: One of the five canary mode families.

    Returns:
        The effective configuration production discovery finds for the
        assembled canary, with no override of any kind applied.
    """
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / mode
        _generate._materialize_canary_case(mode, root)  # noqa: SLF001 -- shared canary assembly
        return load_config(root, data_root=root / "data")


def run_canary(mode: str, root: Path, monkeypatch: pytest.MonkeyPatch) -> RunReport:
    """Run one canary family with production discovery and no overrides.

    Args:
        mode: One of the five canary mode families.
        root: Directory to assemble the canary into and run from.
        monkeypatch: Fixture used to make ``root`` the process CWD, as a real
            structured program's entry point does.

    Returns:
        The run report the v2 Runner produced.
    """
    _generate._materialize_canary_case(mode, root)  # noqa: SLF001 -- shared canary assembly
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # The flow entry unpacks into data/temp, as v1 does (contracts.md §I6-1).
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(canary_flow)
