"""Builtin nodes for validating and saving RDE metadata."""

from __future__ import annotations

import json
from pathlib import Path

from rdetoolkit.core.node import node
from rdetoolkit.rde2util import Meta
from rdetoolkit.types import InvoiceData, Metadata, OutputContext


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
    validator = Meta(metadef_path)
    assignment = validator.assign_vals(custom_fields)
    assigned = assignment["assigned"]
    custom = {key: value for key, value in custom_fields.items() if key in assigned}
    basic = invoice.raw.get("basic")
    return Metadata(custom=custom, basic=basic if isinstance(basic, dict) else None)


@node(tags=["builtin", "meta"], version="2.0.0", idempotent=True)
def save_meta(metadata: Metadata, out: OutputContext) -> Path:
    """Save v2 metadata as the RDE ``metadata.json`` contract.

    Migrated from ``retired/outputcontext_save_methods_v20.py::save_meta``.
    The written shape is the one v1 ``rde2util.Meta.writefile`` produced and
    the Runner's post-validation (``metadata_validate`` against
    ``models.metadata.MetadataItem``) requires: every custom field becomes a
    ``constant`` entry ``{"value": ...}`` and ``variable`` is an empty list.

    ``metadata.basic`` is deliberately not written: ``metadata.json`` has no
    slot for invoice basic information, and v1 never wrote it there.

    Args:
        metadata: Metadata to serialize.
        out: Output resource context.

    Returns:
        Path to ``metadata.json`` under ``out.meta``.
    """
    content = {
        "constant": {key: {"value": value} for key, value in metadata.custom.items()},
        "variable": [],
    }
    encoded = json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
    return out.write_bytes("meta", "metadata.json", encoded)
