"""Invoice initialization processors."""

from __future__ import annotations
from typing import Any

import pandas as pd

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
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
            invoice_dst_filepath.parent.mkdir(parents=True, exist_ok=True)

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
            logger.error("Excel invoice initialization failed with structured error")
            raise
        except Exception as e:
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
            if not context.resource_paths.rawfiles:
                error_msg = "No CSV file found in rawfiles"
                raise StructuredError(error_msg)

            csv_file = context.resource_paths.rawfiles[0]
            logger.debug(f"Processing CSV file: {csv_file}")

            csv_data = pd.read_csv(csv_file, dtype=str)

            # Load original invoice.json to inherit existing values
            invoice_data = {}
            if context.resource_paths.invoice_org.exists():

                invoice_data = readf_json(context.resource_paths.invoice_org)
                logger.debug(f"Loaded original invoice from {context.resource_paths.invoice_org}")
            else:
                # If no original invoice, initialize empty structure
                invoice_data = self._initialize_invoice_data()

            for col in csv_data.columns:
                value = csv_data.iloc[0][col]
                if pd.isna(value) or value == "":
                    continue

                self._process_mapping_key(col, value, invoice_data)

            # Ensure required fields are present
            self._ensure_required_fields(invoice_data)

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

    def _initialize_invoice_data(self) -> dict:
        """Initialize empty invoice data structure."""
        return {
            "basic": {},
            "custom": {},
            "sample": {},
        }

    def _process_mapping_key(self, key: str, value: str, invoice_data: dict[str, Any]) -> None:
        """Process a mapping key and assign value to appropriate location in invoice data.

        Args:
            key: Mapping key (e.g., "basic/dataName", "sample/generalAttributes.termId")
            value: Value to assign
            invoice_data: Invoice data dictionary to update
        """
        if key.startswith("basic/"):
            field = key.replace("basic/", "")
            invoice_data["basic"][field] = value

        elif key.startswith("custom/"):
            field = key.replace("custom/", "")
            invoice_data["custom"][field] = value

        elif key.startswith("sample/generalAttributes."):
            self._process_general_attributes(key, value, invoice_data)

        elif key.startswith("sample/specificAttributes."):
            self._process_specific_attributes(key, value, invoice_data)

        elif key.startswith("sample/"):
            field = key.replace("sample/", "")
            if field == "names":
                # names field should be an array
                invoice_data["sample"][field] = [value]
            else:
                invoice_data["sample"][field] = value

        elif key.startswith("meta/"):
            # meta/ prefix is ignored as per specification
            pass

        elif key.startswith("inputdata"):
            # inputdata columns are handled separately for file mapping
            pass

    def _process_general_attributes(self, key: str, value: str, invoice_data: dict[str, Any]) -> None:
        """Process sample/generalAttributes.<termId> mapping."""
        term_id = key.replace("sample/generalAttributes.", "")
        if "generalAttributes" not in invoice_data["sample"]:
            invoice_data["sample"]["generalAttributes"] = []

        # Find existing entry or create new one
        found = False
        for attr in invoice_data["sample"]["generalAttributes"]:
            if attr.get("termId") == term_id:
                attr["value"] = value
                found = True
                break

        if not found:
            invoice_data["sample"]["generalAttributes"].append({
                "termId": term_id,
                "value": value,
            })

    def _process_specific_attributes(self, key: str, value: str, invoice_data: dict[str, Any]) -> None:
        """Process sample/specificAttributes.<classId>.<termId> mapping."""
        parts = key.replace("sample/specificAttributes.", "").split(".", 1)
        required_parts = 2
        if len(parts) == required_parts:
            class_id, term_id = parts
            if "specificAttributes" not in invoice_data["sample"]:
                invoice_data["sample"]["specificAttributes"] = []

            found = False
            for attr in invoice_data["sample"]["specificAttributes"]:
                if attr.get("classId") == class_id and attr.get("termId") == term_id:
                    attr["value"] = value
                    found = True
                    break

            if not found:
                invoice_data["sample"]["specificAttributes"].append({
                    "classId": class_id,
                    "termId": term_id,
                    "value": value,
                })

    def _ensure_required_fields(self, invoice_data: dict) -> None:
        """Ensure required fields are present in invoice data."""
        if "basic" not in invoice_data:
            invoice_data["basic"] = {}

    def get_name(self) -> str:
        """Get the name of this processor."""
        return "SmartTableInvoiceInitializer"
