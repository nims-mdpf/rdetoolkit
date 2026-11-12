from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from rdetoolkit.types import InvoiceData

def set_custom_fields(invoice: InvoiceData, updates: Mapping[str, Any], *, schema: Mapping[str, Any] | Path | None = None, cast: bool = True) -> InvoiceData: ...
def resolve_custom_key(schema: Mapping[str, Any] | Path, label: str, *, lang: Literal["ja", "en"] | None = None) -> str: ...
