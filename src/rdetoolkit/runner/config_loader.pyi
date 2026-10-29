from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rdetoolkit.types import RdeConfig

def load_config(root: Path, overrides: Mapping[str, Any] | None = None, *, data_root: Path | None = None) -> RdeConfig: ...
