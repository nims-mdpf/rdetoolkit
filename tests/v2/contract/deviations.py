"""Deliberate v2 departures from the frozen v1 corpus, projected out in one place.

The frozen snapshots are the only record of v1's observations and are never
edited (``_generate.py``). When v2 changes a v1 behavior on purpose, the live
observation is projected back onto the v1 view here, so every parity cell keeps
comparing everything else. Each departure is pinned positively by its own test,
because what is projected away here is no longer checked by parity.

Departures:

* #525 -- SmartTable backs the original invoice up to
  ``data/logs/invoice_org.json`` and hands that file to the flow and to the v1
  callback as ``invoice_org``. v1 handed over ``data/invoice/invoice.json``,
  which tile 0 overwrites with its merged row invoice. Projected out: the
  backup's tree entry and digest (seen only when ``data/logs`` content is
  observed) and the callback's ``invoice_org`` path. Pinned by ``tests/v2/runner/test_issue_525_smarttable_invoice_org.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: The run-level invoice backup, as a ``data/``-relative observation path.
SMARTTABLE_BACKUP = "data/logs/invoice_org.json"

#: The ``invoice_org`` v1 handed to a SmartTable callback.
V1_SMARTTABLE_INVOICE_ORG = "data/invoice/invoice.json"


def to_v1_view(observation: Mapping[str, Any], data_root: Path) -> dict[str, Any]:
    """Project a v2 run observation onto what the frozen v1 corpus recorded.

    Args:
        observation: Normalized observation of a v2 run.
        data_root: The run's ``data`` directory, used to recognize the mode.

    Returns:
        A new mapping; the observation is returned unchanged unless the run was
        a SmartTable run.
    """
    view = dict(observation)
    if not _is_smarttable_run(data_root):
        return view
    tree = view.get("output_tree")
    if tree is not None:
        view["output_tree"] = {**tree, "files": [path for path in tree["files"] if path != SMARTTABLE_BACKUP]}
    artifacts = view.get("artifact_sha256")
    if artifacts is not None:
        view["artifact_sha256"] = {path: digest for path, digest in artifacts.items() if path != SMARTTABLE_BACKUP}
    calls = view.get("callback_paths")
    if calls is not None:
        view["callback_paths"] = [_v1_callback_paths(call) for call in calls]
    return view


def _v1_callback_paths(call: Mapping[str, Any]) -> dict[str, Any]:
    output = call.get("output")
    if output is None or output.get("invoice_org") != SMARTTABLE_BACKUP:
        return dict(call)
    return {**call, "output": {**output, "invoice_org": V1_SMARTTABLE_INVOICE_ORG}}


def _is_smarttable_run(data_root: Path) -> bool:
    """Return whether the inputs select SmartTable mode (a ``smarttable_*`` table)."""
    inputdata = data_root / "inputdata"
    return inputdata.is_dir() and any(path.name.startswith("smarttable_") for path in inputdata.iterdir())
