from _typeshed import Incomplete
from rdetoolkit.processing.context import ProcessingContext as ProcessingContext
from rdetoolkit.processing.pipeline import Processor as Processor
from rdetoolkit.rdelogger import get_logger as get_logger

logger: Incomplete

class StructuredInvoiceSaver(Processor):
    def process(self, context: ProcessingContext) -> None: ...
