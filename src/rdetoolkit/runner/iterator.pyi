from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig

class TileIterator(Protocol):
    def __call__(
        self,
        mode: ModeKind,
        inputdata_path: Path,
        unpacked_dir_path: Path,
        data_root: Path,
        config: RdeConfig | None = ...,
    ) -> Iterator[tuple[IterationInfo, InputPaths, OutputContext]]: ...

def iterate_tiles(
    mode: ModeKind,
    inputdata_path: Path,
    unpacked_dir_path: Path,
    data_root: Path,
    config: RdeConfig | None = ...,
) -> Iterator[tuple[IterationInfo, InputPaths, OutputContext]]: ...
