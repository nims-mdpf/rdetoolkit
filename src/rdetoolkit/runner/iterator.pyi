from collections.abc import Iterator
from pathlib import Path
from typing import Protocol
from rdetoolkit.errors import RdeValidationError

from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig

class EmptyExcelInvoiceError(RdeValidationError):
    def __init__(self) -> None: ...

def reject_empty_excelinvoice(mode: ModeKind, inputdata_path: Path) -> None: ...

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
