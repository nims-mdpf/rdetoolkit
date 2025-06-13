"""Invoice initialization processors."""

from __future__ import annotations

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.invoicefile import ExcelInvoiceFile, InvoiceFile
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class StandardInvoiceInitializer(Processor):
    """Initializes invoice file by copying from original invoice.

    Used for RDEFormat, MultiFile, and Invoice modes.
    """

    def process(self, context: ProcessingContext) -> None:
        """Initialize invoice file by copying from original."""
        try:
            invoice_dst_filepath = context.invoice_dst_filepath

            logger.debug(f"Initializing invoice file: {invoice_dst_filepath}")

            # Ensure destination directory exists
            invoice_dst_filepath.parent.mkdir(parents=True, exist_ok=True)

            # Copy original invoice to destination
            InvoiceFile.copy_original_invoice(
                context.resource_paths.invoice_org,
                invoice_dst_filepath,
            )

            logger.debug("Standard invoice initialization completed successfully")

        except Exception as e:
            logger.error(f"Standard invoice initialization failed: {str(e)}")
            raise


class ExcelInvoiceInitializer(Processor):
    """Initializes invoice file from Excel invoice file.

    Used for ExcelInvoice mode.
    """

    def process(self, context: ProcessingContext) -> None:
        """Initialize invoice file from Excel invoice."""
        if context.excel_file is None:
            emsg = "Excel file path is required for ExcelInvoice mode"
            raise ValueError(emsg)
        try:
            logger.debug(f"Initializing invoice from Excel file: {context.excel_file}")

            # Ensure destination directory exists
            context.invoice_dst_filepath.parent.mkdir(parents=True, exist_ok=True)

            # Create Excel invoice handler
            excel_invoice = ExcelInvoiceFile(context.excel_file)

            # Convert index to integer for Excel processing
            idx = self._parse_index(context.index)

            # Overwrite invoice using Excel data
            excel_invoice.overwrite(
                context.resource_paths.invoice_org,
                context.invoice_dst_filepath,
                context.resource_paths.invoice_schema_json,
                idx,
            )

            logger.debug("Excel invoice initialization completed successfully")

        except StructuredError:
            # Re-raise StructuredError as-is
            logger.error("Excel invoice initialization failed with structured error")
            raise
        except Exception as e:
            # Wrap other exceptions in StructuredError
            error_msg = f"Failed to generate invoice file for data {context.index}"
            logger.error(f"Excel invoice initialization failed: {error_msg}")
            raise StructuredError(error_msg, eobj=e) from e

    def _parse_index(self, index: str) -> int:
        """Parse string index to integer.

        Args:
            index: String index (e.g., "0001")

        Returns:
            Integer index

        Raises:
            ValueError: If index cannot be parsed as integer
        """
        try:
            return int(index)
        except ValueError as e:
            raise ValueError(f"Invalid index format: {index}. Expected numeric string.") from e


class InvoiceInitializerFactory:
    """Factory for creating appropriate invoice initializer based on mode."""

    @staticmethod
    def create(mode: str) -> Processor:
        """Create appropriate invoice initializer for the given mode.

        Args:
            mode: Processing mode name

        Returns:
            Appropriate invoice initializer processor

        Raises:
            ValueError: If mode is not supported
        """
        mode_lower = mode.lower()

        if mode_lower in ("rdeformat", "multidatatile", "invoice"):
            return StandardInvoiceInitializer()
        elif mode_lower == "excelinvoice":
            return ExcelInvoiceInitializer()
        else:
            raise ValueError(f"Unsupported mode for invoice initialization: {mode}")

    @staticmethod
    def get_supported_modes() -> tuple[str, ...]:
        """Get list of supported modes.

        Returns:
            Tuple of supported mode names
        """
        return ("rdeformat", "multidatatile", "invoice", "excelinvoice")


# Backward compatibility aliases
InvoiceHandler = StandardInvoiceInitializer
ExcelInvoiceHandler = ExcelInvoiceInitializer
