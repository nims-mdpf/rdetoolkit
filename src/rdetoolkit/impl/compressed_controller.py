from __future__ import annotations

import os
import re
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import charset_normalizer
import pandas as pd

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.interfaces.filechecker import IArtifactPackageCompressor, ICompressedFileStructParser
from rdetoolkit.invoicefile import check_exist_rawfiles
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)


class SystemFilesCleaner:
    """Utility class to clean up OS and application-specific files after extraction.

    This class identifies and removes system-generated files that should not be
    included in the processed data, such as .DS_Store (macOS), Thumbs.db (Windows),
    and temporary files from various applications.
    """

    # OS-specific files
    OS_PATTERNS = [
        "__MACOSX",  # macOS resource fork directory
        ".DS_Store",  # macOS directory metadata
        "Thumbs.db",  # Windows thumbnail cache
        "desktop.ini",  # Windows folder settings
        "$RECYCLE.BIN",  # Windows recycle bin
        ".Spotlight-V100",  # macOS Spotlight index
        ".Trashes",  # macOS trash folder
        ".fseventsd",  # macOS file system events
        ".TemporaryItems",  # macOS temporary items
        "System Volume Information",  # Windows system folder
    ]

    # Application temporary files
    APP_PATTERNS = [
        r"~\$.*\.(docx|xlsx|pptx|doc|xls|ppt)",  # MS Office temp files
        r"\.~lock\.",  # LibreOffice lock files
        r".*\.tmp$",  # General temp files
        r".*\.temp$",  # General temp files
        r".*\.swp$",  # Vim swap files
        r".*\.swo$",  # Vim swap files
        r".*\.swn$",  # Vim swap files
        r".*\.bak$",  # Backup files
        r".*~$",  # Editor backup files
        r".*\.pyc$",  # Python compiled files
    ]

    # Development and version control files
    DEV_PATTERNS = [
        ".git",
        ".svn",
        ".hg",
        ".bzr",
        ".gitignore",
        ".gitattributes",
        ".idea",  # IntelliJ IDEA
        ".vscode",  # Visual Studio Code
        "__pycache__",  # Python cache
        ".pytest_cache",  # Pytest cache
        ".tox",  # Tox test environments
        ".coverage",  # Coverage reports
        ".ipynb_checkpoints",  # Jupyter checkpoints
        "node_modules",  # Node.js modules
        ".sass-cache",  # Sass cache
    ]

    def __init__(self) -> None:
        """Initialize the SystemFilesCleaner with compiled regex patterns."""
        self.regex_patterns = []
        for pattern in self.APP_PATTERNS:
            try:
                self.regex_patterns.append(re.compile(pattern))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

    def is_excluded(self, file_path: Path) -> bool:
        """Check if a file or directory should be excluded.

        Args:
            file_path: Path to check

        Returns:
            True if the file/directory should be excluded, False otherwise
        """
        # Check against OS patterns (exact match in path parts)
        for pattern in self.OS_PATTERNS:
            if pattern in file_path.parts:
                return True
            if file_path.name == pattern:
                return True

        # Check against development patterns
        for pattern in self.DEV_PATTERNS:
            if pattern in file_path.parts or file_path.name == pattern:
                return True

        # Check against regex patterns
        str_path = str(file_path)
        return any(regex.search(str_path) for regex in self.regex_patterns)

    def clean_directory(self, directory: Path) -> list[Path]:
        """Remove all excluded files and directories from the given directory.

        Args:
            directory: Path to the directory to clean

        Returns:
            List of paths that were removed
        """
        removed_paths: list[Path] = []

        if not directory.exists() or not directory.is_dir():
            logger.warning(f"Directory does not exist or is not a directory: {directory}")
            return removed_paths

        # Collect all files and directories to remove
        to_remove_files = []
        to_remove_dirs = []

        for path in directory.rglob("*"):
            if self.is_excluded(path):
                if path.is_file() or path.is_symlink():
                    to_remove_files.append(path)
                elif path.is_dir():
                    to_remove_dirs.append(path)

        # Remove files first
        for file_path in to_remove_files:
            try:
                file_path.unlink()
                removed_paths.append(file_path)
                logger.debug(f"Removed file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove file {file_path}: {e}")

        # Remove directories (deepest first)
        for dir_path in sorted(to_remove_dirs, key=lambda p: -len(p.parts)):
            try:
                shutil.rmtree(dir_path)
                removed_paths.append(dir_path)
                logger.debug(f"Removed directory: {dir_path}")
            except Exception as e:
                logger.warning(f"Failed to remove directory {dir_path}: {e}")

        return removed_paths

    def get_excluded_patterns(self) -> dict[str, list[str]]:
        """Get all excluded patterns organized by category.

        Returns:
            Dictionary with categories as keys and pattern lists as values
        """
        return {
            "os_patterns": self.OS_PATTERNS,
            "app_patterns": self.APP_PATTERNS,
            "dev_patterns": self.DEV_PATTERNS,
        }


class CompressedFlatFileParser(ICompressedFileStructParser):
    """Parser for compressed flat files, providing functionality to read and extract the contents.

    This parser specifically deals with flat files that are compressed. It extracts the files
    and ensures they match the expected structure described in an excelinvoice.

    Attributes:
        xlsx_invoice (pd.DataFrame): DataFrame representing the expected structure or content description
            of the compressed files.
    """

    def __init__(self, xlsx_invoice: pd.DataFrame):
        self.xlsx_invoice = xlsx_invoice

    def read(self, zipfile: Path, target_path: Path) -> list[tuple[Path, ...]]:
        """Extracts the contents of the zipfile to the target path and checks their existence against the Excelinvoice.

        Args:
            zipfile (Path): Path to the compressed flat file to be read.
            target_path (Path): Destination directory where the zipfile will be extracted to.

        Returns:
            List[Tuple[Path, ...]]: A list of tuples containing file paths. Each tuple
            represents files from the compressed archive that matched the xlsx_invoice structure.
        """
        _extracted_files = self._unpacked(zipfile, target_path)
        return [(f,) for f in check_exist_rawfiles(self.xlsx_invoice, _extracted_files)]

    def _unpacked(self, zipfile: Path | str, target_dir: Path | str) -> list[Path]:
        if isinstance(target_dir, str):
            target_dir = Path(target_dir)
        self._extract_zip_with_encoding(zipfile, target_dir)

        # Clean up system files after extraction
        cleaner = SystemFilesCleaner()
        removed_paths = cleaner.clean_directory(target_dir)
        if removed_paths:
            logger.info(f"Removed {len(removed_paths)} system/temporary files after extraction")

        return [f for f in target_dir.glob("**/*") if f.is_file() and not self._is_excluded(f)]

    def _extract_zip_with_encoding(self, zip_path: Path | str, extract_path: Path | str) -> None:
        """Extracts a ZIP file, handling filenames with a specified encoding to prevent garbled text.

        This function attempts to detect and correct the encoding of filenames within the ZIP file to ensure they are extracted with the correct filenames, avoiding issues with garbled text due to encoding mismatches.

        Args:
            zip_path (Path | str): The path to the ZIP file to be extracted.
            extract_path (Path | str): The directory where the contents of the ZIP file will be extracted.

        Raises:
            ValueError: If encoding detection fails for any filename within the ZIP archive.
            UnicodeDecodeError: If a filename cannot be decoded with the detected or specified encoding.

        Example:
            >>> zip_path = 'path/to/your/archive.zip'
            >>> extract_path = 'path/to/extract/directory'
            >>> encoding = 'utf-8'  # or 'cp932' for Japanese text, for example
            >>> self._extract_zip_with_encoding(zip_path, extract_path)
        """
        lang_enc_flag: Final = 0x800
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for zip_info in zip_ref.infolist():
                old_filename = zip_info.filename
                encoding = "utf-8" if zip_info.flag_bits & lang_enc_flag else "cp437"
                enc = charset_normalizer.detect(zip_info.filename.encode(encoding))
                if not enc.get("encoding"):
                    enc["encoding"] = encoding

                zip_info.filename = zip_info.filename.encode(encoding).decode(str(enc["encoding"]))
                zip_ref.NameToInfo[zip_info.filename] = zip_info
                del zip_ref.NameToInfo[old_filename]

                zip_ref.extract(zip_info, extract_path)

    def _is_excluded(self, file: Path) -> bool:
        """Checks a specific file pattern to determine whether it should be excluded.

        This method checks if the file matches any of the predefined excluded patterns or regex.
        The excluded patterns are `__MACOSX` and `.DS_Store`.
        The excluded regex matches any file that starts with `~$` and ends with `.docx`, `.xlsx`, or `.pptx`.

        Args:
            file (Path): The file to check.

        Returns:
            bool: True if the file should be excluded, False otherwise.

        Rules:
            Specifically, the files to be excluded are:

            - Files containing "__MACOSX" or ".DS_Store" in their paths.
            - Files starting with "~$" and ending with ".docx", ".xlsx", or ".pptx".
        """
        excluded_patterns = ["__MACOSX", ".DS_Store"]
        excluded_regex = re.compile(r"~\$.*\.(docx|xlsx|pptx)")
        return any(pattern in file.parts for pattern in excluded_patterns) or bool(excluded_regex.search(str(file)))


class CompressedFolderParser(ICompressedFileStructParser):
    """Parser for compressed folders, extracting contents and ensuring they match an expected structure.

    This parser is specifically designed for compressed folders. It extracts the content
    and verifies against a provided xlsx invoice structure.

    Attributes:
        xlsx_invoice (pd.DataFrame): DataFrame representing the expected structure or content description
            of the compressed folder contents.
    """

    def __init__(self, xlsx_invoice: pd.DataFrame):
        self.xlsx_invoice = xlsx_invoice

    def read(self, zipfile: Path, target_path: Path) -> list[tuple[Path, ...]]:
        """Extracts the contents of the zipfile and returns validated file paths.

        Args:
            zipfile (Path): Path to the compressed folder to be read.
            target_path (Path): Destination directory where the zipfile will be extracted.

        Returns:
            List[Tuple[Path, ...]]: A list of tuples containing file paths that have been
            validated based on unique directory names.
        """
        _ = self._unpacked(zipfile, target_path)
        safe_verification_files = self.validation_uniq_fspath(target_path, exclude_names=["invoice_org.json"])
        return [tuple(f) for f in safe_verification_files.values()]

    def _unpacked(self, zipfile: Path | str, target_dir: Path | str) -> list[Path]:
        if isinstance(target_dir, str):
            target_dir = Path(target_dir)
        self._extract_zip_with_encoding(zipfile, target_dir)

        cleaner = SystemFilesCleaner()
        removed_paths = cleaner.clean_directory(target_dir)
        if removed_paths:
            logger.info(f"Removed {len(removed_paths)} system/temporary files after extraction")

        return [f for f in target_dir.glob("**/*") if f.is_file() and not self._is_excluded(f)]

    def _extract_zip_with_encoding(self, zip_path: Path | str, extract_path: Path | str) -> None:
        """Extracts a ZIP file, handling filenames with a specified encoding to prevent garbled text.

        This function attempts to detect and correct the encoding of filenames within the ZIP file to ensure they are extracted with the correct filenames, avoiding issues with garbled text due to encoding mismatches.

        Args:
            zip_path (Path | str): The path to the ZIP file to be extracted.
            extract_path (Path | str): The directory where the contents of the ZIP file will be extracted.

        Raises:
            ValueError: If encoding detection fails for any filename within the ZIP archive.
            UnicodeDecodeError: If a filename cannot be decoded with the detected or specified encoding.

        Example:
            >>> zip_path = 'path/to/your/archive.zip'
            >>> extract_path = 'path/to/extract/directory'
            >>> encoding = 'utf-8'  # or 'cp932' for Japanese text, for example
            >>> self._extract_zip_with_encoding(zip_path, extract_path)
        """
        lang_enc_flag: Final = 0x800
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for zip_info in zip_ref.infolist():
                old_filename = zip_info.filename
                encoding = "utf-8" if zip_info.flag_bits & lang_enc_flag else "cp437"
                enc = charset_normalizer.detect(zip_info.filename.encode(encoding))
                if not enc.get("encoding"):
                    enc["encoding"] = encoding

                zip_info.filename = zip_info.filename.encode(encoding).decode(str(enc["encoding"]))
                zip_ref.NameToInfo[zip_info.filename] = zip_info
                del zip_ref.NameToInfo[old_filename]

                zip_ref.extract(zip_info, extract_path)

    def _is_excluded(self, file: Path) -> bool:
        """Checks a specific file pattern to determine whether it should be excluded.

        This method checks if the file matches any of the predefined excluded patterns or regex.
        The excluded patterns are `__MACOSX` and `.DS_Store`.
        The excluded regex matches any file that starts with `~$` and ends with `.docx`, `.xlsx`, or `.pptx`.

        Args:
            file (Path): The file to check.

        Returns:
            bool: True if the file should be excluded, False otherwise.

        Rules:
            Specifically, the files to be excluded are:

            - Files containing "__MACOSX" or ".DS_Store" in their paths.
            - Files starting with "~$" and ending with ".docx", ".xlsx", or ".pptx".
        """
        excluded_patterns = ["__MACOSX", ".DS_Store"]
        excluded_regex = re.compile(r"~\$.*\.(docx|xlsx|pptx)")
        return any(pattern in file.parts for pattern in excluded_patterns) or bool(excluded_regex.search(str(file)))

    def validation_uniq_fspath(self, target_path: str | Path, exclude_names: list[str]) -> dict[str, list[Path]]:
        """Check if there are any non-unique directory names under the target directory.

        Args:
            target_path (Union[str, Path]): The directory path to scan
            exclude_names (list[str]): Excluded files

        Raises:
            StructuredError: An exception is raised when duplicate directory names are detected

        Returns:
            dict[str, Path]: Returns the unique directory names and a list of files under each directory

        Note:
            This function checks for the existence of folders with the same name,
            differing only in case (e.g., 'folder1' and 'Folder1'). In a Unix-based filesystem,
            such folders can coexist when creating a zip file. However, Windows does not allow
            for this coexistence when downloading and unzipping the file, leading to an unzip
            failure in my environment. Therefore, it's necessary to check for folders whose names
            differ only in case.
        """
        verification_files: dict[str, list[Path]] = {}
        unique_dirname_set = set()
        for d, _, fnames in os.walk(target_path):
            if not fnames:
                continue
            # check file
            _filered_paths = [Path(d) / Path(f) for f in fnames if f not in exclude_names]
            for f in _filered_paths:
                if str(f).lower() in unique_dirname_set:
                    emsg = "ERROR: folder paths and file paths stored in a zip file must always have unique names."
                    raise StructuredError(emsg)
                unique_dirname_set.add(str(f).lower())

            # check folder
            lower_dir = str(d).lower()
            if lower_dir in unique_dirname_set:
                emsg = "ERROR: folder paths and file paths stored in a zip file must always have unique names."
                raise StructuredError(emsg)
            unique_dirname_set.add(lower_dir)
            verification_files[lower_dir] = _filered_paths

        return verification_files


def parse_compressedfile_mode(
    xlsx_invoice: pd.DataFrame,
) -> ICompressedFileStructParser:
    """Parses the mode of a compressed file and returns the corresponding parser object.

    Args:
        xlsx_invoice (pandas.DataFrame): The invoice data in Excel format.

    Returns:
        ICompressedFileStructParser: An instance of the compressed file structure parser.
    """
    if "data_file_names/name" in xlsx_invoice.columns:
        # File Mode
        return CompressedFlatFileParser(xlsx_invoice)
    return CompressedFolderParser(xlsx_invoice)


class ZipArtifactPackageCompressor(IArtifactPackageCompressor):

    def __init__(self, source_dir: str | Path, exclude_patterns: list[str]) -> None:
        self.source_dir = Path(source_dir) if not isinstance(source_dir, Path) else source_dir
        self._exclude_patterns = [re.compile(pattern) for pattern in exclude_patterns]

    @property
    def exclude_patterns(self) -> list[str]:
        """Get the list of exclude patterns."""
        return [pattern.pattern for pattern in self._exclude_patterns]

    @exclude_patterns.setter
    def exclude_patterns(self, patterns: list[str]) -> None:
        """Set the list of exclude patterns."""
        self._exclude_patterns = [re.compile(pattern) for pattern in patterns]

    def archive(self, output_zip: str | Path) -> list[Path]:
        """Archives the source directory into a zip file with case-insensitive path validation.

        Args:
            output_zip: Path to the output zip file

        Returns:
            List of top-level directories included in the archive

        Raises:
            StructuredError: When case-insensitive duplicate paths are detected
        """
        included_dirs = set()
        files_to_zip = []
        all_file_paths = []

        for root, dirs, files in os.walk(self.source_dir):
            dirs[:] = [d for d in dirs if not self._is_excluded(os.path.join(root, d))]

            for file in files:
                file_path = os.path.join(root, file)
                if self._is_excluded(file_path):
                    continue

                rel_path = os.path.relpath(file_path, self.source_dir)
                lower_path = rel_path.lower()

                if lower_path in included_dirs:
                    emsg = f"ERROR: Case-insensitive duplicate path detected: {rel_path}"
                    raise StructuredError(emsg)

                included_dirs.add(lower_path)
                files_to_zip.append((file_path, rel_path))
                all_file_paths.append(Path(rel_path))

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path, rel_path in files_to_zip:
                zipf.write(file_path, rel_path)

        return list(all_file_paths)

    def _is_excluded(self, path: str) -> bool:
        """Check if path matches any compiled exclude pattern."""
        return any(
            pattern.search(path) for pattern in self._exclude_patterns
        )


class TarGzArtifactPackageCompressor(IArtifactPackageCompressor):
    def __init__(self, source_dir: str | Path, exclude_patterns: list[str]) -> None:
        self.source_dir = Path(source_dir) if not isinstance(source_dir, Path) else source_dir
        self._exclude_patterns = [re.compile(pattern) for pattern in exclude_patterns]

    @property
    def exclude_patterns(self) -> list[str]:
        """Get the list of exclude patterns."""
        return [pattern.pattern for pattern in self._exclude_patterns]

    @exclude_patterns.setter
    def exclude_patterns(self, patterns: list[str]) -> None:
        """Set the list of exclude patterns."""
        self._exclude_patterns = [re.compile(pattern) for pattern in patterns]

    def archive(self, output_tar: str | Path) -> list[Path]:
        """Archives the source directory into a tar.gz file with case-insensitive path validation.

        Args:
            output_tar: Path to the output tar.gz file

        Returns:
            List of top-level directories included in the archive

        Raises:
            StructuredError: When case-insensitive duplicate paths are detected
        """
        included_dirs = set()
        files_to_targz = []
        all_file_paths = []

        for root, dirs, files in os.walk(self.source_dir):
            dirs[:] = [d for d in dirs if not self._is_excluded(os.path.join(root, d))]

            for file in files:
                file_path = os.path.join(root, file)
                if self._is_excluded(file_path):
                    continue

                rel_path = os.path.relpath(file_path, self.source_dir)
                lower_path = rel_path.lower()

                if lower_path in included_dirs:
                    emsg = f"ERROR: Case-insensitive duplicate path detected: {rel_path}"
                    raise StructuredError(emsg)

                included_dirs.add(lower_path)
                files_to_targz.append((file_path, rel_path))
                all_file_paths.append(Path(rel_path))

        with tarfile.open(output_tar, "w:gz") as tar:
            for file_path, rel_path in files_to_targz:
                tar.add(file_path, arcname=rel_path)
        return all_file_paths

    def _is_excluded(self, path: str) -> bool:
        """Check if path matches any compiled exclude pattern."""
        return any(
            pattern.search(path) for pattern in self._exclude_patterns
        )


def get_artifact_archiver(fmt: str, source_dir: str | Path, exclude_patterns: list[str]) -> IArtifactPackageCompressor:
    """Factory function to get the appropriate archiver based on the format.

    Args:
        fmt (str): The format of the archive (e.g., 'zip', 'tar.gz').
        source_dir (str | Path): The source directory to be archived.
        exclude_patterns (list[str]): List of patterns to exclude.

    Returns:
        IArtifactPackageCompressor: An instance of the appropriate archiver class.

    Raises:
        ValueError: If the format is not supported.
    """
    if fmt.lower() == "zip":
        return ZipArtifactPackageCompressor(source_dir, exclude_patterns)
    if fmt.lower() in ("tar.gz", "targz", "tgz"):
        return TarGzArtifactPackageCompressor(source_dir, exclude_patterns)
    emsg = "Unsupported archive format. Use 'zip' or 'tar.gz'."
    raise ValueError(emsg)
