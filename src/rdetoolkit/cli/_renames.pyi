from dataclasses import dataclass

@dataclass(frozen=True)
class CommandRename:
    old: str
    new: str
    origin: str
    pattern: str
    @property
    def alias_kept(self) -> bool: ...

COMMAND_RENAMES: tuple[CommandRename, ...]

def find_renamed_commands(text: str) -> list[CommandRename]: ...
