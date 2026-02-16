"""Type stubs for _magic_variable module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdetoolkit.models.rde2types import RdeDatasetPaths

class MagicVariableResolver:
    MIN_INVOICE_FIELD_SEGMENTS: int
    MIN_METADATA_SEGMENTS: int
    rawfile_path: Path
    invoice_source: dict[str, Any]
    metadata_source: dict[str, Any] | None
    def __init__(
        self,
        *,
        rawfile_path: Path,
        invoice_source: dict[str, Any],
        metadata_source: dict[str, Any] | None,
    ) -> None: ...
    def expand(self, template: str) -> str: ...
    def _trim_redundant_underscore(
        self, literal: str, result_parts: list[str], skip_pending: bool
    ) -> str: ...
    def _resolve_expression(self, expression: str) -> str | None: ...
    def _resolve_invoice_expression(
        self, segments: list[str], expression: str
    ) -> str | None: ...
    def _resolve_sample_expression(
        self, segments: list[str], expression: str
    ) -> str | None: ...
    def _resolve_metadata_expression(
        self, segments: list[str], expression: str
    ) -> str | None: ...
    def _normalize_scalar(self, value: Any, expression: str) -> str | None: ...

def _load_metadata(dataset_paths: RdeDatasetPaths | None) -> dict[str, Any] | None: ...
def apply_magic_variable(
    invoice_path: str | Path,
    rawfile_path: str | Path,
    *,
    save_filepath: str | Path | None = None,
    dataset_paths: RdeDatasetPaths | None = None,
) -> dict[str, Any]: ...
