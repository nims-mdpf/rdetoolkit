"""The old -> new CLI command mapping of the v2.0 command redesign (issue #616).

This table is the single source for everything that names a renamed command:
the deprecation warnings of the v1 aliases, ``rdetoolkit migrate check``, and
the tests that keep the migration guide's mapping table complete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandRename:
    """One renamed CLI command or option.

    Attributes:
        old: The command line as users wrote it before v2.0.
        new: The command line that replaces it.
        origin: ``"v1"`` for names shipped in a stable v1 release (kept as
            deprecated aliases in v2.0.x) or ``"v2rc"`` for names that only
            existed in v2 release candidates (removed without an alias).
        pattern: Regular expression matching the old spelling after the
            ``rdetoolkit`` program name, used by ``migrate check``.
    """

    old: str
    new: str
    origin: str
    pattern: str

    @property
    def alias_kept(self) -> bool:
        """Whether the old spelling still works in v2.0.x (with a warning)."""
        return self.origin == "v1"


COMMAND_RENAMES: tuple[CommandRename, ...] = (
    CommandRename("rdetoolkit gen-config [--template X] [--overwrite]", "rdetoolkit new config [--preset X] [--force]", "v1", r"gen-config\b"),
    CommandRename("rdetoolkit gen-invoice", "rdetoolkit new invoice", "v1", r"gen-invoice\b"),
    CommandRename("rdetoolkit make-excelinvoice", "rdetoolkit new excelinvoice", "v1", r"make-excelinvoice\b"),
    CommandRename("rdetoolkit csv2graph", "rdetoolkit plot", "v1", r"csv2graph\b"),
    CommandRename("rdetoolkit artifact --output-archive", "rdetoolkit package -o", "v1", r"artifact\b"),
    CommandRename("rdetoolkit run TARGET", "rdetoolkit run --legacy TARGET", "v1", r"run\s+(?!--legacy)\S+::\S+"),
    CommandRename("rdetoolkit init --processing-template X", "rdetoolkit new processing X", "v2rc", r"init\b.*--processing-template\b"),
    CommandRename("rdetoolkit run --flow X", "rdetoolkit run X", "v2rc", r"run\b.*--flow\b"),
    CommandRename("rdetoolkit graph REPORT", "rdetoolkit report trace REPORT", "v2rc", r"graph\b"),
    CommandRename("rdetoolkit templates list|describe", "rdetoolkit skeletons list|show", "v2rc", r"templates\s+(list|describe)\b"),
    CommandRename("rdetoolkit nodes describe", "rdetoolkit nodes show", "v2rc", r"nodes\s+describe\b"),
    CommandRename("rdetoolkit flows describe", "rdetoolkit flows show", "v2rc", r"flows\s+describe\b"),
    CommandRename("rdetoolkit migrate apply --out DIR", "rdetoolkit migrate apply -o DIR", "v2rc", r"migrate\s+apply\b.*--out\b"),
)

_PROGRAM = r"(?:\brdetoolkit|-m\s+rdetoolkit)\s+"


def find_renamed_commands(text: str) -> list[CommandRename]:
    """Return the renames whose old spelling appears in ``text``.

    Args:
        text: One line of source, a shell command, or a joined argv list.

    Returns:
        Matching renames in table order; empty when the text uses current
        command names only.
    """
    return [rename for rename in COMMAND_RENAMES if re.search(_PROGRAM + rename.pattern, text)]
