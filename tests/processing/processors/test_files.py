import os
import pathlib
import tempfile
from pathlib import Path
import shutil

import pytest

from rdetoolkit.processing.processors.files import FileCopier, RDEFormatFileCopier
import zipfile


class TestFileCopier:
    """Test cases for FileCopier processor."""

    def test_process_with_save_raw_enabled(self, basic_processing_context, inputfile_single, invoice_json_with_sample_info, tasksupport):
        """Test FileCopier when save_raw is enabled."""
        # Setup
        os.makedirs("data/raw", exist_ok=True)

        processor = FileCopier()
        context = basic_processing_context
        context.srcpaths.config.system.save_raw = True
        context.srcpaths.config.system.save_nonshared_raw = False

        processor.process(context)
        assert os.path.exists("data/raw/test_single.txt")

        # teardown
        if os.path.exists("data/raw"):
            shutil.rmtree("data/raw")

    def test_process_with_save_nonshared_raw_enabled(self, basic_processing_context, inputfile_single, invoice_json_with_sample_info, tasksupport):
        """Test FileCopier when save_nonshared_raw is enabled."""
        # Setup
        os.makedirs("data/nonshared_raw", exist_ok=True)

        processor = FileCopier()
        context = basic_processing_context
        context.srcpaths.config.system.save_raw = False
        context.srcpaths.config.system.save_nonshared_raw = True

        processor.process(context)
        assert os.path.exists("data/nonshared_raw/test_single.txt")

        # teardown
        if os.path.exists("data"):
            shutil.rmtree("data")

    def test_process_with_both_enabled(self, basic_processing_context, inputfile_single, invoice_json_with_sample_info, tasksupport):
        """Test FileCopier when both save options are enabled."""
        # Setup
        os.makedirs("data/raw", exist_ok=True)
        os.makedirs("data/nonshared_raw", exist_ok=True)

        processor = FileCopier()
        context = basic_processing_context
        context.srcpaths.config.system.save_raw = True
        context.srcpaths.config.system.save_nonshared_raw = True

        processor.process(context)

        assert os.path.exists("data/nonshared_raw/test_single.txt")
        assert os.path.exists("data/raw/test_single.txt")

        # teardown
        if os.path.exists("data"):
            shutil.rmtree("data")

    def test_process_with_both_disabled(self, processing_context_disabled_features, inputfile_single, invoice_json_with_sample_info, tasksupport):
        """Test FileCopier when both save options are disabled."""
        # Setup
        os.makedirs("data/raw", exist_ok=True)
        os.makedirs("data/nonshared_raw", exist_ok=True)

        processor = FileCopier()

        context = processing_context_disabled_features
        processor.process(context)

        # teardown
        if os.path.exists("data"):
            shutil.rmtree("data")

    def test_copy_files_to_directory_success(self):
        """Test successful file copying."""
        processor = FileCopier()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source files
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()
            source_file1 = source_dir / "test1.txt"
            source_file2 = source_dir / "test2.txt"
            source_file1.write_text("content1")
            source_file2.write_text("content2")

            # Create destination directory
            dest_dir = Path(temp_dir) / "dest"

            # Test file copying
            source_files = (source_file1, source_file2)
            processor._copy_files(dest_dir, source_files)

            # Verify files were copied
            assert (dest_dir / "test1.txt").exists()
            assert (dest_dir / "test2.txt").exists()
            assert (dest_dir / "test1.txt").read_text() == "content1"
            assert (dest_dir / "test2.txt").read_text() == "content2"

    def test_copy_files_to_directory_empty_list(self):
        """Test file copying with empty file list."""
        processor = FileCopier()

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_dir = Path(temp_dir) / "dest"
            dest_dir.mkdir()

            # Test with empty file list
            processor._copy_files(dest_dir, ())

            # Should not raise an error and directory should remain empty
            assert len(list(dest_dir.iterdir())) == 0

    def test_get_name(self):
        """Test processor name."""
        processor = FileCopier()
        assert processor.get_name() == "FileCopier"


class TestRDEFormatFileCopier:
    """Test cases for RDEFormatFileCopier processor."""

    def test_process_success(self, rdeformat_processing_context, inputfile_rdeformat):
        """Test successful RDEFormatFileCopier processing."""
        processor = RDEFormatFileCopier()
        context = rdeformat_processing_context
        context.resource_paths.raw.mkdir(parents=True, exist_ok=True)
        context.resource_paths.main_image.mkdir(parents=True, exist_ok=True)
        context.resource_paths.other_image.mkdir(parents=True, exist_ok=True)
        context.resource_paths.meta.mkdir(parents=True, exist_ok=True)
        context.resource_paths.struct.mkdir(parents=True, exist_ok=True)
        context.resource_paths.logs.mkdir(parents=True, exist_ok=True)
        context.resource_paths.nonshared_raw.mkdir(parents=True, exist_ok=True)

        # Extract zip to data/temp and get all extracted files
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(os.path.join("data", "inputdata", Path(inputfile_rdeformat).name), 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Get all extracted files as tuple
        extracted_files = tuple(temp_dir.rglob('*'))
        extracted_files = tuple(f for f in extracted_files if f.is_file())
        processor.process(context)

        assert pathlib.Path("data", "raw", "test_child1.txt").exists()
        assert pathlib.Path("data", "structured", "test.csv").exists()

        # teardown
        if os.path.exists("data"):
            shutil.rmtree("data")

    def test_process_with_unmatched_files(self, basic_processing_context):
        """Test RDEFormatFileCopier with files that don't match any directory."""
        processor = RDEFormatFileCopier()
        context = basic_processing_context

        # Mock rawfiles with some unmatched files
        mock_rawfiles = (
            Path("data/raw/file1.txt"),
            Path("data/unknown/file2.txt"),  # This won't match any directory
            Path("data/main_image/image1.jpg"),
        )
        context.resource_paths.rawfiles = mock_rawfiles

        with pytest.raises(Exception) as exc_info:
            processor.process(context)

        assert str(exc_info.value) == "Error: Failed to copy data/raw/file1.txt to data/raw"

    def test_process_with_empty_rawfiles(self, processing_context_no_rawfiles):
        """Test RDEFormatFileCopier with no raw files."""
        processor = RDEFormatFileCopier()
        context = processing_context_no_rawfiles
        processor.process(context)

        assert not context.resource_paths.rawfiles, "Expected no raw files in context"

    def test_get_name(self):
        """Test processor name."""
        processor = RDEFormatFileCopier()
        assert processor.get_name() == "RDEFormatFileCopier"

    @pytest.mark.parametrize("dir_name,expected_attr", [
        ("raw", "raw"),
        ("main_image", "main_image"),
        ("other_image", "other_image"),
        ("meta", "meta"),
        ("structured", "struct"),
        ("logs", "logs"),
        ("nonshared_raw", "nonshared_raw"),
    ])
    def test_directory_mapping_with_real_files(self, dir_name, expected_attr, test_processing_context_mapping):
        """実際のファイルを使ったディレクトリマッピングテスト"""
        processor = RDEFormatFileCopier()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # テスト用のソースファイルを作成
            source_dir = temp_path / "source" / dir_name
            source_dir.mkdir(parents=True)
            test_file = source_dir / "test.txt"
            test_file.write_text("test content")

            # コンテキストを設定
            context = test_processing_context_mapping
            context.resource_paths.rawfiles = (test_file,)

            # プロセッサを実行
            processor.process(context)

            # 期待される出力先にファイルが存在することを確認
            expected_dest = getattr(context.resource_paths, expected_attr)
            expected_file = expected_dest / "test.txt"

            assert expected_file.exists()
            assert expected_file.read_text() == "test content"
