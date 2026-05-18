"""Backward-compatible re-exports for validation helpers.

The implementation lives in :mod:`rdetoolkit.domain.validation`.
"""

from __future__ import annotations

from rdetoolkit.domain.validation import (  # noqa: F401
    InvoiceValidator,
    MetadataDefinitionValidator,
    MetadataValidator,
    invoice_validate,
    metadata_validate,
)
