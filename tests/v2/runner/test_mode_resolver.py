"""Tests for rdetoolkit v2 mode_resolver (TC-MODE-001..011).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority:
  - local/develop/v2/Design.md §6.2 (mode resolution priority + W1001)
  - decisions_pre_A1.md Ruling 5 (v1 spellings in config, lowercase enums in v2)
  - local/develop/v2/session_b1.md (CONTEXT: selected_input_checker delegation)

Resolution priority (inherited from domain/mode.py, MUST NOT change):
  smarttable files > excelinvoice files > config value

ModeKind enum members (lowercase, Design Ruling 5):
  invoice / excelinvoice / multidatatile / smarttable / rdeformat

W1001 ModeOverriddenByFileDetection:
  Emitted to EventSink AND stderr when config.system.extended_mode conflicts
  with the file-detected mode.

Function under test:
  resolve_mode(config, inputdata_path, unpacked_dir_path, event_sink, run_id) -> ModeKind
  (in rdetoolkit.runner.mode_resolver)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Target imports — fail until implementation exists (expected in Red phase):
# from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
# from rdetoolkit.types import RdeConfig, V2SystemSettings
# from rdetoolkit.report.events import MemoryEventSink


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _setup_inputdata(tmp_path: Path, filenames: list[str]) -> tuple[Path, Path]:
    """Create an inputdata directory with the given files; return (inputdata, unpacked) paths."""
    inputdata = tmp_path / "inputdata"
    inputdata.mkdir(parents=True, exist_ok=True)
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (inputdata / name).touch()
    return inputdata, unpacked


# ---------------------------------------------------------------------------
# ModeKind enum tests
# ---------------------------------------------------------------------------

class TestModeKindEnum:
    """Verify ModeKind enum has exactly the 5 lowercase members from Ruling 5."""

    def test_modekind_has_exactly_five_lowercase_members(self) -> None:
        """ModeKind must contain exactly {invoice, excelinvoice, multidatatile, smarttable, rdeformat}."""
        from rdetoolkit.runner.mode_resolver import ModeKind

        actual = {m.name for m in ModeKind}
        expected = {"invoice", "excelinvoice", "multidatatile", "smarttable", "rdeformat"}
        assert actual == expected, (
            f"ModeKind members mismatch. Expected {expected}, got {actual}"
        )


# ---------------------------------------------------------------------------
# resolve_mode — mode detection tests
# ---------------------------------------------------------------------------

class TestResolveMode:
    """Tests for resolve_mode() 5-mode detection (TC-MODE-001..011)."""

    def test_invoice_mode_with_invoice_config_and_no_special_files(
        self, tmp_path: Path
    ) -> None:
        """TC-MODE-001: config=invoice + no special input files -> ModeKind.invoice."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig

        config = RdeConfig()  # default: system.extended_mode = "invoice"
        inputdata, unpacked = _setup_inputdata(tmp_path, [])
        sink = MemoryEventSink()
        sink.open("run-001")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-001")

        assert mode == ModeKind.invoice, (
            f"invoice config + no special files must resolve to ModeKind.invoice, got {mode!r}"
        )

    def test_multidatatile_mode_with_multidatatile_config_and_no_special_files(
        self, tmp_path: Path
    ) -> None:
        """TC-MODE-002: config=MultiDataTile + no special input files -> ModeKind.multidatatile."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig, V2SystemSettings

        config = RdeConfig(system=V2SystemSettings(extended_mode="MultiDataTile"))
        inputdata, unpacked = _setup_inputdata(tmp_path, [])
        sink = MemoryEventSink()
        sink.open("run-002")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-002")

        assert mode == ModeKind.multidatatile, (
            f"MultiDataTile config + no special files must resolve to ModeKind.multidatatile, "
            f"got {mode!r}"
        )

    def test_rdeformat_mode_with_rdeformat_config_and_no_special_files(
        self, tmp_path: Path
    ) -> None:
        """TC-MODE-003: config=rdeformat + no special input files -> ModeKind.rdeformat."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig, V2SystemSettings

        config = RdeConfig(system=V2SystemSettings(extended_mode="rdeformat"))
        inputdata, unpacked = _setup_inputdata(tmp_path, [])
        sink = MemoryEventSink()
        sink.open("run-003")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-003")

        assert mode == ModeKind.rdeformat, (
            f"rdeformat config + no special files must resolve to ModeKind.rdeformat, "
            f"got {mode!r}"
        )

    def test_smarttable_mode_detected_regardless_of_config_when_smarttable_file_exists(
        self, tmp_path: Path
    ) -> None:
        """TC-MODE-004: smarttable_*.xlsx in inputdata -> ModeKind.smarttable (config-agnostic).

        File detection priority overrides configured mode per Design §6.2 / domain/mode.py.
        """
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig

        config = RdeConfig()  # default: invoice
        inputdata, unpacked = _setup_inputdata(tmp_path, ["smarttable_data.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-004")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-004")

        assert mode == ModeKind.smarttable, (
            f"smarttable_*.xlsx present must resolve to ModeKind.smarttable, got {mode!r}"
        )

    def test_excelinvoice_mode_detected_regardless_of_config_when_excel_invoice_file_exists(
        self, tmp_path: Path
    ) -> None:
        """TC-MODE-005: *_excel_invoice.xlsx in inputdata -> ModeKind.excelinvoice (config-agnostic).

        File detection priority overrides configured mode per Design §6.2 / domain/mode.py.
        """
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig

        config = RdeConfig()  # default: invoice
        inputdata, unpacked = _setup_inputdata(tmp_path, ["sample_excel_invoice.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-005")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-005")

        assert mode == ModeKind.excelinvoice, (
            f"*_excel_invoice.xlsx present must resolve to ModeKind.excelinvoice, got {mode!r}"
        )

    def test_smarttable_overrides_multidatatile_config_and_emits_w1001(
        self, tmp_path: Path
    ) -> None:
        """TC-MODE-006: config=MultiDataTile + smarttable file -> ModeKind.smarttable + W1001."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig, V2SystemSettings

        config = RdeConfig(system=V2SystemSettings(extended_mode="MultiDataTile"))
        inputdata, unpacked = _setup_inputdata(tmp_path, ["smarttable_measurements.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-006")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-006")

        assert mode == ModeKind.smarttable, (
            f"smarttable detection must override MultiDataTile config, got {mode!r}"
        )
        warning_events = [e for e in sink.events if e.name == "warning"]
        assert warning_events, (
            "W1001 must be emitted to EventSink when file detection overrides configured mode"
        )
        codes = [e.payload.get("code") for e in warning_events]
        assert 1001 in codes, (
            f"W1001 (code=1001) must be in emitted warnings, got codes={codes}"
        )

    def test_excelinvoice_overrides_multidatatile_config_and_emits_w1001(
        self, tmp_path: Path
    ) -> None:
        """TC-MODE-007: config=MultiDataTile + excel_invoice file -> ModeKind.excelinvoice + W1001."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig, V2SystemSettings

        config = RdeConfig(system=V2SystemSettings(extended_mode="MultiDataTile"))
        inputdata, unpacked = _setup_inputdata(tmp_path, ["data_excel_invoice.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-007")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-007")

        assert mode == ModeKind.excelinvoice, (
            f"excelinvoice detection must override MultiDataTile config, got {mode!r}"
        )
        warning_events = [e for e in sink.events if e.name == "warning"]
        assert warning_events, (
            "W1001 must be emitted to EventSink when file detection overrides configured mode"
        )
        codes = [e.payload.get("code") for e in warning_events]
        assert 1001 in codes, (
            f"W1001 (code=1001) must be in emitted warnings, got codes={codes}"
        )


# ---------------------------------------------------------------------------
# W1001 event and stderr tests
# ---------------------------------------------------------------------------

class TestW1001Emission:
    """Tests for W1001 ModeOverriddenByFileDetection event and stderr emission."""

    def test_w1001_emitted_to_eventsink_on_mode_conflict(self, tmp_path: Path) -> None:
        """TC-MODE-008: On mode conflict, EventSink receives Event with name='warning' and code=1001."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import resolve_mode
        from rdetoolkit.types import RdeConfig, V2SystemSettings

        config = RdeConfig(system=V2SystemSettings(extended_mode="MultiDataTile"))
        inputdata, unpacked = _setup_inputdata(tmp_path, ["smarttable_test.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-008")

        resolve_mode(config, inputdata, unpacked, sink, "run-008")

        warning_events = [
            e for e in sink.events
            if e.name == "warning" and e.payload.get("code") == 1001
        ]
        assert warning_events, (
            "EventSink must receive at least one warning event with code=1001 on mode conflict. "
            f"Events received: {sink.events}"
        )

    def test_w1001_message_written_to_stderr_on_mode_conflict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """TC-MODE-009: On mode conflict, stderr contains 'ModeOverriddenByFileDetection'."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import resolve_mode
        from rdetoolkit.types import RdeConfig, V2SystemSettings

        config = RdeConfig(system=V2SystemSettings(extended_mode="MultiDataTile"))
        inputdata, unpacked = _setup_inputdata(tmp_path, ["smarttable_test.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-009")

        resolve_mode(config, inputdata, unpacked, sink, "run-009")

        captured = capsys.readouterr()
        assert "ModeOverriddenByFileDetection" in captured.err, (
            f"stderr must contain 'ModeOverriddenByFileDetection' on conflict. "
            f"stderr was: {captured.err!r}"
        )

    def test_w1001_not_emitted_when_no_mode_conflict(self, tmp_path: Path) -> None:
        """TC-MODE-010: When configured mode matches detected mode, W1001 is NOT emitted."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import resolve_mode
        from rdetoolkit.types import RdeConfig

        config = RdeConfig()  # default: invoice, no special files -> invoice (no conflict)
        inputdata, unpacked = _setup_inputdata(tmp_path, [])
        sink = MemoryEventSink()
        sink.open("run-010")

        resolve_mode(config, inputdata, unpacked, sink, "run-010")

        warning_events = [
            e for e in sink.events
            if e.name == "warning" and e.payload.get("code") == 1001
        ]
        assert not warning_events, (
            f"W1001 must NOT be emitted when configured mode matches detected mode. "
            f"Unexpected warning events: {warning_events}"
        )


# ---------------------------------------------------------------------------
# domain/input_checker.py zero-diff guard
# ---------------------------------------------------------------------------

class TestInputCheckerZeroDiff:
    """Verify that the checker-selection contract is not modified by the mode_resolver implementation."""

    def test_input_checker_py_has_no_uncommitted_changes(self) -> None:
        """TC-MODE-011: git diff HEAD -- src/rdetoolkit/domain/input_checker.py must be empty.

        ``selected_input_checker`` carries the v1 detection order (SmartTable,
        Excel invoice, RDEFormat, MultiDataTile, invoice). Session K2(a) moved
        it from ``domain/mode.py`` into ``domain/input_checker.py``; the
        mode resolver wraps that function and must never rewrite it.
        """
        project_root = Path(__file__).parents[3]
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", "src/rdetoolkit/domain/input_checker.py"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        assert result.returncode == 0, (
            f"git diff failed with exit code {result.returncode}. "
            f"stderr: {result.stderr!r}"
        )
        assert result.stdout == "", (
            "domain/mode.py must not be modified. Diff found:\n" + result.stdout
        )


class TestW1001ExplicitScopeOnly:
    """PR #504 review: W1001 fires only when an EXPLICIT mode is overridden (Design §6.2)."""

    def test_no_w1001_when_default_config_and_file_detection(self, tmp_path: Path) -> None:
        """Default RdeConfig() + smarttable file: detection is normal, no warning."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig

        config = RdeConfig()  # extended_mode not explicitly set
        inputdata, unpacked = _setup_inputdata(tmp_path, ["smarttable_data.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-901")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-901")

        assert mode is ModeKind.smarttable
        warnings = [e for e in sink.events if e.name == "warning"]
        assert warnings == [], "W1001 must not fire for file detection over the implicit default"

    def test_w1001_still_fires_for_explicit_mode_conflict(self, tmp_path: Path) -> None:
        """Explicit MultiDataTile + smarttable file: the warning contract is unchanged."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
        from rdetoolkit.types import RdeConfig, V2SystemSettings

        config = RdeConfig(system=V2SystemSettings(extended_mode="MultiDataTile"))
        inputdata, unpacked = _setup_inputdata(tmp_path, ["smarttable_data.xlsx"])
        sink = MemoryEventSink()
        sink.open("run-902")

        mode = resolve_mode(config, inputdata, unpacked, sink, "run-902")

        assert mode is ModeKind.smarttable
        warnings = [e for e in sink.events if e.name == "warning"]
        assert len(warnings) == 1
