"""Magic variable processing."""

from __future__ import annotations

from rdetoolkit.invoicefile import apply_magic_variable
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class VariableApplier(Processor):
    """Applies magic variables to invoice files."""

    def process(self, context: ProcessingContext) -> None:
        """Apply magic variables if enabled."""
        if not context.srcpaths.config.system.magic_variable:
            logger.debug("Magic variables disabled, skipping")
            return

        if not context.resource_paths.rawfiles:
            logger.debug("No raw files available for variable replacement")
            return

        try:
            # Apply magic variable replacement using the first raw file
            result = apply_magic_variable(
                context.invoice_dst_filepath,
                context.resource_paths.rawfiles[0],
                save_filepath=context.invoice_dst_filepath,
            )

            if result:
                logger.debug("Magic variable replacement completed successfully")
            else:
                logger.debug("No magic variables found for replacement")
        except Exception as e:
            logger.error(f"Magic variable replacement failed: {str(e)}")
            raise
