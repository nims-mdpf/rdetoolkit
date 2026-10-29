"""Real, file-backed ``ProcessingTemplate`` fixture that violates
``E2101 TemplateSlotMissing`` at import time (Session F2, Conflict #8).

This module is intentionally UNIMPORTABLE: evaluating
``LintMissingSlotOffender``'s class body triggers
``ProcessingTemplate.__init_subclass__`` (Design §5.2.2 point 2), which must
raise ``rdetoolkit.errors.RdeRegistryError(code=2101, ...)`` because the
``read`` slot declared by ``LintSkeletonWithSlot`` is never overridden here.

Used exclusively by ``tests/v2/cli/test_cli_nodes.py``'s ``nodes lint
--module <this dotted path>`` case (Conflict #8): the lint command's
``load_modules()`` call must catch this import-time ``RdeRegistryError`` and
report it as a clean lint message (never a raw traceback). It must NEVER be
imported directly by any other test -- doing so would raise on import, by
design.
"""

from __future__ import annotations

from typing import final

from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths


class LintSkeletonWithSlot(ProcessingTemplate):
    """Depth-1 skeleton fixture: declares one required slot, ``read``."""

    @slot
    def read(self, paths: InputPaths) -> None: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        self.read(paths)


class LintMissingSlotOffender(LintSkeletonWithSlot):
    """Depth-2 subclass that never overrides ``read`` -> E2101 at import
    time. Deliberately has no body beyond the docstring."""
