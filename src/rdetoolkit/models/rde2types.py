"""Type definitions for RDE toolkit.

This module provides type definitions used throughout the RDE toolkit, including:
- Legacy type aliases for backward compatibility
- NewType definitions for improved type safety
- Validated path types with runtime checks
- Data classes for path and configuration management

NewType Definitions:
    NewType provides compile-time type distinction without runtime overhead.
    Use the helper functions (create_*) to construct typed instances safely.
"""

from __future__ import annotations

import os
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, NewType, Protocol, TypedDict, Union, overload

if TYPE_CHECKING:
    from rdetoolkit.models.config import Config

# Legacy type aliases - kept for backward compatibility
# Consider using NewType definitions (ZipFilePath, etc.) for new code
ZipFilesPathList = Sequence[Path]
UnZipFilesPathList = Sequence[Path]
ExcelInvoicePathList = Sequence[Path]
OtherFilesPathList = Sequence[Path]
PathTuple = tuple[Path, ...]
# Legacy type - use FileGroup for new code
InputFilesGroup = tuple[ZipFilesPathList, ExcelInvoicePathList, OtherFilesPathList]
RawFiles = Sequence[PathTuple]
MetaType = dict[str, Union[str, int, float, list, bool]]
RepeatedMetaType = dict[str, list[Union[str, int, float, list, bool]]]
MetaItem = dict[str, Union[str, int, float, list, bool]]
RdeFsPath = Union[str, Path]

# NewType definitions for improved type safety
# These provide compile-time distinction without runtime overhead

# Individual file path types
ZipFilePath = NewType("ZipFilePath", Path)
UnzippedFilePath = NewType("UnzippedFilePath", Path)
ExcelInvoicePath = NewType("ExcelInvoicePath", Path)
SmartTablePath = NewType("SmartTablePath", Path)
OtherFilePath = NewType("OtherFilePath", Path)

# Directory path types
InputDataDir = NewType("InputDataDir", Path)
OutputDir = NewType("OutputDir", Path)
TemporaryDir = NewType("TemporaryDir", Path)
TaskSupportDir = NewType("TaskSupportDir", Path)
InvoiceDir = NewType("InvoiceDir", Path)


def create_zip_file_path(path: Path | str) -> ZipFilePath:
    """Create a ZipFilePath from a Path or string.

    Args:
        path: Path to a ZIP file

    Returns:
        ZipFilePath: Typed path instance
    """
    return ZipFilePath(Path(path) if isinstance(path, str) else path)


def create_excel_invoice_path(path: Path | str) -> ExcelInvoicePath:
    """Create an ExcelInvoicePath from a Path or string.

    Args:
        path: Path to an Excel invoice file

    Returns:
        ExcelInvoicePath: Typed path instance
    """
    return ExcelInvoicePath(Path(path) if isinstance(path, str) else path)


def create_smarttable_path(path: Path | str) -> SmartTablePath:
    """Create a SmartTablePath from a Path or string.

    Args:
        path: Path to a SmartTable file

    Returns:
        SmartTablePath: Typed path instance
    """
    return SmartTablePath(Path(path) if isinstance(path, str) else path)


def create_input_data_dir(path: Path | str) -> InputDataDir:
    """Create an InputDataDir from a Path or string.

    Args:
        path: Path to input data directory

    Returns:
        InputDataDir: Typed directory path instance
    """
    return InputDataDir(Path(path) if isinstance(path, str) else path)


def create_output_dir(path: Path | str) -> OutputDir:
    """Create an OutputDir from a Path or string.

    Args:
        path: Path to output directory

    Returns:
        OutputDir: Typed directory path instance
    """
    return OutputDir(Path(path) if isinstance(path, str) else path)


# Validated path types with runtime validation
# These provide both compile-time type safety and runtime validation


@dataclass(frozen=True)
class ValidatedPath:
    """Base class for validated path types.

    This class provides a foundation for path types that require validation.
    Subclasses should override __post_init__ to add specific validation logic.

    Attributes:
        path: The filesystem path being validated

    Note:
        This is a frozen dataclass for immutability and to prevent
        accidental modification after validation.
    """

    path: Path

    def __post_init__(self) -> None:
        """Validate the path. Override in subclasses for specific validation.

        Raises:
            TypeError: If path is not a Path instance
        """
        if not isinstance(self.path, Path):
            msg = f"path must be a Path instance, got {type(self.path)}"  # type: ignore[unreachable]
            raise TypeError(msg)

    def __str__(self) -> str:
        """Return string representation of the path."""
        return str(self.path)

    def __fspath__(self) -> str:
        """Return the file system path representation.

        This allows ValidatedPath instances to be used with standard
        library functions that accept path-like objects.
        """
        return str(self.path)

    @classmethod
    def from_string(cls, path_str: str) -> ValidatedPath:
        """Create a ValidatedPath from a string.

        Args:
            path_str: String representation of a path

        Returns:
            ValidatedPath instance

        Example:
            >>> path = ValidatedPath.from_string("/data/file.txt")
        """
        return cls(Path(path_str))

    @classmethod
    def from_parts(cls, *parts: str) -> ValidatedPath:
        """Create a ValidatedPath from path components.

        Args:
            *parts: Path components to join

        Returns:
            ValidatedPath instance

        Example:
            >>> path = ValidatedPath.from_parts("data", "files", "file.txt")
        """
        return cls(Path(*parts))


@dataclass(frozen=True)
class ZipFile(ValidatedPath):
    """ZIP file path with validation.

    Validates that the path has a .zip extension.

    Example:
        >>> zip_file = ZipFile(Path("data.zip"))
        >>> zip_file.path
        PosixPath('data.zip')

    Raises:
        ValueError: If the file does not have a .zip extension
    """

    def __post_init__(self) -> None:
        """Validate that the path is a ZIP file."""
        ValidatedPath.__post_init__(self)
        if self.path.suffix.lower() != ".zip":
            msg = f"Not a ZIP file: {self.path}"
            raise ValueError(msg)


@dataclass(frozen=True)
class ExcelFile(ValidatedPath):
    """Excel file path with validation.

    Validates that the path has an Excel extension (.xls, .xlsx, .xlsm).

    Example:
        >>> excel_file = ExcelFile(Path("invoice.xlsx"))
        >>> excel_file.path
        PosixPath('invoice.xlsx')

    Raises:
        ValueError: If the file does not have an Excel extension
    """

    def __post_init__(self) -> None:
        """Validate that the path is an Excel file."""
        ValidatedPath.__post_init__(self)
        valid_extensions = {".xls", ".xlsx", ".xlsm"}
        if self.path.suffix.lower() not in valid_extensions:
            msg = f"Not an Excel file: {self.path} (expected {valid_extensions})"
            raise ValueError(msg)


@dataclass(frozen=True)
class CsvFile(ValidatedPath):
    """CSV file path with validation.

    Validates that the path has a .csv extension.

    Example:
        >>> csv_file = CsvFile(Path("data.csv"))
        >>> csv_file.path
        PosixPath('data.csv')

    Raises:
        ValueError: If the file does not have a .csv extension
    """

    def __post_init__(self) -> None:
        """Validate that the path is a CSV file."""
        ValidatedPath.__post_init__(self)
        if self.path.suffix.lower() != ".csv":
            msg = f"Not a CSV file: {self.path}"
            raise ValueError(msg)


@dataclass(frozen=True)
class JsonFile(ValidatedPath):
    """JSON file path with validation.

    Validates that the path has a .json extension.

    Example:
        >>> json_file = JsonFile(Path("config.json"))
        >>> json_file.path
        PosixPath('config.json')

    Raises:
        ValueError: If the file does not have a .json extension
    """

    def __post_init__(self) -> None:
        """Validate that the path is a JSON file."""
        ValidatedPath.__post_init__(self)
        if self.path.suffix.lower() != ".json":
            msg = f"Not a JSON file: {self.path}"
            raise ValueError(msg)


@dataclass(frozen=True)
class ValidatedDirectory(ValidatedPath):
    """Base class for validated directory paths.

    Attributes:
        path: The directory path
        must_exist: If True, validates that directory exists

    Raises:
        ValueError: If must_exist is True and directory doesn't exist
    """

    must_exist: bool = field(default=False)

    def __post_init__(self) -> None:
        """Validate directory path and existence if required."""
        ValidatedPath.__post_init__(self)
        if self.must_exist and not self.path.exists():
            msg = f"Directory does not exist: {self.path}"
            raise ValueError(msg)
        if self.must_exist and not self.path.is_dir():
            msg = f"Path is not a directory: {self.path}"
            raise ValueError(msg)


@dataclass(frozen=True)
class FileGroup:
    """Typed collection of files for RDE processing.

    Groups related files by type for structured processing. This replaces
    the simple tuple-based InputFilesGroup with a type-safe, self-documenting
    structure.

    Attributes:
        raw_files: Raw input files (any type)
        zip_files: ZIP archive files
        excel_invoices: Excel invoice files
        other_files: Other supporting files

    Example:
        >>> group = FileGroup(
        ...     raw_files=(Path("data.txt"),),
        ...     zip_files=(ZipFile(Path("archive.zip")),),
        ...     excel_invoices=(ExcelFile(Path("invoice.xlsx")),),
        ...     other_files=(Path("readme.txt"),)
        ... )

    Note:
        Using tuples (immutable) instead of lists to maintain immutability
        consistent with frozen dataclass.
    """

    raw_files: tuple[Path, ...]
    zip_files: tuple[ZipFile, ...] = ()
    excel_invoices: tuple[ExcelFile, ...] = ()
    other_files: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        """Validate that collections are tuples."""
        for field_name in ["raw_files", "zip_files", "excel_invoices", "other_files"]:
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                msg = f"{field_name} must be a tuple, got {type(value)}"
                raise TypeError(msg)

    @property
    def all_files(self) -> tuple[Path, ...]:
        """Return all files as a flat tuple of Paths.

        Combines all files from all categories, preserving order and avoiding duplicates.
        When using from_paths(), raw_files contains all paths and this returns raw_files.
        When manually constructed, combines unique paths from all collections.

        Returns:
            Tuple containing all unique file paths

        Example:
            >>> group = FileGroup(raw_files=(Path("a.txt"),), zip_files=(ZipFile(Path("b.zip")),))
            >>> len(group.all_files)
            2
        """
        # Use a dict to maintain order while ensuring uniqueness
        seen: dict[Path, None] = {}

        # Add from raw_files first
        for path in self.raw_files:
            seen[path] = None

        # Add from specialized collections
        for zf in self.zip_files:
            seen[zf.path] = None
        for ef in self.excel_invoices:
            seen[ef.path] = None
        for path in self.other_files:
            seen[path] = None

        return tuple(seen.keys())

    @property
    def file_count(self) -> int:
        """Return total number of files in all categories.

        Returns:
            Total count of files across all groups
        """
        return len(self.all_files)

    @property
    def has_zip_files(self) -> bool:
        """Check if group contains any ZIP files.

        Returns:
            True if zip_files is non-empty
        """
        return len(self.zip_files) > 0

    @property
    def has_excel_invoices(self) -> bool:
        """Check if group contains any Excel invoice files.

        Returns:
            True if excel_invoices is non-empty
        """
        return len(self.excel_invoices) > 0

    @classmethod
    def from_paths(
        cls,
        paths: Sequence[Path],
        *,
        auto_classify: bool = True,
    ) -> FileGroup:
        """Create FileGroup from a sequence of paths.

        Args:
            paths: Sequence of Path objects to classify
            auto_classify: If True, automatically classify files by extension

        Returns:
            FileGroup with files classified by type

        Example:
            >>> paths = [Path("data.txt"), Path("archive.zip"), Path("invoice.xlsx")]
            >>> group = FileGroup.from_paths(paths)
            >>> group.has_zip_files
            True
        """
        if not auto_classify:
            return cls(raw_files=tuple(paths))

        zip_files: list[ZipFile] = []
        excel_files: list[ExcelFile] = []
        other_files: list[Path] = []

        for path in paths:
            try:
                if path.suffix.lower() == ".zip":
                    zip_files.append(ZipFile(path))
                elif path.suffix.lower() in {".xls", ".xlsx", ".xlsm"}:
                    excel_files.append(ExcelFile(path))
                else:
                    other_files.append(path)
            except ValueError:
                # If validation fails, treat as other file
                other_files.append(path)

        return cls(
            raw_files=tuple(paths),
            zip_files=tuple(zip_files),
            excel_invoices=tuple(excel_files),
            other_files=tuple(other_files),
        )

    @classmethod
    def empty(cls) -> FileGroup:
        """Create an empty FileGroup.

        Returns:
            FileGroup with no files

        Example:
            >>> empty = FileGroup.empty()
            >>> empty.file_count
            0
        """
        return cls(raw_files=())


@dataclass(frozen=True)
class ProcessedFileGroup:
    """Collection of files after processing (unzipping, parsing, etc.).

    Represents the result of processing a FileGroup, typically after
    unpacking ZIP files and identifying special file types.

    Attributes:
        unzipped_files: Files extracted from ZIP archives
        excel_invoice: Primary Excel invoice file (if found)
        smarttable_csv: SmartTable CSV file (if found)
        raw_data_files: Raw data files for processing
        metadata_files: Metadata or configuration files

    Example:
        >>> processed = ProcessedFileGroup(
        ...     unzipped_files=(Path("data1.txt"), Path("data2.csv")),
        ...     excel_invoice=ExcelFile(Path("invoice.xlsx")),
        ...     smarttable_csv=CsvFile(Path("smart_table.csv")),
        ...     raw_data_files=(Path("data1.txt"),)
        ... )
    """

    unzipped_files: tuple[Path, ...] = ()
    excel_invoice: ExcelFile | None = None
    smarttable_csv: CsvFile | None = None
    raw_data_files: tuple[Path, ...] = ()
    metadata_files: tuple[Path, ...] = ()

    @property
    def has_excel_invoice(self) -> bool:
        """Check if an Excel invoice is present.

        Returns:
            True if excel_invoice is not None
        """
        return self.excel_invoice is not None

    @property
    def has_smarttable(self) -> bool:
        """Check if a SmartTable CSV is present.

        Returns:
            True if smarttable_csv is not None
        """
        return self.smarttable_csv is not None

    @property
    def total_file_count(self) -> int:
        """Return total number of files.

        Returns:
            Sum of files across all categories
        """
        count = len(self.unzipped_files) + len(self.raw_data_files) + len(self.metadata_files)
        if self.excel_invoice is not None:
            count += 1
        if self.smarttable_csv is not None:
            count += 1
        return count


@dataclass
class RdeFormatFlags:  # pragma: no cover
    """Class for managing flags used in RDE.

    This class has two private attributes: _is_rdeformat_enabled and _is_multifile_enabled.
    These attributes are set in the __post_init__ method, depending on the existence of certain files.
    Additionally, properties and setters are used to get and modify the values of these attributes.
    However, it is not allowed for both attributes to be True simultaneously.

    Warning:
        Currently, this class is not used because the `data/tasksupport/rdeformat.txt` and `data/tasksupport/multifile.txt` files are not used. It is scheduled to be deleted in the next update.

    Attributes:
        _is_rdeformat_enabled (bool): Flag indicating whether RDE format is enabled
        _is_multifile_enabled (bool): Flag indicating whether multi-file support is enabled
    """

    _is_rdeformat_enabled: bool = False
    _is_multifile_enabled: bool = False

    def __init__(self) -> None:
        warnings.warn("The RdeFormatFlags class is scheduled to be deleted in the next update.", FutureWarning, stacklevel=2)

    def __post_init__(self) -> None:
        """Method called after object initialization.

        This method checks for the existence of files named rdeformat.txt and multifile.txt in the data/tasksupport directory,
        and sets the values of _is_rdeformat_enabled and _is_multifile_enabled accordingly.
        """
        self.is_rdeformat_enabled = os.path.exists("data/tasksupport/rdeformat.txt")
        self.is_multifile_enabled = os.path.exists("data/tasksupport/multifile.txt")

    @property
    def is_rdeformat_enabled(self) -> bool:
        """Property returning whether the RDE format is enabled.

        Returns:
            bool: Whether the RDE format is enabled
        """
        return self._is_rdeformat_enabled

    @is_rdeformat_enabled.setter
    def is_rdeformat_enabled(self, value: bool) -> None:
        """Setter to change the enabled state of the RDE format.

        Args:
            value (bool): Whether to enable the RDE format

        Raises:
            ValueError: If both flags are set to True
        """
        if value and self.is_multifile_enabled:
            emsg = "both flags cannot be True"
            raise ValueError(emsg)
        self._is_rdeformat_enabled = value

    @property
    def is_multifile_enabled(self) -> bool:
        """Property returning whether multi-file support is enabled.

        Returns:
            bool: Whether multi-file support is enabled
        """
        return self._is_multifile_enabled

    @is_multifile_enabled.setter
    def is_multifile_enabled(self, value: bool) -> None:
        """Setter to change the enabled state of multi-file support.

        Args:
            value (bool): Whether to enable multi-file support

        Raises:
            ValueError: If both flags are set to True
        """
        if value and self.is_rdeformat_enabled:
            emsg = "both flags cannot be True"
            raise ValueError(emsg)
        self._is_multifile_enabled = value


def create_default_config() -> Config:
    """Creates and returns a default configuration object.

    Returns:
        Config: A default configuration object.
    """
    from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings  # noqa: PLC0415

    return Config(
        system=SystemSettings(
            extended_mode=None,
            save_raw=True,
            save_nonshared_raw=True,
            save_thumbnail_image=False,
            magic_variable=False,
        ),
        multidata_tile=MultiDataTileSettings(ignore_errors=False),
        smarttable=None,
        traceback=None,
    )


@dataclass
class RdeInputDirPaths:
    """A data class that holds folder paths used for input in the RDE.

    It manages the folder paths for input data necessary for the RDE.

    Attributes:
        inputdata (Path): Path to the folder where input data is stored.
        invoice (Path): Path to the folder where invoice.json is stored.
        tasksupport (Path): Path to the folder where task support data is stored.
        config (Config): The configuration object.

    Properties:
        default_csv (Path): Provides the path to the `default_value.csv` file.
                If `tasksupport` is specified, it uses the path under it; otherwise,
                it uses the default path under `data/tasksupport`.
    """

    inputdata: Path
    invoice: Path
    tasksupport: Path
    config: Config = field(default_factory=create_default_config)

    @property
    def default_csv(self) -> Path:
        """Returns the path to the 'default_value.csv' file.

        If `tasksupport` is set, this path is used.
        If not set, the default path under 'data/tasksupport' is used.

        Returns:
            Path: Path to the 'default_value.csv' file.
        """
        tasksupport = self.tasksupport if self.tasksupport else Path("data", "tasksupport")
        return tasksupport.joinpath("default_value.csv")


@dataclass
class RdeOutputResourcePath:
    """A data class that holds folder paths used as output destinations for RDE.

    It maintains the paths for various files used in the structuring process.

    Attributes:
        raw (Path): Path where raw data is stored.
        nonshared_raw (Path): Path where nonshared raw data is stored.
        rawfiles (tuple[Path, ...]): Holds a tuple of input file paths,
                                    such as those unzipped, for a single tile of data.
        struct (Path): Path for storing structured data.
        main_image (Path): Path for storing the main image file.
        other_image (Path): Path for storing other image files.
        meta (Path): Path for storing metadata files.
        thumbnail (Path): Path for storing thumbnail image files.
        logs (Path): Path for storing log files.
        invoice (Path): Path for storing invoice files.
        invoice_schema_json (Path): Path for the invoice.schema.json file.
        invoice_org (Path): Path for storing the backup of invoice.json.
        smarttable_rowfile (Optional[Path]): Path for the SmartTable-generated row CSV file.
        temp (Optional[Path]): Path for storing temporary files.
        invoice_patch (Optional[Path]): Path for storing modified invoice files.
        attachment (Optional[Path]): Path for storing attachment files.
    """

    raw: Path
    nonshared_raw: Path
    rawfiles: tuple[Path, ...]
    struct: Path
    main_image: Path
    other_image: Path
    meta: Path
    thumbnail: Path
    logs: Path
    invoice: Path
    invoice_schema_json: Path
    invoice_org: Path
    smarttable_rowfile: Path | None = None
    temp: Path | None = None
    invoice_patch: Path | None = None
    attachment: Path | None = None


@dataclass
class RdeDatasetPaths:
    """Unified view over input and output paths used by dataset callbacks.

    This class bundles the existing :class:`RdeInputDirPaths` and
    :class:`RdeOutputResourcePath` instances while preserving the original
    structures for backwards compatibility.  Callbacks using the new
    single-argument style receive an instance of this class.

    Attributes:
        input_paths: Original input directory information.
        output_paths: Original output resource path information.
    """

    input_paths: RdeInputDirPaths
    output_paths: RdeOutputResourcePath

    @property
    def inputdata(self) -> Path:
        """Return the input data directory."""
        return self.input_paths.inputdata

    @property
    def tasksupport(self) -> Path:
        """Return the tasksupport directory."""
        return self.input_paths.tasksupport

    @property
    def config(self) -> Config:
        """Return the configuration associated with the dataset."""
        return self.input_paths.config

    @property
    def default_csv(self) -> Path:
        """Return the resolved default CSV path."""
        wmsg = "RdeDatasetPaths.default_csv is deprecated and will be removed in a future release."
        warnings.warn(
            wmsg,
            DeprecationWarning,
            stacklevel=2,
        )
        return self.input_paths.default_csv

    @property
    def raw(self) -> Path:
        """Return the output directory for raw data."""
        return self.output_paths.raw

    @property
    def nonshared_raw(self) -> Path:
        """Return the output directory for non-shared raw data."""
        return self.output_paths.nonshared_raw

    @property
    def smarttable_rowfile(self) -> Path | None:
        """Return SmartTable row CSV path with rawfiles fallback."""
        rowfile = self.output_paths.smarttable_rowfile
        if rowfile is not None:
            return rowfile

        rawfiles = getattr(self.output_paths, "rawfiles", ())
        if rawfiles:
            candidate = rawfiles[0]
            if isinstance(candidate, Path) and candidate.suffix.lower() == ".csv" and candidate.stem.startswith("fsmarttable_"):
                warnings.warn(
                    "RdeDatasetPaths.smarttable_rowfile uses rawfiles[0] fallback; update generators to populate smarttable_rowfile.",
                    FutureWarning,
                    stacklevel=2,
                )
                return candidate
        return None

    @property
    def rawfiles(self) -> tuple[Path, ...]:
        """Return the tuple of raw input files for the dataset."""
        return self.output_paths.rawfiles

    @property
    def struct(self) -> Path:
        """Return the structured output directory."""
        return self.output_paths.struct

    @property
    def main_image(self) -> Path:
        """Return the main image output directory."""
        return self.output_paths.main_image

    @property
    def other_image(self) -> Path:
        """Return the auxiliary image output directory."""
        return self.output_paths.other_image

    @property
    def meta(self) -> Path:
        """Return the metadata output directory."""
        return self.output_paths.meta

    @property
    def thumbnail(self) -> Path:
        """Return the thumbnail image output directory."""
        return self.output_paths.thumbnail

    @property
    def logs(self) -> Path:
        """Return the logs output directory."""
        return self.output_paths.logs

    @property
    def invoice(self) -> Path:
        """Return the output-side invoice directory."""
        return self.output_paths.invoice

    @property
    def invoice_schema_json(self) -> Path:
        """Return the path to the invoice schema file."""
        return self.output_paths.invoice_schema_json

    @property
    def invoice_org(self) -> Path:
        """Return the path to the original invoice.json file."""
        if self.output_paths.invoice_org is not None:
            return self.output_paths.invoice_org
        return self.input_paths.invoice.joinpath("invoice.json")  # type: ignore[unreachable]  # noqa: RET503

    @property
    def temp(self) -> Path | None:
        """Return the temporary directory if available."""
        return self.output_paths.temp

    @property
    def invoice_patch(self) -> Path | None:
        """Return the directory for invoice patch files if available."""
        return self.output_paths.invoice_patch

    @property
    def attachment(self) -> Path | None:
        """Return the directory for attachment files if available."""
        return self.output_paths.attachment

    @property
    def metadata_def_json(self) -> Path:
        """Return the path to metadata-def.json under tasksupport."""
        return self.input_paths.tasksupport.joinpath("metadata-def.json")

    def as_legacy_args(self) -> tuple[RdeInputDirPaths, RdeOutputResourcePath]:
        """Return the bundled legacy arguments."""
        return self.input_paths, self.output_paths


class DatasetCallback(Protocol):
    """Protocol that supports both legacy and unified callback signatures."""

    @overload
    def __call__(self, paths: RdeDatasetPaths, /) -> None:  # pragma: no cover
        ...

    @overload
    def __call__(
        self,
        srcpaths: RdeInputDirPaths,
        resource_paths: RdeOutputResourcePath,
        /,
    ) -> None:  # pragma: no cover
        ...


class Name(TypedDict):
    """Represents a name structure as a Typed Dictionary.

    This class is designed to hold names in different languages,
    specifically Japanese and English.

    Attributes:
        ja (str): The name in Japanese.
        en (str): The name in English.
    """

    ja: str
    en: str


class Schema(TypedDict, total=False):
    """Represents a schema definition as a Typed Dictionary.

    This class is used to define the structure of a schema with optional keys.
    It extends TypedDict with `total=False` to allow partial dictionaries.

    Attributes:
        type (str): The type of the schema.
        format (str): The format of the schema.
    """

    type: str
    format: str


class MetadataDefJson(TypedDict):
    """Defines the metadata structure for a JSON object as a Typed Dictionary.

    This class specifies the required structure of metadata, including various fields
    that describe characteristics and properties of the data.

    Attributes:
        name (Name): The name associated with the metadata.
        schema (Schema): The schema of the metadata.
        unit (str): The unit of measurement.
        description (str): A description of the metadata.
        uri (str): The URI associated with the metadata.
        originalName (str): The original name of the metadata.
        originalType (str): The original type of the metadata.
        mode (str): The mode associated with the metadata.
        order (str): The order of the metadata.
        valiable (int): A variable associated with the metadata.
        _feature (bool): A private attribute indicating a feature.
        action (str): An action associated with the metadata.
    """

    name: Name
    schema: Schema
    unit: str
    description: str
    uri: str
    originalName: str
    originalType: str
    mode: str
    order: str
    valiable: int
    _feature: bool
    action: str


@dataclass
class ValueUnitPair:
    """Dataclass representing a pair of value and unit.

    This class is used to store and manage a value along with its associated unit.
    It uses the features of dataclass for simplified data handling.

    Attributes:
        value (str): The value part of the pair.
        unit (str): The unit associated with the value.
    """

    value: str
    unit: str
