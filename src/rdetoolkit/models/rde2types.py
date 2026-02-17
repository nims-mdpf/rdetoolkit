"""RDE type definitions and path structures.

This module defines the core types and data structures used throughout rdetoolkit
for representing RDE (Research Data Express) workflows, paths, and callbacks.

The module provides several categories of type definitions:

1. Path Management Classes (Primary):
   - RdeInputDirPaths: Input directory structure for reading source data
   - RdeOutputResourcePath: Output directory structure for writing processed data
   - RdeDatasetPaths: Unified view combining input and output paths

2. Callback Protocols:
   - DatasetCallback: Type protocol for custom processing functions

3. File Collection Types:
   - FileGroup: Typed collection of files grouped by type
   - ProcessedFileGroup: Files after processing (unzipping, parsing)
   - RawFiles: Collection of raw input files

4. Validated Path Types:
   - ValidatedPath: Base class for paths with runtime validation
   - ZipFile, ExcelFile, CsvFile, JsonFile: File type-specific validated paths
   - ValidatedDirectory: Directory paths with existence validation

5. NewType Definitions:
   - ZipFilePath, ExcelInvoicePath, SmartTablePath: Individual file path types
   - InputDataDir, OutputDir, TemporaryDir: Directory path types
   (Use helper functions create_* to construct these safely)

6. Legacy Type Aliases (Backward Compatibility):
   - InputFilesGroup, PathTuple, MetaType, etc.
   (Use newer types like FileGroup for new code)

7. Type Dictionaries:
   - MetadataDefJson: Metadata definition structure
   - Name, Schema: Supporting structures for metadata

8. Utility Types:
   - ValueUnitPair: Value with associated unit
   - RdeFormatFlags: Legacy format flags (deprecated)

Key Types for Custom Processing Functions:
    These are the primary types users interact with when writing custom dataset
    processing functions:

    - RdeInputDirPaths: Access input data, invoice, and configuration
    - RdeOutputResourcePath: Write processed outputs to structured directories
    - RdeDatasetPaths: Unified interface to both input and output paths
    - DatasetCallback: Protocol for function signatures

Example:
    Custom processing function using the path types:

        >>> from pathlib import Path
        >>> import pandas as pd
        >>> from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
        >>>
        >>> def process_data(srcpaths: RdeInputDirPaths, output: RdeOutputResourcePath):
        ...     # Read input data
        ...     for csv_file in srcpaths.inputdata.glob("*.csv"):
        ...         df = pd.read_csv(csv_file)
        ...
        ...     # Save processed output
        ...     result_file = output.struct / "results.csv"
        ...     df.to_csv(result_file, index=False)

Notes:
    - All Path objects use pathlib.Path
    - Validated types perform runtime checks on construction
    - NewType definitions provide compile-time type safety
    - Legacy types maintained for backward compatibility
    - Use RdeDatasetPaths for new code (single-argument callback style)

See Also:
    - workflows.run: Main workflow entry point using these types
    - models.config: Configuration types referenced by RdeInputDirPaths
    - processing.pipeline: Processing pipeline using these path structures
"""

from __future__ import annotations

import os
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NewType, Protocol, TypedDict, Union, overload

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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class ValidatedDirectory(ValidatedPath):
    """Base class for validated directory paths.

    Attributes:
        path: The directory path
        must_exist: If True, validates that directory exists

    Raises:
        ValueError: If must_exist is True and directory doesn't exist
    """

    must_exist: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        """Validate directory path and existence if required."""
        ValidatedPath.__post_init__(self)
        if self.must_exist and not self.path.exists():
            msg = f"Directory does not exist: {self.path}"
            raise ValueError(msg)
        if self.must_exist and not self.path.is_dir():
            msg = f"Path is not a directory: {self.path}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(slots=True)
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


@dataclass(slots=True)
class RdeInputDirPaths:
    """Input directory paths for RDE workflow processing.

    This class encapsulates the directory structure for input data in the RDE workflow.
    It provides access to raw data files, invoice configuration, and task support files
    that custom processing functions can read and utilize.

    The typical directory structure is:
        container/data/
            raw/              # Raw input data files (CSV, images, etc.)
            invoice/          # Invoice configuration (invoice.json)
            tasksupport/      # Task support files (config, schemas, templates)

    Attributes:
        inputdata: Path to the input data directory containing unprocessed input files.
            This is the primary location where custom processing functions read data from.
            Common file types: CSV, Excel, images (PNG/JPG), text files, ZIP archives.

        invoice: Path to the invoice directory containing invoice.json and related files.
            The invoice defines the dataset structure, metadata schema, and processing
            configuration. Custom functions typically read invoice.json for metadata
            definitions and validation rules.

        tasksupport: Path to the task support directory containing auxiliary files
            such as configuration files (config.toml), schema definitions, CSV templates
            (default_value.csv), and metadata definitions (metadata-def.json).

        config: Configuration object controlling workflow behavior.
            Contains system settings (extended_mode, save_raw, etc.), MultiDataTile
            settings, and SmartTable configuration. Custom functions can access this
            to adjust processing based on the current execution mode.

    Properties:
        default_csv: Path to the 'default_value.csv' file in tasksupport directory.
            This CSV file provides default values for metadata fields when not
            explicitly specified in the input data.

    Examples:
        Accessing input data files:
            >>> def process_data(srcpaths: RdeInputDirPaths, output):
            ...     # Iterate over all files in inputdata directory
            ...     for file_path in srcpaths.inputdata.glob("*.csv"):
            ...         df = pd.read_csv(file_path)
            ...         # Process dataframe
            ...         pass

        Reading invoice configuration:
            >>> def process_data(srcpaths: RdeInputDirPaths, output):
            ...     import json
            ...     invoice_file = srcpaths.invoice / "invoice.json"
            ...     with open(invoice_file) as f:
            ...         invoice_data = json.load(f)
            ...         # Use invoice metadata definitions
            ...         metadata = invoice_data.get("metadata", [])

        Checking configuration mode:
            >>> def process_data(srcpaths: RdeInputDirPaths, output):
            ...     if srcpaths.config.system.extended_mode == "MultiDataTile":
            ...         # Process for MultiDataTile mode
            ...         pass
            ...     elif srcpaths.config.system.extended_mode == "SmartTable":
            ...         # Process for SmartTable mode
            ...         pass

        Using task support files:
            >>> def process_data(srcpaths: RdeInputDirPaths, output):
            ...     # Read default values
            ...     default_csv = srcpaths.default_csv
            ...     if default_csv.exists():
            ...         defaults = pd.read_csv(default_csv)
            ...
            ...     # Read metadata definitions
            ...     metadata_def = srcpaths.tasksupport / "metadata-def.json"
            ...     if metadata_def.exists():
            ...         with open(metadata_def) as f:
            ...             metadata_schema = json.load(f)

    Notes:
        - All Path objects are pathlib.Path instances
        - Use Path.exists() to check file/directory existence before access
        - Path.glob() and Path.rglob() enable pattern-based file discovery
        - config.system.extended_mode determines execution mode (None, "MultiDataTile", "SmartTable")
        - Invoice directory structure depends on execution mode

    See Also:
        - RdeOutputResourcePath: Output path structure for processed data
        - RdeDatasetPaths: Unified view of input and output paths
        - workflows.run: Main workflow function that provides these paths
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


@dataclass(slots=True)
class RdeOutputResourcePath:
    r"""Output resource paths for RDE workflow processing.

    This class encapsulates the directory structure for output data in the RDE workflow.
    Custom processing functions write their results to these directories, which are then
    packaged into the final RDE dataset structure.

    The typical directory structure is:
        container/data/invoice/
            raw/              # Preserved raw input files
            nonshared_raw/    # Non-shared raw input files
            structured/       # Structured data outputs (CSV, Parquet, etc.)
            main_image/       # Primary visualization images
            other_image/      # Additional visualization images
            meta/             # Metadata JSON files
            thumbnail/        # Thumbnail preview images
            logs/             # Processing log files

    Attributes:
        raw: Path to the raw data directory for preserving original input files.
            Files copied here are included in the final dataset package for reproducibility.
            Controlled by config.system.save_raw setting.

        nonshared_raw: Path to the non-shared raw data directory.
            Similar to raw but for files that should not be shared externally.
            Controlled by config.system.save_nonshared_raw setting.

        rawfiles: Tuple of input file paths being processed in the current iteration.
            In standard mode, contains all input files.
            In MultiDataTile mode, contains files for the current tile.
            In SmartTable mode, contains the current row's associated files.
            Use this to identify which files triggered the current processing.

        struct: Path to the structured data directory for processed outputs.
            Save tabular data, analysis results, or transformed data here.
            Common formats: CSV, JSON, Parquet, Arrow.
            Files here are registered in the dataset metadata automatically.

        main_image: Path to the main image directory for primary visualizations.
            Save the most important plots, graphs, or representative images here.
            Common formats: PNG, JPG, SVG, PDF.
            Typically used for dataset preview images.

        other_image: Path to the other image directory for auxiliary visualizations.
            Save supplementary charts, diagnostic plots, or additional figures here.
            Same format support as main_image.

        meta: Path to the metadata directory for JSON metadata files.
            Save extracted metadata, processing parameters, or analysis summaries here.
            Format: JSON only. Files here are merged into dataset metadata.

        thumbnail: Path to the thumbnail directory for preview images.
            Thumbnail images are automatically generated for supported file types.
            Manual thumbnails can also be saved here for custom preview images.
            Controlled by config.system.save_thumbnail_image setting.

        logs: Path to the logs directory for processing logs and diagnostics.
            Save execution logs, error reports, or debugging information here.
            Helps track processing history and troubleshoot issues.

        invoice: Path to the invoice directory for dataset configuration.
            Contains invoice.json (dataset metadata) and invoice.schema.json.
            Custom functions can read but typically should not modify these directly.

        invoice_schema_json: Path to the invoice.schema.json file.
            Defines the JSON schema for validating invoice.json structure.
            Use this to understand expected metadata structure.

        invoice_org: Path to the original invoice.json backup.
            Preserved copy of the original invoice.json before processing.
            Useful for comparing changes or recovering original configuration.

        smarttable_rowfile: Optional path to the SmartTable-generated row CSV file.
            Available only in SmartTable mode. Contains the current row being processed.
            File name format: fsmarttable_<row_index>.csv

        smarttable_row_data: Optional dictionary of parsed SmartTable row data.
            Available only in SmartTable mode. Contains column names as keys.
            Use this to access row-specific metadata like sample names, parameters, etc.
            Example: row_data.get("sample/name", "") or row_data.get("basic/dataName", "")

        temp: Optional path to the temporary directory for intermediate files.
            Use this for temporary processing files that should not be in the final dataset.
            Files here are typically cleaned up after processing.

        invoice_patch: Optional path to the invoice patch directory.
            Used for storing invoice modification fragments that are merged later.
            Advanced feature for dynamic metadata updates.

        attachment: Optional path to the attachment directory.
            Used for storing additional files that should be attached to the dataset
            but don't fit into the standard output categories.

    Examples:
        Saving processed data:
            >>> def process_data(srcpaths, resource_paths: RdeOutputResourcePath):
            ...     import pandas as pd
            ...
            ...     # Process and save structured data
            ...     result_df = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
            ...     output_file = resource_paths.struct / "processed_results.csv"
            ...     result_df.to_csv(output_file, index=False)
            ...
            ...     # Generate and save main visualization
            ...     import matplotlib.pyplot as plt
            ...     plt.figure()
            ...     plt.plot([1, 2, 3], [4, 5, 6])
            ...     figure_file = resource_paths.main_image / "plot.png"
            ...     plt.savefig(figure_file)
            ...     plt.close()

        Creating subdirectories:
            >>> def process_data(srcpaths, resource_paths: RdeOutputResourcePath):
            ...     # Organize outputs into subdirectories
            ...     analysis_dir = resource_paths.struct / "analysis"
            ...     analysis_dir.mkdir(exist_ok=True)
            ...
            ...     summary_file = analysis_dir / "summary.json"
            ...     with open(summary_file, "w") as f:
            ...         json.dump({"status": "complete"}, f)

        Preserving raw files:
            >>> def process_data(srcpaths, resource_paths: RdeOutputResourcePath):
            ...     # Copy specific input files to raw directory
            ...     for raw_file in resource_paths.rawfiles:
            ...         if raw_file.suffix == ".csv":
            ...             import shutil
            ...             dest = resource_paths.raw / raw_file.name
            ...             shutil.copy2(raw_file, dest)

        Saving metadata:
            >>> def process_data(srcpaths, resource_paths: RdeOutputResourcePath):
            ...     import json
            ...
            ...     # Save processing metadata
            ...     metadata = {
            ...         "processing_date": "2024-01-01",
            ...         "algorithm": "custom_analysis",
            ...         "parameters": {"threshold": 0.5}
            ...     }
            ...     meta_file = resource_paths.meta / "processing_info.json"
            ...     with open(meta_file, "w") as f:
            ...         json.dump(metadata, f, indent=2)

        Using SmartTable row data:
            >>> def process_data(srcpaths, resource_paths: RdeOutputResourcePath):
            ...     # Access SmartTable row-specific data
            ...     if resource_paths.smarttable_row_data:
            ...         sample_name = resource_paths.smarttable_row_data.get("sample/name", "")
            ...         data_name = resource_paths.smarttable_row_data.get("basic/dataName", "")
            ...
            ...         # Use row data for file naming
            ...         output_file = resource_paths.struct / f"{sample_name}_results.csv"

        Saving structured data formats:
            >>> def process_data(srcpaths, resource_paths: RdeOutputResourcePath):
            ...     import polars as pl
            ...
            ...     # Save as Parquet for efficient storage
            ...     df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
            ...     parquet_file = resource_paths.struct / "data.parquet"
            ...     df.write_parquet(parquet_file)

    Notes:
        - All output directories are automatically created by the workflow
        - Use pathlib.Path methods for file operations (write_text, write_bytes, etc.)
        - Create subdirectories as needed with Path.mkdir(exist_ok=True)
        - Ensure file names are valid across platforms (avoid special characters: / \\ : * ? " < > |)
        - Use appropriate file extensions for proper type detection (.csv, .json, .png, etc.)
        - Files in struct/ and meta/ are automatically registered in dataset metadata
        - SmartTable mode provides row-specific data via smarttable_row_data
        - Check Path.exists() and handle None for optional paths (temp, invoice_patch, attachment)

    See Also:
        - RdeInputDirPaths: Input path structure for source data
        - RdeDatasetPaths: Unified view of input and output paths
        - workflows.run: Main workflow function that provides these paths
        - Config: Configuration controlling save_raw, save_thumbnail_image, and extended_mode
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
    smarttable_row_data: dict[str, Any] | None = None
    temp: Path | None = None
    invoice_patch: Path | None = None
    attachment: Path | None = None


@dataclass(slots=True)
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
    def smarttable_row_data(self) -> dict[str, Any] | None:
        """Return parsed SmartTable row data as dictionary.

        Returns:
            Dictionary containing the row data with column names as keys,
            or None if not in SmartTable mode or data not available.

        Example:
            >>> paths = RdeDatasetPaths(input_paths, output_paths)
            >>> row_data = paths.smarttable_row_data
            >>> if row_data:
            ...     sample_name = row_data.get("sample/name", "")
            ...     data_name = row_data.get("basic/dataName", "")
        """
        return self.output_paths.smarttable_row_data

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
        return self.output_paths.invoice_org

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


@dataclass(slots=True)
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
