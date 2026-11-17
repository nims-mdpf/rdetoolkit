from pathlib import Path
from typing import Literal

from rdetoolkit.types import RdeConfig

ConfigOrigin = Literal["v1", "v2"]

class ConfigNormalizer:
    def normalize(
        self,
        source: object | None,
        *,
        root: Path,
        origin: ConfigOrigin,
        data_root: Path | None = None,
    ) -> RdeConfig: ...

def _find_tasksupport_config(data_root: Path) -> Path | None: ...
def _load_optional_mapping(path: Path) -> dict[str, Any] | None: ...
