from typing import Any

from rdetoolkit.domain.magic import MagicOptions, ResolutionPreview
from rdetoolkit.models.rde2types import RdeDatasetPaths

def apply_interpolation(
    dataset_paths: RdeDatasetPaths,
    *,
    original_invoice_snapshot: str | None,
    options: MagicOptions,
    iteration_index: int,
    mode: str,
) -> ResolutionPreview: ...

def validate_templates(invoice: dict[str, Any], options: MagicOptions) -> bool: ...
