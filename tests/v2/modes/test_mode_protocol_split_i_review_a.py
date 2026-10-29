"""ModeHandler capabilities are split (Session I-REVIEW-A, ruling #8 / F6, R6).

The executor reads ``raw_copy_strategy`` and ``artifact_stage_order`` through
``getattr``, and the docstrings called them optional. ``ModeHandler(Protocol)``
and its ``.pyi`` nevertheless declared them as ordinary members, so a handler
with only ``kind`` and ``create_tiles`` worked at runtime but was rejected by a
type checker. The repository's own mypy gate checks ``src/`` only, so the
mismatch was invisible.

``ModeHandler`` is now the minimum contract; the two capabilities are separate
protocols a handler may also satisfy.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-8-EP-070 | minimum | handler with ``kind`` + ``create_tiles`` | registers at runtime |
| TC-IRA-8-EP-071 | typing | same handler in a consumer module | mypy accepts it |
| TC-IRA-8-EP-072 | capabilities | built-in handlers | satisfy both capability protocols |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-8-EV-073 | typing | wrong ``raw_copy_strategy`` return type | mypy rejects it |
| TC-IRA-8-EV-074 | exports | ``rdetoolkit.modes`` | both capability protocols are public |
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterable
from pathlib import Path

import pytest

from rdetoolkit.modes import (
    ArtifactStageProvider,
    ModeHandler,
    PlanningContext,
    RawCopyStrategyProvider,
    handler_for,
    register,
)
from rdetoolkit.modes.excelinvoice import ExcelInvoiceModeHandler
from rdetoolkit.modes.invoice import InvoiceModeHandler
from rdetoolkit.modes.multidatatile import MultiDataTileModeHandler
from rdetoolkit.modes.rdeformat import RdeFormatModeHandler
from rdetoolkit.modes.smarttable import SmartTableModeHandler
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import TilePlan

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_MINIMAL_CONSUMER = """
from collections.abc import Iterable

from rdetoolkit.modes import ModeHandler, PlanningContext, register
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import TilePlan


class MinimalHandler:
    kind = ModeKind.invoice

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        return ()


def install() -> None:
    handler: ModeHandler = MinimalHandler()
    register(ModeKind.invoice, handler)
"""

_BAD_CAPABILITY_CONSUMER = """
from rdetoolkit.modes import RawCopyStrategyProvider
from rdetoolkit.runner.planner import ExecutionPlan


class WrongStrategyHandler:
    def raw_copy_strategy(self, plan: ExecutionPlan) -> int:
        return 1


def check() -> None:
    provider: RawCopyStrategyProvider = WrongStrategyHandler()
"""


class _MinimalHandler:
    """A handler that implements the documented minimum and nothing else."""

    kind = ModeKind.invoice

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        """Return no tiles; registration is what is under test."""
        _ = context
        return ()


def _run_mypy(source: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    module = tmp_path / "consumer.py"
    module.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "mypy",
            "--follow-imports=silent",
            "--no-error-summary",
            str(module),
        ],
        cwd=_REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _require_mypy() -> None:
    if shutil.which("mypy") is None and subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mypy", "--version"],
        check=False,
        capture_output=True,
    ).returncode != 0:
        pytest.skip("mypy is not available in this environment")


def test_minimum_handler_registers_at_runtime__tc_ira_8_ep_070(
    empty_mode_registry: None,
) -> None:
    """TC-IRA-8-EP-070: the documented minimum really is enough at runtime."""
    # Given: a handler with only the two required members
    _ = empty_mode_registry
    handler = _MinimalHandler()

    # When: registering it for a mode
    register(ModeKind.invoice, handler)

    # Then: the registry accepts and returns it
    assert handler_for(ModeKind.invoice) is handler


def test_minimum_handler_type_checks__tc_ira_8_ep_071(tmp_path: Path) -> None:
    """TC-IRA-8-EP-071: a typed consumer can implement the documented minimum."""
    # Given: a consumer module implementing only kind and create_tiles
    _require_mypy()

    # When: type checking it against the published protocol
    completed = _run_mypy(_MINIMAL_CONSUMER, tmp_path)

    # Then: mypy accepts what the runtime accepts
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "handler_type",
    [
        pytest.param(handler_type, id=f"TC-IRA-8-EP-072-{handler_type.__name__}")
        for handler_type in (
            InvoiceModeHandler,
            ExcelInvoiceModeHandler,
            MultiDataTileModeHandler,
            RdeFormatModeHandler,
            SmartTableModeHandler,
        )
    ],
)
def test_builtin_handlers_declare_both_capabilities__tc_ira_8_ep_072(handler_type: type) -> None:
    """TC-IRA-8-EP-072: splitting the protocol must not lose the built-ins' contract."""
    # Given: a built-in handler
    handler = handler_type()

    # When / Then: it satisfies the minimum and both capability protocols
    assert isinstance(handler, ModeHandler)
    assert isinstance(handler, RawCopyStrategyProvider)
    assert isinstance(handler, ArtifactStageProvider)


def test_wrong_capability_signature_is_rejected__tc_ira_8_ev_073(tmp_path: Path) -> None:
    """TC-IRA-8-EV-073: the capability protocols still constrain what they accept."""
    # Given: a consumer whose raw_copy_strategy returns the wrong type
    _require_mypy()

    # When: type checking it
    completed = _run_mypy(_BAD_CAPABILITY_CONSUMER, tmp_path)

    # Then: mypy rejects it, so the split did not weaken the contract
    assert completed.returncode != 0
    assert "RawCopyStrategyProvider" in completed.stdout


def test_capability_protocols_are_public__tc_ira_8_ev_074() -> None:
    """TC-IRA-8-EV-074: an external mode can name what it implements."""
    # Given / When: the public mode package
    import rdetoolkit.modes as module  # noqa: PLC0415

    # Then: both capabilities are exported alongside the minimum contract
    assert set(module.__all__) >= {
        "ArtifactStageProvider",
        "ModeHandler",
        "PlanningContext",
        "RawCopyStrategyProvider",
    }
