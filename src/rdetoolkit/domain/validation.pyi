from _typeshed import Incomplete as Incomplete
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rdetoolkit.errors import RdeValidationError

class MetadataValidator:
    schema: Incomplete
    def __init__(self) -> None: ...
    def validate(self, *, path: str | Path | None = None, json_obj: dict[str, Any] | None = None) -> dict[str, Any]: ...

class MetadataDefinitionValidator:
    schema: Incomplete
    def __init__(self) -> None: ...
    def validate(self, *, path: str | Path | None = None, json_obj: dict[str, Any] | None = None) -> dict[str, Any]: ...

def metadata_validate(path: str | Path) -> None: ...

class InvoiceValidator:
    pre_basic_info_schema: Incomplete
    schema_path: Incomplete
    schema: Incomplete
    def __init__(self, schema_path: str | Path) -> None: ...
    def validate(
        self,
        *,
        path: str | Path | None = None,
        obj: Mapping[str, Any] | None = None,
        preserve_none_values: bool = False,
    ) -> dict[str, Any]: ...

def invoice_validate(path: str | Path, schema: str | Path) -> None: ...

def validate_tile_outputs(*, invoice_path: Path, schema_path: Path, metadata_path: Path) -> None: ...
def wrap_validation_error(exc: Exception) -> RdeValidationError: ...
