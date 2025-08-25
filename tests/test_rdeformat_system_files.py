import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

from rdetoolkit.impl.input_controller import RDEFormatChecker
from rdetoolkit.exceptions import StructuredError


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    input_dir = Path(tempfile.mkdtemp())
    output_dir = Path(tempfile.mkdtemp())
    yield input_dir, output_dir
    shutil.rmtree(input_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)


def create_test_zip_with_system_files(zip_path: Path, include_ds_store=True, include_macosx=True, include_thumbs=True):
    """Create a test ZIP file with system files and valid data files.

    Args:
        zip_path: Path where the ZIP file will be created
        include_ds_store: Whether to include .DS_Store files
        include_macosx: Whether to include __MACOSX directory
        include_thumbs: Whether to include Thumbs.db files
    """
    with zipfile.ZipFile(zip_path, 'w') as zf:
        # Add valid data files with folder structure for RDEFormat
        # RDEFormat expects folders with 4-digit names
        zf.writestr("0001/data.txt", "Sample data 1")
        zf.writestr("0001/metadata.json", '{"title": "Sample 1"}')
        zf.writestr("0002/data.txt", "Sample data 2")
        zf.writestr("0002/metadata.json", '{"title": "Sample 2"}')

        # Add system files that should be removed
        if include_ds_store:
            zf.writestr(".DS_Store", b"Mac metadata")
            zf.writestr("0001/.DS_Store", b"Mac metadata")
            zf.writestr("0002/.DS_Store", b"Mac metadata")

        if include_macosx:
            zf.writestr("__MACOSX/._data.txt", b"Mac resource fork")
            zf.writestr("__MACOSX/0001/._metadata.json", b"Mac resource fork")

        if include_thumbs:
            zf.writestr("Thumbs.db", b"Windows thumbnail cache")
            zf.writestr("0001/Thumbs.db", b"Windows thumbnail cache")

        # Add Office temp files
        zf.writestr("~$document.docx", b"Office temp file")
        zf.writestr("0001/~$spreadsheet.xlsx", b"Office temp file")


class TestRDEFormatCheckerWithSystemFiles:
    """Test RDEFormatChecker with system files in ZIP archives."""

    def test_rdeformat_removes_ds_store(self, temp_dirs):
        """Test that .DS_Store files are removed after extraction."""
        input_dir, output_dir = temp_dirs

        # Create test ZIP with .DS_Store files
        zip_path = input_dir / "test_data.zip"
        create_test_zip_with_system_files(zip_path, include_ds_store=True, include_macosx=False, include_thumbs=False)

        # Process with RDEFormatChecker
        checker = RDEFormatChecker(output_dir)
        raw_files, _ = checker.parse(input_dir)

        # Verify .DS_Store files don't exist in output
        assert not (output_dir / ".DS_Store").exists()
        assert not (output_dir / "0001" / ".DS_Store").exists()
        assert not (output_dir / "0002" / ".DS_Store").exists()

        # Verify valid files still exist
        assert (output_dir / "0001" / "data.txt").exists()
        assert (output_dir / "0001" / "metadata.json").exists()
        assert (output_dir / "0002" / "data.txt").exists()
        assert (output_dir / "0002" / "metadata.json").exists()

        # Verify raw_files doesn't include .DS_Store
        all_files = []
        for file_tuple in raw_files:
            all_files.extend(file_tuple)

        ds_store_files = [f for f in all_files if ".DS_Store" in str(f)]
        assert len(ds_store_files) == 0

    def test_rdeformat_removes_macosx_directory(self, temp_dirs):
        """Test that __MACOSX directory is removed after extraction."""
        input_dir, output_dir = temp_dirs

        # Create test ZIP with __MACOSX directory
        zip_path = input_dir / "test_data.zip"
        create_test_zip_with_system_files(zip_path, include_ds_store=False, include_macosx=True, include_thumbs=False)

        # Process with RDEFormatChecker
        checker = RDEFormatChecker(output_dir)
        raw_files, _ = checker.parse(input_dir)

        # Verify __MACOSX directory doesn't exist
        assert not (output_dir / "__MACOSX").exists()

        # Verify valid files still exist
        assert (output_dir / "0001" / "data.txt").exists()
        assert (output_dir / "0002" / "data.txt").exists()

        # Verify raw_files doesn't include __MACOSX files
        all_files = []
        for file_tuple in raw_files:
            all_files.extend(file_tuple)

        macosx_files = [f for f in all_files if "__MACOSX" in str(f)]
        assert len(macosx_files) == 0

    def test_rdeformat_removes_windows_files(self, temp_dirs):
        """Test that Windows system files are removed after extraction."""
        input_dir, output_dir = temp_dirs

        # Create test ZIP with Windows system files
        zip_path = input_dir / "test_data.zip"
        create_test_zip_with_system_files(zip_path, include_ds_store=False, include_macosx=False, include_thumbs=True)

        # Process with RDEFormatChecker
        checker = RDEFormatChecker(output_dir)
        raw_files, _ = checker.parse(input_dir)

        # Verify Thumbs.db files don't exist
        assert not (output_dir / "Thumbs.db").exists()
        assert not (output_dir / "0001" / "Thumbs.db").exists()

        # Verify valid files still exist
        assert (output_dir / "0001" / "data.txt").exists()
        assert (output_dir / "0002" / "data.txt").exists()

    def test_rdeformat_removes_office_temp_files(self, temp_dirs):
        """Test that Office temporary files are removed after extraction."""
        input_dir, output_dir = temp_dirs

        # Create test ZIP with all system files
        zip_path = input_dir / "test_data.zip"
        create_test_zip_with_system_files(zip_path)

        # Process with RDEFormatChecker
        checker = RDEFormatChecker(output_dir)
        raw_files, _ = checker.parse(input_dir)

        # Verify Office temp files don't exist
        assert not (output_dir / "~$document.docx").exists()
        assert not (output_dir / "0001" / "~$spreadsheet.xlsx").exists()

        # Verify all system files are removed
        assert not (output_dir / ".DS_Store").exists()
        assert not (output_dir / "__MACOSX").exists()
        assert not (output_dir / "Thumbs.db").exists()

        # Verify valid files still exist
        assert (output_dir / "0001" / "data.txt").exists()
        assert (output_dir / "0001" / "metadata.json").exists()
        assert (output_dir / "0002" / "data.txt").exists()
        assert (output_dir / "0002" / "metadata.json").exists()

    def test_rdeformat_with_clean_zip(self, temp_dirs):
        """Test that clean ZIP files (without system files) work correctly."""
        input_dir, output_dir = temp_dirs

        # Create clean ZIP without system files
        zip_path = input_dir / "clean_data.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("0001/data.txt", "Clean data 1")
            zf.writestr("0001/metadata.json", '{"title": "Clean 1"}')
            zf.writestr("0002/data.txt", "Clean data 2")

        # Process with RDEFormatChecker
        checker = RDEFormatChecker(output_dir)
        raw_files, _ = checker.parse(input_dir)

        # Verify all valid files exist
        assert (output_dir / "0001" / "data.txt").exists()
        assert (output_dir / "0001" / "metadata.json").exists()
        assert (output_dir / "0002" / "data.txt").exists()

        # Verify correct number of files in raw_files
        assert len(raw_files) == 2  # Two folders (0001 and 0002)

    def test_rdeformat_no_zip_raises_error(self, temp_dirs):
        """Test that missing ZIP file raises appropriate error."""
        input_dir, output_dir = temp_dirs

        # Create input directory without ZIP file
        (input_dir / "not_a_zip.txt").touch()

        # Should raise StructuredError
        checker = RDEFormatChecker(output_dir)
        with pytest.raises(StructuredError) as exc_info:
            checker.parse(input_dir)

        assert "no zipped input files" in str(exc_info.value)

    def test_rdeformat_multiple_zips_raises_error(self, temp_dirs):
        """Test that multiple ZIP files raise appropriate error."""
        input_dir, output_dir = temp_dirs

        # Create multiple ZIP files
        for i in range(2):
            zip_path = input_dir / f"data{i}.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr(f"file{i}.txt", f"Data {i}")

        # Should raise StructuredError
        checker = RDEFormatChecker(output_dir)
        with pytest.raises(StructuredError) as exc_info:
            checker.parse(input_dir)

        assert "no zipped input files" in str(exc_info.value)  # The error message is misleading but that's the current behavior

    def test_rdeformat_nested_system_directories(self, temp_dirs):
        """Test removal of deeply nested system directories."""
        input_dir, output_dir = temp_dirs

        # Create ZIP with nested system directories
        zip_path = input_dir / "nested.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Valid files
            zf.writestr("0001/data/file.txt", "Valid data")
            zf.writestr("0001/data/subfolder/deep.txt", "Deep data")

            # System files at various levels
            zf.writestr("0001/.DS_Store", b"Mac metadata")
            zf.writestr("0001/data/.DS_Store", b"Mac metadata")
            zf.writestr("0001/data/subfolder/.DS_Store", b"Mac metadata")
            zf.writestr("0001/.git/config", b"Git config")
            zf.writestr("0001/__pycache__/module.pyc", b"Python cache")

        # Process with RDEFormatChecker
        checker = RDEFormatChecker(output_dir)
        raw_files, _ = checker.parse(input_dir)

        # Verify system files are removed at all levels
        assert not (output_dir / "0001" / ".DS_Store").exists()
        assert not (output_dir / "0001" / "data" / ".DS_Store").exists()
        assert not (output_dir / "0001" / "data" / "subfolder" / ".DS_Store").exists()
        assert not (output_dir / "0001" / ".git").exists()
        assert not (output_dir / "0001" / "__pycache__").exists()

        # Verify valid files remain
        assert (output_dir / "0001" / "data" / "file.txt").exists()
        assert (output_dir / "0001" / "data" / "subfolder" / "deep.txt").exists()
