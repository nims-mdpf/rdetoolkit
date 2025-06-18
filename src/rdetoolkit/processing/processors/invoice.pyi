from _typeshed import Incomplete as Incomplete
from rdetoolkit.processing.context import ProcessingContext as ProcessingContext
from rdetoolkit.processing.pipeline import Processor as Processor

logger: Incomplete

class StandardInvoiceInitializer(Processor):
    def process(self, context: ProcessingContext) -> None: ...

class ExcelInvoiceInitializer(Processor):
    def process(self, context: ProcessingContext) -> None: ...

class InvoiceInitializerFactory:
    @staticmethod
    def create(mode: str) -> Processor: ...
    @staticmethod
    def get_supported_modes() -> tuple[str, ...]: ...
InvoiceHandler = StandardInvoiceInitializer
ExcelInvoiceHandler = ExcelInvoiceInitializer

class SmartTableInvoiceInitializer(Processor):
    def process(self, context: ProcessingContext) -> None: ...
    def get_name(self) -> str: ...
