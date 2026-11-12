"""GA596 EP: the documented v1 ``catch_exception_with_message`` → ``@flow`` mapping.

v1 ``catch_exception_with_message`` turns a plain exception into a
``StructuredError`` with ``ecode=1`` and an ``Error: `` prefixed message, while
``@flow(error_message=...)`` keeps the catalogue default 3001 (#596, kept as
designed). The migration guide therefore maps the v1 decorator to an explicit
``@flow(error_code=1, ...)``; these tests pin that mapping to the v1 result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.errors import catch_exception_with_message
from rdetoolkit.exceptions import StructuredError
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


def _v1_failure(options: dict[str, Any]) -> tuple[int, str]:
    @catch_exception_with_message(**options)
    def callback() -> None:
        raise ValueError("boom")

    with pytest.raises(StructuredError) as raised:
        callback()
    return raised.value.ecode, raised.value.emsg


@pytest.mark.parametrize("v1_options, flow_options", [
    ({"error_message": "fixed text"}, {"error_code": 1, "error_message": "Error: fixed text"}),
    ({}, {"error_code": 1, "error_message": "Error: {error}"}),
    ({"error_code": 7, "error_message": "fixed text"}, {"error_code": 7, "error_message": "Error: fixed text"}),
])
def test_documented_flow_mapping_reproduces_v1_failure__ga596_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, v1_options: dict[str, Any], flow_options: dict[str, Any]) -> None:
    """GA596-EP-1: the mapped flow writes the same job.failed as the v1 decorator."""
    # Given: the v1 decorator result and a real Runner dataset
    code, message = _v1_failure(v1_options)
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(**flow_options)
    def pipeline() -> None:
        raise ValueError("boom")

    # When: executing the mapped flow through the public v2 entry
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: code and message match the v1 decorator exactly
    assert code == flow_options["error_code"]
    assert report.error is not None and report.error["code"] == code
    assert report.error["message"] == message
    assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8") == f"ErrorCode={code}\nErrorMessage={message}\n"


def test_message_only_flow_keeps_catalogue_default__ga596_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA596-EP-2: a literal rewrite keeps 3001, which is why the guide maps explicitly."""
    # Given: a flow carrying only the v1 decorator's message
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(error_message="fixed text")
    def pipeline() -> None:
        raise ValueError("boom")

    # When: executing it through the public v2 entry
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: the catalogue default code is used, unlike v1's ecode 1
    assert report.error is not None and report.error["code"] == 3001
    assert report.error["message"] == "fixed text"
