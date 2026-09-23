"""SmartTable-mode planning handler and tile invoice builder."""

from __future__ import annotations

import copy
import math
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from rdetoolkit.domain.invoice import load_invoice
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson
from rdetoolkit.rde2util import castval
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import TilePlan, TilePreparation, create_common_tiles

if TYPE_CHECKING:
    from rdetoolkit.modes.protocol import PlanningContext, RawCopyStrategy
    from rdetoolkit.runner.planner import ExecutionPlan

logger = get_logger(__name__)

#: Mapping-key prefixes that address invoice fields rather than metadata or
#: input-file columns.
_INVOICE_PREFIXES = ("basic/", "custom/", "sample/")

#: Sample fields whose *structure* survives new-sample clearing: the CSV may
#: leave them empty without the clearing step being undone.
_PRESERVED_CLEARED_SAMPLE_FIELDS = frozenset({
    "sample/sampleId",
    "sample/description",
    "sample/composition",
    "sample/referenceUrl",
})

#: Metadata value types v1 accepts for a ``meta/`` mapping column.
_SUPPORTED_METADATA_TYPES = frozenset({"string", "number", "integer", "boolean"})

#: ``sample/specificAttributes.<classId>.<termId>`` splits into two parts.
_SPECIFIC_ATTRIBUTE_PARTS = 2

#: Extensions the SmartTable input checker accepts for the original table.
_SMARTTABLE_SUFFIXES = frozenset({".csv", ".tsv", ".xlsx"})


class SmartTableModeHandler:
    """Plan SmartTable-mode tiles.

    Tile enumeration is the common one; what SmartTable owns is the per-row
    invoice construction, which :class:`SmartTableInvoiceBuilder` performs for
    the run-owned ``InvoiceService``, and the EarlyExit tile that
    ``save_table_file`` adds.
    """

    kind = ModeKind.smarttable

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        """Create SmartTable-mode tile plans.

        With ``save_table_file`` enabled the input checker registers the
        original table as its own tile. v1 handles that tile in
        ``SmartTableEarlyExitProcessor``: rename, copy, validate, skip the rest.
        Here it becomes a pre-completed tile, so the executor publishes its raw
        inputs and records the iteration without invoking the flow.

        Args:
            context: Run-scoped paths and invoice operations.

        Returns:
            Lazily iterable common tile plans for the executor.
        """
        tiles = create_common_tiles(self.kind, context)
        if context.config is None or not context.config.smarttable.save_table_file:
            return tiles
        return _with_early_exit_tile(tiles)

    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None:
        """Return no mode-specific raw copy strategy.

        Args:
            plan: Immutable run execution plan.

        Returns:
            ``None``, selecting the generic ``RawArtifactService``.
        """
        _ = plan
        return None

    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None:
        """Run the v1 invoice pipeline's artifact sequence.

        Args:
            plan: Immutable run execution plan.

        Returns:
            ``None``, selecting thumbnail -> structured -> magic -> description.
        """
        _ = plan
        return None


def _with_early_exit_tile(tiles: Iterable[TilePlan]) -> Iterator[TilePlan]:
    """Mark the tile whose raw input is the original SmartTable file."""
    for tile in tiles:
        table = _original_smarttable_file(tile.paths.rawfiles)
        if table is None:
            yield tile
            continue
        yield replace(
            tile,
            precompleted=True,
            prepare_invoice=partial(_early_exit_invoice, table=table, invoice_dir=tile.out.invoice),
        )


def _original_smarttable_file(rawfiles: tuple[Path, ...]) -> Path | None:
    """Return the original SmartTable input of a tile, if it holds one.

    Ported from v1's ``SmartTableEarlyExitProcessor._is_original_smarttable_file``:
    only a ``smarttable_*`` file that still lives under ``inputdata`` is the
    original table; the generated ``fsmarttable_*`` row CSVs never match.
    """
    for path in rawfiles:
        if "inputdata" in path.parts and path.name.startswith("smarttable_") and path.suffix.lower() in _SMARTTABLE_SUFFIXES:
            return path
    return None


def _early_exit_invoice(*, table: Path, invoice_dir: Path) -> TilePreparation:
    """Publish the EarlyExit invoice of the original SmartTable tile.

    v1 rewrites ``basic.dataName`` of the tile's own ``invoice.json`` — for the
    tile the checker registers at index 0 that file is the run's source invoice
    — and performs no other invoice work for this tile.

    Args:
        table: Original SmartTable file registered as this tile's raw input.
        invoice_dir: This tile's invoice directory.

    Returns:
        The published tile invoice. The EarlyExit tile has no SmartTable row,
        so it carries no row data for the callback.
    """
    invoice_path = invoice_dir / "invoice.json"
    invoice_data = readf_json(invoice_path)
    invoice_data["basic"]["dataName"] = table.name
    writef_json(invoice_path, invoice_data)
    return TilePreparation(invoice=load_invoice(invoice_path))


class SmartTableInvoiceBuilder:
    """Build one SmartTable tile invoice per row, for the duration of one run.

    This is the v2 port of the SmartTable invoice initializer in
    ``processing/processors/invoice.py``: the merge rules, the casting rules
    and the ``StructuredError`` messages are the v1 ones, and
    ``tests/v2/modes/test_smarttable_invoice_builder_i6_c.py`` pins them
    against that v1 processor used as an oracle.

    The one deliberate difference is ownership of the base invoice. v1 read the
    run's source invoice into a **class** attribute keyed by resolved path,
    because SmartTable tile 0 writes its merged invoice back over that very
    file and later tiles must not inherit it. A class cache makes two runs over
    one root observe each other, so the snapshot lives on the instance instead:
    the owning ``InvoiceService`` creates one builder per run and resets it at
    the run boundary.
    """

    def __init__(self) -> None:
        """Create a builder that has not yet read any base invoice."""
        self._base_invoice: dict[Path, dict[str, Any]] = {}

    def reset(self) -> None:
        """Release the base invoice snapshot taken for the previous run."""
        self._base_invoice.clear()

    def build(
        self,
        *,
        rowfile: Path,
        invoice_org: Path,
        invoice_schema_path: Path,
        dist_path: Path,
        metadata_def_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any] | None:
        """Write one tile invoice from one SmartTable row.

        Args:
            rowfile: Per-row CSV generated by the SmartTable input checker.
            invoice_org: Run-level source invoice inherited by every tile.
            invoice_schema_path: ``invoice.schema.json`` used for casting.
            dist_path: Destination tile ``invoice.json``.
            metadata_def_path: ``metadata-def.json`` for ``meta/`` columns.
            metadata_path: Destination tile ``meta/metadata.json``.

        Returns:
            The row dictionary a v1 callback receives as
            ``smarttable_row_data``, or ``None`` when the CSV has no data row.

        Raises:
            StructuredError: If the row cannot be merged into an invoice, with
                v1's message. Any other failure is wrapped exactly as v1's
                processor wrapped it.
        """
        try:
            return self._build(
                rowfile=rowfile,
                invoice_org=invoice_org,
                invoice_schema_path=invoice_schema_path,
                dist_path=dist_path,
                metadata_def_path=metadata_def_path,
                metadata_path=metadata_path,
            )
        except StructuredError:
            raise
        except Exception as exc:
            error_msg = f"Failed to initialize invoice from SmartTable: {str(exc)}"
            raise StructuredError(error_msg) from exc

    def _build(
        self,
        *,
        rowfile: Path,
        invoice_org: Path,
        invoice_schema_path: Path,
        dist_path: Path,
        metadata_def_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any] | None:
        csv_data = pd.read_csv(rowfile, dtype=str)
        row_data = _row_dictionary(csv_data)
        invoice_data = self._base_invoice_data(invoice_org)
        invoice_schema = InvoiceSchemaJson(**readf_json(invoice_schema_path))
        metadata_updates = _apply_smarttable_row(
            csv_data,
            invoice_data,
            invoice_schema,
            metadata_def_path=metadata_def_path,
        )
        _ensure_required_fields(invoice_data)
        dist_path.parent.mkdir(parents=True, exist_ok=True)
        writef_json(dist_path, invoice_data)
        if metadata_updates:
            _write_metadata(metadata_path, metadata_updates)
        return row_data

    def _base_invoice_data(self, invoice_org: Path) -> dict[str, Any]:
        """Return a private copy of the run's original invoice data.

        The source is read at most once per run: later rows must not observe
        the values earlier rows wrote, and SmartTable's tile 0 destination *is*
        the source file.
        """
        key = invoice_org.resolve()
        if key not in self._base_invoice:
            self._base_invoice[key] = readf_json(key) if key.exists() else _empty_invoice_data()
        return copy.deepcopy(self._base_invoice[key])


def _empty_invoice_data() -> dict[str, Any]:
    """Return the invoice skeleton v1 uses when no source invoice exists."""
    return {"basic": {}, "custom": {}, "sample": {}}


def _row_dictionary(csv_data: pd.DataFrame) -> dict[str, Any] | None:
    """Return the single data row as the dictionary a v1 callback receives."""
    if len(csv_data) > 0:
        row_dict: dict[str, Any] = csv_data.iloc[0].to_dict()
        return row_dict
    return None


def _apply_smarttable_row(
    csv_data: pd.DataFrame,
    invoice_data: dict[str, Any],
    invoice_schema: InvoiceSchemaJson,
    *,
    metadata_def_path: Path,
) -> dict[str, dict[str, Any]]:
    """Apply the row to the invoice and collect its metadata updates."""
    metadata_updates: dict[str, dict[str, Any]] = {}
    metadata_def: dict[str, Any] | None = None
    csv_has_sample_owner_id = False
    if len(csv_data) == 0:
        return metadata_updates

    # First pass: the CSV's intent is decided before any value is applied, so
    # clearing a dummy sample cannot overwrite a field the row sets itself.
    is_new_sample = _detect_new_sample_registration(csv_data)
    if is_new_sample:
        _clear_sample_for_new_registration(invoice_data)

    for column in csv_data.columns:
        value = csv_data.iloc[0][column]
        if pd.isna(value) or str(value).strip() == "":
            _clear_empty_column(column, invoice_data, is_new_sample=is_new_sample)
            continue
        if column.startswith("meta/"):
            # The definition file is read at most once per row, as v1 does.
            metadata_def = _apply_meta_column(
                column,
                value,
                metadata_def_path=metadata_def_path,
                metadata_def=metadata_def,
                metadata_updates=metadata_updates,
            )
        else:
            _process_mapping_key(column, value, invoice_data, invoice_schema)
        if column == "sample/ownerId":
            csv_has_sample_owner_id = True

    if not csv_has_sample_owner_id:
        _set_sample_owner_id(invoice_data)
    return metadata_updates


def _clear_empty_column(column: str, invoice_data: dict[str, Any], *, is_new_sample: bool) -> None:
    """Clear an inherited value the row leaves empty, as v1 does."""
    if not _is_invoice_mapping(column):
        return
    if is_new_sample and _should_preserve_cleared_sample_field(column):
        return
    _clear_mapping_key(column, invoice_data)


def _apply_meta_column(
    column: str,
    value: Any,
    *,
    metadata_def_path: Path,
    metadata_def: dict[str, Any] | None,
    metadata_updates: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Collect one ``meta/`` column and return the definition in use.

    A missing ``metadata-def.json`` makes v1 skip the column rather than fail,
    because the file is optional for modes that declare no metadata.
    """
    if not metadata_def_path.exists():
        return metadata_def
    loaded = metadata_def if metadata_def is not None else _load_metadata_definition(metadata_def_path)
    meta_key, meta_entry = _process_meta_mapping(column, value, loaded)
    metadata_updates[meta_key] = meta_entry
    return loaded


def _process_mapping_key(
    key: str,
    value: str,
    invoice_data: dict[str, Any],
    invoice_schema: InvoiceSchemaJson,
) -> None:
    """Assign one mapping key to its invoice location."""
    if key.startswith("basic/"):
        invoice_data["basic"][key.replace("basic/", "")] = value
        return
    if key.startswith("custom/"):
        _process_custom_key(key.replace("custom/", ""), value, invoice_data, invoice_schema)
        return
    if key.startswith("sample/generalAttributes."):
        _process_general_attributes(key, value, invoice_data)
        return
    if key.startswith("sample/specificAttributes."):
        _process_specific_attributes(key, value, invoice_data)
        return
    if key.startswith("sample/"):
        field = key.replace("sample/", "")
        # ``names`` is an array in the invoice schema; every other sample field
        # is scalar.
        invoice_data["sample"][field] = [value] if field == "names" else value
    # ``meta/`` and ``inputdata`` columns are handled by their own passes.


def _process_custom_key(
    field: str,
    value: str,
    invoice_data: dict[str, Any],
    invoice_schema: InvoiceSchemaJson,
) -> None:
    """Cast one custom field with the schema's declared type."""
    schema_value = _resolve_custom_schema_field(field, invoice_schema)
    field_format = schema_value.get("format")
    field_type = schema_value["type"]
    try:
        invoice_data["custom"][field] = _cast_custom_field_value(value, field_type, field_format)
    except StructuredError as cast_error:
        emsg = (
            "Value for invoice.json field "
            f"'custom.{field}' does not match the type defined in "
            f"invoice.schema.json (expected: {field_type})."
        )
        raise StructuredError(emsg) from cast_error


def _resolve_custom_schema_field(field: str, invoice_schema: InvoiceSchemaJson) -> dict[str, Any]:
    """Return the schema definition of one custom field.

    v1 also guarded against a declaration without ``type``. That guard is
    unreachable here: ``InvoiceSchemaJson`` makes ``type`` a required field, so
    a schema missing it is rejected while it is parsed — with the same
    ``StructuredError`` wrapping, because the whole build is wrapped.

    Raises:
        StructuredError: If the field is not declared in the schema.
    """
    schema_value = invoice_schema.find_field(field, custom_only=True)
    if schema_value is None:
        emsg = f"Field 'custom.{field}' is not defined in invoice.schema.json."
        raise StructuredError(emsg)
    return schema_value


def _cast_custom_field_value(
    value: str,
    field_type: str,
    field_format: str | None,
) -> bool | int | float | str:
    """Cast a custom field value with v1's strict SmartTable semantics.

    Raises:
        StructuredError: If the value does not represent the declared type.
    """
    if field_type == "boolean":
        return _cast_boolean(value)
    if field_type == "integer":
        return _cast_integer(value)
    if field_type == "number":
        return _cast_number(value)
    result: bool | int | float | str = castval(value, field_type, field_format)
    return result


def _cast_boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    emsg = "ERROR: failed to cast SmartTable custom field to boolean"
    raise StructuredError(emsg)


def _cast_integer(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        emsg = "ERROR: failed to cast SmartTable custom field to integer"
        raise StructuredError(emsg) from exc


def _cast_number(value: str) -> int | float:
    normalized = value.strip()
    try:
        return int(normalized)
    except ValueError:
        pass
    try:
        number_value = float(normalized)
    except ValueError as exc:
        emsg = "ERROR: failed to cast SmartTable custom field to number"
        raise StructuredError(emsg) from exc
    if not math.isfinite(number_value):
        emsg = "ERROR: failed to cast SmartTable custom field to number"
        raise StructuredError(emsg) from None
    return number_value


def _clear_mapping_key(key: str, invoice_data: dict[str, Any]) -> None:
    """Drop the inherited value a mapping key addresses."""
    if key.startswith("basic/"):
        invoice_data.setdefault("basic", {}).pop(key.replace("basic/", ""), None)
        return
    if key.startswith("custom/"):
        invoice_data.setdefault("custom", {}).pop(key.replace("custom/", ""), None)
        return
    if key.startswith("sample/generalAttributes."):
        _clear_general_attribute(key.replace("sample/generalAttributes.", ""), invoice_data)
        return
    if key.startswith("sample/specificAttributes."):
        _clear_specific_attribute(key.replace("sample/specificAttributes.", ""), invoice_data)
        return
    if key.startswith("sample/"):
        invoice_data.setdefault("sample", {}).pop(key.replace("sample/", ""), None)


def _clear_general_attribute(term_id: str, invoice_data: dict[str, Any]) -> None:
    sample_section = invoice_data.setdefault("sample", {})
    existing = sample_section.get("generalAttributes") or []
    sample_section["generalAttributes"] = [attr for attr in existing if attr.get("termId") != term_id]


def _clear_specific_attribute(suffix: str, invoice_data: dict[str, Any]) -> None:
    parts = suffix.split(".", 1)
    if len(parts) != _SPECIFIC_ATTRIBUTE_PARTS:
        return
    class_id, term_id = parts
    sample_section = invoice_data.setdefault("sample", {})
    existing = sample_section.get("specificAttributes") or []
    sample_section["specificAttributes"] = [
        attr
        for attr in existing
        if not (attr.get("classId") == class_id and attr.get("termId") == term_id)
    ]


def _is_invoice_mapping(key: str) -> bool:
    """Return True when the mapping key targets invoice fields."""
    return key.startswith(_INVOICE_PREFIXES)


def _should_preserve_cleared_sample_field(key: str) -> bool:
    """Return True when new-sample clearing must survive an empty cell."""
    if key in _PRESERVED_CLEARED_SAMPLE_FIELDS:
        return True
    return key.startswith(("sample/generalAttributes.", "sample/specificAttributes."))


def _ensure_sample_attribute_list(invoice_data: dict[str, Any], field_name: str) -> list[dict[str, Any]]:
    """Normalize one sample attribute container so updates can append safely.

    Raises:
        StructuredError: If the container is neither a list nor null.
    """
    sample_section = invoice_data.setdefault("sample", {})
    attribute_list = sample_section.get(field_name)
    if attribute_list is None:
        sample_section[field_name] = []
        result: list[dict[str, Any]] = sample_section[field_name]
        return result
    if not isinstance(attribute_list, list):
        emsg = f"SmartTable sample attribute container must be a list or null: sample.{field_name}"
        raise StructuredError(emsg)
    return attribute_list


def _process_general_attributes(key: str, value: str, invoice_data: dict[str, Any]) -> None:
    """Apply one ``sample/generalAttributes.<termId>`` column."""
    term_id = key.replace("sample/generalAttributes.", "")
    general_attributes = _ensure_sample_attribute_list(invoice_data, "generalAttributes")
    for attr in general_attributes:
        if attr.get("termId") == term_id:
            attr["value"] = value
            return
    general_attributes.append({"termId": term_id, "value": value})


def _process_specific_attributes(key: str, value: str, invoice_data: dict[str, Any]) -> None:
    """Apply one ``sample/specificAttributes.<classId>.<termId>`` column."""
    parts = key.replace("sample/specificAttributes.", "").split(".", 1)
    if len(parts) != _SPECIFIC_ATTRIBUTE_PARTS:
        return
    class_id, term_id = parts
    specific_attributes = _ensure_sample_attribute_list(invoice_data, "specificAttributes")
    for attr in specific_attributes:
        if attr.get("classId") == class_id and attr.get("termId") == term_id:
            attr["value"] = value
            return
    specific_attributes.append({"classId": class_id, "termId": term_id, "value": value})


def _ensure_required_fields(invoice_data: dict[str, Any]) -> None:
    """Guarantee the ``basic`` section every invoice must carry."""
    if "basic" not in invoice_data:
        invoice_data["basic"] = {}


def _detect_new_sample_registration(csv_data: pd.DataFrame) -> bool:
    """Return True when the row registers a new sample rather than linking one."""
    csv_has_sample_names = False
    csv_has_sample_id_with_value = False
    for column in csv_data.columns:
        value = csv_data.iloc[0][column]
        if pd.isna(value) or str(value).strip() == "":
            continue
        if column == "sample/names":
            csv_has_sample_names = True
        if column == "sample/sampleId":
            csv_has_sample_id_with_value = True
    return csv_has_sample_names and not csv_has_sample_id_with_value


def _clear_sample_for_new_registration(invoice_data: dict[str, Any]) -> None:
    """Clear the dummy reference sample inherited from the source invoice.

    ``sample.ownerId`` is deliberately untouched: it is owned by
    :func:`_set_sample_owner_id` (v1 Issue #389 policy).
    """
    sample_section = invoice_data.setdefault("sample", {})
    sample_section["sampleId"] = None
    for field in ("description", "composition", "referenceUrl"):
        sample_section[field] = None
    for attr in sample_section.get("generalAttributes") or []:
        attr["value"] = None
    for attr in sample_section.get("specificAttributes") or []:
        attr["value"] = None


def _set_sample_owner_id(invoice_data: dict[str, Any]) -> None:
    """Set ``sample.ownerId`` to ``basic.dataOwnerId`` when the row omits it."""
    basic_section = invoice_data.get("basic", {})
    data_owner_id = basic_section.get("dataOwnerId")
    if data_owner_id is None or data_owner_id == "":
        logger.warning(
            "basic.dataOwnerId is missing or empty; sample.ownerId will not be updated. "
            "This may cause incorrect sample owner assignment.",
        )
        return
    invoice_data.setdefault("sample", {})["ownerId"] = data_owner_id


def _load_metadata_definition(metadata_def_path: Path) -> dict[str, Any]:
    """Load ``metadata-def.json`` for ``meta/`` mapping columns.

    The caller only reaches this once the file exists, so v1's redundant
    existence guard is not ported; a file that disappears in between still
    fails as a ``StructuredError`` through ``readf_json``.

    Raises:
        StructuredError: If the file is not a JSON object.
    """
    metadata_def = readf_json(metadata_def_path)
    if not isinstance(metadata_def, dict):
        emsg = "metadata-def.json must contain an object at the top level"
        raise StructuredError(emsg)
    return metadata_def


def _process_meta_mapping(
    key: str,
    value: str,
    metadata_def: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Convert one ``meta/`` column into a ``metadata.json`` entry.

    Raises:
        StructuredError: If the definition is missing, unsupported, or the
            value does not match the declared type.
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
    if meta_type and meta_type not in _SUPPORTED_METADATA_TYPES:
        emsg = f"Unsupported metadata type for key {meta_key}: {meta_type}"
        raise StructuredError(emsg)

    meta_entry: dict[str, Any] = {"value": _cast_metadata_value(meta_key, value, meta_type, meta_format)}
    unit = definition.get("unit")
    if unit:
        meta_entry["unit"] = unit
    return meta_key, meta_entry


def _cast_metadata_value(
    meta_key: str,
    value: str,
    meta_type: str | None,
    meta_format: str | None,
) -> Any:
    """Cast one metadata value, reporting v1's type-mismatch message."""
    if not meta_type:
        return value
    try:
        return castval(value, meta_type, meta_format)
    except StructuredError as cast_error:
        emsg = (
            "Value for metadata.json key "
            f"'{meta_key}' does not match the type defined in "
            f"metadata-def.json (expected: {meta_type})."
        )
        raise StructuredError(emsg) from cast_error


def _write_metadata(metadata_path: Path, metadata_updates: dict[str, dict[str, Any]]) -> None:
    """Merge the collected ``meta/`` values into the tile's metadata.json."""
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_obj = readf_json(metadata_path) if metadata_path.exists() else {"constant": {}, "variable": []}
    constant_section = metadata_obj.setdefault("constant", {})
    metadata_obj.setdefault("variable", [])
    constant_section.update(metadata_updates)
    writef_json(metadata_path, metadata_obj)
