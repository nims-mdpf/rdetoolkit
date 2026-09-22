"""Observation helper for v2 runs compared against frozen v1 snapshots.

``_generate.py`` owns the v1 oracle and stays byte-frozen, so this module
reuses its walkers instead of re-implementing them: the observed keys, the
``data/`` relative POSIX form, the sort order and the ``normalize_snapshot``
volatility rules are therefore identical on both sides of a parity assertion.

The single deliberate asymmetry is ``data/logs/`` (Design §6.3 addendum,
Session I6-1 ruling #2): v1 writes ``rdesys_<ts>.log`` there while v2 writes
its RunReport JSON, so the *contents* of that one directory are excluded from
tree parity. The directory entry itself is kept, and the exclusion is applied
to both sides through :func:`parity_view`, so a frozen expected file is never
edited to make a comparison pass.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tests.v2.contract.fixtures import _generate

#: Directory whose contents are contractually excluded from tree parity.
LOGS_PREFIX = "data/logs/"

#: Observation keys produced by :func:`observe_v2_run`.
#: ``artifact_sha256`` was added by Session I-REVIEW-B (review F4): without it
#: ``thumbnail/1.jpg.write_bytes(b"broken")`` passed full parity, because the
#: other three keys compare paths, raw bytes and invoice values only.
PARITY_KEYS = ("output_tree", "raw_sha256", "invoices", "artifact_sha256")

#: Parity keys the *frozen* corpus does not carry yet. The generator emits
#: them, so every live-oracle comparison is already unconditional, but
#: ``tests/v2/contract/fixtures/expected/**`` is only rewritten by the human
#: re-freeze ritual (contracts.md §I-REVIEW-B steps (b)/(c)). Until then a
#: frozen observation legitimately lacks these keys and they are skipped; every
#: other parity key stays mandatory, so this is not a general escape hatch.
#: After step (c) this tuple becomes empty and the comparison is unconditional.
PENDING_FREEZE_KEYS = ("artifact_sha256",)


def observe_v2_run(root: Path, *, exclude_logs: bool = True) -> dict[str, Any]:
    """Observe the output artifacts a v2 run left under ``root``.

    Args:
        root: Run root that owns the ``data`` directory (or the data root).
        exclude_logs: Drop entries below ``data/logs/`` from the output tree.

    Returns:
        Normalized :data:`PARITY_KEYS` observation directly comparable with the
        same keys of a frozen v1 snapshot passed through :func:`parity_view`.
    """
    data_root = root if root.name == "data" else root / "data"
    observation = {
        "output_tree": _generate._output_tree(data_root),  # noqa: SLF001 -- frozen v1 walker is the contract
        "invoices": _generate._invoice_outputs(data_root),  # noqa: SLF001
        "raw_sha256": _generate._raw_hashes(data_root),  # noqa: SLF001
        "artifact_sha256": _generate._artifact_hashes(data_root),  # noqa: SLF001
    }
    normalized: dict[str, Any] = _generate.normalize_snapshot(observation, roots=(root,))
    return _strip_logs(normalized) if exclude_logs else normalized


def parity_view(observed: Mapping[str, Any], *, exclude_logs: bool = True) -> dict[str, Any]:
    """Project a v1 observation onto the comparable parity keys.

    Args:
        observed: The ``observed`` mapping of a frozen snapshot, or a live v1
            oracle observation produced by ``_generate``.
        exclude_logs: Drop entries below ``data/logs/`` from the output tree.

    Returns:
        A new mapping holding the available :data:`PARITY_KEYS`, log-excluded in
        memory. The frozen file on disk is never modified.

    Raises:
        KeyError: If the observation lacks a parity key that is not awaiting the
            re-freeze ritual.
    """
    missing = [key for key in PARITY_KEYS if key not in observed and key not in PENDING_FREEZE_KEYS]
    if missing:
        msg = f"v1 observation is missing mandatory parity keys: {sorted(missing)}"
        raise KeyError(msg)
    view = {key: observed[key] for key in PARITY_KEYS if key in observed}
    return _strip_logs(view) if exclude_logs else view


def pending_freeze_view(actual: Mapping[str, Any], frozen: Mapping[str, Any]) -> dict[str, Any]:
    """Narrow a live observation to what the frozen corpus can still express.

    Only :data:`PENDING_FREEZE_KEYS` are ever dropped, and only while the frozen
    snapshot genuinely lacks them. Once the human re-freeze ritual has run
    (contracts.md §I-REVIEW-B steps (b)/(c)) every snapshot carries the key,
    this function becomes the identity, and the tuple is emptied.

    Args:
        actual: Observation produced by the current generator.
        frozen: The ``observed`` mapping of a frozen snapshot.

    Returns:
        ``actual`` without the not-yet-frozen keys the expectation lacks.
    """
    return {
        key: value
        for key, value in actual.items()
        if key in frozen or key not in PENDING_FREEZE_KEYS
    }


def parity_pair(
    root: Path,
    observed: Mapping[str, Any],
    *,
    exclude_logs: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the (actual, expected) parity views for a frozen comparison.

    A frozen snapshot predating a newly added parity key would otherwise turn
    every cell RED for a missing key rather than for a behavior difference, so
    the actual observation is narrowed to the keys the expectation carries.
    Only :data:`PENDING_FREEZE_KEYS` can ever be narrowed away — anything else
    already raised in :func:`parity_view`.

    Args:
        root: Run root the v2 run wrote to.
        observed: The ``observed`` mapping of the frozen v1 snapshot.
        exclude_logs: Drop entries below ``data/logs/`` from the output tree.

    Returns:
        The observed v2 view and the frozen v1 view, ready for ``==``.
    """
    expected = parity_view(observed, exclude_logs=exclude_logs)
    actual = observe_v2_run(root, exclude_logs=exclude_logs)
    return pending_freeze_view(actual, expected), expected


def _strip_logs(observation: dict[str, Any]) -> dict[str, Any]:
    """Remove entries *below* ``data/logs/`` while keeping the directory itself."""
    tree = observation["output_tree"]
    return {
        **observation,
        "output_tree": {
            "directories": [path for path in tree["directories"] if not _below_logs(path)],
            "files": [path for path in tree["files"] if not _below_logs(path)],
        },
    }


def _below_logs(path: str) -> bool:
    return path.startswith(LOGS_PREFIX) and path != LOGS_PREFIX
