"""Description updating processor."""

from __future__ import annotations

import contextlib

from rdetoolkit.invoicefile import update_description_with_features
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class DescriptionUpdater(Processor):
    """Updates descriptions with feature information."""

    def process(self, context: ProcessingContext) -> None:
        """Update descriptions with features, ignoring any errors."""
        try:
            logger.debug("Updating descriptions with features")

            # Use contextlib.suppress to ignore any exceptions during this step
            # This matches the behavior in the original code
            with contextlib.suppress(Exception):
                update_description_with_features(
                    context.resource_paths,
                    context.invoice_dst_filepath,
                    context.metadata_def_path,
                )

            logger.debug("Description update completed (errors suppressed)")

        except Exception as e:
            # This should never be reached due to contextlib.suppress above,
            # but keeping it for safety
            logger.warning(f"Description update failed: {str(e)}")
