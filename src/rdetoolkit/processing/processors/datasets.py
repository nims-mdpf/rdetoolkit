"""Dataset processing processor."""

from __future__ import annotations

from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class DatasetRunner(Processor):
    """Executes custom dataset processing functions."""

    def process(self, context: ProcessingContext) -> None:
        """Run custom dataset processing function if provided."""
        if context.datasets_function is None:
            logger.debug("No dataset processing function provided, skipping")
            return

        try:
            logger.debug("Executing custom dataset processing function")
            context.datasets_function(context.srcpaths, context.resource_paths)
            logger.debug("Custom dataset processing completed successfully")
        except Exception as e:
            logger.error(f"Custom dataset processing failed: {str(e)}")
            raise
