"""Builtin nodes for validating and saving RDE metadata."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.rde2util import Meta
from rdetoolkit.types import InvoiceData, Metadata, OutputContext

_MatchMode = Literal["key", "original_name", "both"]


def _definition_validator(source: Path | Mapping[str, Any]) -> Meta:
    if not isinstance(source, Mapping):
        return Meta(source)
    validator = Meta("")
    validator.metaDef = dict(source)
    # Meta's file reader initializes these lookup tables alongside the definition.
    for definition in source.values():
        action = definition.get("action")
        if action:
            validator.actions.append(action)
        unit = definition.get("unit")
        if unit and unit.startswith("$"):
            validator.referedmap[unit[1:]] = None
    return validator


def _source_key(key: str, definition: Mapping[str, Any], entries: Mapping[str, Any], match: _MatchMode) -> str:
    if match == "key":
        return key
    alias = cast("str", definition.get("originalName", key))
    if match == "original_name":
        return alias
    return key if key in entries else alias


def _stripped_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_stripped_value(item) for item in value]
    return value


def _variable_values(value: Any) -> Any:
    return value if value is None or isinstance(value, list) else [value]


def _assignment_values(
    values: Mapping[str, Any], repeated: Mapping[str, Sequence[Any]] | None, definitions: Mapping[str, Any],
    *, match: _MatchMode = "both", strip_strings: bool = False,
) -> dict[str, Any]:
    entries = dict(values)
    if repeated is not None:
        entries.update({key: list(column) for key, column in repeated.items()})
    assignments = dict(entries)
    for key, definition in definitions.items():
        source = _source_key(key, definition, entries, match)
        value = entries.get(source)
        if strip_strings:
            value = _stripped_value(value)
        # Explicit None blocks Meta's own alias fallback for unmatched definitions.
        assignments[key] = _variable_values(value) if definition.get("variable") else value
    return assignments


def _build_metadata(
    values: Mapping[str, Any], metadef_path: Path | Mapping[str, Any], repeated: Mapping[str, Sequence[Any]] | None = None,
    *, match: _MatchMode = "both", keep_empty_strings: bool = False, strip_strings: bool = False,
) -> Metadata:
    validator = _definition_validator(metadef_path)
    assignments = _assignment_values(values, repeated, validator.metaDef, match=match, strip_strings=strip_strings)
    validator.assign_vals(assignments, ignore_empty_strvalue=not keep_empty_strings)
    payload = validator.to_dict()
    constant = payload["constant"]
    return Metadata(
        custom={key: cell["value"] for key, cell in constant.items()},
        units={key: cell["unit"] for key, cell in constant.items() if "unit" in cell},
        variable=payload["variable"],
    )


@node(tags=["builtin", "meta"], version="2.0.0", idempotent=True)
def build_meta(
    values: Mapping[str, Any], metadef_path: Path | Mapping[str, Any], *, repeated: Mapping[str, Sequence[Any]] | None = None,
    match: _MatchMode = "both", keep_empty_strings: bool = False,
) -> Metadata:
    """Build metadata by applying the RDE metadata definition to measured values.

    Undefined keys and absent values are excluded. Values are converted using
    ``schema.type`` and ``schema.format``; literal units and ``$Key`` references
    are resolved in definition order. Scalar values declared variable become a
    single repeated row. The shared conversion engine keeps v1 output parity
    without requiring v1 objects or adapters in user flows.

    By default, source keys follow v1 ``Meta.assign_vals``: each definition reads the
    value stored under its own definition key and falls back to its
    ``originalName`` only when the definition key is absent from the input.
    The definition key therefore wins when both spellings are present, and
    a definition key present with a None value is excluded without falling
    back. ``match="key"`` disables alias matching; ``match="original_name"``
    uses only the alias where one is declared, or the definition key otherwise.
    Strings are stripped before the emptiness check. Empty strings are omitted
    by default; ``keep_empty_strings=True`` retains them when the schema accepts
    them, including in variable rows. Non-string schema validation still applies.

    Args:
        values: Measured values keyed by definition key or ``originalName``,
            including optional unit-reference sources.
        metadef_path: Path to ``metadata-def.json`` or a definition Mapping.
            Pass a filtered Mapping to select definitions without a temporary file.
        repeated: Columns of repeated values for variable definitions. These
            override same-named entries in ``values`` and may differ in length.
        match: Source matching mode: ``key``, ``original_name`` or ``both``.
            The default ``both`` gives definition keys precedence.
        keep_empty_strings: Retain stripped empty strings instead of omitting them.

    Returns:
        Metadata ready for ``save_meta`` with typed values, units and rows.

    Raises:
        RdeConfigError: With code 1004 if ``match`` is unsupported.
        StructuredError: If a value violates the metadata definition.
        OSError: If the definition cannot be read.
        json.JSONDecodeError: If the definition is not valid JSON.
    """
    if match not in ("key", "original_name", "both"):
        error_cls: Any = RdeConfigError
        raise error_cls(code=1004, message=ERROR_CATALOG[1004].message_template.format(mode=match))
    return _build_metadata(values, metadef_path, repeated, match=match, keep_empty_strings=keep_empty_strings, strip_strings=True)


@node(tags=["builtin", "meta"], version="2.0.0", idempotent=True)
def parse_invoice_meta(invoice: InvoiceData, metadef_path: Path) -> Metadata:
    """Validate invoice fields against a metadata definition.

    This is the v2 node form of ``rde2util.Meta.__init__`` and
    ``Meta.assign_vals``. Its ``StructuredError`` validation failures are
    intentionally preserved for migration parity.

    Args:
        invoice: Parsed invoice data.
        metadef_path: Path to ``metadata-def.json``.

    Returns:
        Metadata containing definition-assigned custom fields.

    Raises:
        StructuredError: If a field violates the v1 metadata definition.
        OSError: If the metadata definition cannot be read.
    """
    custom_fields = invoice.get_custom_fields()
    metadata = _build_metadata(custom_fields, metadef_path)
    basic = invoice.raw.get("basic")
    metadata.basic = basic if isinstance(basic, dict) else None
    return metadata


@node(tags=["builtin", "meta"], version="2.0.0", idempotent=True)
def save_meta(metadata: Metadata, out: OutputContext, *, indent: int | None = 4) -> Path:
    """Save v2 metadata as the RDE ``metadata.json`` contract.

    Constant custom values carry the corresponding ``metadata.units`` entry,
    when present. Repeated cells come from ``metadata.variable`` and retain
    their per-row units. The resulting shape matches the v1 metadata contract,
    and the default four-space indentation matches v1 ``Meta.writefile``
    byte for byte.

    ``metadata.basic`` is deliberately not written: ``metadata.json`` has no
    slot for invoice basic information, and v1 never wrote it there.

    Args:
        metadata: Metadata to serialize.
        out: Output resource context.
        indent: JSON indentation, as for ``json.dumps``.

    Returns:
        Path to ``metadata.json`` under ``out.meta``.
    """
    content = {
        "constant": {
            key: {"value": value, **({"unit": metadata.units[key]} if key in metadata.units else {})}
            for key, value in metadata.custom.items()
        },
        "variable": metadata.variable,
    }
    encoded = json.dumps(content, ensure_ascii=False, indent=indent).encode("utf-8")
    return out.write_bytes("meta", "metadata.json", encoded)
