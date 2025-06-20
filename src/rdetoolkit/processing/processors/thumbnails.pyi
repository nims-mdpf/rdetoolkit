from _typeshed import Incomplete as Incomplete
from rdetoolkit.processing.context import ProcessingContext as ProcessingContext
from rdetoolkit.processing.pipeline import Processor as Processor

logger: Incomplete

class ThumbnailGenerator(Processor):
    def process(self, context: ProcessingContext) -> None: ...
