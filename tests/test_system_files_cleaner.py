import pathlib
import shutil
import tempfile
from pathlib import Path

import pytest

from rdetoolkit.impl.compressed_controller import SystemFilesCleaner


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def cleaner():
    """Create a SystemFilesCleaner instance."""
    return SystemFilesCleaner()


class TestSystemFilesCleaner:
    """Test cases for SystemFilesCleaner."""

    def test_is_excluded_os_files(self, cleaner):
        """Test detection of OS-specific files."""
        # macOS files
        assert cleaner.is_excluded(Path(".DS_Store"))
        assert cleaner.is_excluded(Path("folder/.DS_Store"))
        assert cleaner.is_excluded(Path("__MACOSX/test.txt"))

        # Windows files
        assert cleaner.is_excluded(Path("Thumbs.db"))
        assert cleaner.is_excluded(Path("desktop.ini"))
        assert cleaner.is_excluded(Path("$RECYCLE.BIN/file.txt"))

        # Valid files should not be excluded
        assert not cleaner.is_excluded(Path("normal_file.txt"))
        assert not cleaner.is_excluded(Path("data/important.json"))

    def test_is_excluded_app_files(self, cleaner):
        """Test detection of application temporary files."""
        # MS Office temp files
        assert cleaner.is_excluded(Path("~$document.docx"))
        assert cleaner.is_excluded(Path("~$spreadsheet.xlsx"))
        assert cleaner.is_excluded(Path("~$presentation.pptx"))

        # Vim swap files
        assert cleaner.is_excluded(Path(".file.swp"))
        assert cleaner.is_excluded(Path("file.swo"))
        assert cleaner.is_excluded(Path("file.swn"))

        # Backup files
        assert cleaner.is_excluded(Path("file.bak"))
        assert cleaner.is_excluded(Path("file~"))

        # Temp files
        assert cleaner.is_excluded(Path("tempfile.tmp"))
        assert cleaner.is_excluded(Path("tempfile.temp"))

    def test_is_excluded_dev_files(self, cleaner):
        """Test detection of development-related files."""
        # Version control
        assert cleaner.is_excluded(Path(".git/config"))
        assert cleaner.is_excluded(Path(".svn/entries"))
        assert cleaner.is_excluded(Path(".gitignore"))

        # IDE files
        assert cleaner.is_excluded(Path(".idea/workspace.xml"))
        assert cleaner.is_excluded(Path(".vscode/settings.json"))

        # Python files
        assert cleaner.is_excluded(Path("__pycache__/module.pyc"))
        assert cleaner.is_excluded(Path("script.pyc"))
        assert cleaner.is_excluded(Path(".pytest_cache/v/cache"))
        assert cleaner.is_excluded(Path(".ipynb_checkpoints/notebook.ipynb"))

    def test_clean_directory_removes_files(self, cleaner, temp_dir):
        """Test that clean_directory removes excluded files."""
        # Create test structure
        (temp_dir / "data").mkdir()
        (temp_dir / "__MACOSX").mkdir()
        (temp_dir / ".git").mkdir()

        # Create files to be removed
        (temp_dir / ".DS_Store").touch()
        (temp_dir / "data" / ".DS_Store").touch()
        (temp_dir / "Thumbs.db").touch()
        (temp_dir / "~$temp.docx").touch()
        (temp_dir / "file.bak").touch()
        (temp_dir / "__MACOSX" / "resource").touch()
        (temp_dir / ".git" / "config").touch()

        # Create files to be kept
        (temp_dir / "important.txt").touch()
        (temp_dir / "data" / "data.json").touch()
        (temp_dir / "README.md").touch()

        # Clean the directory
        removed = cleaner.clean_directory(temp_dir)

        # Check that excluded files were removed
        assert not (temp_dir / ".DS_Store").exists()
        assert not (temp_dir / "data" / ".DS_Store").exists()
        assert not (temp_dir / "Thumbs.db").exists()
        assert not (temp_dir / "~$temp.docx").exists()
        assert not (temp_dir / "file.bak").exists()
        assert not (temp_dir / "__MACOSX").exists()
        assert not (temp_dir / ".git").exists()

        # Check that valid files were kept
        assert (temp_dir / "important.txt").exists()
        assert (temp_dir / "data" / "data.json").exists()
        assert (temp_dir / "README.md").exists()

        # Check the removed paths list
        assert len(removed) >= 7  # At least 7 items should be removed

    def test_clean_directory_handles_nested_structures(self, cleaner, temp_dir):
        """Test cleaning of nested directory structures."""
        # Create nested structure
        nested = temp_dir / "level1" / "level2" / "level3"
        nested.mkdir(parents=True)

        # Add .DS_Store at each level
        (temp_dir / ".DS_Store").touch()
        (temp_dir / "level1" / ".DS_Store").touch()
        (temp_dir / "level1" / "level2" / ".DS_Store").touch()
        (nested / ".DS_Store").touch()

        # Add valid files
        (nested / "data.txt").touch()

        # Clean
        removed = cleaner.clean_directory(temp_dir)

        # Check all .DS_Store files were removed
        assert not (temp_dir / ".DS_Store").exists()
        assert not (temp_dir / "level1" / ".DS_Store").exists()
        assert not (temp_dir / "level1" / "level2" / ".DS_Store").exists()
        assert not (nested / ".DS_Store").exists()

        # Check valid file remains
        assert (nested / "data.txt").exists()
        assert len(removed) == 4

    def test_clean_directory_nonexistent_path(self, cleaner):
        """Test behavior with non-existent directory."""
        non_existent = Path("/tmp/does_not_exist_12345")
        removed = cleaner.clean_directory(non_existent)
        assert removed == []

    def test_clean_directory_file_path(self, cleaner, temp_dir):
        """Test behavior when given a file path instead of directory."""
        file_path = temp_dir / "file.txt"
        file_path.touch()
        removed = cleaner.clean_directory(file_path)
        assert removed == []

    def test_get_excluded_patterns(self, cleaner):
        """Test that get_excluded_patterns returns all pattern categories."""
        patterns = cleaner.get_excluded_patterns()

        assert "os_patterns" in patterns
        assert "app_patterns" in patterns
        assert "dev_patterns" in patterns

        assert ".DS_Store" in patterns["os_patterns"]
        assert "Thumbs.db" in patterns["os_patterns"]
        assert r"~\$.*\.(docx|xlsx|pptx|doc|xls|ppt)" in patterns["app_patterns"]
        assert ".git" in patterns["dev_patterns"]

    def test_clean_directory_with_special_chars(self, cleaner, temp_dir):
        """Test cleaning files with special characters in names."""
        # Create files with special characters
        (temp_dir / "~$document (1).docx").touch()
        (temp_dir / "file.2023.bak").touch()
        (temp_dir / "test-file~").touch()

        # Create valid files with similar patterns
        (temp_dir / "document.docx").touch()
        (temp_dir / "file.2023.txt").touch()

        _ = cleaner.clean_directory(temp_dir)

        # Check excluded files were removed
        assert not (temp_dir / "~$document (1).docx").exists()
        assert not (temp_dir / "file.2023.bak").exists()
        assert not (temp_dir / "test-file~").exists()

        # Check valid files remain
        assert (temp_dir / "document.docx").exists()
        assert (temp_dir / "file.2023.txt").exists()

    def test_clean_directory_handles_permission_errors(self, cleaner, temp_dir, monkeypatch):
        """Test that permission errors are handled gracefully."""
        # Create a file to remove
        test_file = temp_dir / ".DS_Store"
        test_file.touch()

        # Mock unlink to raise PermissionError
        original_unlink = pathlib.Path.unlink

        def mock_unlink(self):
            if self.name == ".DS_Store":
                raise PermissionError("Permission denied")
            return original_unlink(self)

        monkeypatch.setattr(pathlib.Path, "unlink", mock_unlink)

        # Should not raise exception
        removed = cleaner.clean_directory(temp_dir)

        # File should still exist due to permission error
        assert test_file.exists()
        assert removed == []  # Nothing was successfully removed
