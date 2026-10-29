from pathlib import Path
from rdetoolkit.types import RdeConfig

class RawArtifactService:
    def copy(self, source_files: tuple[Path, ...], *, raw_dir: Path, nonshared_raw_dir: Path, config: RdeConfig, smarttable: bool = ..., data_root: Path | None = ...) -> None: ...

class ImageArtifactService:
    def generate(self, *, main_image_dir: Path, thumbnail_dir: Path, config: RdeConfig) -> None: ...
