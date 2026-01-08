"""Processors related to structured invoice handling."""

from __future__ import annotations

import shutil
from pathlib import Path

from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)


class StructuredInvoiceSaver(Processor):
    """Copies invoice.json to the structured directory when configured."""

    def process(self, context: ProcessingContext) -> None:
        """Persist invoice.json to structured output based on configuration.

        Args:
            context: Processing context containing configuration and paths.

        Raises:
            FileNotFoundError: If the original invoice file is missing while the
                structured save option is enabled.
        """
        system_settings = getattr(context.srcpaths.config, "system", None)
        if system_settings is None:
            logger.debug("No system settings found; skipping structured invoice save")
            return

        if not getattr(system_settings, "save_invoice_to_structured", False):
            logger.debug("save_invoice_to_structured disabled; skipping")
            return

        invoice_source = context.resource_paths.invoice_org
        if not invoice_source.exists():
            emsg = f"Original invoice not found for structured export: {invoice_source}"
            logger.error(emsg)
            raise FileNotFoundError(emsg)

        structured_dir = context.resource_paths.struct
        structured_dir.mkdir(parents=True, exist_ok=True)
        destination = structured_dir / "invoice.json"

        # Avoid redundant copies when the paths already align.
        if _paths_identical(invoice_source, destination):
            logger.debug("Invoice source and destination are identical; skipping copy")
            return

        shutil.copy2(invoice_source, destination)
        logger.info("Stored invoice.json at %s from %s", destination, invoice_source)


def _paths_identical(source: Path, dest: Path) -> bool:
    """Return True when the two paths point to the same file."""
    if source == dest:
        return True

    try:
        return source.exists() and dest.exists() and source.samefile(dest)
    except FileNotFoundError:
        return False
