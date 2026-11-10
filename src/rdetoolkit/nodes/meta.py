"""Builtin nodes for validating and saving RDE metadata."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from rdetoolkit.core.node import node
from rdetoolkit.rde2util import Meta
from rdetoolkit.types import InvoiceData, Metadata, OutputContext


def _variable_values(value: Any) -> Any:
    return value if value is None or isinstance(value, list) else [value]


def _assignment_values(values: Mapping[str, Any], repeated: Mapping[str, Sequence[Any]] | None, definitions: Mapping[str, Any]) -> dict[str, Any]:
    entries = dict(values)
    if repeated is not None:
        entries.update({key: list(column) for key, column in repeated.items()})
    assignments = dict(entries)
    for key, definition in definitions.items():
        source = key if key in entries else definition.get("originalName", key)
        if source in entries:
            value = entries[source]
            assignments[key] = _variable_values(value) if definition.get("variable") else value
    return assignments


def _build_metadata(values: Mapping[str, Any], metadef_path: Path, repeated: Mapping[str, Sequence[Any]] | None = None) -> Metadata:
    validator = Meta(metadef_path)
    validator.assign_vals(_assignment_values(values, repeated, validator.metaDef))
    payload = validator.to_dict()
    constant = payload["constant"]
    return Metadata(
        custom={key: cell["value"] for key, cell in constant.items()},
        units={key: cell["unit"] for key, cell in constant.items() if "unit" in cell},
        variable=payload["variable"],
    )


@node(tags=["builtin", "meta"], version="2.0.0", idempotent=True)
def build_meta(values: Mapping[str, Any], metadef_path: Path, *, repeated: Mapping[str, Sequence[Any]] | None = None) -> Metadata:
    """Build metadata by applying the RDE metadata definition to measured values.

    Undefined keys and absent values are excluded. Values are converted using
    ``schema.type`` and ``schema.format``; literal units and ``$Key`` references
    are resolved in definition order. Scalar values declared variable become a
    single repeated row. The shared conversion engine keeps v1 output parity
    without requiring v1 objects or adapters in user flows.

    Source keys follow v1 ``Meta.assign_vals``: each definition reads the
    value stored under its own definition key and falls back to its
    ``originalName`` only when the definition key is absent from the input.
    The definition key therefore wins when both spellings are present, and
    a definition key present with a None value is excluded without falling
    back. Programs that preferred the ``originalName`` spelling must map
    those values onto the definition keys before calling this node.

    Args:
        values: Measured values keyed by definition key or ``originalName``,
            including optional unit-reference sources.
        metadef_path: Path to ``metadata-def.json``.
        repeated: Columns of repeated values for variable definitions. These
            override same-named entries in ``values`` and may differ in length.

    Returns:
        Metadata ready for ``save_meta`` with typed values, units and rows.

    Raises:
        StructuredError: If a value violates the metadata definition.
        OSError: If the definition cannot be read.
        json.JSONDecodeError: If the definition is not valid JSON.
    """
    return _build_metadata(values, metadef_path, repeated)


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
