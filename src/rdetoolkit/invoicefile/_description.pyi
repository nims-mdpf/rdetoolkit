from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rdetoolkit.fileops import writef_json as writef_json
from rdetoolkit.models.rde2types import RdeOutputResourcePath as RdeOutputResourcePath

def backup_invoice_json_files(excel_invoice_file: Path | None, mode: str | None) -> Path: ...
def compose_feature_description(description: str | None, metadata_def_obj: Mapping[str, Any], metadata_json_obj: Mapping[str, Any]) -> str: ...
def update_description_with_features(rde_resource: RdeOutputResourcePath, dst_invoice_json: Path, metadata_def_json: Path) -> None: ...
