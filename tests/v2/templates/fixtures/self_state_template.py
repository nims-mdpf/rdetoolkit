"""Real, file-backed ``ProcessingTemplate`` fixture exercising
``W1101 TemplateSelfStateUsage`` (Session F2, Conflict #8, Known Trap #5).

Unlike the E2101-E2105 codes, W1101 is *not* raised at import time (Design
§5.2.2 point 3: it is an advisory, detected only by ``nodes lint``'s own
static source inspection). This module must therefore import CLEANLY (no
E2101-E2105 violations) -- only ``nodes lint``'s heuristic
``inspect.getsource``-based check may flag it, which is why this fixture
must be a real, on-disk, source-backed module: dynamically ``exec``-built
classes have no backing source file for ``inspect.getsource`` to read.

Used by ``tests/v2/cli/test_cli_nodes.py``'s ``nodes lint --module <this
dotted path>`` case.
"""

from __future__ import annotations

from typing import final

from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths


class SelfStateSkeleton(ProcessingTemplate):
    """Depth-1 skeleton fixture: a single required slot, ``read``."""

    @slot
    def read(self, paths: InputPaths) -> None: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        self.read(paths)


class SelfStateOffender(SelfStateSkeleton):
    """Depth-2 subclass that stores state on ``self`` outside ``__init__``
    and is otherwise fully valid (imports cleanly, no E2101-E2105
    violation) -- exactly the anti-pattern Design §5.2.2 point 3 forbids by
    convention and ``nodes lint`` must flag as an advisory (W1101), not a
    hard import-time error."""

    def read(self, paths: InputPaths) -> None:
        # Self-state write outside __init__: forbidden by convention
        # (Design §5.2.2 point 3) -- slots must pass values explicitly
        # through the skeleton's __flow__, never stash them on self for a
        # later call to read back.
        self.last_paths = paths  # noqa: B010 - intentional W1101 trigger
        return None
