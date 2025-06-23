from _typeshed import Incomplete
from rdetoolkit.processing.context import ProcessingContext as ProcessingContext
from rdetoolkit.processing.pipeline import Processor as Processor
from rdetoolkit.rdelogger import get_logger as get_logger

logger: Incomplete

class FileCopier(Processor):
    def process(self, context: ProcessingContext) -> None: ...

class RDEFormatFileCopier(Processor):
    def process(self, context: ProcessingContext) -> None: ...

class SmartTableFileCopier(Processor):
    def process(self, context: ProcessingContext) -> None: ...
