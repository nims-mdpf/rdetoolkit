"""Factory for creating predefined processing pipelines."""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum

from rdetoolkit.processing.pipeline import Pipeline
from rdetoolkit.processing.processors import (
    DatasetRunner,
    DescriptionUpdater,
    StandardInvoiceInitializer,
    ExcelInvoiceInitializer,
    SmartTableInvoiceInitializer,
    FileCopier,
    InvoiceValidator,
    MetadataValidator,
    RDEFormatFileCopier,
    SmartTableFileCopier,
    ThumbnailGenerator,
    VariableApplier,
)
from rdetoolkit.processing.processors.smarttable_early_exit import SmartTableEarlyExitProcessor


class ProcessingMode(Enum):
    """Enumeration of supported processing modes."""
    RDEFORMAT = "rdeformat"
    MULTIDATATILE = "multidatatile"
    EXCELINVOICE = "excelinvoice"
    INVOICE = "invoice"
    SMARTTABLEINVOICE = "smarttableinvoice"


class PipelineBuilder(ABC):
    """Abstract base class for pipeline builders."""

    @abstractmethod
    def build(self) -> Pipeline:
        """Build and return a configured pipeline."""
        ...

    def _create_base_pipeline(self) -> Pipeline:
        """Create a base pipeline with common processors."""
        return Pipeline()


class RDEFormatPipelineBuilder(PipelineBuilder):
    """Builder for RDEFormat mode pipelines."""

    def build(self) -> Pipeline:
        """Build RDEFormat pipeline."""
        return (self._create_base_pipeline()
                .add(StandardInvoiceInitializer())
                .add(RDEFormatFileCopier())
                .add(DatasetRunner())
                .add(ThumbnailGenerator())
                .add(DescriptionUpdater())
                .add(MetadataValidator())
                .add(InvoiceValidator()))


class MultiFilePipelineBuilder(PipelineBuilder):
    """Builder for MultiFile mode pipelines."""

    def build(self) -> Pipeline:
        """Build MultiFile pipeline."""
        return (self._create_base_pipeline()
                .add(StandardInvoiceInitializer())
                .add(FileCopier())
                .add(DatasetRunner())
                .add(VariableApplier())
                .add(ThumbnailGenerator())
                .add(DescriptionUpdater())
                .add(MetadataValidator())
                .add(InvoiceValidator()))


class ExcelInvoicePipelineBuilder(PipelineBuilder):
    """Builder for ExcelInvoice mode pipelines."""

    def build(self) -> Pipeline:
        """Build ExcelInvoice pipeline."""
        return (self._create_base_pipeline()
                .add(ExcelInvoiceInitializer())
                .add(FileCopier())
                .add(DatasetRunner())
                .add(VariableApplier())
                .add(ThumbnailGenerator())
                .add(DescriptionUpdater())
                .add(MetadataValidator())
                .add(InvoiceValidator()))


class InvoicePipelineBuilder(PipelineBuilder):
    """Builder for Invoice mode pipelines."""

    def build(self) -> Pipeline:
        """Build Invoice pipeline."""
        return (self._create_base_pipeline()
                .add(FileCopier())
                .add(DatasetRunner())
                .add(ThumbnailGenerator())
                .add(VariableApplier())
                .add(DescriptionUpdater())
                .add(MetadataValidator())
                .add(InvoiceValidator()))


class SmartTableInvoicePipelineBuilder(PipelineBuilder):
    """Builder for SmartTableInvoice mode pipelines."""

    def build(self) -> Pipeline:
        """Build SmartTableInvoice pipeline."""
        return (self._create_base_pipeline()
                .add(SmartTableEarlyExitProcessor())
                .add(SmartTableInvoiceInitializer())
                .add(SmartTableFileCopier())
                .add(DatasetRunner())
                .add(ThumbnailGenerator())
                .add(VariableApplier())
                .add(DescriptionUpdater())
                .add(MetadataValidator())
                .add(InvoiceValidator()))


class PipelineFactory:
    """Factory for creating predefined processing pipelines with Pythonic design."""

    _builders: dict[ProcessingMode, type[PipelineBuilder]] = {
        ProcessingMode.RDEFORMAT: RDEFormatPipelineBuilder,
        ProcessingMode.MULTIDATATILE: MultiFilePipelineBuilder,
        ProcessingMode.EXCELINVOICE: ExcelInvoicePipelineBuilder,
        ProcessingMode.INVOICE: InvoicePipelineBuilder,
        ProcessingMode.SMARTTABLEINVOICE: SmartTableInvoicePipelineBuilder,
    }

    @classmethod
    def create_pipeline(cls, mode: str | ProcessingMode) -> Pipeline:
        """Create a pipeline for the specified mode.

        Args:
            mode: Processing mode (string or ProcessingMode enum)

        Returns:
            Pipeline configured for the specified mode

        Raises:
            ValueError: If mode is not supported
        """
        if isinstance(mode, str):
            try:
                mode = ProcessingMode(mode.lower())
            except ValueError as e:
                supported_modes = [m.value for m in ProcessingMode]
                emsg = f"Unsupported mode: {mode}. Supported modes: {supported_modes}"
                raise ValueError(emsg) from e

        builder_class = cls._builders.get(mode)
        if not builder_class:
            emsg = f"No builder found for mode: {mode}"
            raise ValueError(emsg)

        builder = builder_class()
        return builder.build()

    @classmethod
    def get_supported_modes(cls) -> list[str]:
        """Get list of supported mode names.

        Returns:
            List of supported mode strings
        """
        return [mode.value for mode in ProcessingMode]

    # Backward compatibility methods
    @staticmethod
    def create_rdeformat_pipeline() -> Pipeline:
        """Create a pipeline for RDEFormat mode processing.

        Returns:
            Pipeline configured for RDEFormat mode
        """
        return PipelineFactory.create_pipeline(ProcessingMode.RDEFORMAT)

    @staticmethod
    def create_multifile_pipeline() -> Pipeline:
        """Create a pipeline for MultiFile mode processing.

        Returns:
            Pipeline configured for MultiFile mode
        """
        return PipelineFactory.create_pipeline(ProcessingMode.MULTIDATATILE)

    @staticmethod
    def create_excel_pipeline() -> Pipeline:
        """Create a pipeline for ExcelInvoice mode processing.

        Returns:
            Pipeline configured for ExcelInvoice mode
        """
        return PipelineFactory.create_pipeline(ProcessingMode.EXCELINVOICE)

    @staticmethod
    def create_invoice_pipeline() -> Pipeline:
        """Create a pipeline for Invoice mode processing.

        Returns:
            Pipeline configured for Invoice mode
        """
        return PipelineFactory.create_pipeline(ProcessingMode.INVOICE)

    @staticmethod
    def create_smarttable_invoice_pipeline() -> Pipeline:
        """Create a pipeline for SmartTableInvoice mode processing.

        Returns:
            Pipeline configured for SmartTableInvoice mode
        """
        return PipelineFactory.create_pipeline(ProcessingMode.SMARTTABLEINVOICE)
