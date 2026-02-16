"""Type stubs for _invoice module."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

from rdetoolkit.models.rde2types import RdeFsPath

def _assign_invoice_val(
    invoiceobj: MutableMapping[str, Any],
    key1: str,
    key2: str,
    valobj: Any,
    invoiceschema_obj: Mapping[str, Any],
) -> None: ...
def overwrite_invoicefile_for_dpfterm(
    invoiceobj: dict[str, Any],
    invoice_dst_filepath: RdeFsPath,
    invoiceschema_filepath: RdeFsPath,
    invoice_info: Mapping[str, Any],
) -> None: ...

class InvoiceFile:
    invoice_path: Path
    schema_path: Path | None
    def __init__(self, invoice_path: Path, *, schema_path: Path | None = None) -> None: ...
    @property
    def invoice_obj(self) -> dict[str, Any]: ...
    @invoice_obj.setter
    def invoice_obj(self, value: dict[str, Any]) -> None: ...
    def __getitem__(self, key: str) -> Any: ...
    def __setitem__(self, key: str, value: Any) -> None: ...
    def __delitem__(self, key: str) -> None: ...
    def read(self, *, target_path: Path | None = None) -> dict: ...
    def overwrite(
        self,
        dst_file_path: Path | None = None,
        *,
        src_obj: dict[str, Any] | Path | str | None = None,
        schema_path: Path | None = None,
    ) -> None: ...
    def _sanitize_invoice_data(
        self, candidate: dict[str, Any], schema_path: Path | None
    ) -> dict[str, Any]: ...
    @classmethod
    def copy_original_invoice(
        cls, src_file_path: Path, dst_file_path: Path
    ) -> None: ...
