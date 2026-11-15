from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from rdetoolkit.graph.result import ArtifactRole

@runtime_checkable
class ArtifactSink(Protocol):
    def resolve(self, role: ArtifactRole, filename: str) -> Path: ...
    def write(self, role: ArtifactRole, filename: str, content: bytes) -> Path: ...

@dataclass(frozen=True, slots=True)
class DirectorySink:
    output_dir: Path
    main_image_dir: Path | None = None
    html_dir: Path | None = None
    def directory_for(self, role: ArtifactRole) -> Path: ...
    def resolve(self, role: ArtifactRole, filename: str) -> Path: ...
    def write(self, role: ArtifactRole, filename: str, content: bytes) -> Path: ...
