from _typeshed import Incomplete
from rdetoolkit.exceptions import SkipRemainingProcessorsError as SkipRemainingProcessorsError
from rdetoolkit.processing.context import ProcessingContext as ProcessingContext
from rdetoolkit.processing.pipeline import Processor as Processor
from rdetoolkit.rdelogger import get_logger as get_logger

logger: Incomplete

class SmartTableEarlyExitProcessor(Processor):
    def process(self, context: ProcessingContext) -> None: ...
