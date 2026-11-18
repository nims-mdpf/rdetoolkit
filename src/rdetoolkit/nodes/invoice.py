"""Builtin helpers for editing the invoice ``custom`` section by schema."""

from __future__ import annotations

import copy
import datetime as dt
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json
from rdetoolkit.invoicefile._description import compose_feature_description
from rdetoolkit.rde2util import ValueCaster, castval
from rdetoolkit.types import InvoiceData, Metadata

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


def _catalog_error(code: int, **fields: str) -> StructuredError:
    """Return a ``StructuredError`` carrying a catalog code and its remediation (#621).

    A ``StructuredError`` keeps its own code through ``@flow(error_code=...)``,
    and the remediation reaches ``job.failed`` through the message.
    """
    definition = ERROR_CATALOG[code]
    return StructuredError(f"{definition.message_template.format(**fields)} Remediation: {definition.remediation}", ecode=code)


def _custom_definitions(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    custom = schema.get("properties", {}).get("custom", {}) if isinstance(schema.get("properties"), Mapping) else {}
    definitions = custom.get("properties", {}) if isinstance(custom, Mapping) else {}
    return definitions if isinstance(definitions, Mapping) else {}


def _is_missing(value: Any) -> bool:
    """Return whether a scalar is a missing cell: None, NaN, NaT or ``pd.NA``, in any pandas / NumPy form."""
    return value is None or (pd.api.types.is_scalar(value) and bool(pd.isna(value)))


def _to_python(value: Any) -> Any:
    """Return the plain Python value of a NumPy scalar, so the stored value serializes as JSON."""
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).to_pydatetime()
    if isinstance(value, np.generic):
        return value.item()
    return value


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
    value = _to_python(value)
    if value_type == "string":
        return _cast_string(value, fmt)
    if value_type == "integer" and isinstance(value, float) and value.is_integer():
        return int(value)
    return castval(value, value_type, None)


def _definition(key: str, definitions: Mapping[str, Any]) -> Mapping[str, Any]:
    definition = definitions.get(key)
    if not isinstance(definition, Mapping):
        raise _catalog_error(4011, key=key)
    return definition


def _cast_field(key: str, value: Any, definition: Mapping[str, Any]) -> Any:
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
    keep_empty_strings: bool = False,
) -> InvoiceData:
    """Return a copy of the invoice with ``custom`` values cast by the invoice schema.

    This is the v2 form of the v1 ``invoicefile._assign_invoice_val`` /
    ``rde2util.castval`` update of ``invoice.custom``. Each value is cast by
    its ``properties.custom.properties.<key>`` ``type`` and ``format``:

    - ``None``, NaN, NaT or ``pandas.NA`` (in any pandas / NumPy form, as
      in a frame read with ``dtype_backend="numpy_nullable"``) is stored as
      ``None`` for every type; filter such values out beforehand to keep
      the old value. Other NumPy scalars are cast as their Python value.
    - ``boolean``: the strings ``"true"`` / ``"false"`` (case-insensitive,
      surrounding spaces ignored); any other value by Python truthiness.
    - ``integer``: digits with an optional trailing unit (``"12 mm"`` -> 12)
      or an integral float (``3.0`` -> 3).
    - ``number``: as ``integer`` when the text is integral, else a float.
    - ``string`` with format ``date`` / ``date-time`` / ``time``: parsed by
      dateutil and written as ``YYYY-MM-DD`` / ISO 8601 / ``HH:MM:SS``;
      ``datetime.date`` and ``datetime.datetime`` values are accepted.
      Any other string format, or none, keeps the value unchanged,
      including a non-string value (v1 ``castval``). Such a value then
      fails the invoice validation after processing (``1.5 is not of
      type 'string'``, ErrorCode 4001), so convert it deliberately. To
      keep the digits as entered (``1.50``), read the cell as text
      (``read_excel(..., dtype=str)``): ``str(1.5)`` cannot restore them.

    A string that is empty after stripping whitespace is not applied by
    default, for every type: the key keeps its current value in
    ``custom``, or stays absent, as ``build_meta`` omits empty strings.
    With ``keep_empty_strings=True`` the string is cast like any other
    value: stored unchanged for a ``string`` field without a date format,
    a type mismatch for ``integer`` / ``number`` / ``boolean`` and the
    date formats. An undeclared key is rejected even with an empty value.

    Keys keep their position in ``custom``; new keys are appended. The input
    invoice is never modified.

    Args:
        invoice: Parsed invoice to update.
        updates: New values keyed by custom field key. Use
            ``resolve_custom_key`` to translate schema labels.
        schema: ``invoice.schema.json`` as a mapping or a path. Defaults to
            ``invoice.schema``, which the Runner fills with
            ``tasksupport/invoice.schema.json`` in every mode.
        cast: When false, values are stored as given and the schema is not
            read, so undeclared keys are accepted. Empty strings are then
            stored as well.
        keep_empty_strings: Cast empty and whitespace-only strings instead
            of skipping them.

    Returns:
        A new ``InvoiceData`` with the same mode and schema.

    Raises:
        StructuredError: If a key is not declared in the schema (code 4011
            ``InvoiceCustomKeyUndefined``), or a value does not match its
            declared type (the v1 message, code 1).
        ValueError: If casting is requested and no schema is available.
    """
    raw = copy.deepcopy(invoice.raw)
    custom = raw.get("custom")
    fields = dict(custom) if isinstance(custom, dict) else {}
    if cast:
        definitions = _custom_definitions(_load_schema(schema, invoice))
        for key, value in updates.items():
            definition = _definition(key, definitions)
            if keep_empty_strings or not (isinstance(value, str) and not value.strip()):
                fields[key] = _cast_field(key, value, definition)
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
        StructuredError: If no field has the label (code 4012
            ``InvoiceCustomLabelUnknown``), or more than one field has it
            (code 4013 ``InvoiceCustomLabelAmbiguous``).
    """
    wanted = label.strip()
    languages: tuple[str, ...] = (lang,) if lang is not None else _LABEL_LANGUAGES
    matches = [key for key, definition in _custom_definitions(_load_schema(schema)).items() if _has_label(definition, wanted, languages)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise _catalog_error(4012, label=wanted)
    raise _catalog_error(4013, label=wanted, keys=", ".join(matches))


def _metadata_json(metadata: Metadata | Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(metadata, Metadata):
        return metadata
    # The metadata.json shape save_meta writes, which the Runner reads back.
    constant = {key: {"value": value} for key, value in metadata.custom.items()}
    return {"constant": constant, "variable": metadata.variable}


@node(tags=["builtin", "invoice"], version="2.0.0", idempotent=True)
def describe_features(
    invoice: InvoiceData,
    metadata: Metadata | Mapping[str, Any],
    metadef_path: Path | Mapping[str, Any],
) -> InvoiceData:
    """Return a copy of the invoice with ``_feature`` metadata in its description.

    This is the formatting the Runner applies after the flow when
    ``system.feature_description`` is enabled (v1
    ``update_description_with_features``), for programs that build or edit
    the description themselves. For each ``metadata-def.json`` definition
    marked ``_feature``, in definition order, one line
    ``<name.ja>(<unit>):<value>`` is appended to ``basic.description``; a
    variable field gives its single value, or ``[A,B]`` for several rows,
    and a field without a value adds nothing.

    The Runner still appends the same lines to the saved ``invoice.json``
    unless ``system.feature_description`` is false, so set it to false in
    ``rdeconfig.yaml`` when a flow saves the result of this node.

    Args:
        invoice: Parsed invoice to update; it is not modified.
        metadata: Metadata as built by ``build_meta``, or ``metadata.json``
            content with ``constant`` and ``variable`` sections.
        metadef_path: Path to ``metadata-def.json`` or its content.

    Returns:
        A new ``InvoiceData`` with the same mode and schema.

    Raises:
        ValueError: If the invoice has no ``basic`` object.
        StructuredError: If the definition file cannot be read.
        KeyError: If a ``_feature`` definition has no ``name.ja``.
    """
    raw = copy.deepcopy(invoice.raw)
    basic = raw.get("basic")
    if not isinstance(basic, dict):
        msg = "describe_features needs an invoice with a 'basic' object"
        raise ValueError(msg)
    definitions = readf_json(metadef_path) if isinstance(metadef_path, Path) else metadef_path
    basic["description"] = compose_feature_description(basic.get("description"), definitions, _metadata_json(metadata))
    return replace(invoice, raw=raw)
