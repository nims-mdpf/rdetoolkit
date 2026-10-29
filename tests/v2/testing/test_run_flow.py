"""Tests for the rdetoolkit.testing Phase B skeleton (TC-TEST-001..003).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md §13.3
Session authority: local/develop/v2/tasks/session_b2.md (B2.7, v2.1 supplement),
    local/develop/v2/review/phase_c_kickoff.md §C-0 item 3

Scope note (Phase B only): ``rdetoolkit.testing`` provides only the skeleton
API exercised here — ``run_flow`` and ``assert_output_tree``. The pytest
plugin (entry_points registration) and the fixtures kit
(``rde_paths``/``rde_out``/``rde_config``/``rde_invoice``/builders) are
Phase C scope and are intentionally NOT exercised by this file.

Note: this file corresponds to the "test_testing_kit.py" acceptance surface
named in local/develop/v2/tasks/session_b2.md; it is placed at
``test_run_flow.py`` per the tdd-enforcer dispatch for this session.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.domain.output import create_output_context
from rdetoolkit.report.run_report import RunReport

# Target import — fails until implementation exists (expected in Red phase):
from rdetoolkit.testing import assert_output_tree, run_flow

_CANONICAL_OUTPUT_DIRNAMES = (
    "structured",
    "meta",
    "main_image",
    "other_image",
    "thumbnail",
    "attachment",
    "nonshared_raw",
    "raw",
    "invoice",
    "logs",
)


class TestRunFlowSkeleton:
    """TC-TEST-001: run_flow(flow_fn, fixture_dir) returns a RunReport instance."""

    def test_run_flow_returns_run_report_instance(self, tmp_path: Path) -> None:
        """A normal run_flow() call must return a RunReport, not a raw dict or None."""

        def stub_flow(*args: object, **kwargs: object) -> None:
            return None

        report = run_flow(stub_flow, tmp_path)

        assert isinstance(report, RunReport)


class TestAssertOutputTreeMatch:
    """TC-TEST-002: assert_output_tree passes silently when trees match."""

    def test_assert_output_tree_passes_when_trees_match(self, tmp_path: Path) -> None:
        """No exception must be raised when out and golden_dir share the same directory set."""
        out = create_output_context(tmp_path / "out", create=True)
        golden_dir = tmp_path / "golden"
        for dirname in _CANONICAL_OUTPUT_DIRNAMES:
            (golden_dir / dirname).mkdir(parents=True)

        assert assert_output_tree(out, golden_dir) is None


class TestAssertOutputTreeMismatch:
    """TC-TEST-003: assert_output_tree raises AssertionError when trees mismatch."""

    def test_assert_output_tree_raises_on_missing_directory(self, tmp_path: Path) -> None:
        """Omitting one golden directory (e.g. logs/) must raise AssertionError."""
        out = create_output_context(tmp_path / "out", create=True)
        golden_dir = tmp_path / "golden"
        for dirname in _CANONICAL_OUTPUT_DIRNAMES:
            if dirname == "logs":
                continue
            (golden_dir / dirname).mkdir(parents=True)

        with pytest.raises(AssertionError):
            assert_output_tree(out, golden_dir)

    def test_assert_output_tree_raises_on_extra_directory(self, tmp_path: Path) -> None:
        """An unexpected extra directory in golden_dir must also raise AssertionError."""
        out = create_output_context(tmp_path / "out", create=True)
        golden_dir = tmp_path / "golden"
        for dirname in _CANONICAL_OUTPUT_DIRNAMES:
            (golden_dir / dirname).mkdir(parents=True)
        (golden_dir / "unexpected_extra_dir").mkdir(parents=True)

        with pytest.raises(AssertionError):
            assert_output_tree(out, golden_dir)


class TestMissingDirectoryDetection:
    """PR #504 review: a missing output directory must fail assert_output_tree."""

    def test_missing_actual_directory_raises(self, tmp_path: Path) -> None:
        from types import SimpleNamespace

        from rdetoolkit.testing import assert_output_tree
        from rdetoolkit.types import OutputContext

        base = tmp_path / "out"
        names = (
            "struct", "meta", "main_image", "other_image", "thumbnail",
            "attachment", "nonshared_raw", "raw", "invoice", "logs",
        )
        out = OutputContext.from_resource_paths(
            SimpleNamespace(**{n: base / n for n in names})
        )
        golden = tmp_path / "golden"
        for n in names:
            (golden / n).mkdir(parents=True)
        # actual has NO directories on disk -> must not be treated as complete
        with pytest.raises(AssertionError):
            assert_output_tree(out, golden)
