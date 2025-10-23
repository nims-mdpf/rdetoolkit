"""Processing context for mode processing operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from rdetoolkit.models.rde2types import DatasetCallback, RdeDatasetPaths, RdeInputDirPaths, RdeOutputResourcePath


@dataclass
class ProcessingContext:
    """Context for mode processing operations.

    This class encapsulates all the information needed for processing
    operations in different modes (RDEFormat, MultiFile, etc.). For the
    dataset callback it exposes both the legacy attributes (`srcpaths`,
    `resource_paths`) and the unified :class:`RdeDatasetPaths` view via the
    :pyattr:`dataset_paths` property.
    """

    index: str
    srcpaths: RdeInputDirPaths
    resource_paths: RdeOutputResourcePath
    datasets_function: DatasetCallback | None
    mode_name: str
    excel_file: Path | None = None
    excel_index: int | None = None
    smarttable_file: Path | None = None

    @property
    def dataset_paths(self) -> RdeDatasetPaths:
        """Unified dataset paths view for single-argument callbacks."""
        return RdeDatasetPaths(self.srcpaths, self.resource_paths)

    @property
    def basedir(self) -> str:
        """Get the base directory for the processing operation."""
        if len(self.resource_paths.rawfiles) > 0:
            return str(self.resource_paths.rawfiles[0].parent)
        return ""

    @property
    def invoice_dst_filepath(self) -> Path:
        """Get the destination invoice file path."""
        return self.resource_paths.invoice.joinpath("invoice.json")

    @property
    def schema_path(self) -> Path:
        """Get the invoice schema file path."""
        return self.srcpaths.tasksupport.joinpath("invoice.schema.json")

    @property
    def metadata_def_path(self) -> Path:
        """Get the metadata definition file path."""
        return self.srcpaths.tasksupport.joinpath("metadata-def.json")

    @property
    def metadata_path(self) -> Path:
        """Get the metadata.json file path."""
        return self.resource_paths.meta.joinpath("metadata.json")

    @property
    def is_excel_mode(self) -> bool:
        """Check if this is Excel invoice processing mode."""
        return self.excel_file is not None and self.excel_index is not None

    @property
    def excel_invoice_file(self) -> Path:
        """Get the Excel invoice file path (for Excel mode only)."""
        if self.excel_file is None:
            error_msg = "Excel file not set for this context"
            raise ValueError(error_msg)
        return self.excel_file

    @property
    def is_smarttable_mode(self) -> bool:
        """Check if this is SmartTable processing mode."""
        return self.smarttable_file is not None

    @property
    def smarttable_invoice_file(self) -> Path:
        """Get the SmartTable file path (for SmartTable mode only)."""
        if self.smarttable_file is None:
            error_msg = "SmartTable file not set for this context"
            raise ValueError(error_msg)
        return self.smarttable_file
