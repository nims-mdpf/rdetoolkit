"""Static access to the frozen v1 corpus for contract tests (Session K1 ruling #3).

Every expectation a v2 test compares against is a snapshot ``_generate.py``
froze from the v1 oracle; no test executes v1 itself. A case registered in the
generator whose snapshot has not been frozen yet (the window between the two
commits of the freeze ritual, contracts.md §I-REVIEW-B) makes the dependent
test skip with ``pending freeze: <path>`` -- never pass -- and only while
``_generate.ALLOW_PENDING_SNAPSHOTS`` holds. Session K1-b turns that switch off,
after which a missing snapshot or observation key is a test failure.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest

from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import PENDING_FREEZE_KEYS


def snapshot_relpath(case_id: str) -> str:
    """Return the repository-relative POSIX path of a registered case's snapshot."""
    path = _generate.oracle_case(case_id).snapshot_path()
    return path.relative_to(_generate.REPOSITORY_ROOT).as_posix()


def require_snapshot(case_id: str, *, keys: Sequence[str] = ()) -> dict[str, Any]:
    """Return the frozen payload of a registered case, or skip while it is pending.

    Args:
        case_id: ``<family>/<mode>/<stem>``, e.g. ``v1/smarttable/ok__save_table_file``.
        keys: ``observed`` keys the caller needs. A key that is still listed in
            ``observe.PENDING_FREEZE_KEYS`` and absent from the snapshot is
            pending; any other absent key is a corpus defect.

    Returns:
        The parsed snapshot (``source`` / ``case`` / ``observed``).
    """
    relpath = snapshot_relpath(case_id)
    path = _generate.oracle_case(case_id).snapshot_path()
    if not path.exists():
        if _generate.ALLOW_PENDING_SNAPSHOTS:
            pytest.skip(f"pending freeze: {relpath}")
        pytest.fail(f"missing frozen snapshot: {relpath}")
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in keys if key not in payload["observed"]]
    if missing:
        pending = _generate.ALLOW_PENDING_SNAPSHOTS and all(key in PENDING_FREEZE_KEYS for key in missing)
        if pending:
            pytest.skip(f"pending freeze: {relpath} (observed {', '.join(missing)})")
        pytest.fail(f"frozen snapshot {relpath} lacks observed key(s): {missing}")
    return payload


def frozen_observed(case_id: str, *, keys: Sequence[str] = ()) -> dict[str, Any]:
    """Return the ``observed`` mapping of a registered case (see :func:`require_snapshot`)."""
    observed: dict[str, Any] = require_snapshot(case_id, keys=keys)["observed"]
    return observed
