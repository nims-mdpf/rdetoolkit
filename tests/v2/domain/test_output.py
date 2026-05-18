"""Tests for v2 domain output context implementation.

EP Table:
| API                   | Partition       | Rationale         | Expected       | Test ID   |
|-----------------------|-----------------|-------------------|----------------|-----------|
| create_output_context | valid root      | normal creation   | OutputContext  | TC-EP-001 |
| create_output_context | file root       | invalid root      | NotADirectoryError | TC-EP-002 |

BV Table:
| API                   | Boundary        | Rationale         | Expected       | Test ID   |
|-----------------------|-----------------|-------------------|----------------|-----------|
| create_output_context | create=False    | no side effects   | paths only     | TC-BV-001 |
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestCreateOutputContext:
    """Tests for OutputContext factory."""

    def test_creates_output_context_and_dirs__tc_ep_001(self, tmp_path: Path) -> None:
        """TC-EP-001: output context is created with standard directories."""
        from rdetoolkit.domain.output import create_output_context
        from rdetoolkit.types import OutputContext

        # Given: an output root
        output_root = tmp_path / "outputs"

        # When: creating output context
        context = create_output_context(output_root)

        # Then: concrete OutputContext and directories are available
        assert isinstance(context, OutputContext)
        assert context.logs.is_dir()
        assert context.other_image == output_root / "other_image"

    def test_file_root_raises__tc_ep_002(self, tmp_path: Path) -> None:
        """TC-EP-002: file output root is rejected."""
        from rdetoolkit.domain.output import create_output_context

        # Given: a file where a directory root is expected
        output_root = tmp_path / "outputs"
        output_root.write_text("not a directory", encoding="utf-8")

        # When / Then: context creation fails
        with pytest.raises(NotADirectoryError, match="Output root is not a directory"):
            create_output_context(output_root)

    def test_create_false_returns_paths_only__tc_bv_001(self, tmp_path: Path) -> None:
        """TC-BV-001: create=False does not create directories."""
        from rdetoolkit.domain.output import create_output_context

        # Given: a missing output root
        output_root = tmp_path / "outputs"

        # When: creating output context without filesystem writes
        context = create_output_context(output_root, create=False)

        # Then: path fields are resolved only
        assert context.raw == output_root / "raw"
        assert not context.raw.exists()
