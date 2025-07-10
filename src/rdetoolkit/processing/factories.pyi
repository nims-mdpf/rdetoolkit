import abc
from abc import ABC, abstractmethod
from enum import Enum
from rdetoolkit.processing.pipeline import Pipeline as Pipeline
from rdetoolkit.processing.processors import DatasetRunner as DatasetRunner, DescriptionUpdater as DescriptionUpdater, ExcelInvoiceInitializer as ExcelInvoiceInitializer, FileCopier as FileCopier, InvoiceValidator as InvoiceValidator, MetadataValidator as MetadataValidator, RDEFormatFileCopier as RDEFormatFileCopier, SmartTableFileCopier as SmartTableFileCopier, SmartTableInvoiceInitializer as SmartTableInvoiceInitializer, StandardInvoiceInitializer as StandardInvoiceInitializer, ThumbnailGenerator as ThumbnailGenerator, VariableApplier as VariableApplier
from rdetoolkit.processing.processors.smarttable_early_exit import SmartTableEarlyExitProcessor as SmartTableEarlyExitProcessor

class ProcessingMode(Enum):
    RDEFORMAT = 'rdeformat'
    MULTIDATATILE = 'multidatatile'
    EXCELINVOICE = 'excelinvoice'
    INVOICE = 'invoice'
    SMARTTABLEINVOICE = 'smarttableinvoice'

class PipelineBuilder(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    def build(self) -> Pipeline: ...

class RDEFormatPipelineBuilder(PipelineBuilder):
    def build(self) -> Pipeline: ...

class MultiFilePipelineBuilder(PipelineBuilder):
    def build(self) -> Pipeline: ...

class ExcelInvoicePipelineBuilder(PipelineBuilder):
    def build(self) -> Pipeline: ...

class InvoicePipelineBuilder(PipelineBuilder):
    def build(self) -> Pipeline: ...

class SmartTableInvoicePipelineBuilder(PipelineBuilder):
    def build(self) -> Pipeline: ...

class PipelineFactory:
    @classmethod
    def create_pipeline(cls, mode: str | ProcessingMode) -> Pipeline: ...
    @classmethod
    def get_supported_modes(cls) -> list[str]: ...
    @staticmethod
    def create_rdeformat_pipeline() -> Pipeline: ...
    @staticmethod
    def create_multifile_pipeline() -> Pipeline: ...
    @staticmethod
    def create_excel_pipeline() -> Pipeline: ...
    @staticmethod
    def create_invoice_pipeline() -> Pipeline: ...
    @staticmethod
    def create_smarttable_invoice_pipeline() -> Pipeline: ...
