"""Tests for v2 domain path resolution.

EP Table:
| API                 | Partition       | Rationale          | Expected         | Test ID   |
|---------------------|-----------------|--------------------|------------------|-----------|
| resolve_input_paths | valid root      | normal structure   | InputPaths       | TC-EP-001 |
| resolve_output_paths| valid root      | normal structure   | OutputContext    | TC-EP-002 |
| resolve_input_paths | missing root    | error path         | FileNotFoundError| TC-EP-003 |

BV Table:
| API                 | Boundary        | Rationale          | Expected         | Test ID   |
|---------------------|-----------------|--------------------|------------------|-----------|
| resolve_output_paths| create=False    | no side effects    | dirs absent      | TC-BV-001 |
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestDomainPaths:
    """Tests for path resolver helpers."""

    def test_resolve_input_paths__tc_ep_001(self, tmp_path: Path) -> None:
        """TC-EP-001: input paths are resolved from a root directory."""
        from rdetoolkit.domain.paths import resolve_input_paths

        # Given: an existing data root
        data_root = tmp_path / "data"
        data_root.mkdir()

        # When: resolving input paths
        paths = resolve_input_paths(data_root)

        # Then: standard v1-compatible child paths are returned
        assert paths.inputdata == data_root / "inputdata"
        assert paths.invoice == data_root / "invoice"
        assert paths.tasksupport == data_root / "tasksupport"

    def test_resolve_output_paths_creates_dirs__tc_ep_002(self, tmp_path: Path) -> None:
        """TC-EP-002: output paths create standard output directories."""
        from rdetoolkit.domain.paths import resolve_output_paths

        # Given: an output root
        output_root = tmp_path / "outputs"

        # When: resolving output paths with directory creation
        context = resolve_output_paths(output_root)

        # Then: output paths exist and use v1 names
        assert context.raw.is_dir()
        assert context.struct == output_root / "structured"
        assert context.thumbnail == output_root / "thumbnail"

    def test_missing_input_root_raises__tc_ep_003(self, tmp_path: Path) -> None:
        """TC-EP-003: missing input root is rejected."""
        from rdetoolkit.domain.paths import resolve_input_paths

        # Given: a missing input root
        data_root = tmp_path / "missing"

        # When / Then: resolving fails
        with pytest.raises(FileNotFoundError, match="Input root does not exist"):
            resolve_input_paths(data_root)

    def test_output_paths_without_create_have_no_side_effects__tc_bv_001(self, tmp_path: Path) -> None:
        """TC-BV-001: create=False does not create directories."""
        from rdetoolkit.domain.paths import resolve_output_paths

        # Given: a missing output root
        output_root = tmp_path / "outputs"

        # When: resolving without creation
        context = resolve_output_paths(output_root, create=False)

        # Then: paths are returned but not created
        assert context.raw == output_root / "raw"
        assert not context.raw.exists()
