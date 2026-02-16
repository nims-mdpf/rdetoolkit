"""Magic variable expansion for invoice files.

This module provides classes and functions for resolving magic variables
(e.g., ${variable_name}) in invoice files using metadata from datasets.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.invoicefile._helpers import MAGIC_VARIABLE_PATTERN, logger

if TYPE_CHECKING:
    from rdetoolkit.models.rde2types import RdeDatasetPaths


class MagicVariableResolver:
    """Resolve and expand supported magic-variable expressions."""

    MIN_INVOICE_FIELD_SEGMENTS = 2
    MIN_METADATA_SEGMENTS = 2

    def __init__(
        self,
        *,
        rawfile_path: Path,
        invoice_source: dict[str, Any],
        metadata_source: dict[str, Any] | None,
    ) -> None:
        self.rawfile_path = rawfile_path
        self.invoice_source = invoice_source
        self.metadata_source = metadata_source

    def expand(self, template: str) -> str:
        """Expand all magic variables present in *template*."""
        result_parts: list[str] = []
        last_end = 0
        skip_pending = False

        for match in MAGIC_VARIABLE_PATTERN.finditer(template):
            literal = template[last_end : match.start()]
            if literal:
                literal = self._trim_redundant_underscore(literal, result_parts, skip_pending)
                result_parts.append(literal)
                skip_pending = False

            expression = match.group(1).strip()
            replacement = self._resolve_expression(expression)
            if replacement is None:
                skip_pending = True
            else:
                result_parts.append(replacement)
                skip_pending = False

            last_end = match.end()

        trailing_literal = template[last_end:]
        if trailing_literal:
            trailing_literal = self._trim_redundant_underscore(trailing_literal, result_parts, skip_pending)
            result_parts.append(trailing_literal)

        return "".join(result_parts)

    def _trim_redundant_underscore(self, literal: str, result_parts: list[str], skip_pending: bool) -> str:
        """Drop leading underscores when a skipped placeholder already supplied one."""
        if skip_pending and literal.startswith("_") and result_parts and result_parts[-1].endswith("_"):
            return literal[1:]
        return literal

    def _resolve_expression(self, expression: str) -> str | None:
        if not expression:
            emsg = "Encountered empty magic variable expression"
            raise StructuredError(emsg)

        segments = expression.split(":")
        prefix = segments[0]

        if prefix == "filename":
            return self.rawfile_path.name
        if prefix == "invoice":
            return self._resolve_invoice_expression(segments[1:], expression)
        if prefix == "metadata":
            return self._resolve_metadata_expression(segments[1:], expression)

        emsg = f"Unsupported magic variable '{expression}'"
        raise StructuredError(emsg)

    def _resolve_invoice_expression(self, segments: list[str], expression: str) -> str | None:
        if not segments:
            emsg = f"Invalid invoice magic variable '{expression}'"
            raise StructuredError(emsg)

        section = segments[0]
        invoice_section = self.invoice_source.get(section)
        if invoice_section is None:
            emsg = f"Invoice section '{section}' not found for magic variable '{expression}'"
            raise StructuredError(emsg)

        if section in {"basic", "custom"}:
            if len(segments) < self.MIN_INVOICE_FIELD_SEGMENTS:
                emsg = f"Magic variable '{expression}' requires a field name"
                raise StructuredError(emsg)
            field = segments[1]
            if not isinstance(invoice_section, dict) or field not in invoice_section:
                emsg = f"Field '{section}.{field}' is missing for magic variable '{expression}'"
                raise StructuredError(emsg)
            value = invoice_section.get(field)
            return self._normalize_scalar(value, expression)

        if section == "sample":
            return self._resolve_sample_expression(segments[1:], expression)

        emsg = f"Unsupported invoice section '{section}' in magic variable '{expression}'"
        raise StructuredError(emsg)

    def _resolve_sample_expression(self, segments: list[str], expression: str) -> str | None:
        if not segments:
            emsg = f"Magic variable '{expression}' must specify a sample field"
            raise StructuredError(emsg)

        sample_section = self.invoice_source.get("sample")
        if sample_section is None:
            emsg = f"Sample information missing in invoice for '{expression}'"
            raise StructuredError(emsg)

        field = segments[0]
        if field != "names":
            emsg = f"Unsupported sample field '{field}' in magic variable '{expression}'"
            raise StructuredError(emsg)

        names = sample_section.get("names")
        if names is None or not isinstance(names, list):
            emsg = f"'sample.names' is unavailable for magic variable '{expression}'"
            raise StructuredError(emsg)
        if len(names) == 0:
            emsg = f"Magic variable '{expression}' cannot be applied because sample.names is empty"
            raise StructuredError(emsg)

        filtered_names = [name for name in names if isinstance(name, str) and name]
        if not filtered_names:
            emsg = f"Magic variable '{expression}' cannot be applied because sample.names only contains empty strings"
            raise StructuredError(emsg)

        return "_".join(filtered_names)

    def _resolve_metadata_expression(self, segments: list[str], expression: str) -> str | None:
        if not segments:
            emsg = f"Invalid metadata magic variable '{expression}'"
            raise StructuredError(emsg)

        if segments[0] != "constant":
            emsg = f"Unsupported metadata field '{segments[0]}' in magic variable '{expression}'"
            raise StructuredError(emsg)

        if self.metadata_source is None:
            emsg = f"metadata.json is required to resolve '{expression}'"
            raise StructuredError(emsg)

        if len(segments) < self.MIN_METADATA_SEGMENTS:
            emsg = f"Magic variable '{expression}' requires a constant key"
            raise StructuredError(emsg)

        constant_key = segments[1]
        constants = self.metadata_source.get("constant", {})
        metadata_entry = constants.get(constant_key)
        if metadata_entry is None:
            emsg = f"metadata.constant['{constant_key}'] is missing for magic variable '{expression}'"
            raise StructuredError(emsg)

        return self._normalize_scalar(metadata_entry.get("value"), expression)

    def _normalize_scalar(self, value: Any, expression: str) -> str | None:
        if value is None or (isinstance(value, str) and value == ""):
            logger.warning("Magic variable '%s' resolved to an empty value and will be skipped", expression)
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)

        emsg = f"Magic variable '{expression}' must resolve to a scalar value, got {type(value).__name__!s}"
        raise StructuredError(emsg)


def _load_metadata(dataset_paths: RdeDatasetPaths | None) -> dict[str, Any] | None:
    """Load metadata.json when dataset paths are available.

    Args:
        dataset_paths: Dataset paths that may include a metadata directory.

    Returns:
        Parsed metadata contents when the file exists; otherwise None.
    """
    if dataset_paths is None:
        return None

    metadata_path = dataset_paths.meta.joinpath("metadata.json")
    if not metadata_path.exists():
        return None

    return readf_json(metadata_path)


def apply_magic_variable(
    invoice_path: str | Path,
    rawfile_path: str | Path,
    *,
    save_filepath: str | Path | None = None,
    dataset_paths: RdeDatasetPaths | None = None,
) -> dict[str, Any]:
    """Expand supported magic variables inside ``invoice.json``.

    Magic variables can reference the input filename, invoice metadata sourced
    from ``invoice_org`` and constants defined in ``metadata.json``.  Only
    ``basic.dataName`` currently supports substitution.

    Args:
        invoice_path: Target invoice file to update.
        rawfile_path: Raw input file supplying ``${filename}``.
        save_filepath: Destination path for the updated invoice. Defaults to ``invoice_path``.
        dataset_paths: Dataset paths used to locate ``invoice_org`` and metadata files.

    Returns:
        dict[str, Any]: Updated invoice contents when substitutions occur. An empty dict is returned when
        no magic variables are present.

    Raises:
        StructuredError: If required fields or metadata are missing for a referenced magic variable.
    """
    invoice_path = Path(invoice_path)
    rawfile_path = Path(rawfile_path)
    destination_path = Path(save_filepath) if save_filepath is not None else invoice_path

    invoice_contents = readf_json(invoice_path)
    basic_section = invoice_contents.get("basic")
    if basic_section is None:
        emsg = "invoice.json is missing the 'basic' section required for magic variable processing"
        raise StructuredError(emsg)

    data_name_template = basic_section.get("dataName")
    if not isinstance(data_name_template, str) or MAGIC_VARIABLE_PATTERN.search(data_name_template) is None:
        # No magic variables to apply.
        return {}

    invoice_source_path = dataset_paths.invoice_org if dataset_paths is not None else invoice_path
    invoice_source = readf_json(invoice_source_path)

    metadata_contents = _load_metadata(dataset_paths)

    resolver = MagicVariableResolver(
        rawfile_path=rawfile_path,
        invoice_source=invoice_source,
        metadata_source=metadata_contents,
    )
    resolved_name = resolver.expand(data_name_template)
    if resolved_name == "":
        emsg = "Magic variable expansion produced an empty dataName"
        raise StructuredError(emsg)

    basic_section["dataName"] = resolved_name
    writef_json(destination_path, invoice_contents)
    return invoice_contents
