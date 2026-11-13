from collections.abc import Sequence
from dataclasses import dataclass

PANEL_SCAFFOLD: str
PANEL_GENERATE: str
PANEL_VALIDATE: str
PANEL_RUN: str
PANEL_INSPECT: str
PANEL_PACKAGE: str
PANEL_MIGRATE: str
PANEL_INFO: str
PANEL_DEPRECATED: str
SECTION_EXAMPLES: str
SECTION_EXIT_CODES: str
EXIT_OK: tuple[int, str]
EXIT_V1_FAILED: tuple[int, str]
EXIT_CLICK_USAGE: tuple[int, str]
EXIT_USAGE: tuple[int, str]

@dataclass(frozen=True)
class CommandHelp:
    summary: str
    examples: Sequence[str]
    exit_codes: Sequence[tuple[int, str]]
    inputs: Sequence[str] = ...
    outputs: Sequence[str] = ...
    see_also: Sequence[str] = ...
    details: str = ...
    def render(self) -> str: ...

def deprecation_message(old: str, new: str) -> str: ...
