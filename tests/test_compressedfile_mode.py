import pathlib
import platform
import shutil
from unittest import mock
import zipfile

import pandas as pd
import pytest
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.impl.compressed_controller import (
    CompressedFlatFileParser,
    CompressedFolderParser,
    ZipArtifactPackageCompressor,
    TarGzArtifactPackageCompressor,
    get_artifact_archiver,
)


@pytest.fixture
def temp_dir():
    test_temp = pathlib.Path("tests/temp")
    test_temp.mkdir(parents=True, exist_ok=True)
    yield test_temp
    shutil.rmtree(test_temp)


class TestCompressedFlatFileParser:
    @mock.patch("rdetoolkit.impl.compressed_controller.check_exist_rawfiles")
    def test_read(self, mocker, inputfile_zip_with_file, temp_dir):
        xlsx_invoice = pd.DataFrame()
        expected_files = [(pathlib.Path(temp_dir, "test_child1.txt"),)]

        mocker.return_value = [pathlib.Path(temp_dir, "test_child1.txt")]
        parser = CompressedFlatFileParser(xlsx_invoice)
        files = parser.read(inputfile_zip_with_file, temp_dir)
        assert files == expected_files


class TestCompressedFolderParser:
    def test_read(self, inputfile_zip_with_folder, temp_dir):
        xlsx_invoice = pd.DataFrame()
        parser = CompressedFolderParser(xlsx_invoice)
        files = parser.read(pathlib.Path(inputfile_zip_with_folder), pathlib.Path(temp_dir))

        assert len(files) == 1
        assert len(files[0]) == 2

    def test_unpacked(self, inputfile_zip_with_folder, temp_dir):
        xlsx_invoice = pd.DataFrame()
        parser = CompressedFolderParser(xlsx_invoice)
        files = parser._unpacked(inputfile_zip_with_folder, temp_dir)
        assert len(files) == 2
        assert {f.name for f in files} == {"test_child2.txt", "test_child1.txt"}

    def test_mac_specific_file_unpacked(self, inputfile_mac_zip_with_folder, temp_dir):
        # mac特有のファイルを除外できるかテスト
        xlsx_invoice = pd.DataFrame()
        parser = CompressedFolderParser(xlsx_invoice)
        files = parser._unpacked(inputfile_mac_zip_with_folder, temp_dir)
        assert len(files) == 1
        assert {f.name for f in files} == {"test_child1.txt"}

    def test_microsoft_temp_file_unpacked(self, inputfile_microsoft_tempfile_zip_with_folder, temp_dir):
        # Microfsoft特有のファイルを除外できるかテスト
        xlsx_invoice = pd.DataFrame()
        parser = CompressedFolderParser(xlsx_invoice)
        files = parser._unpacked(inputfile_microsoft_tempfile_zip_with_folder, temp_dir)
        assert len(files) == 1
        assert {f.name for f in files} == {"test_child1.txt"}

    def test_japanese_temp_file_unpacked(self, inputfile_japanese_tempfile_zip_with_folder, temp_dir):
        # 日本語名を含むzipファイルを解凍できるかテスト
        xlsx_invoice = pd.DataFrame()
        parser = CompressedFolderParser(xlsx_invoice)
        files = parser._unpacked(inputfile_japanese_tempfile_zip_with_folder, temp_dir)
        assert len(files) == 10
        expect_files = {
            "テストファイル名１.txt": "これはテストファイル１です。",
            "漢字ファイル名.txt": "これは漢字ファイルです。",
            "かなファイル名.txt": "これはかなファイルです。",
            "カナファイル名.txt": "これはカナファイルです。",
            "全角スペースファイル名　.txt": "これは全角スペースファイルです。",
            "特殊記号！@＃$.txt": "これは特殊記号ファイルです。",
            "括弧（カッコ）.txt": "これは括弧ファイルです。",
            "波ダッシュ〜.txt": "これは波ダッシュファイルです。",
            "ファイル名_令和３年.txt": "これは令和３年ファイルです。",
            "テストデータ①.txt": "これはテストデータ１です。",
        }
        for file in files:
            with open(file, encoding="utf-8") as f:
                assert f.read() == expect_files[file.name]

    def test_validation_uniq_fspath(self, temp_dir):
        compressed_filepath1 = pathlib.Path("tests", "temp", "test1.txt")
        compressed_filepath2 = pathlib.Path("tests", "temp", "test2.txt")
        compressed_filepath1.touch()
        compressed_filepath2.touch()

        xlsx_invoice = pd.DataFrame()
        parser = CompressedFolderParser(xlsx_invoice)
        verification_files = parser.validation_uniq_fspath(pathlib.Path("tests/temp"), exclude_names=["invoice_org.json"])

        assert len(verification_files) == 1
        assert "test1.txt" in [p.name for p in verification_files["tests/temp"]]
        assert "test2.txt" in [p.name for p in verification_files["tests/temp"]]

    def test_invalid_validation_uniq_fspath_folder(self, temp_dir):
        # import pdb;pdb.set_trace()
        xlsx_invoice = pd.DataFrame()

        if platform.system() == "Linux":
            pathlib.Path("tests", "temp", "sample").mkdir(parents=True, exist_ok=True)
            pathlib.Path("tests", "temp", "Sample").mkdir(parents=True, exist_ok=True)
            compressed_filepath1 = pathlib.Path("tests", "temp", "sample", "test1.txt")
            compressed_filepath2 = pathlib.Path("tests", "temp", "Sample", "test2.txt")
            compressed_filepath1.touch()
            compressed_filepath2.touch()
            parser = CompressedFolderParser(xlsx_invoice)
            with pytest.raises(StructuredError) as e:
                verification_files = parser.validation_uniq_fspath(pathlib.Path("tests/temp"), exclude_names=["invoice_org.json"])
            assert str(e.value) == "ERROR: folder paths and file paths stored in a zip file must always have unique names."
        else:
            pathlib.Path("tests", "temp", "sample").mkdir(parents=True, exist_ok=True)
            pathlib.Path("tests", "temp", "Sample").mkdir(parents=True, exist_ok=True)
            compressed_filepath1 = pathlib.Path("tests", "temp", "sample", "test1.txt")
            compressed_filepath2 = pathlib.Path("tests", "temp", "Sample", "Test1.txt")
            compressed_filepath1.touch()
            compressed_filepath2.touch()
            parser = CompressedFolderParser(xlsx_invoice)
            verification_files = parser.validation_uniq_fspath(pathlib.Path("tests/temp"), exclude_names=["invoice_org.json"])

            assert len(verification_files) == 1
            assert "test1.txt" in [p.name for p in verification_files["tests/temp/sample"]]

    def test_invalid_validation_uniq_fspath_file(self, temp_dir):
        # import pdb;pdb.set_trace()
        xlsx_invoice = pd.DataFrame()

        if platform.system() == "Linux":
            pathlib.Path("tests", "temp", "sample").mkdir(parents=True, exist_ok=True)
            pathlib.Path("tests", "temp", "Sample").mkdir(parents=True, exist_ok=True)
            compressed_filepath1 = pathlib.Path("tests", "temp", "sample", "test1.txt")
            compressed_filepath2 = pathlib.Path("tests", "temp", "sample", "Test1.txt")
            compressed_filepath1.touch()
            compressed_filepath2.touch()
            parser = CompressedFolderParser(xlsx_invoice)
            with pytest.raises(StructuredError) as e:
                verification_files = parser.validation_uniq_fspath(pathlib.Path("tests/temp"), exclude_names=["invoice_org.json"])
            assert str(e.value) == "ERROR: folder paths and file paths stored in a zip file must always have unique names."
        else:
            pathlib.Path("tests", "temp", "sample").mkdir(parents=True, exist_ok=True)
            pathlib.Path("tests", "temp", "Sample").mkdir(parents=True, exist_ok=True)
            compressed_filepath1 = pathlib.Path("tests", "temp", "sample", "test1.txt")
            compressed_filepath2 = pathlib.Path("tests", "temp", "Sample", "Test1.txt")
            compressed_filepath1.touch()
            compressed_filepath2.touch()
            parser = CompressedFolderParser(xlsx_invoice)
            verification_files = parser.validation_uniq_fspath(pathlib.Path("tests/temp"), exclude_names=["invoice_org.json"])

            assert len(verification_files) == 1
            assert "test1.txt" in [p.name for p in verification_files["tests/temp/sample"]]


@pytest.fixture
def sample_dir(temp_dir):
    source_dir = pathlib.Path(temp_dir) / "source"
    source_dir.mkdir()

    sub_dir1 = source_dir / "subdir1"
    sub_dir1.mkdir()
    (sub_dir1 / "file1.txt").write_text("Content1")
    (sub_dir1 / "file2.txt").write_text("Content2")

    sub_dir2 = source_dir / "subdir2"
    sub_dir2.mkdir()
    (sub_dir2 / "file3.txt").write_text("Content3")

    jp_dir = source_dir / "日本語ディレクトリ"
    jp_dir.mkdir()
    (jp_dir / "日本語ファイル.txt").write_text("日本語コンテンツ")

    # 除外されるべきファイル
    mac_dir = source_dir / "__MACOSX"
    mac_dir.mkdir()
    (mac_dir / "some_file.txt").write_text("Should be excluded")
    (source_dir / ".DS_Store").write_text("Should be excluded")
    (source_dir / "~$temp.docx").write_text("Should be excluded")

    yield source_dir

    if source_dir.exists():
        shutil.rmtree(source_dir)


class TestZipArtifactPackageCompressor:
    @pytest.fixture
    def compressor(self, sample_dir):
        exclude_patterns = [
            r"__MACOSX", r"\.DS_Store", r"~\$.*\.(docx|xlsx|pptx)",
        ]
        return ZipArtifactPackageCompressor(sample_dir, exclude_patterns=exclude_patterns)

    def test_archive_basic(self, compressor, temp_dir):
        output_zip = pathlib.Path(temp_dir) / "archive.zip"
        file_paths = compressor.archive(output_zip)

        assert output_zip.exists()

        assert len(file_paths) == 4
        file_names = [str(p) for p in file_paths]
        assert "subdir1/file1.txt" in file_names
        assert "subdir1/file2.txt" in file_names
        assert "subdir2/file3.txt" in file_names
        assert "日本語ディレクトリ/日本語ファイル.txt" in file_names

        with zipfile.ZipFile(output_zip) as zipf:
            # Check if the files are in the zip
            assert "__MACOSX/some_file.txt" not in zipf.namelist()
            assert ".DS_Store" not in zipf.namelist()
            assert "~$temp.docx" not in zipf.namelist()

    def test_case_insensitive_duplicate_detection(self, sample_dir, temp_dir):
        if platform.system() == "Darwin":
            pytest.skip("Skipping case sensitivity test on macOS")
        (sample_dir / "CaseSensitive").mkdir()
        (sample_dir / "CaseSensitive" / "file.txt").write_text("Content")
        (sample_dir / "casesensitive").mkdir()
        (sample_dir / "casesensitive" / "file.txt").write_text("Content")

        compresor = ZipArtifactPackageCompressor(sample_dir, [])
        output_zip = temp_dir / "duplicate.zip"
        with pytest.raises(StructuredError, match="Case-insensitive duplicate path detected"):
            compresor.archive(output_zip)


class TestGetArtifactArchiver:
    def test_get_zip_archiver(self, sample_dir):
        """Test if the ZIP archiver can be correctly retrieved."""
        archiver = get_artifact_archiver("zip", sample_dir, [])
        assert isinstance(archiver, ZipArtifactPackageCompressor)

    def test_get_targz_archiver(self, sample_dir):
        """Test if the tar.gz archiver can be correctly retrived."""
        archiver = get_artifact_archiver("tar.gz", sample_dir, [])
        assert isinstance(archiver, TarGzArtifactPackageCompressor)

        archiver = get_artifact_archiver("targz", sample_dir, [])
        assert isinstance(archiver, TarGzArtifactPackageCompressor)

        archiver = get_artifact_archiver("tgz", sample_dir, [])
        assert isinstance(archiver, TarGzArtifactPackageCompressor)

    def test_unsupported_format(self, sample_dir):
        """Test if ValueError is raised for unsupported formats."""
        with pytest.raises(ValueError, match="Unsupported archive format"):
            get_artifact_archiver("unsupported", sample_dir, [])


def test_japanese_filename_end_to_end(temp_dir):
    """End-to-end test for Japanese filenames."""
    source_dir = pathlib.Path(temp_dir) / "source"
    source_dir.mkdir()

    (source_dir / "文書フォルダ").mkdir()
    (source_dir / "文書フォルダ" / "重要資料.txt").write_text("重要な文書内容")
    (source_dir / "画像フォルダ").mkdir()
    (source_dir / "画像フォルダ" / "写真.txt").write_text("写真のプレースホルダー")

    output_zip = pathlib.Path(temp_dir) / "日本語アーカイブ.zip"
    compressor = ZipArtifactPackageCompressor(source_dir, [])
    file_paths = compressor.archive(output_zip)

    assert len(file_paths) == 2
    file_names = [str(p) for p in file_paths]
    assert "文書フォルダ/重要資料.txt" in file_names
    assert "画像フォルダ/写真.txt" in file_names

    extract_dir = pathlib.Path(temp_dir) / "extracted"
    extract_dir.mkdir()

    with zipfile.ZipFile(output_zip, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    assert (extract_dir / "文書フォルダ" / "重要資料.txt").exists()
    assert (extract_dir / "文書フォルダ" / "重要資料.txt").read_text() == "重要な文書内容"
    assert (extract_dir / "画像フォルダ" / "写真.txt").exists()
    assert (extract_dir / "画像フォルダ" / "写真.txt").read_text() == "写真のプレースホルダー"


def test_get_zip_archiver(sample_dir: pathlib.Path):
    """ZIP アーカイバを取得できるかテスト"""
    archiver = get_artifact_archiver("zip", sample_dir, [])
    assert isinstance(archiver, ZipArtifactPackageCompressor)


def test_get_targz_archiver(sample_dir: pathlib.Path):
    """tar.gz アーカイバを取得できるかテスト"""
    archiver = get_artifact_archiver("tar.gz", sample_dir, [])
    assert isinstance(archiver, TarGzArtifactPackageCompressor)

    archiver = get_artifact_archiver("targz", sample_dir, [])
    assert isinstance(archiver, TarGzArtifactPackageCompressor)

    archiver = get_artifact_archiver("tgz", sample_dir, [])
    assert isinstance(archiver, TarGzArtifactPackageCompressor)


def test_get_unsupported_archiver(sample_dir: pathlib.Path):
    """サポートされていない形式でエラーが発生するかテスト"""
    with pytest.raises(ValueError, match="Unsupported archive format"):
        get_artifact_archiver("invalid", sample_dir, [])


def test_exclude_patterns_are_passed(sample_dir: pathlib.Path):
    exclude_patterns = [".DS_Store", "__MACOSX"]
    archiver = get_artifact_archiver("zip", sample_dir, exclude_patterns)
    assert archiver.exclude_patterns == exclude_patterns
