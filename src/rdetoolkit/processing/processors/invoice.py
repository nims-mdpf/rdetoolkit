from __future__ import annotations
from pathlib import Path
from typing import Any
import copy

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

    _BASE_INVOICE_CACHE: dict[Path, dict[str, Any]] = {}

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
            csv_file = context.smarttable_rowfile
            if csv_file is None:
                error_msg = "No SmartTable row CSV file found"
                raise StructuredError(error_msg)
            logger.debug(f"Processing CSV file: {csv_file}")

            csv_data = pd.read_csv(csv_file, dtype=str)

            # Load original invoice.json to inherit existing values (cached for multi-row processing)
            invoice_data = self._get_base_invoice_data(context)

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

    @staticmethod
    def _initialize_invoice_data() -> dict[str, Any]:
        """Initialize empty invoice data structure."""
        return {
            "basic": {},
            "custom": {},
            "sample": {},
        }

    @classmethod
    def _get_base_invoice_data(cls, context: ProcessingContext) -> dict[str, Any]:
        """Return a fresh copy of the original invoice data.

        SmartTable processing iterates per-row; we cache the original invoice once so later rows
        are not affected by modifications made during earlier iterations.
        """
        cache_key = context.resource_paths.invoice_org.resolve()
        if cache_key not in cls._BASE_INVOICE_CACHE:
            if cache_key.exists():
                cls._BASE_INVOICE_CACHE[cache_key] = readf_json(cache_key)
                logger.debug(f"Loaded original invoice from {cache_key}")
            else:
                cls._BASE_INVOICE_CACHE[cache_key] = cls._initialize_invoice_data()
                logger.debug("Original invoice not found; using empty invoice template")

        return copy.deepcopy(cls._BASE_INVOICE_CACHE[cache_key])

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

    def _clear_mapping_key(self, key: str, invoice_data: dict[str, Any]) -> None:
        """Clear existing invoice data for the given mapping key to avoid stale inheritance."""
        if key.startswith("basic/"):
            field = key.replace("basic/", "")
            invoice_data.setdefault("basic", {}).pop(field, None)
            return

        if key.startswith("custom/"):
            field = key.replace("custom/", "")
            invoice_data.setdefault("custom", {}).pop(field, None)
            return

        if key.startswith("sample/generalAttributes."):
            term_id = key.replace("sample/generalAttributes.", "")
            sample_section = invoice_data.setdefault("sample", {})
            existing = sample_section.get("generalAttributes") or []
            sample_section["generalAttributes"] = [
                attr for attr in existing if attr.get("termId") != term_id
            ]
            return

        if key.startswith("sample/specificAttributes."):
            parts = key.replace("sample/specificAttributes.", "").split(".", 1)
            required_parts = 2
            if len(parts) == required_parts:
                class_id, term_id = parts
                sample_section = invoice_data.setdefault("sample", {})
                existing = sample_section.get("specificAttributes") or []
                sample_section["specificAttributes"] = [
                    attr
                    for attr in existing
                    if not (
                        attr.get("classId") == class_id
                        and attr.get("termId") == term_id
                    )
                ]
            return

        if key.startswith("sample/"):
            field = key.replace("sample/", "")
            invoice_data.setdefault("sample", {}).pop(field, None)

    def _is_invoice_mapping(self, key: str) -> bool:
        """Return True when the mapping key targets invoice fields (not meta/inputdata)."""
        invoice_prefixes = ("basic/", "custom/", "sample/")
        return key.startswith(invoice_prefixes)

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
                if self._is_invoice_mapping(col):
                    self._clear_mapping_key(col, invoice_data)
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
