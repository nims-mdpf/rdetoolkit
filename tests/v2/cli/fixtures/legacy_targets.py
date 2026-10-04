"""v1 dataset callbacks resolvable as ``rdetoolkit run <module>::<attr>``.

Session J2 ruling #3 gives the CLI's legacy target the uniform 0/1/2/3 exit
contract, so TC-CLI-RUN-EP-016..018 need three callbacks whose outcomes are
exactly success, failure and per-tile failure. They live in a dotted-importable
module because ``cli/app.py::_load_target_function`` rejects anything that is
not a plain function taking two positional arguments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdetoolkit.exceptions import StructuredError

#: Marker a callback appends one line to per invocation, in the process CWD.
#: It is the tile counter the per-tile failure callback keys off, and it stays
#: outside ``data/`` so it never becomes an observed artifact.
CALL_MARKER_NAME = ".legacy_target_calls"

#: ``ecode``/message the failing callbacks raise. 999 is v1's own "unexpected"
#: code, so job.failed carries a value a v1 operator recognizes.
FAILURE_CODE = 999
FAILURE_MESSAGE = "legacy target failed. Remediation: fix the CLI fixture input."

#: Tile the per-tile callback fails. Index 1 of a two-tile family is the only
#: choice that produces one completed and one failed tile, which is what
#: distinguishes a partial run from a failed one.
FAILING_TILE_INDEX = 1


def _record_call() -> int:
    """Append one invocation to the marker and return the new call count."""
    marker = Path(CALL_MARKER_NAME)
    with marker.open("a", encoding="utf-8") as stream:
        stream.write("called\n")
    return len(marker.read_text(encoding="utf-8").splitlines())


def call_count(root: Path) -> int:
    """Return how many times a fixture callback ran under ``root``."""
    marker = root / CALL_MARKER_NAME
    if not marker.exists():
        return 0
    return len(marker.read_text(encoding="utf-8").splitlines())


def succeeds(srcpaths: Any, resource_paths: Any) -> None:
    """TC-CLI-RUN-EP-016: a callback that does nothing and returns."""
    del srcpaths, resource_paths
    _record_call()


def always_fails(srcpaths: Any, resource_paths: Any) -> None:
    """TC-CLI-RUN-EP-017: a callback that fails on every tile.

    Raises:
        StructuredError: Always, with v1's ``ecode`` 999.
    """
    del srcpaths, resource_paths
    _record_call()
    raise StructuredError(FAILURE_MESSAGE, ecode=FAILURE_CODE)


def second_tile_fails(srcpaths: Any, resource_paths: Any) -> None:
    """TC-CLI-RUN-EP-018: a callback that fails only tile 1.

    Raises:
        StructuredError: On tile :data:`FAILING_TILE_INDEX` only.
    """
    del srcpaths, resource_paths
    if _record_call() == FAILING_TILE_INDEX + 1:
        raise StructuredError(FAILURE_MESSAGE, ecode=FAILURE_CODE)
