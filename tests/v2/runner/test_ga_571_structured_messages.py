"""GA571 EP/BV: preserve non-string user error messages on both public entries.

GA571-EP-1/2: exception, dict and list messages are failure partitions.
GA571-BV-1/2: numeric and existing string messages cover representation bounds.
GA571-BV-3: non-StructuredError exceptions are not passthrough records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.runner.finalize import structured_error_record
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


@pytest.mark.parametrize("entry", ["v1", "v2"])
@pytest.mark.parametrize("message", [ValueError("boom"), {"reason": "boom"}, ["boom"], 7, "boom"])
def test_public_entry_preserves_message__ga571_ep_1_2_bv_1_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str, message: Any,
) -> None:
    """GA571-EP-1/2/BV-1/2: all user error messages survive JSON publication."""
    # Given: a valid single-tile dataset and the issue's callback/flow failure
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        raise StructuredError(message, 7)

    @flow
    def pipeline() -> None:
        raise StructuredError(message, 7)

    config = {"system": {"save_thumbnail_image": False}}

    # When: executing the real public entry, including aggregation/finalization
    if entry == "v1":
        with pytest.raises(SystemExit) as raised:
            workflows.run(custom_dataset_function=callback, config=config)
        assert raised.value.code == 1
    else:
        report = workflows.run(flow=pipeline, config=config)
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["code"] == 7
        assert report.error["name"] == "StructuredError"
        assert report.error["message"] == str(message)

    # Then: the frozen v1 text contract and every published JSON retain the error
    marker = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
    assert "ErrorCode=7" in marker
    assert f"ErrorMessage={message}" in marker
    logs = tmp_path / "data" / "logs"
    iteration = json.loads((logs / "iterations" / "iteration_0.json").read_text(encoding="utf-8"))
    persisted = json.loads(next(logs.glob("run_report_*.json")).read_text(encoding="utf-8"))
    assert iteration["error"]["code"] == persisted["error"]["code"] == 7
    assert iteration["error"]["message"] == persisted["error"]["message"] == str(message)


def test_plain_exception_has_no_passthrough_record__ga571_bv_3() -> None:
    """GA571-BV-3: ordinary exceptions keep the framework error route."""
    # Given: an exception with no user-supplied error code
    error = ValueError("boom")
    # When: considering it for the StructuredError translation
    record = structured_error_record(error)
    # Then: no StructuredError record is manufactured
    assert record is None
