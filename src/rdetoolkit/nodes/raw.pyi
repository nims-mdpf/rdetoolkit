from collections.abc import Sequence
from pathlib import Path

from rdetoolkit.types import OutputContext, RdeConfig

def remove_raw_copy(out: OutputContext, config: RdeConfig, filename: str) -> list[Path]: ...
def replace_raw_copy(out: OutputContext, config: RdeConfig, filename: str, members: Sequence[Path]) -> list[Path]: ...
