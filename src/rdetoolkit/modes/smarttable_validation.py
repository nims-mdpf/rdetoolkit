"""Read-only SmartTable mapping and cell validation for v2 flows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from rdetoolkit._interrupt import is_run_interrupted
from rdetoolkit.errors import ERROR_CATALOG, RdeValidationError
from rdetoolkit.fileops import readf_json
from rdetoolkit.rde2util import castval

_SUPPORTED_TYPES = frozenset({"string", "number", "integer", "boolean"})
_BASIC_FIELDS = frozenset({"dataName", "dateSubmitted", "dataOwnerId", "instrumentId", "experimentId", "description"})
_SAMPLE_FIELDS = frozenset({"names", "sampleId", "ownerId", "composition", "referenceUrl", "description"})
_ATTRIBUTE_PARTS = 2
_TABLE_SUFFIXES = frozenset({".csv", ".tsv", ".xlsx"})
#: Destinations the schema does not declare. Like v1, which skips a blank cell
#: before it looks its column up, these are reported only for a column that
#: some data row would write to (#782).
_VALUE_GATED_REASONS = frozenset({"unknown_custom_field", "unknown_invoice_field"})


@dataclass(frozen=True, slots=True)
class SmartTableDiagnostic:
    """A mapping problem whose serialized form never includes a cell value.

    Attributes:
        row: Physical one-based table row, with mapping headers on row 2.
        column: Original mapping header identifying the destination field.
        expected_type: Required field type or mapping contract.
        reason: Stable machine-readable reason for rejection.
        suggestion: A corrective action without the rejected value.
    """

    row: int
    column: str
    expected_type: str
    reason: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class _ColumnContract:
    index: int
    name: str
    source: Literal["custom", "meta"]
    field_type: str | None
    field_format: str | None


def validate_smarttable_mapping(
    table_path: Path,
    invoice_schema_path: Path,
    metadata_def_path: Path,
) -> tuple[SmartTableDiagnostic, ...]:
    """Validate all mapping headers and nonempty cells without producing files.

    Custom and metadata values use their existing distinct SmartTable casters.
    Blank cells retain the builder's clearing and omission behavior. Descriptive
    columns without mapping syntax are ignored as in legacy processing, and so
    is a ``custom/``, ``basic/`` or ``sample/`` column the schema does not
    declare while every cell in it is blank.

    Args:
        table_path: Original CSV, TSV, or XLSX SmartTable.
        invoice_schema_path: Invoice schema declaring custom destinations.
        metadata_def_path: Metadata definitions, required for ``meta/`` headers.

    Returns:
        Deterministically ordered, redacted diagnostics. An empty tuple means
        every checked mapping and nonempty cell satisfies its declared type.
    """
    table = _read_mapping_table(table_path)
    if table is None:
        return (_diagnostic(2, "", "SmartTable", "unreadable_table"),)
    schema = _read_optional_json(invoice_schema_path)
    if schema is None:
        return (_diagnostic(2, "", "invoice schema object", "invalid_invoice_schema"),)
    headers = _mapping_headers(table)
    metadata = _read_optional_json(metadata_def_path) if any(name.startswith("meta/") for name in headers) else None
    rows = table.iloc[1:]
    contracts, diagnostics = _validate_headers(headers, schema, metadata, _blank_columns(rows))
    if diagnostics:
        return tuple(diagnostics)
    return tuple(_validate_cells(rows, contracts))


def ensure_smarttable_valid(inputdata_path: Path, tasksupport_path: Path) -> None:
    """Reject invalid v2 SmartTable mappings before any row invokes the flow.

    Args:
        inputdata_path: Directory containing the selected SmartTable.
        tasksupport_path: Directory containing invoice and metadata definitions.

    Raises:
        RdeValidationError: Catalogued error 4005 with redacted diagnostics.
    """
    tables = sorted(path for path in inputdata_path.glob("smarttable_*") if path.is_file() and path.suffix.lower() in _TABLE_SUFFIXES)
    for table in tables:
        diagnostics = validate_smarttable_mapping(table, tasksupport_path / "invoice.schema.json", tasksupport_path / "metadata-def.json")
        if diagnostics:
            definition = ERROR_CATALOG[4005]
            first = diagnostics[0]
            message = definition.message_template.format(row=first.row, column=first.column, reason=first.reason)
            raise RdeValidationError(code=4005, message=f"{message} Remediation: {definition.remediation}", detail={"diagnostics": [asdict(item) for item in diagnostics]})


def _diagnostic(row: int, column: str, expected: str, reason: str) -> SmartTableDiagnostic:
    return SmartTableDiagnostic(row, column, expected, reason, f"Correct the mapping or supply a value matching {expected}; inspect the named row and column locally.")


def _read_mapping_table(path: Path) -> pd.DataFrame | None:
    try:
        table = (
            pd.read_excel(path, sheet_name=0, dtype=str, skiprows=[0], header=None)
            if path.suffix.lower() == ".xlsx"
            else pd.read_csv(path, sep="\t" if path.suffix.lower() == ".tsv" else ",", dtype=str, skiprows=[0], header=None, skip_blank_lines=False)
        )
    except Exception as exc:  # noqa: BLE001
        if is_run_interrupted(exc):
            raise
        return None
    return None if table.empty else table


def _mapping_headers(table: pd.DataFrame) -> list[str]:
    return ["" if pd.isna(value) else str(value) for value in table.iloc[0]]


def _is_blank(value: Any) -> bool:
    return bool(pd.isna(value)) or str(value).strip() == ""


def _blank_columns(rows: pd.DataFrame) -> frozenset[int]:
    return frozenset(index for index in range(rows.shape[1]) if all(_is_blank(value) for value in rows.iloc[:, index]))


def _read_optional_json(path: Path) -> Mapping[str, Any] | None:
    try:
        data = readf_json(path)
    except Exception as exc:  # noqa: BLE001
        if is_run_interrupted(exc):
            raise
        return None
    return data if isinstance(data, Mapping) else None


def _validate_headers(
    headers: list[str],
    schema: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
    blank_columns: frozenset[int],
) -> tuple[list[_ColumnContract], list[SmartTableDiagnostic]]:
    seen: set[str] = set()
    contracts: list[_ColumnContract] = []
    diagnostics: list[SmartTableDiagnostic] = []
    for index, name in enumerate(headers):
        if not _is_mapping(name):
            continue
        if name in seen:
            diagnostics.append(_diagnostic(2, name, "unique mapping header", "duplicate_mapping"))
            continue
        seen.add(name)
        contract, diagnostic = _header_contract(index, name, schema, metadata)
        if diagnostic is not None and not (diagnostic.reason in _VALUE_GATED_REASONS and index in blank_columns):
            diagnostics.append(diagnostic)
        if contract is not None:
            contracts.append(contract)
    if not seen:
        diagnostics.append(_diagnostic(2, "", "mapping header", "missing_mapping_headers"))
    return contracts, diagnostics


def _is_mapping(name: str) -> bool:
    return "/" in name or name.startswith("inputdata")


def _header_contract(
    index: int,
    name: str,
    schema: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
) -> tuple[_ColumnContract | None, SmartTableDiagnostic | None]:
    if name.startswith("inputdata"):
        suffix = name.removeprefix("inputdata")
        return None, None if suffix.isdecimal() else _diagnostic(2, name, "inputdata<N>", "invalid_mapping_path")
    prefix, field = name.split("/", 1)
    if not field or "/" in field:
        return None, _diagnostic(2, name, "one field after the mapping prefix", "invalid_mapping_path")
    return _destination_contract(index, name, prefix, field, schema, metadata)


def _destination_contract(
    index: int,
    name: str,
    prefix: str,
    field: str,
    schema: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
) -> tuple[_ColumnContract | None, SmartTableDiagnostic | None]:
    if prefix in {"basic", "sample"}:
        return None, _invoice_header_diagnostic(name, prefix, field, schema)
    if prefix == "custom":
        return _typed_header(index, name, "custom", _custom_definition(schema, field), "unknown_custom_field")
    if prefix == "meta":
        return _metadata_contract(index, name, field, metadata)
    return None, _diagnostic(2, name, "basic/, custom/, sample/, meta/ or inputdata<N>", "unknown_mapping_prefix")


def _custom_definition(schema: Mapping[str, Any], field: str) -> Any:
    current: Any = schema
    for key in ("properties", "custom", "properties", field):
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _invoice_header_diagnostic(name: str, prefix: str, field: str, schema: Mapping[str, Any]) -> SmartTableDiagnostic | None:
    if prefix == "sample" and field.startswith(("generalAttributes.", "specificAttributes.")):
        return _attribute_diagnostic(name, field)
    fields = _BASIC_FIELDS if prefix == "basic" else _SAMPLE_FIELDS
    known = field in fields or field in _declared_section_fields(schema, prefix)
    return None if known else _diagnostic(2, name, "known invoice field", "unknown_invoice_field")


def _declared_section_fields(schema: Mapping[str, Any], prefix: str) -> Mapping[str, Any]:
    declared: Any = schema
    for key in ("properties", prefix, "properties"):
        declared = declared.get(key, {}) if isinstance(declared, Mapping) else {}
    return declared if isinstance(declared, Mapping) else {}


def _attribute_diagnostic(name: str, field: str) -> SmartTableDiagnostic | None:
    if field.startswith("generalAttributes."):
        valid = bool(field.removeprefix("generalAttributes."))
        return None if valid else _diagnostic(2, name, "sample/generalAttributes.<termId>", "invalid_mapping_path")
    parts = field.removeprefix("specificAttributes.").split(".", 1)
    valid = len(parts) == _ATTRIBUTE_PARTS and all(parts)
    return None if valid else _diagnostic(2, name, "sample/specificAttributes.<classId>.<termId>", "invalid_mapping_path")


def _metadata_contract(index: int, name: str, field: str, metadata: Mapping[str, Any] | None) -> tuple[_ColumnContract | None, SmartTableDiagnostic | None]:
    if metadata is None:
        return None, _diagnostic(2, name, "metadata-def.json object", "missing_metadata_definition")
    return _metadata_header(index, name, metadata.get(field))


def _metadata_header(index: int, name: str, definition: Any) -> tuple[_ColumnContract | None, SmartTableDiagnostic | None]:
    if isinstance(definition, Mapping) and definition.get("variable"):
        return None, _diagnostic(2, name, "constant metadata", "variable_metadata")
    schema = definition.get("schema", {}) if isinstance(definition, Mapping) else None
    return _typed_header(index, name, "meta", schema, "unknown_metadata_field")


def _typed_header(
    index: int,
    name: str,
    source: Literal["custom", "meta"],
    definition: Any,
    missing_reason: str,
) -> tuple[_ColumnContract | None, SmartTableDiagnostic | None]:
    if not isinstance(definition, Mapping):
        return None, _diagnostic(2, name, "declared field", missing_reason)
    field_type = definition.get("type")
    if field_type is None and source == "custom":
        return None, _diagnostic(2, name, "declared custom type", "unsupported_custom_type")
    if field_type is not None and (not isinstance(field_type, str) or field_type not in _SUPPORTED_TYPES):
        return None, _diagnostic(2, name, "string, number, integer or boolean", f"unsupported_{'metadata' if source == 'meta' else 'custom'}_type")
    return _ColumnContract(index, name, source, field_type, definition.get("format")), None


def _validate_cells(table: pd.DataFrame, contracts: list[_ColumnContract]) -> list[SmartTableDiagnostic]:
    diagnostics: list[SmartTableDiagnostic] = []
    for row_number, values in enumerate(table.itertuples(index=False, name=None), start=3):
        for contract in contracts:
            value = values[contract.index]
            if _is_blank(value):
                continue
            diagnostic = _cell_diagnostic(str(value), row_number, contract)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
    return diagnostics


def _cell_diagnostic(value: str, row: int, contract: _ColumnContract) -> SmartTableDiagnostic | None:
    from rdetoolkit.modes.smarttable import _cast_custom_field_value  # noqa: PLC0415

    try:
        if contract.source == "custom":
            _cast_custom_field_value(value, contract.field_type or "string", contract.field_format)
        elif contract.field_type is not None:
            castval(value, contract.field_type, contract.field_format)
    except Exception as exc:  # noqa: BLE001
        if is_run_interrupted(exc):
            raise
        return _diagnostic(row, contract.name, contract.field_type or "string", "invalid_cell_type")
    return None
