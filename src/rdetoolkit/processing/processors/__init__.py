"""Processor implementations for the processing pipeline."""

from .datasets import DatasetRunner
from .descriptions import DescriptionUpdater
from .files import FileCopier, RDEFormatFileCopier
from .invoice import (
    StandardInvoiceInitializer,
    ExcelInvoiceInitializer,
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
    "InvoiceInitializerFactory",
    "FileCopier",
    "InvoiceValidator",
    "MetadataValidator",
    "RDEFormatFileCopier",
    "ThumbnailGenerator",
    "VariableApplier",
    # Backward compatibility aliases
    "InvoiceHandler",
    "ExcelInvoiceHandler",
]
