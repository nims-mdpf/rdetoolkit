"""GA590 EP/BV: ``@flow(error_message=)`` context placeholders and job.failed warnings.

| API | Partition / boundary | Expected | Test ID |
|-----|----------------------|----------|---------|
| ``error_message`` | ``{error}`` | replaced by the exception text | GA590-FLOW-EP-1 |
| ``error_message`` | ``{error_type}`` | replaced by the exception class name | GA590-FLOW-EP-1 |
| ``error_message`` | both, repeated | every occurrence replaced | GA590-FLOW-EP-1 |
| ``error_message`` | no placeholder | fixed text (unchanged) | GA590-FLOW-EP-2 |
| ``error_message`` | other braces / ``{0}`` / unknown names | kept verbatim, no format error | GA590-FLOW-BV-1 |
| ``error_message`` | exception text itself contains ``{error_type}`` | not substituted again | GA590-FLOW-BV-2 |
| ``error_message`` | empty exception text | ``{error}`` becomes empty | GA590-FLOW-BV-3 |
| direct call | placeholders set | original exception propagates | GA590-FLOW-EP-3 |
| failed run | job.failed written | no ``get_datadir`` DeprecationWarning | GA590-FLOW-EP-4 |
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


def _run_failing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, **options: Any) -> Any:
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(**options)
    def pipeline() -> None:
        raise error

    return workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})


@pytest.mark.parametrize(
    "template, expected",
    [
        ("Cannot read sample: {error}", "Cannot read sample: bad column 'x'"),
        ("{error_type} while reading", "KeyError while reading"),
        ("{error_type}: {error} ({error_type})", "KeyError: bad column 'x' (KeyError)"),
    ],
)
def test_message_placeholders_carry_context__ga590_flow_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template: str, expected: str) -> None:
    """GA590-FLOW-EP-1: placeholders combine fixed context with the cause."""
    # Given / When: a Runner run whose body fails with a KeyError
    report = _run_failing(tmp_path, monkeypatch, KeyError("bad column 'x'"), error_code=21, error_message=template)
    # Then: the report and job.failed carry the formatted message
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 21
    # str(KeyError) quotes its argument, as Python itself renders it
    rendered = expected.replace("bad column 'x'", str(KeyError("bad column 'x'")))
    assert report.error["message"] == rendered
    assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8") == f"ErrorCode=21\nErrorMessage={rendered}\n"


def test_message_without_placeholders_is_fixed__ga590_flow_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-FLOW-EP-2: a message without placeholders keeps the GA577 behaviour."""
    # Given / When: a fixed message
    report = _run_failing(tmp_path, monkeypatch, ValueError("boom"), error_message="Cannot process input")
    # Then: the message is used verbatim with the default code
    assert report.error is not None
    assert report.error["code"] == 3001
    assert report.error["message"] == "Cannot process input"


@pytest.mark.parametrize(
    "template",
    ["Literal {braces} stay", "Index {0} and {} stay", "Escaped {{error}} stays {{ }}", "Unbalanced { brace", "{errors} {error_types}"],
)
def test_other_braces_are_kept_verbatim__ga590_flow_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template: str) -> None:
    """GA590-FLOW-BV-1: only the two documented placeholders are substituted."""
    # Given / When: a message with braces that are not placeholders
    report = _run_failing(tmp_path, monkeypatch, ValueError("boom"), error_code=5, error_message=template)
    # Then: no format error occurs and the text is unchanged
    assert report.error is not None
    expected = template.replace("{{error}}", "{boom}") if "{{error}}" in template else template
    assert report.error["message"] == expected


def test_substitution_is_single_pass__ga590_flow_bv_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-FLOW-BV-2: placeholder-like text inside the exception is not expanded."""
    # Given / When: an exception whose text looks like a placeholder
    report = _run_failing(tmp_path, monkeypatch, ValueError("{error_type}"), error_code=5, error_message="Failed: {error}")
    # Then: the exception text is inserted literally
    assert report.error is not None
    assert report.error["message"] == "Failed: {error_type}"


def test_empty_exception_text__ga590_flow_bv_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-FLOW-BV-3: an exception without text leaves the context intact."""
    # Given / When: an exception with no message
    report = _run_failing(tmp_path, monkeypatch, RuntimeError(), error_code=5, error_message="[{error_type}] {error}")
    # Then: the type is still reported
    assert report.error is not None
    assert report.error["message"] == "[RuntimeError] "


def test_direct_call_is_unchanged__ga590_flow_ep_3() -> None:
    """GA590-FLOW-EP-3: placeholders never affect plain direct calls."""
    # Given: a flow with a placeholder message
    original = ValueError("direct")

    @flow(error_code=7, error_message="Failed: {error}")
    def pipeline() -> None:
        raise original

    # When / Then: the original exception escapes unwrapped
    with pytest.raises(ValueError) as raised:
        pipeline()
    assert raised.value is original


def test_job_failed_emits_no_deprecation_warning__ga590_flow_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-FLOW-EP-4: writing job.failed does not warn about rdetoolkit's own v1 helper."""
    # Given: every warning recorded
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # When: a v2 run fails and finalize writes job.failed
        report = _run_failing(tmp_path, monkeypatch, ValueError("boom"), error_code=7)
    # Then: the marker exists and no get_datadir deprecation was emitted
    assert report.status == "failed"
    assert (tmp_path / "data" / "job.failed").is_file()
    messages = [str(item.message) for item in caught if issubclass(item.category, DeprecationWarning)]
    assert not [message for message in messages if "get_datadir" in message], messages
