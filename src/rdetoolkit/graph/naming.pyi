from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

DEFAULT_BASE_STEM: Final[str]
FILENAME_COLLISION: Final[str]

@dataclass(frozen=True, slots=True)
class GraphDiagnostic:
    code: str
    severity: Literal["info", "warning"]
    message: str
    series_ids: tuple[str, ...] = ()

def sanitize_stem(text: str) -> str: ...
def collision_key(stem: str) -> str: ...
def series_stem(base: str, header_series: str | None, raw_header: str) -> str: ...
def reserve_stems(
    candidates: Sequence[tuple[str, str]],
) -> tuple[tuple[str, ...], tuple[GraphDiagnostic, ...]]: ...
