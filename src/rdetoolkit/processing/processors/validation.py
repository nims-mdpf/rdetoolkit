"""Validation processors."""

from __future__ import annotations

from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.validation import invoice_validate, metadata_validate

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class MetadataValidator(Processor):
    """Validates metadata.json files."""

    def process(self, context: ProcessingContext) -> None:
        """Validate metadata.json if it exists."""
        if not context.metadata_path.exists():
            logger.debug("metadata.json does not exist, skipping validation")
            return

        try:
            metadata_validate(context.metadata_path)
            logger.debug("Metadata validation completed successfully")
        except Exception as e:
            logger.error(f"Metadata validation failed: {str(e)}")
            raise


class InvoiceValidator(Processor):
    """Validates invoice files against schema."""

    def process(self, context: ProcessingContext) -> None:
        """Validate invoice.json against schema."""
        try:
            invoice_validate(context.invoice_dst_filepath, context.schema_path)
            logger.debug("Invoice validation completed successfully")
        except Exception as e:
            logger.error(f"Invoice validation failed: {str(e)}")
            raise
