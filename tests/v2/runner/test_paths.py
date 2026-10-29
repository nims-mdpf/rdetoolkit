"""Tests for rdetoolkit v2 runner tile path resolution (TC-PATH-001..007).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md §6.3, §6.4, §4.2 (v2.1 R3)
Session authority: local/develop/v2/tasks/session_b2.md (B2.1/B2.2)

Divided/ rule (v1-compatible, StorageDir.__nDigit == 4):
    idx == 0 -> directly under base_dir (no ``divided/`` segment)
    idx >= 1 -> base_dir/divided/{idx:04d}/

``resolve_tile_paths`` MUST NOT create any directory on disk (no ``mkdir``);
directory creation is owned exclusively by Runner step 4a. Its return value
must expose the ten canonical output-kind attributes (Design §4.2) so that
``OutputContext.from_resource_paths(...)`` can adapt it into an
``OutputContext`` instance.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``resolve_data_root`` | existing nested ``data`` | nested directory | TC-EP-HR2-B-002 |
| ``resolve_data_root`` | alias-flat markers | supplied root | TC-EP-HR2-B-003 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``resolve_data_root`` | root named ``data`` | supplied root | TC-BV-HR2-B-002 |
| ``resolve_data_root`` | bare project root | future ``root/data`` | TC-BV-HR2-B-003 |
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.types import OutputContext

# Target import — fails until implementation exists (expected in Red phase):
from rdetoolkit.runner.paths import resolve_data_root, resolve_tile_paths

# v1 RdeOutputResourcePath field -> on-disk directory basename
# (rdetoolkit.types.OutputContext docstring "v1 field coverage" table).
_OUTPUT_FIELD_TO_DIRNAME = {
    "struct": "structured",
    "meta": "meta",
    "main_image": "main_image",
    "other_image": "other_image",
    "thumbnail": "thumbnail",
    "attachment": "attachment",
    "nonshared_raw": "nonshared_raw",
    "raw": "raw",
    "invoice": "invoice",
    "logs": "logs",
}


class TestResolveDataRootPriority:
    """Finding B pins the four-tier project/flat-root resolver contract."""

    def test_explicit_data_name_is_flat__tc_bv_hr2_b_002(self, tmp_path: Path) -> None:
        """TC-BV-HR2-B-002: a directory named data is explicitly flat."""
        # Given: an existing root whose basename is data
        root = tmp_path / "data"
        root.mkdir()

        # When/Then: the explicit flat root resolves to itself
        assert resolve_data_root(root) == root

    def test_existing_nested_data_wins__tc_ep_hr2_b_002(self, tmp_path: Path) -> None:
        """TC-EP-HR2-B-002: an existing nested data directory is canonical."""
        # Given: a project root with an existing data child
        candidate = tmp_path / "data"
        candidate.mkdir()

        # When/Then: the existing nested child is selected
        assert resolve_data_root(tmp_path) == candidate

    def test_alias_flat_markers_select_root__tc_ep_hr2_b_003(self, tmp_path: Path) -> None:
        """TC-EP-HR2-B-003: RDE marker directories identify an alias-flat root."""
        # Given: a non-data-named root with the minimum RDE marker vocabulary
        root = tmp_path / "fixture-root"
        root.mkdir()
        (root / "inputdata").mkdir()

        # When/Then: the alias-flat root remains direct
        assert resolve_data_root(root) == root

    def test_bare_project_root_selects_future_data_child__tc_bv_hr2_b_003(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-BV-HR2-B-003: a bare project root defaults to its data child."""
        # Given: a bare project root with no data child or RDE markers
        root = tmp_path / "project-root"
        root.mkdir()

        # When/Then: resolution identifies the child Runner must create
        assert resolve_data_root(root) == root / "data"


class TestResolveTilePathsBaseCase:
    """TC-PATH-001: index=0 resolves directly under base_dir, no divided/."""

    def test_idx_zero_resolves_directly_under_base_dir(self, tmp_path: Path) -> None:
        """idx=0 must place every output-kind directory directly under base_dir."""
        resource_paths = resolve_tile_paths(tmp_path, 0)

        for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
            resolved = getattr(resource_paths, field)
            assert "divided" not in str(resolved), f"idx=0 must not use divided/: {field} -> {resolved}"
            assert resolved == tmp_path / dirname


class TestResolveTilePathsDividedCase:
    """TC-PATH-002 / TC-PATH-003: index>=1 resolves under divided/{idx:04d}/."""

    def test_idx_one_resolves_under_divided_0001(self, tmp_path: Path) -> None:
        """idx=1 must place every output-kind directory under divided/0001/."""
        resource_paths = resolve_tile_paths(tmp_path, 1)

        for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
            resolved = getattr(resource_paths, field)
            assert resolved == tmp_path / "divided" / "0001" / dirname

    def test_idx_9999_resolves_under_divided_9999(self, tmp_path: Path) -> None:
        """idx=9999 must still use the fixed 4-digit zero-padded scheme."""
        resource_paths = resolve_tile_paths(tmp_path, 9999)

        for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
            resolved = getattr(resource_paths, field)
            assert resolved == tmp_path / "divided" / "9999" / dirname


class TestResolveTilePathsOutputContextAdapter:
    """TC-PATH-004: return value is convertible via OutputContext.from_resource_paths()."""

    def test_from_resource_paths_returns_output_context_instance(self, tmp_path: Path) -> None:
        """OutputContext.from_resource_paths(resolve_tile_paths(...)) must yield an OutputContext."""
        resource_paths = resolve_tile_paths(tmp_path, 0)

        ctx = OutputContext.from_resource_paths(resource_paths)

        assert isinstance(ctx, OutputContext)
        assert ctx.struct == tmp_path / "structured"
        assert ctx.logs == tmp_path / "logs"


class TestResolveTilePathsNoSideEffects:
    """TC-PATH-005: resolve_tile_paths never creates directories (Runner step 4a owns mkdir)."""

    def test_resolve_tile_paths_does_not_create_directories(self, tmp_path: Path) -> None:
        """Calling resolve_tile_paths for idx=0 and idx=1 must leave tmp_path empty on disk."""
        resolve_tile_paths(tmp_path, 0)
        resolve_tile_paths(tmp_path, 1)
        resolve_tile_paths(tmp_path, 42)

        assert list(tmp_path.iterdir()) == [], "resolve_tile_paths must not perform any mkdir"


class TestResolveTilePathsFieldCoverage:
    """TC-PATH-006: all ten canonical output-kind fields are present as Path values."""

    def test_resolve_tile_paths_exposes_ten_output_fields(self, tmp_path: Path) -> None:
        """Every OutputContext-compatible field must be present and a Path instance."""
        resource_paths = resolve_tile_paths(tmp_path, 0)

        for field in _OUTPUT_FIELD_TO_DIRNAME:
            value = getattr(resource_paths, field)
            assert isinstance(value, Path), f"{field} must be a Path, got {type(value)!r}"

    def test_resolve_tile_paths_field_set_matches_output_context_kinds(self, tmp_path: Path) -> None:
        """No output-kind field may be missing when adapted through from_resource_paths()."""
        resource_paths = resolve_tile_paths(tmp_path, 0)
        ctx = OutputContext.from_resource_paths(resource_paths)

        for field in _OUTPUT_FIELD_TO_DIRNAME:
            assert isinstance(getattr(ctx, field), Path)


class TestResolveTilePathsRelativeLayout:
    """TC-PATH-007: idx=0 -> base/{dir}; idx>0 -> base/divided/{n:04d}/{dir}."""

    @pytest.mark.parametrize("idx", [0, 1, 2, 42, 9999])
    def test_relative_layout_matches_divided_rule(self, tmp_path: Path, idx: int) -> None:
        """The base-relative layout must follow the fixed divided/ rule for any idx."""
        resource_paths = resolve_tile_paths(tmp_path, idx)

        expected_root = tmp_path if idx == 0 else tmp_path / "divided" / f"{idx:04d}"

        assert resource_paths.logs == expected_root / "logs"
        assert resource_paths.invoice == expected_root / "invoice"
        assert resource_paths.struct == expected_root / "structured"
