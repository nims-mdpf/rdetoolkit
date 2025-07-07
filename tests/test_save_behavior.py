"""Tests for save_raw and save_nonshared_raw behavior."""
from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.modeproc import copy_input_to_rawfile
from rdetoolkit.models.config import Config, SystemSettings


class TestCopyInputToRawfile:
    """Test copy_input_to_rawfile function."""

    def test_copy_files_to_existing_directory(self, tmp_path: Path) -> None:
        """Test copying files to an existing directory."""
        # Setup
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        source_file1 = tmp_path / "file1.txt"
        source_file2 = tmp_path / "file2.txt"
        source_file1.write_text("content1")
        source_file2.write_text("content2")

        # Execute
        copy_input_to_rawfile(raw_dir, (source_file1, source_file2))

        # Verify
        assert (raw_dir / "file1.txt").exists()
        assert (raw_dir / "file2.txt").exists()
        assert (raw_dir / "file1.txt").read_text() == "content1"
        assert (raw_dir / "file2.txt").read_text() == "content2"

    def test_copy_files_to_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test copying files to a non-existent directory (should create it)."""
        # Setup
        raw_dir = tmp_path / "raw" / "nested" / "dir"
        assert not raw_dir.exists()

        source_file = tmp_path / "file.txt"
        source_file.write_text("content")

        copy_input_to_rawfile(raw_dir, (source_file,))

        assert raw_dir.exists()
        assert (raw_dir / "file.txt").exists()
        assert (raw_dir / "file.txt").read_text() == "content"

    def test_copy_empty_file_list(self, tmp_path: Path) -> None:
        """Test copying an empty list of files."""
        raw_dir = tmp_path / "raw"

        copy_input_to_rawfile(raw_dir, ())

        assert raw_dir.exists()


class TestSaveBehaviorParameters:
    """Test save_raw and save_nonshared_raw parameter behavior."""

    def test_default_values(self) -> None:
        """Test that default values are save_raw=False, save_nonshared_raw=True."""
        config = Config()
        assert config.system.save_raw is False
        assert config.system.save_nonshared_raw is True

    def test_save_raw_true_creates_and_copies_files(self, tmp_path: Path) -> None:
        """Test that when save_raw=True, files are copied to raw directory."""
        # Setup
        config = Config(system=SystemSettings(save_raw=True, save_nonshared_raw=False))
        raw_dir = tmp_path / "raw"
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        if config.system.save_raw:
            copy_input_to_rawfile(raw_dir, (source_file,))

        assert raw_dir.exists()
        assert (raw_dir / "test.txt").exists()
        assert (raw_dir / "test.txt").read_text() == "test content"

    def test_save_nonshared_raw_true_creates_and_copies_files(self, tmp_path: Path) -> None:
        """Test that when save_nonshared_raw=True, files are copied to nonshared_raw directory."""
        config = Config(system=SystemSettings(save_raw=False, save_nonshared_raw=True))
        nonshared_raw_dir = tmp_path / "nonshared_raw"
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        if config.system.save_nonshared_raw:
            copy_input_to_rawfile(nonshared_raw_dir, (source_file,))

        assert nonshared_raw_dir.exists()
        assert (nonshared_raw_dir / "test.txt").exists()
        assert (nonshared_raw_dir / "test.txt").read_text() == "test content"

    def test_both_false_no_copy(self, tmp_path: Path) -> None:
        """Test that when both save_raw=False and save_nonshared_raw=False, no files are copied."""
        config = Config(system=SystemSettings(save_raw=False, save_nonshared_raw=False))
        raw_dir = tmp_path / "raw"
        nonshared_raw_dir = tmp_path / "nonshared_raw"
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        if config.system.save_raw:
            copy_input_to_rawfile(raw_dir, (source_file,))

        if config.system.save_nonshared_raw:
            copy_input_to_rawfile(nonshared_raw_dir, (source_file,))

        assert not raw_dir.exists()
        assert not nonshared_raw_dir.exists()

    def test_both_true_copies_to_both_directories(self, tmp_path: Path) -> None:
        """Test that when both save_raw=True and save_nonshared_raw=True, files are copied to both directories."""
        config = Config(system=SystemSettings(save_raw=True, save_nonshared_raw=True))
        raw_dir = tmp_path / "raw"
        nonshared_raw_dir = tmp_path / "nonshared_raw"
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        if config.system.save_raw:
            copy_input_to_rawfile(raw_dir, (source_file,))

        if config.system.save_nonshared_raw:
            copy_input_to_rawfile(nonshared_raw_dir, (source_file,))

        assert raw_dir.exists()
        assert nonshared_raw_dir.exists()
        assert (raw_dir / "test.txt").exists()
        assert (nonshared_raw_dir / "test.txt").exists()
        assert (raw_dir / "test.txt").read_text() == "test content"
        assert (nonshared_raw_dir / "test.txt").read_text() == "test content"

    @pytest.mark.parametrize(
        "save_raw,save_nonshared_raw",
        [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ],
    )
    def test_no_error_with_any_combination(self, tmp_path: Path, save_raw: bool, save_nonshared_raw: bool) -> None:
        """Test that no error occurs with any combination of save_raw and save_nonshared_raw, and files are copied correctly."""
        config = Config(system=SystemSettings(save_raw=save_raw, save_nonshared_raw=save_nonshared_raw))
        raw_dir = tmp_path / "raw"
        nonshared_raw_dir = tmp_path / "nonshared_raw"
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        # Execute - should not raise any errors
        try:
            if config.system.save_raw:
                copy_input_to_rawfile(raw_dir, (source_file,))

            if config.system.save_nonshared_raw:
                copy_input_to_rawfile(nonshared_raw_dir, (source_file,))
        except Exception as e:
            pytest.fail(f"Unexpected error occurred with save_raw={save_raw}, save_nonshared_raw={save_nonshared_raw}: {e}")

        # Verify files are copied correctly based on configuration
        if save_raw:
            assert raw_dir.exists(), f"raw directory should exist when save_raw={save_raw}"
            assert (raw_dir / "test.txt").exists(), f"File should be copied to raw when save_raw={save_raw}"
            assert (raw_dir / "test.txt").read_text() == "test content"
        else:
            assert not raw_dir.exists(), f"raw directory should not exist when save_raw={save_raw}"

        if save_nonshared_raw:
            assert nonshared_raw_dir.exists(), f"nonshared_raw directory should exist when save_nonshared_raw={save_nonshared_raw}"
            assert (nonshared_raw_dir / "test.txt").exists(), f"File should be copied to nonshared_raw when save_nonshared_raw={save_nonshared_raw}"
            assert (nonshared_raw_dir / "test.txt").read_text() == "test content"
        else:
            assert not nonshared_raw_dir.exists(), f"nonshared_raw directory should not exist when save_nonshared_raw={save_nonshared_raw}"
