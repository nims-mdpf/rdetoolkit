from __future__ import annotations

import re
import shutil
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.impl import compressed_controller
from rdetoolkit.interfaces.filechecker import IInputFileChecker
from rdetoolkit.invoicefile import read_excelinvoice, SmartTableFile
from rdetoolkit.models.rde2types import (
    ExcelInvoicePathList,
    InputFilesGroup,
    OtherFilesPathList,
    RawFiles,
    ZipFilesPathList,
)


class InvoiceChecker(IInputFileChecker):
    """A checker class to determine and parse the invoice mode.

    This class groups and checks invoice files, specifically identifying zip files, Excel invoice files,
    and other types of files.

    Attributes:
        out_dir_temp (Path): Temporary directory for the unpacked content.

    Note:
        For the purpose of this checker, notable files are primarily Excel invoices with a specific naming convention.
    """

    def __init__(self, unpacked_dir_basename: Path):
        self.out_dir_temp = unpacked_dir_basename

    @property
    def checker_type(self) -> str:
        """Return the type identifier for this checker."""
        return "invoice"

    def parse(self, src_dir_input: Path) -> tuple[RawFiles, Path | None]:
        """Parses the source input directory, grouping files based on their type.

        Args:
            src_dir_input (Path): Source directory containing the input files.

        Returns:
            tuple[RawFiles, Optional[Path]]:

                - RawFiles: A list of tuples where each tuple contains file paths grouped as 'other files'.
                - Optional[Path]: This is always None for this implementation.
        """
        input_files = list(src_dir_input.glob("*"))
        zipfiles, _, other_files = self._get_group_by_files(input_files)
        if not isinstance(other_files, list):
            other_files = list(other_files)
        if zipfiles:
            other_files.extend(zipfiles)
        rawfiles = [tuple(other_files)]
        return rawfiles, None

    def _get_group_by_files(self, input_files: list[Path]) -> InputFilesGroup:
        zipfiles = [f for f in input_files if f.suffix.lower() == ".zip"]
        excel_invoice_files = [f for f in input_files if f.suffix.lower() in [".xls", "xlsx"] and f.stem.endswith("_excel_invoice")]
        other_files = [f for f in input_files if f not in zipfiles and f not in excel_invoice_files]
        return zipfiles, excel_invoice_files, other_files


class ExcelInvoiceChecker(IInputFileChecker):
    """A checker class to determine and parse the ExcelInvoice mode.

    This class is used to identify, group, and validate the files in ExcelInvoice mode. The primary focus is on
    determining the presence and validity of ZIP files, Excel Invoice files, and other file types.

    Attributes:
        out_dir_temp (Path): Temporary directory for unpacked content.

    Methods:
        parse(src_dir_input: Path) -> tuple[RawFiles, Optional[Path]]:
            Parse the source input directory, validate the file groups, and return the raw files and the Excel Invoice file.
    """

    def __init__(self, unpacked_dir_basename: Path):
        self.out_dir_temp = unpacked_dir_basename

    @property
    def checker_type(self) -> str:
        """Return the type identifier for this checker."""
        return "excel_invoice"

    def parse(self, src_dir_input: Path) -> tuple[RawFiles, Path | None]:
        """Parse the source input directory, group files by their type, validate the groups, and return the raw files and Excel Invoice file.

        Args:
            src_dir_input (Path): Source directory containing the input files.

        Returns:
            tuple[RawFiles, Optional[Path]]:

                - RawFiles: List of tuples containing paths of raw files.
                - Optional[Path]: Path to the Excel Invoice file.
        """
        input_files = list(src_dir_input.glob("*"))
        zipfiles, excel_invoice_files, other_files = self._get_group_by_files(input_files)
        self._validate_files(zipfiles, excel_invoice_files, other_files)

        rawfiles = self._get_rawfiles(zipfiles[0], excel_invoice_files[0]) if zipfiles else self._get_rawfiles(None, excel_invoice_files[0])

        return rawfiles, excel_invoice_files[0]

    def _get_group_by_files(self, input_files: list[Path]) -> InputFilesGroup:
        zipfiles = [f for f in input_files if f.suffix.lower() == ".zip"]
        excel_invoice_files = [f for f in input_files if f.suffix.lower() in [".xls", ".xlsx"] and f.stem.endswith("_excel_invoice")]
        other_files = [f for f in input_files if f not in zipfiles and f not in excel_invoice_files]
        return zipfiles, excel_invoice_files, other_files

    def _get_rawfiles(self, zipfile: Path | None, excel_invoice_file: Path) -> list[tuple[Path, ...]]:
        df_excel_invoice, _, _ = read_excelinvoice(excel_invoice_file)
        original_sort_items = df_excel_invoice.iloc[:, 0].to_list()
        if zipfile is None:
            return [() for _ in range(len(df_excel_invoice["basic/dataName"]))]

        archive_parser = compressed_controller.parse_compressedfile_mode(df_excel_invoice)
        _parse = archive_parser.read(zipfile, self.out_dir_temp)

        # When storing the same filename in all tiles, fill the values with
        # the same file so that the number of decompressed files matches
        # the number of "filename" columns in the data frame.
        if len(_parse) == 1 and len(_parse) != len(df_excel_invoice[df_excel_invoice.columns[0]]):
            return sorted(
                [_parse[0] for _ in df_excel_invoice[df_excel_invoice.columns[0]]],
                key=lambda paths: self.get_index(paths[0], original_sort_items),
            )
        if len(_parse) == len(df_excel_invoice[df_excel_invoice.columns[0]]):
            return sorted(_parse, key=lambda paths: self.get_index(paths[0], original_sort_items))
        emsg = "Error! The input file and the description in the ExcelInvoice are not consistent."
        raise StructuredError(emsg)

    def get_index(self, paths: Path, sort_items: Sequence) -> int:
        """Retrieves the index of the `divided` folder.

        Args:
            paths (pathlib.Path): Directory path of the raw files.
            sort_items (Sequence): A list of files sorted in the order described in the Excel invoice.

        Returns:
            int: The index number.
        """
        for idx, item in enumerate(sort_items):
            if item in paths.parts:
                return idx
        return len(sort_items)

    def _validate_files(self, zipfiles: ZipFilesPathList, excel_invoice_files: ExcelInvoicePathList, other_files: OtherFilesPathList) -> None:
        self._detect_invalid_zipfiles(zipfiles)
        self._detect_invalid_excel_invoice_files(excel_invoice_files)
        self._detect_invalid_other_files(other_files)

    def _detect_invalid_zipfiles(self, zipfiles: ZipFilesPathList) -> None:
        if len(zipfiles) > 1:
            emsg = "ERROR: more than 1 zipped input files"
            raise StructuredError(emsg)

    def _detect_invalid_excel_invoice_files(self, excel_invoice_files: ExcelInvoicePathList) -> None:
        if len(excel_invoice_files) > 1:
            emsg = f"ERROR: more than 1 excelinvoice file list. file num: {len(excel_invoice_files)}"
            raise StructuredError(emsg)

    def _detect_invalid_other_files(self, other_files: OtherFilesPathList) -> None:
        if len(other_files) > 0:
            emsg = "ERROR: input file should be EXCEL or ZIP file"
            raise StructuredError(emsg)


class RDEFormatChecker(IInputFileChecker):
    """A checker class to identify and parse the RDE Format.

    This class is designed to handle files in the RDE Format. It checks the presence of ZIP files,
    unpacks them, and retrieves raw files from the unpacked content.

    Attributes:
        out_dir_temp (Path): Temporary directory for unpacked content.
    """

    def __init__(self, unpacked_dir_basename: Path):
        self.out_dir_temp = unpacked_dir_basename

    @property
    def checker_type(self) -> str:
        """Return the type identifier for this checker."""
        return "rde_format"

    def parse(self, src_dir_input: Path) -> tuple[RawFiles, Path | None]:
        """Parse the source input directory, identify ZIP files, unpack the ZIP file, and return the raw files.

        Args:
            src_dir_input (Path): Source directory containing the input files.

        Returns:
            tuple[RawFiles, Optional[Path]]:

                - RawFiles: List of tuples containing paths of raw files.
                - Optional[Path]: This will always return None for this implementation.
        """
        input_files = list(src_dir_input.glob("*"))
        zipfiles = self._get_zipfiles(input_files)
        if len(zipfiles) != 1:
            emsg = "ERROR: no zipped input files"
            raise StructuredError(emsg)
        unpacked_files = self._unpacked(zipfiles[0], self.out_dir_temp)
        _rawfiles = self._get_rawfiles(unpacked_files)
        return _rawfiles, None

    def _get_zipfiles(self, input_files: list[Path]) -> ZipFilesPathList:
        return [f for f in input_files if f.suffix.lower() == ".zip"]

    def _unpacked(self, zipfile: Path, target_dir: Path) -> list[Path]:
        shutil.unpack_archive(zipfile, self.out_dir_temp)
        return [f for f in target_dir.glob("**/*") if f.is_file()]

    def _get_rawfiles(self, unpacked_files: list[Path]) -> RawFiles:
        _rdefmt_file_groups = defaultdict(list)
        for f in unpacked_files:
            match = re.search(r"/(\d{4})/", str(f))
            if match:
                idx_folder_num = int(match.group(1))
                _rdefmt_file_groups[idx_folder_num].append(f)
            else:
                _rdefmt_file_groups[0].append(f)

        if _rdefmt_file_groups:
            return [tuple(_rdefmt_file_groups[key]) for key in sorted(_rdefmt_file_groups.keys())]
        return [()]


class MultiFileChecker(IInputFileChecker):
    """A checker class to identify and parse the MultiFile mode.

    This class is designed to handle multiple file modes. It checks the files in the source input
    directory, groups them, and retrieves the raw files.

    Attributes:
        out_dir_temp (Path): Temporary directory used for certain operations.
    """

    def __init__(self, unpacked_dir_basename: Path):
        self.out_dir_temp = unpacked_dir_basename

    @property
    def checker_type(self) -> str:
        """Return the type identifier for this checker."""
        return "multifile"

    def parse(self, src_dir_input: Path) -> tuple[RawFiles, Path | None]:
        """Parse the source input directory, group ZIP files and other files, and return the raw files.

        Args:
            src_dir_input (Path): Source directory containing the input files.

        Returns:
            tuple[RawFiles, Optional[Path]]:

                - RawFiles: List of tuples containing paths of raw files.
                - Optional[Path]: This will always return None for this implementation.
        """
        input_files = list(src_dir_input.glob("*"))
        other_files = self._get_group_by_files(input_files)
        _rawfiles: list[tuple[Path, ...]] = [(f,) for f in other_files]
        return sorted(_rawfiles, key=lambda path: str(path)), None

    def _get_group_by_files(self, input_files: list[Path]) -> OtherFilesPathList:
        excel_invoice_files = [f for f in input_files if f.suffix.lower() in [".xls", "xlsx"] and f.stem.endswith("_excel_invoice")]
        return [f for f in input_files if f not in excel_invoice_files]

    def _unpacked(self, zipfile: Path, target_dir: Path) -> list[Path]:
        shutil.unpack_archive(zipfile, self.out_dir_temp)
        return [f for f in target_dir.glob("**/*") if f.is_file()]


class SmartTableChecker(IInputFileChecker):
    """A checker class to determine and parse the SmartTable invoice mode.

    This class handles SmartTable files (Excel/CSV/TSV) and optionally zip files,
    processing them for metadata extraction and invoice generation.

    Attributes:
        out_dir_temp (Path): Temporary directory for the unpacked content.
    """

    def __init__(self, unpacked_dir_basename: Path, save_table_file: bool = False):
        self.out_dir_temp = unpacked_dir_basename
        self.save_table_file = save_table_file

    @property
    def checker_type(self) -> str:
        """Return the type identifier for this checker."""
        return "smarttable"

    def parse(self, src_dir_input: Path) -> tuple[RawFiles, Path | None]:
        """Parses the source input directory for SmartTable files and zip files.

        Creates individual CSV files for each SmartTable row and maps them to related files.

        Args:
            src_dir_input (Path): Source directory containing the input files.

        Returns:
            tuple[RawFiles, Path | None]:
                - RawFiles: A list of tuples where each tuple contains (csv_file, related_files...)
                - Path | None: Path to the SmartTable file if found, otherwise None.

        Raises:
            StructuredError: If no SmartTable files are found or if multiple SmartTable files are present.
        """
        input_files = list(src_dir_input.glob("*"))

        # Find SmartTable files
        smarttable_files = [
            f for f in input_files
            if (f.name.startswith("smarttable_") and f.suffix.lower() in [".xlsx", ".csv", ".tsv"])
        ]

        if not smarttable_files:
            error_msg = "No SmartTable files found. Files must start with 'smarttable_' and have .xlsx, .csv, or .tsv extension."
            raise StructuredError(error_msg)

        if len(smarttable_files) > 1:
            error_msg = f"Multiple SmartTable files found: {[f.name for f in smarttable_files]}. Only one SmartTable file is allowed."
            raise StructuredError(error_msg)

        smarttable_file = smarttable_files[0]

        # Process zip files if present
        extracted_files = None
        zip_files = [f for f in input_files if f.suffix.lower() == ".zip"]
        if zip_files:
            extracted_files = []
            for zip_file in zip_files:
                extracted_files.extend(self._unpacked_smarttable(zip_file))

        # Generate CSV files for each row with file mapping
        st_handler = SmartTableFile(smarttable_file)
        csv_file_mappings = st_handler.generate_row_csvs_with_file_mapping(
            self.out_dir_temp, extracted_files,
        )

        # Convert to RawFiles format: each mapping becomes a tuple
        raw_files = []

        # First entry: SmartTable file only (if save_table_file is True)
        if self.save_table_file:
            raw_files.append((smarttable_file,))

        # Subsequent entries: Each CSV file with its related files
        for csv_path, related_files in csv_file_mappings:
            raw_files.append((csv_path,) + related_files)

        return raw_files, smarttable_file

    def _unpacked_smarttable(self, zipfile: Path) -> list[Path]:
        """Extract zip file to temporary directory.

        Args:
            zipfile (Path): Path to the zip file to extract.

        Returns:
            list[Path]: List of extracted file paths.
        """
        shutil.unpack_archive(zipfile, self.out_dir_temp)
        return [f for f in self.out_dir_temp.glob("**/*") if f.is_file()]
