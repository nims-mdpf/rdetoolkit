"""Processor implementations for the processing pipeline."""

from .datasets import DatasetRunner
from .descriptions import DescriptionUpdater
from .files import FileCopier, RDEFormatFileCopier, SmartTableFileCopier
from .invoice import (
    StandardInvoiceInitializer,
    ExcelInvoiceInitializer,
    SmartTableInvoiceInitializer,
    InvoiceInitializerFactory,
    # Backward compatibility aliases
    InvoiceHandler,
    ExcelInvoiceHandler,
)
from .thumbnails import ThumbnailGenerator
from .validation import InvoiceValidator, MetadataValidator
from .variables import VariableApplier

__all__ = [
    "DatasetRunner",
    "DescriptionUpdater",
    "StandardInvoiceInitializer",
    "ExcelInvoiceInitializer",
    "SmartTableInvoiceInitializer",
    "InvoiceInitializerFactory",
    "FileCopier",
    "InvoiceValidator",
    "MetadataValidator",
    "RDEFormatFileCopier",
    "SmartTableFileCopier",
    "ThumbnailGenerator",
    "VariableApplier",
    # Backward compatibility aliases
    "InvoiceHandler",
    "ExcelInvoiceHandler",
]
