"""Release PR #553 review fix F6-1 (Session K4-F6).

``save_meta`` must write the RDE ``metadata.json`` contract that the Runner's
post-validation (``domain.validation.metadata_validate``) enforces, so a flow
that only saves metadata ends in ``success`` (v1 ``Meta.writefile`` shape).

EP table:

| TC-ID          | Partition                                              | Expected                                            |
|----------------|--------------------------------------------------------|-----------------------------------------------------|
| TC-K4F6-EP-001 | flow body is only save_meta(Metadata(custom=...), out) | report success, error None, metadata.json validates |

Negative partitions (the shape the validator rejects) are pinned by the unit
tests in ``tests/v2/nodes/test_meta.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.domain.validation import metadata_validate
from rdetoolkit.nodes.meta import save_meta
from rdetoolkit.types import Metadata, OutputContext
from tests.v2.runner.test_event_log_robustness_k4 import _full_runner


@flow
def _save_meta_only_flow(out: OutputContext) -> None:
    save_meta(Metadata(custom={"temperature": 300}), out)


def test_save_meta_only_flow_succeeds_through_runner__tc_k4f6_ep_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F6-EP-001: the metadata save_meta writes passes the Runner's post-validation."""
    # Given: a single-tile invoice-mode tree and a flow that only saves metadata
    runner = _full_runner(tmp_path, monkeypatch, "k4f6-ep-001")

    # When: running it through the Runner
    report = runner.run(_save_meta_only_flow)

    # Then: the run succeeds and metadata.json satisfies the RDE contract
    assert report.status == "success", report.error
    assert report.error is None
    metadata_path = tmp_path / "data" / "meta" / "metadata.json"
    metadata_validate(metadata_path)
    decoded = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert decoded["constant"]["temperature"]["value"] == 300
