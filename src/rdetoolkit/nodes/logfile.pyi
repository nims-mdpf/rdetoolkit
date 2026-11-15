import logging
from pathlib import Path
from types import TracebackType
from typing import Literal

from rdetoolkit.types import OutputContext, OutputKind

DEFAULT_LOG_FORMAT: str

class ArtifactLogger:
    def __init__(self, logger: logging.Logger, path: Path, *, fmt: str, level: int, mode: str, encoding: str) -> None: ...
    @property
    def logger(self) -> logging.Logger: ...
    @property
    def path(self) -> Path: ...
    def __enter__(self) -> logging.Logger: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...

def artifact_logger(
    out: OutputContext,
    filename: str,
    *,
    name: str | None = None,
    kind: OutputKind = "struct",
    fmt: str = ...,
    level: int = ...,
    mode: Literal["a", "w"] = "a",
    encoding: str = "utf-8",
) -> ArtifactLogger: ...
