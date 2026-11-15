from collections.abc import Sequence
from typing import Final

__all__ = ["ARBITRARY_UNIT", "group_units", "normalize_unit"]

ARBITRARY_UNIT: Final[str]

def normalize_unit(unit: str | None) -> str | None: ...
def group_units(units: Sequence[str | None]) -> tuple[tuple[int, ...], tuple[str | None, ...]]: ...
