"""GA589 EP/BV: ``@flow`` error options never override a body ``StructuredError``.

GA589-EP-1: v1 ``catch_exception_with_message`` keeps a raised StructuredError's
            ecode/emsg (reference row of the issue table).
GA589-EP-2: every v2 option partition (code+message, code only, message only,
            none) publishes the StructuredError's own code and message.
GA589-EP-3: ordinary exceptions are still mapped by the declared options.
GA589-BV-1: a direct call re-raises the identical StructuredError object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.errors import catch_exception_with_message
from rdetoolkit.exceptions import StructuredError
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree

_CONFIG = {"system": {"save_thumbnail_image": False}}


def test_v1_decorator_keeps_structured_error__ga589_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA589-EP-1: the v1 reference keeps ecode=5 and the user message."""
    # Given: the issue's body under the v1 decorator on the v1 callback entry
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @catch_exception_with_message(error_code=1, error_message="generic failure")
    def callback(srcpaths: Any, resource_paths: Any) -> None:
        raise StructuredError("user message", 5)

    # When: executing the frozen v1 entry
    with pytest.raises(SystemExit) as raised:
        workflows.run(custom_dataset_function=callback, config=_CONFIG)
    # Then: the StructuredError's own code and message reach job.failed
    assert raised.value.code == 1
    marker = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
    assert marker.splitlines()[0] == "ErrorCode=5"
    assert "user message" in marker
    assert "generic failure" not in marker


@pytest.mark.parametrize("options", [
    {"error_code": 1, "error_message": "generic failure"},
    {"error_code": 1},
    {"error_message": "generic failure"},
    {},
], ids=["code+message", "code-only", "message-only", "no-options"])
def test_flow_options_keep_structured_error__ga589_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]) -> None:
    """GA589-EP-2: no option partition rewrites a body StructuredError."""
    # Given: the issue's flow raising StructuredError("user message", 5)
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(**options)
    def mapped() -> None:
        raise StructuredError("user message", 5)

    # When: executing through the public v2 entry
    report = workflows.run(flow=mapped, config=_CONFIG)
    # Then: the report and the platform marker carry the user's code/message
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 5
    assert report.error["name"] == "StructuredError"
    assert report.error["message"] == "user message"
    assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8") == "ErrorCode=5\nErrorMessage=user message\n"


@pytest.mark.parametrize("options, code, message", [
    ({"error_code": 1, "error_message": "generic failure"}, 1, "generic failure"),
    ({"error_code": 1}, 1, "boom"),
    ({"error_message": "generic failure"}, 3001, "generic failure"),
], ids=["code+message", "code-only", "message-only"])
def test_flow_options_still_map_plain_exception__ga589_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any], code: int, message: str) -> None:
    """GA589-EP-3: a plain ValueError is still mapped by the declaration."""
    # Given: an opted-in flow raising an ordinary exception
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(**options)
    def mapped() -> None:
        raise ValueError("boom")

    # When: executing through the public v2 entry
    report = workflows.run(flow=mapped, config=_CONFIG)
    # Then: the declared policy applies, as before the fix
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == code
    assert report.error["message"] == message
    assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8") == f"ErrorCode={code}\nErrorMessage={message}\n"


def test_direct_call_reraises_identical_structured_error__ga589_bv_1() -> None:
    """GA589-BV-1: direct calls keep the exact StructuredError object."""
    # Given: an opted-in flow raising a specific StructuredError
    original = StructuredError("user message", 5)

    @flow(error_code=1, error_message="generic failure")
    def mapped() -> None:
        raise original

    # When: calling it directly
    with pytest.raises(StructuredError) as raised:
        mapped()
    # Then: the identical exception escapes with its own code
    assert raised.value is original
    assert raised.value.ecode == 5
