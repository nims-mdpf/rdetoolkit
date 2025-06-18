"""Invoice initialization processors."""

from __future__ import annotations

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.invoicefile import ExcelInvoiceFile, InvoiceFile, SmartTableFile
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.fileops import writef_json

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
            emsg = f"Invalid index format: {index}. Expected numeric string."
            raise ValueError(emsg) from e


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
        if mode_lower == "excelinvoice":
            return ExcelInvoiceInitializer()
        emsg = f"Unsupported mode for invoice initialization: {mode}"
        raise ValueError(emsg)

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


class SmartTableInvoiceInitializer(Processor):
    """Processor for initializing invoice from SmartTable files."""

    def process(self, context: ProcessingContext) -> None:
        """Process SmartTable file and generate invoice.

        Args:
            context: Processing context containing SmartTable file information

        Raises:
            ValueError: If SmartTable file is not provided in context
            StructuredError: If SmartTable processing fails
        """
        logger.debug(f"Processing SmartTable invoice initialization for {context.mode_name}")

        if not context.is_smarttable_mode:
            error_msg = "SmartTable file not provided in processing context"
            raise ValueError(error_msg)

        try:
            smarttable_file = context.smarttable_invoice_file
            st_handler = SmartTableFile(smarttable_file)
            data = st_handler.read_table()
            logger.debug(f"Read SmartTable with {len(data)} rows")

            # Process the row corresponding to the current context index
            # The index corresponds to the row being processed in the current iteration
            row_index = int(context.index)

            if row_index >= len(data):
                error_msg = f"Row index {row_index} out of range. SmartTable has {len(data)} rows."
                raise StructuredError(error_msg)

            # Get extracted files from rawfiles (excluding the CSV file itself)
            extracted_files = None
            if len(context.resource_paths.rawfiles) > 1:
                # First file should be the CSV file, rest are extracted files
                extracted_files = list(context.resource_paths.rawfiles[1:])

            invoice_data = st_handler.map_row_to_invoice(row_index, extracted_files)

            if "basic" not in invoice_data:
                invoice_data["basic"] = {}
            if "custom" not in invoice_data:
                invoice_data["custom"] = {}
            if "sample" not in invoice_data:
                invoice_data["sample"] = {}

            invoice_path = context.invoice_dst_filepath
            invoice_path.parent.mkdir(parents=True, exist_ok=True)

            writef_json(invoice_path, invoice_data)

            logger.debug(f"Successfully generated invoice at {invoice_path}")

        except Exception as e:
            logger.error(f"SmartTable invoice initialization failed: {str(e)}")
            if isinstance(e, StructuredError):
                raise
            error_msg = f"Failed to initialize invoice from SmartTable: {str(e)}"
            raise StructuredError(error_msg) from e

    def get_name(self) -> str:
        """Get the name of this processor."""
        return "SmartTableInvoiceInitializer"
