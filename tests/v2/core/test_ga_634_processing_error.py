"""GA634 EP/BV: the ``ProcessingError`` public API and the v1 decorator deprecation.

``ProcessingError`` lets structured-processing code report "this input cannot
be processed" with a message and remediation guidance, without choosing an
error code: the Runner publishes it as the catalogued 3007 ``ProcessingFailed``
(#634). ``catch_exception_with_message`` keeps its v1 behaviour but warns.

EP table

| API | Partition | Rationale | Expected | Test ID |
|-----|-----------|-----------|----------|---------|
| ``ProcessingError(...)`` | message + remediation | normal | code 3007, both texts kept, ``RdeExecutionError`` | GA634-EP-1 |
| ``ProcessingError(...)`` | message only | normal | catalog 3007 remediation | GA634-EP-2 |
| ``rdetoolkit.exceptions`` | import path | public surface | same class as ``rdetoolkit.errors`` | GA634-EP-3 |
| flow node raises it | v2 flow entry | normal | report/iteration/job.failed carry 3007, message, remediation, call_id | GA634-EP-4 |
| ``raise ... from exc`` | chained cause | traceability | ``__cause__`` kept; call record names ``ProcessingError`` | GA634-EP-5 |
| flow raises ``ValueError`` | ordinary exception | regression | 3001 as before | GA634-EP-6 |
| ``@flow(error_code=7)`` | declared options | explicit error wins | 3007 kept, not remapped | GA634-EP-7 |
| ``@flow(prepare=...)`` raises it | run-level failure | normal | run error 3007 with user remediation | GA634-EP-8 |
| v1 callback raises it | v1 entry | normal | job.failed ``ErrorCode=3007`` | GA634-EP-9 |
| v1 callback raises ``StructuredError`` | legacy API | compatibility | ecode/emsg verbatim | GA634-EP-10 |
| ``catch_exception_with_message`` | decoration | deprecation | ``DeprecationWarning``; v1 conversion unchanged | GA634-EP-11 |
| ``catch_exception_with_message`` | wraps a ``ProcessingError`` | explicit error wins | re-raised unchanged | GA634-EP-12 |
| ``import rdetoolkit.img2thumb`` | internal decorator use | no user-facing noise | no ``DeprecationWarning`` | GA634-EP-13 |
| ``ProcessingError(42)`` | non-str message | invalid | ``TypeError`` | GA634-EP-14 |
| ``ProcessingError("m", remediation=1)`` | non-str remediation | invalid | ``TypeError`` | GA634-EP-15 |

BV table

| API | Boundary | Rationale | Expected | Test ID |
|-----|----------|-----------|----------|---------|
| message | ``"x"`` (1 char) | minimal valid | accepted | GA634-BV-1 |
| message | ``""`` / ``"   "`` | empty | ``ValueError`` | GA634-BV-2 |
| remediation | ``""`` / ``"   "`` | empty (R9: never empty) | ``ValueError`` | GA634-BV-3 |
| remediation | ``None`` | omitted | catalog default | GA634-EP-2 |
| message | contains ``"Remediation:"`` | marker-like text | remediation still appended once | GA634-BV-4 |
"""

from __future__ import annotations

import json
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, node, workflows
from rdetoolkit.errors import ERROR_CATALOG, RdeError, RdeExecutionError, catch_exception_with_message
from rdetoolkit.exceptions import StructuredError
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree

_CONFIG = {"system": {"save_thumbnail_image": False}}
_MESSAGE = "Input file was not found."
_REMEDIATION = "Verify the input file location."


def _job_failed(tmp_path: Path) -> str:
    return (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")


def _iteration_error(tmp_path: Path) -> dict[str, Any]:
    path = tmp_path / "data" / "logs" / "iterations" / "iteration_0.json"
    return json.loads(path.read_text(encoding="utf-8"))


@node(id="tests.ga634.read_input")
def _read_input(path: str) -> str:
    from rdetoolkit.exceptions import ProcessingError

    raise ProcessingError(_MESSAGE, remediation=_REMEDIATION)


class TestProcessingErrorApi:
    def test_message_and_remediation_are_kept__ga634_ep_1(self) -> None:
        """GA634-EP-1: the exception carries the catalogued code and both texts."""
        from rdetoolkit.exceptions import ProcessingError

        # Given: a message and remediation written by the user
        # When: constructing the error without any code
        error = ProcessingError(_MESSAGE, remediation=_REMEDIATION)
        # Then: the framework assigned 3007 and kept the user texts
        assert isinstance(error, RdeExecutionError)
        assert isinstance(error, RdeError)
        assert error.code == 3007
        assert error.name == "ProcessingFailed" == ERROR_CATALOG[3007].name
        assert error.message == _MESSAGE
        assert error.remediation == _REMEDIATION
        assert error.to_dict() == {"code": 3007, "name": "ProcessingFailed", "message": _MESSAGE, "remediation": _REMEDIATION}

    def test_omitted_remediation_uses_catalog__ga634_ep_2(self) -> None:
        """GA634-EP-2: without remediation the catalog guidance is used."""
        from rdetoolkit.exceptions import ProcessingError

        # Given / When: an error with a message only
        error = ProcessingError(_MESSAGE)
        # Then: the catalogued, non-empty remediation fills in
        assert error.remediation == ERROR_CATALOG[3007].remediation
        assert error.remediation.strip() != ""

    def test_exceptions_module_reexports_errors_class__ga634_ep_3(self) -> None:
        """GA634-EP-3: both public import paths name one class."""
        # Given / When: importing from both modules
        from rdetoolkit import errors, exceptions

        # Then: the class is identical
        assert exceptions.ProcessingError is errors.ProcessingError

    def test_non_str_message_is_rejected__ga634_ep_14(self) -> None:
        """GA634-EP-14: a non-str message is a TypeError."""
        from rdetoolkit.exceptions import ProcessingError

        # Given / When / Then: an int message is rejected
        with pytest.raises(TypeError, match="message"):
            ProcessingError(42)  # type: ignore[arg-type]

    def test_non_str_remediation_is_rejected__ga634_ep_15(self) -> None:
        """GA634-EP-15: a non-str remediation is a TypeError."""
        from rdetoolkit.exceptions import ProcessingError

        # Given / When / Then: an int remediation is rejected
        with pytest.raises(TypeError, match="remediation"):
            ProcessingError(_MESSAGE, remediation=1)  # type: ignore[arg-type]

    def test_one_character_message_is_accepted__ga634_bv_1(self) -> None:
        """GA634-BV-1: the shortest non-empty message is valid."""
        from rdetoolkit.exceptions import ProcessingError

        # Given / When: a one-character message
        error = ProcessingError("x")
        # Then: it is kept verbatim
        assert error.message == "x"

    @pytest.mark.parametrize("message", ["", "   "])
    def test_empty_message_is_rejected__ga634_bv_2(self, message: str) -> None:
        """GA634-BV-2: an empty or blank message is a ValueError."""
        from rdetoolkit.exceptions import ProcessingError

        # Given / When / Then: the blank message is rejected
        with pytest.raises(ValueError, match="message"):
            ProcessingError(message)

    @pytest.mark.parametrize("remediation", ["", "   "])
    def test_empty_remediation_is_rejected__ga634_bv_3(self, remediation: str) -> None:
        """GA634-BV-3: an empty or blank remediation is a ValueError."""
        from rdetoolkit.exceptions import ProcessingError

        # Given / When / Then: the blank remediation is rejected
        with pytest.raises(ValueError, match="remediation"):
            ProcessingError(_MESSAGE, remediation=remediation)


class TestRunnerTranslation:
    def test_flow_failure_reaches_every_record__ga634_ep_4(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-EP-4: report, iteration file and job.failed carry the user texts."""
        # Given: a flow whose node raises ProcessingError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        @flow
        def pipeline() -> None:
            _read_input("sample.csv")

        # When: executing it through the public v2 entry
        report = workflows.run(flow=pipeline, config=_CONFIG)
        # Then: the catalogued code, message and user remediation are published
        expected_message = f"{_MESSAGE} Remediation: {_REMEDIATION}"
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["code"] == 3007
        assert report.error["name"] == "ProcessingFailed"
        assert report.error["message"] == expected_message
        assert report.error["remediation"] == _REMEDIATION
        assert report.error["call_id"] == "tests.ga634.read_input#1"
        iteration = _iteration_error(tmp_path)
        assert iteration["error"] == report.error
        assert _job_failed(tmp_path) == f"ErrorCode=3007\nErrorMessage={expected_message}\n"

    def test_cause_and_call_record_stay_traceable__ga634_ep_5(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-EP-5: ``raise ... from`` keeps the cause; the call log names the type."""
        from rdetoolkit.exceptions import ProcessingError

        # Given: a flow chaining an OSError into a ProcessingError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        @flow
        def pipeline() -> None:
            try:
                raise OSError("disk unreadable")
            except OSError as exc:
                raise ProcessingError(_MESSAGE, remediation=_REMEDIATION) from exc

        # When: calling it directly, then through the Runner
        with pytest.raises(ProcessingError) as raised:
            pipeline()
        workflows.run(flow=pipeline, config=_CONFIG)
        # Then: the original exception is the cause and the record shows the type
        assert isinstance(raised.value.__cause__, OSError)
        assert _iteration_error(tmp_path)["error"]["code"] == 3007

    def test_node_call_record_names_processing_error__ga634_ep_5b(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-EP-5: the failed call record attributes the failure to ProcessingError."""
        # Given: a flow whose node raises ProcessingError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        @flow
        def pipeline() -> None:
            _read_input("sample.csv")

        # When: executing it
        workflows.run(flow=pipeline, config=_CONFIG)
        # Then: the call log keeps the exception type and the user message
        record = _iteration_error(tmp_path)["call_records"][0]
        assert record["status"] == "failed"
        assert record["error"]["type"] == "ProcessingError"
        assert _MESSAGE in record["error"]["message"]

    def test_ordinary_exception_keeps_3001__ga634_ep_6(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-EP-6: ordinary Python exceptions are unchanged."""
        # Given: a flow raising ValueError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        @flow
        def pipeline() -> None:
            raise ValueError("bad value")

        # When: executing it
        report = workflows.run(flow=pipeline, config=_CONFIG)
        # Then: the catalogue's generic execution failure is reported
        assert report.error is not None
        assert report.error["code"] == 3001
        assert report.error["remediation"] == ERROR_CATALOG[3001].remediation
        assert _job_failed(tmp_path).splitlines()[0] == "ErrorCode=3001"

    @pytest.mark.parametrize("options", [
        {"error_code": 7, "error_message": "generic failure"},
        {"error_code": 7},
        {"error_message": "generic failure"},
    ], ids=["code+message", "code-only", "message-only"])
    def test_flow_options_do_not_remap__ga634_ep_7(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]) -> None:
        """GA634-EP-7: a declared flow mapping leaves an explicit ProcessingError alone."""
        # Given: a flow declaring error options whose node raises ProcessingError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        @flow(**options)
        def pipeline() -> None:
            _read_input("sample.csv")

        # When: executing it
        report = workflows.run(flow=pipeline, config=_CONFIG)
        # Then: 3007 and the user's texts win over the declaration
        assert report.error is not None
        assert report.error["code"] == 3007
        assert report.error["remediation"] == _REMEDIATION
        assert "generic failure" not in _job_failed(tmp_path)

    def test_prepare_failure_keeps_user_remediation__ga634_ep_8(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-EP-8: a run-level ProcessingError keeps the user's remediation."""
        from rdetoolkit.exceptions import ProcessingError

        # Given: a flow whose preparation raises ProcessingError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        def prepare(inputdata: Path, config: Any) -> None:
            raise ProcessingError(_MESSAGE, remediation=_REMEDIATION)

        @flow(prepare=prepare)
        def pipeline() -> None:
            return None

        # When: executing it
        report = workflows.run(flow=pipeline, config=_CONFIG)
        # Then: the run error carries 3007 and the user remediation
        expected_message = f"{_MESSAGE} Remediation: {_REMEDIATION}"
        assert report.status == "failed"
        assert report.error == {"code": 3007, "name": "ProcessingFailed", "message": expected_message, "remediation": _REMEDIATION}
        assert _job_failed(tmp_path) == f"ErrorCode=3007\nErrorMessage={expected_message}\n"

    def test_v1_callback_publishes_3007__ga634_ep_9(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-EP-9: the v1 callback entry publishes the same record."""
        from rdetoolkit.exceptions import ProcessingError

        # Given: a v1 callback raising ProcessingError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        def callback(srcpaths: Any, resource_paths: Any) -> None:
            raise ProcessingError(_MESSAGE, remediation=_REMEDIATION)

        # When: executing the v1 entry
        with pytest.raises(SystemExit) as raised:
            workflows.run(custom_dataset_function=callback, config=_CONFIG)
        # Then: job.failed carries 3007 and the user texts
        assert raised.value.code == 1
        assert _job_failed(tmp_path) == f"ErrorCode=3007\nErrorMessage={_MESSAGE} Remediation: {_REMEDIATION}\n"

    def test_v1_structured_error_is_unchanged__ga634_ep_10(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-EP-10: a StructuredError still publishes its ecode/emsg verbatim."""
        # Given: a v1 callback raising StructuredError
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)

        def callback(srcpaths: Any, resource_paths: Any) -> None:
            raise StructuredError("user message", 5)

        # When: executing the v1 entry
        with pytest.raises(SystemExit):
            workflows.run(custom_dataset_function=callback, config=_CONFIG)
        # Then: the v1 contract holds
        assert _job_failed(tmp_path) == "ErrorCode=5\nErrorMessage=user message\n"

    def test_marker_text_in_message_still_gets_remediation__ga634_bv_4(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GA634-BV-4: user text containing 'Remediation:' does not suppress the guidance."""
        from rdetoolkit.exceptions import ProcessingError

        # Given: a message that itself contains the marker
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)
        message = "Remediation: column missing"

        @flow
        def pipeline() -> None:
            raise ProcessingError(message, remediation=_REMEDIATION)

        # When: executing it
        report = workflows.run(flow=pipeline, config=_CONFIG)
        # Then: the user remediation is appended exactly once
        assert report.error is not None
        assert report.error["message"] == f"{message} Remediation: {_REMEDIATION}"


class TestLegacyDecorator:
    def test_decoration_warns_and_keeps_v1_conversion__ga634_ep_11(self) -> None:
        """GA634-EP-11: the decorator warns at decoration and still converts."""
        # Given / When: decorating a failing function
        with pytest.warns(DeprecationWarning, match="ProcessingError"):
            @catch_exception_with_message(error_message="fixed text", error_code=7)
            def func() -> None:
                raise ValueError("boom")

        # Then: calling it still raises the v1 StructuredError
        with pytest.raises(StructuredError) as raised:
            func()
        assert raised.value.ecode == 7
        assert raised.value.emsg == "Error: fixed text"
        assert isinstance(raised.value.__cause__, ValueError)

    def test_decorator_passes_processing_error_through__ga634_ep_12(self) -> None:
        """GA634-EP-12: an explicit ProcessingError is not wrapped into StructuredError."""
        from rdetoolkit.exceptions import ProcessingError

        # Given: a decorated function raising ProcessingError
        with pytest.warns(DeprecationWarning):
            @catch_exception_with_message(error_message="fixed text", error_code=7)
            def func() -> None:
                raise ProcessingError(_MESSAGE, remediation=_REMEDIATION)

        # When / Then: the identical error propagates
        with pytest.raises(ProcessingError) as raised:
            func()
        assert raised.value.remediation == _REMEDIATION

    def test_internal_use_does_not_warn__ga634_ep_13(self) -> None:
        """GA634-EP-13: importing rdetoolkit's own decorated module emits no warning."""
        # Given: a fresh interpreter promoting this deprecation to an error
        code = (
            "import warnings\n"
            "warnings.filterwarnings('error', message='catch_exception_with_message', category=DeprecationWarning)\n"
            "import rdetoolkit.img2thumb\n"
        )
        # When: importing the module that uses the decorator internally
        completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
        # Then: the import succeeds
        assert completed.returncode == 0, completed.stderr

    def test_direct_decorator_warning_points_at_caller__ga634_ep_11b(self) -> None:
        """GA634-EP-11: the warning is attributed to the decorating module."""
        # Given / When: decorating while recording warnings
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            catch_exception_with_message()
        # Then: the reported file is this test module, not rdetoolkit
        deprecations = [item for item in caught if issubclass(item.category, DeprecationWarning)]
        assert len(deprecations) == 1
        assert deprecations[0].filename == __file__
