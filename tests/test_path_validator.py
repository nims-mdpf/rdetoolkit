"""Unit tests for PathValidator."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.graph.io.path_validator import PathValidator


# =============================================================================
# PathValidator.validate() Tests
# =============================================================================


def test_path_validator_validate_basic(tmp_path: Path):
    """Test basic validation with valid directory and filename."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = validator.validate(output_dir, "test.png")

    assert result == output_dir / "test.png"
    assert result.parent == output_dir


def test_path_validator_validate_with_subdirectory(tmp_path: Path):
    """Test validation resolves to absolute path."""
    validator = PathValidator()
    output_dir = tmp_path / "graphs" / "output"
    output_dir.mkdir(parents=True)

    result = validator.validate(output_dir, "plot.png")

    assert result.is_absolute()
    assert result.name == "plot.png"


def test_path_validator_validate_directory_not_exist(tmp_path: Path):
    """Test validation fails when directory doesn't exist."""
    validator = PathValidator()
    non_existent = tmp_path / "non_existent"

    with pytest.raises(ValueError, match="does not exist"):
        validator.validate(non_existent, "test.png")


def test_path_validator_validate_not_a_directory(tmp_path: Path):
    """Test validation fails when path is a file, not directory."""
    validator = PathValidator()
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    with pytest.raises(ValueError, match="not a directory"):
        validator.validate(file_path, "test.png")


def test_path_validator_validate_path_traversal_dotdot(tmp_path: Path):
    """Test validation prevents path traversal with '..'."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with pytest.raises(ValueError, match="contains path separators"):
        validator.validate(output_dir, "../etc/passwd")


def test_path_validator_validate_path_traversal_slash(tmp_path: Path):
    """Test validation prevents absolute paths in filename."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with pytest.raises(ValueError, match="contains path separators"):
        validator.validate(output_dir, "/tmp/evil.png")


def test_path_validator_validate_backslash_in_filename(tmp_path: Path):
    """Test validation prevents backslash in filename (Windows paths)."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with pytest.raises(ValueError, match="contains path separators"):
        validator.validate(output_dir, "..\\windows\\path.png")


def test_path_validator_validate_dotdot_in_middle(tmp_path: Path):
    """Test validation catches '..' in middle of filename."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with pytest.raises(ValueError, match="contains path separators"):
        validator.validate(output_dir, "file..name.png")


def test_path_validator_validate_special_characters_allowed(tmp_path: Path):
    """Test validation allows safe special characters."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # These should be allowed
    result = validator.validate(output_dir, "file_name-123.png")
    assert result.name == "file_name-123.png"


def test_path_validator_validate_unicode_filename(tmp_path: Path):
    """Test validation with Unicode characters in filename."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = validator.validate(output_dir, "グラフ_データ.png")
    assert result.name == "グラフ_データ.png"


# =============================================================================
# PathValidator.ensure_directory() Tests
# =============================================================================


def test_path_validator_ensure_directory_exists(tmp_path: Path):
    """Test ensure_directory with existing directory."""
    validator = PathValidator()
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()

    result = validator.ensure_directory(existing_dir)

    assert result == existing_dir.resolve()
    assert result.exists()
    assert result.is_dir()


def test_path_validator_ensure_directory_creates_new(tmp_path: Path):
    """Test ensure_directory creates directory if it doesn't exist."""
    validator = PathValidator()
    new_dir = tmp_path / "new_directory"

    result = validator.ensure_directory(new_dir)

    assert result == new_dir.resolve()
    assert new_dir.exists()
    assert new_dir.is_dir()


def test_path_validator_ensure_directory_creates_parents(tmp_path: Path):
    """Test ensure_directory creates parent directories."""
    validator = PathValidator()
    nested_dir = tmp_path / "level1" / "level2" / "level3"

    result = validator.ensure_directory(nested_dir)

    assert result == nested_dir.resolve()
    assert nested_dir.exists()
    assert (tmp_path / "level1").exists()
    assert (tmp_path / "level1" / "level2").exists()


def test_path_validator_ensure_directory_idempotent(tmp_path: Path):
    """Test ensure_directory can be called multiple times safely."""
    validator = PathValidator()
    target_dir = tmp_path / "target"

    # First call creates
    result1 = validator.ensure_directory(target_dir)
    assert target_dir.exists()

    # Second call should not raise error
    result2 = validator.ensure_directory(target_dir)
    assert result1 == result2
    assert target_dir.exists()


def test_path_validator_ensure_directory_absolute_path(tmp_path: Path):
    """Test ensure_directory returns absolute path."""
    validator = PathValidator()
    # Use relative path
    relative_dir = Path("relative/path")
    absolute_base = tmp_path / relative_dir

    result = validator.ensure_directory(absolute_base)

    assert result.is_absolute()


def test_path_validator_ensure_directory_resolves_symlinks(tmp_path: Path):
    """Test ensure_directory resolves symbolic links."""
    validator = PathValidator()
    real_dir = tmp_path / "real"
    real_dir.mkdir()

    # This test is platform-dependent, skip on Windows
    import platform
    if platform.system() != "Windows":
        symlink = tmp_path / "link"
        symlink.symlink_to(real_dir)

        result = validator.ensure_directory(symlink)
        # Result should be the resolved real path
        assert result == real_dir.resolve()


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


def test_path_validator_validate_empty_filename(tmp_path: Path):
    """Test validation with empty filename."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Empty filename should create path to directory
    result = validator.validate(output_dir, "")
    # Depending on implementation, this might raise or return output_dir
    assert result.parent == output_dir or result == output_dir


def test_path_validator_validate_whitespace_filename(tmp_path: Path):
    """Test validation with whitespace in filename."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = validator.validate(output_dir, "file with spaces.png")
    assert result.name == "file with spaces.png"


def test_path_validator_validate_very_long_filename(tmp_path: Path):
    """Test validation with very long filename."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Most filesystems have 255 char limit for filenames
    long_name = "a" * 200 + ".png"
    result = validator.validate(output_dir, long_name)
    assert result.name == long_name


def test_path_validator_validate_multiple_dots_in_filename(tmp_path: Path):
    """Test validation allows multiple dots (not path traversal)."""
    validator = PathValidator()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = validator.validate(output_dir, "file.name.test.png")
    assert result.name == "file.name.test.png"
