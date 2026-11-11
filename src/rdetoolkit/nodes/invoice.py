"""Builtin helpers for editing the invoice ``custom`` section by schema."""

from __future__ import annotations

import copy
import datetime as dt
import math
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from rdetoolkit.core.node import node
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json
from rdetoolkit.rde2util import ValueCaster, castval
from rdetoolkit.types import InvoiceData

_DATE_FORMATS = frozenset({"date", "date-time", "time"})
_LABEL_LANGUAGES = ("ja", "en")


def _load_schema(schema: Mapping[str, Any] | Path | None, invoice: InvoiceData | None = None) -> Mapping[str, Any]:
    if isinstance(schema, Path):
        loaded: Any = readf_json(schema)
        if not isinstance(loaded, Mapping):
            msg = f"invoice.schema.json root must be an object: {schema}"
            raise ValueError(msg)
        return loaded
    resolved = schema if schema is not None else (invoice.schema if invoice is not None else None)
    if resolved is None:
        msg = "No invoice schema: pass schema= (a mapping or the path to invoice.schema.json)"
        raise ValueError(msg)
    return resolved


def _custom_definitions(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    custom = schema.get("properties", {}).get("custom", {}) if isinstance(schema.get("properties"), Mapping) else {}
    definitions = custom.get("properties", {}) if isinstance(custom, Mapping) else {}
    return definitions if isinstance(definitions, Mapping) else {}


def _is_missing(value: Any) -> bool:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return True
    return type(value).__name__ == "NaTType"


def _cast_string(value: Any, fmt: str | None) -> Any:
    if fmt not in _DATE_FORMATS:
        return value
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, dt.date):
        parsed = dt.datetime.combine(value, dt.time())
    else:
        return ValueCaster.convert_to_date_format(value, fmt)
    return parsed.isoformat() if fmt == "date-time" else parsed.strftime("%Y-%m-%d" if fmt == "date" else "%H:%M:%S")


def _cast_value(value: Any, value_type: Any, fmt: str | None) -> Any:
    if _is_missing(value):
        return None
    if value_type == "string":
        return _cast_string(value, fmt)
    if value_type == "integer" and isinstance(value, float) and value.is_integer():
        return int(value)
    return castval(value, value_type, None)


def _cast_field(key: str, value: Any, definitions: Mapping[str, Any]) -> Any:
    definition = definitions.get(key)
    if not isinstance(definition, Mapping):
        msg = f"Field 'custom.{key}' is not defined in invoice.schema.json."
        raise StructuredError(msg)
    value_type = definition.get("type")
    try:
        return _cast_value(value, value_type, definition.get("format"))
    except (StructuredError, ValueError, TypeError, OverflowError) as exc:
        msg = f"Value for invoice.json field 'custom.{key}' does not match the type defined in invoice.schema.json (expected: {value_type})."
        raise StructuredError(msg) from exc


@node(tags=["builtin", "invoice"], version="2.0.0", idempotent=True)
def set_custom_fields(
    invoice: InvoiceData,
    updates: Mapping[str, Any],
    *,
    schema: Mapping[str, Any] | Path | None = None,
    cast: bool = True,
) -> InvoiceData:
    """Return a copy of the invoice with ``custom`` values cast by the invoice schema.

    This is the v2 form of the v1 ``invoicefile._assign_invoice_val`` /
    ``rde2util.castval`` update of ``invoice.custom``. Each value is cast by
    its ``properties.custom.properties.<key>`` ``type`` and ``format``:

    - ``None``, a float NaN or ``pandas.NaT`` is stored as ``None`` for
      every type; filter such values out beforehand to keep the old value.
    - ``boolean``: the strings ``"true"`` / ``"false"`` (case-insensitive,
      surrounding spaces ignored); any other value by Python truthiness.
    - ``integer``: digits with an optional trailing unit (``"12 mm"`` -> 12)
      or an integral float (``3.0`` -> 3).
    - ``number``: as ``integer`` when the text is integral, else a float.
    - ``string`` with format ``date`` / ``date-time`` / ``time``: parsed by
      dateutil and written as ``YYYY-MM-DD`` / ISO 8601 / ``HH:MM:SS``;
      ``datetime.date`` and ``datetime.datetime`` values are accepted.
      Any other string format, or none, keeps the value unchanged.

    Keys keep their position in ``custom``; new keys are appended. The input
    invoice is never modified.

    Args:
        invoice: Parsed invoice to update.
        updates: New values keyed by custom field key. Use
            ``resolve_custom_key`` to translate schema labels.
        schema: ``invoice.schema.json`` as a mapping or a path. Defaults to
            ``invoice.schema``.
        cast: When false, values are stored as given and the schema is not
            read, so undeclared keys are accepted.

    Returns:
        A new ``InvoiceData`` with the same mode and schema.

    Raises:
        StructuredError: If a key is not declared in the schema, or a value
            does not match its declared type (the v1 message, code 1).
        ValueError: If casting is requested and no schema is available.
    """
    raw = copy.deepcopy(invoice.raw)
    custom = raw.get("custom")
    fields = dict(custom) if isinstance(custom, dict) else {}
    if cast:
        definitions = _custom_definitions(_load_schema(schema, invoice))
        fields.update({key: _cast_field(key, value, definitions) for key, value in updates.items()})
    else:
        fields.update(copy.deepcopy(dict(updates)))
    raw["custom"] = fields
    return replace(invoice, raw=raw)


def _has_label(definition: Any, wanted: str, languages: tuple[str, ...]) -> bool:
    labels = definition.get("label") if isinstance(definition, Mapping) else None
    if not isinstance(labels, Mapping):
        return False
    return any(str(labels.get(language, "")).strip() == wanted for language in languages)


def resolve_custom_key(schema: Mapping[str, Any] | Path, label: str, *, lang: Literal["ja", "en"] | None = None) -> str:
    """Return the custom field key whose schema ``label`` equals ``label``.

    Labels are compared exactly after stripping surrounding whitespace,
    against ``label.ja`` and ``label.en`` or only the language given by
    ``lang``. A field whose ja and en labels are equal matches once.

    Args:
        schema: ``invoice.schema.json`` as a mapping or a path.
        label: Label text, such as a spreadsheet header cell.
        lang: Restrict matching to one label language.

    Returns:
        The key under ``properties.custom.properties``.

    Raises:
        StructuredError: If no field, or more than one field, has the label.
    """
    wanted = label.strip()
    languages: tuple[str, ...] = (lang,) if lang is not None else _LABEL_LANGUAGES
    matches = [key for key, definition in _custom_definitions(_load_schema(schema)).items() if _has_label(definition, wanted, languages)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        msg = f"Label '{wanted}' does not match any custom field label in invoice.schema.json."
        raise StructuredError(msg)
    msg = f"Label '{wanted}' matches more than one custom field in invoice.schema.json: {', '.join(matches)}."
    raise StructuredError(msg)
