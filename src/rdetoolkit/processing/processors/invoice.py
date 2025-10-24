from __future__ import annotations
from pathlib import Path
from typing import Any

import pandas as pd

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.invoicefile import ExcelInvoiceFile, InvoiceFile
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson
from rdetoolkit.rde2util import castval

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

            schema_dict = readf_json(context.resource_paths.invoice_schema_json)
            invoice_schema_json_data = InvoiceSchemaJson(**schema_dict)

            metadata_updates = self._apply_smarttable_row(
                csv_data,
                context,
                invoice_data,
                invoice_schema_json_data,
            )

            # Ensure required fields are present
            self._ensure_required_fields(invoice_data)

            invoice_path = context.invoice_dst_filepath
            invoice_path.parent.mkdir(parents=True, exist_ok=True)
            writef_json(invoice_path, invoice_data)
            logger.debug(f"Successfully generated invoice at {invoice_path}")

            if metadata_updates:
                self._write_metadata(context, metadata_updates)
                logger.debug(
                    "Updated metadata.json with keys: %s",
                    ", ".join(metadata_updates.keys()),
                )

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

    def _process_mapping_key(self, key: str, value: str, invoice_data: dict[str, Any], invoice_schema_obj: InvoiceSchemaJson) -> None:
        """Process a mapping key and assign the provided value to the appropriate location in the invoice data dictionary.

        Args:
            key (str): Mapping key indicating the target field (e.g., "basic/dataName", "sample/generalAttributes.termId").
            value (str): Value to assign to the specified field.
            invoice_data (dict[str, Any]): Invoice data dictionary to update.
            invoice_schema_obj (InvoiceSchemaJson): Schema object used for field validation and lookup.

        Returns:
            None

        """
        if key.startswith("basic/"):
            field = key.replace("basic/", "")
            # schema_value = invoice_schema_obj.find_field(field)
            invoice_data["basic"][field] = value

        elif key.startswith("custom/"):
            field = key.replace("custom/", "")
            schema_value = invoice_schema_obj.find_field(field)
            _fmt = schema_value.get("format", None) if schema_value else None
            _type = schema_value.get("type", None) if schema_value else None
            # If type is not found in schema, use the value as string
            if _type:
                invoice_data["custom"][field] = castval(value, _type, _fmt)
            else:
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
            # meta/ prefix is handled separately for metadata.json generation
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

    def _apply_smarttable_row(
        self,
        csv_data: pd.DataFrame,
        context: ProcessingContext,
        invoice_data: dict[str, Any],
        invoice_schema_json_data: InvoiceSchemaJson,
    ) -> dict[str, dict[str, Any]]:
        """Apply SmartTable row data to invoice and collect metadata updates."""
        metadata_updates: dict[str, dict[str, Any]] = {}
        metadata_def: dict[str, Any] | None = None

        for col in csv_data.columns:
            value = csv_data.iloc[0][col]
            if pd.isna(value) or value == "":
                continue
            if col.startswith("meta/"):
                if not context.metadata_def_path.exists():
                    logger.debug(
                        "Skipping meta column %s because metadata-def.json is missing",
                        col,
                    )
                    continue
                if metadata_def is None:
                    metadata_def = self._load_metadata_definition(context.metadata_def_path)
                meta_key, meta_entry = self._process_meta_mapping(col, value, metadata_def)
                metadata_updates[meta_key] = meta_entry
                continue
            self._process_mapping_key(col, value, invoice_data, invoice_schema_json_data)

        return metadata_updates

    def _load_metadata_definition(self, metadata_def_path: Path) -> dict[str, Any]:
        """Load metadata definitions for SmartTable meta column processing.

        Args:
            metadata_def_path: Path to ``metadata-def.json`` obtained from the processing context.

        Returns:
            Dictionary containing metadata definitions keyed by metadata name.

        Raises:
            StructuredError: If the file is missing or not a JSON object.
        """
        if not metadata_def_path.exists():
            emsg = f"metadata-def.json not found: {metadata_def_path}"
            raise StructuredError(emsg)

        metadata_def = readf_json(metadata_def_path)
        if not isinstance(metadata_def, dict):
            emsg = "metadata-def.json must contain an object at the top level"
            raise StructuredError(emsg)

        return metadata_def

    def _process_meta_mapping(
        self,
        key: str,
        value: str,
        metadata_def: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """Convert a SmartTable meta column into a metadata.json entry.

        Args:
            key: Column name from SmartTable (e.g., ``meta/comment``).
            value: String representation of the value extracted from the CSV row.
            metadata_def: Loaded metadata definition dictionary.

        Returns:
            Tuple of metadata key and the corresponding metadata entry.

        Raises:
            StructuredError: If definitions are missing, unsupported, or type conversion fails.
        """
        meta_key = key.replace("meta/", "", 1)
        definition = metadata_def.get(meta_key)
        if definition is None:
            emsg = f"Metadata definition not found for key: {meta_key}"
            raise StructuredError(emsg)

        if definition.get("variable"):
            emsg = f"Variable metadata is not supported for SmartTable meta mapping: {meta_key}"
            raise StructuredError(emsg)

        schema = definition.get("schema", {})
        meta_type = schema.get("type")
        meta_format = schema.get("format")

        if meta_type and meta_type not in {"string", "number", "integer", "boolean"}:
            emsg = f"Unsupported metadata type for key {meta_key}: {meta_type}"
            raise StructuredError(emsg)

        try:
            converted_value = (
                castval(value, meta_type, meta_format)
                if meta_type
                else value
            )
        except StructuredError as cast_error:
            emsg = f"Failed to cast metadata value for key: {meta_key}"
            raise StructuredError(emsg) from cast_error

        meta_entry: dict[str, Any] = {"value": converted_value}
        unit = definition.get("unit")
        if unit:
            meta_entry["unit"] = unit

        return meta_key, meta_entry

    def _write_metadata(
        self,
        context: ProcessingContext,
        metadata_updates: dict[str, dict[str, Any]],
    ) -> None:
        """Persist metadata.json with collected SmartTable meta values.

        Args:
            context: Current processing context containing destination paths.
            metadata_updates: Mapping of metadata keys to entry dictionaries.
        """
        metadata_path = context.metadata_path
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        metadata_obj = (
            readf_json(metadata_path)
            if metadata_path.exists() else {"constant": {}, "variable": []}
        )

        constant_section = metadata_obj.setdefault("constant", {})
        metadata_obj.setdefault("variable", [])

        constant_section.update(metadata_updates)
        writef_json(metadata_path, metadata_obj)

    def get_name(self) -> str:
        """Get the name of this processor."""
        return "SmartTableInvoiceInitializer"
