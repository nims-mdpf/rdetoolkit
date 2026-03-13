"""Tests for v2 RdeError hierarchy (Phase 1.1).

EP Table:
| API                  | Partition             | Rationale              | Expected                  | Test ID     |
|----------------------|-----------------------|------------------------|---------------------------|-------------|
| RdeError()           | valid code+message    | normal construction    | fields accessible         | TC-EP-012   |
| RdeError()           | missing code          | negative               | TypeError                 | TC-EP-013   |
| RdeError             | is Exception subclass | inheritance check      | isinstance(Exception)     | TC-EP-014   |
| RdeError.to_dict()   | serialization         | normal                 | dict with code+message    | TC-EP-015   |
| RdeError             | raise + catch         | exception behavior     | catchable as Exception    | TC-EP-016   |
| RdeError             | str representation    | string conversion      | includes code+message     | TC-EP-017   |
| Subclass errors      | specific error types  | hierarchy check        | isinstance(RdeError)      | TC-EP-018   |
| ErrorCode enum       | E001-E025 defined     | completeness           | all codes exist           | TC-EP-019   |
| RdeError             | with detail           | optional detail field  | detail preserved          | TC-EP-020   |

BV Table:
| API                  | Boundary              | Rationale              | Expected                  | Test ID     |
|----------------------|-----------------------|------------------------|---------------------------|-------------|
| RdeError             | empty message         | minimal                | constructed ok            | TC-BV-004   |
| RdeError             | None detail           | default                | detail is None            | TC-BV-005   |
"""

from __future__ import annotations

import pytest


class TestRdeError:
    """Tests for RdeError base class."""

    def test_construction_with_valid_code_and_message__tc_ep_012(self) -> None:
        """TC-EP-012: RdeError constructed with valid error code and message."""
        # Given: valid error code and message
        from rdetoolkit.errors import RdeError

        # When: constructing RdeError
        err = RdeError(code="E001", message="Graph contains a cycle")

        # Then: fields are accessible
        assert err.code == "E001"
        assert err.message == "Graph contains a cycle"

    def test_construction_missing_code_raises__tc_ep_013(self) -> None:
        """TC-EP-013: RdeError without code raises TypeError."""
        from rdetoolkit.errors import RdeError

        # When / Then: missing required field
        with pytest.raises(TypeError):
            RdeError(message="test")  # type: ignore[call-arg]

    def test_is_exception_subclass__tc_ep_014(self) -> None:
        """TC-EP-014: RdeError is a subclass of Exception."""
        from rdetoolkit.errors import RdeError

        # When: creating an RdeError
        err = RdeError(code="E001", message="test")

        # Then: it is an Exception
        assert isinstance(err, Exception)

    def test_to_dict_serialization__tc_ep_015(self) -> None:
        """TC-EP-015: RdeError.to_dict() returns dict with code and message."""
        from rdetoolkit.errors import RdeError

        # Given: an RdeError instance
        err = RdeError(code="E002", message="Node not found")

        # When: serializing to dict
        d = err.to_dict()

        # Then: contains code and message
        assert d["code"] == "E002"
        assert d["message"] == "Node not found"

    def test_raise_and_catch_as_exception__tc_ep_016(self) -> None:
        """TC-EP-016: RdeError can be raised and caught as Exception."""
        from rdetoolkit.errors import RdeError

        # When / Then: raise and catch
        with pytest.raises(Exception) as exc_info:
            raise RdeError(code="E001", message="cycle detected")

        assert isinstance(exc_info.value, RdeError)

    def test_str_representation__tc_ep_017(self) -> None:
        """TC-EP-017: str(RdeError) includes code and message."""
        from rdetoolkit.errors import RdeError

        # Given: an RdeError
        err = RdeError(code="E003", message="Compilation failed")

        # When: converting to string
        s = str(err)

        # Then: includes both code and message
        assert "E003" in s
        assert "Compilation failed" in s

    def test_with_detail__tc_ep_020(self) -> None:
        """TC-EP-020: RdeError with optional detail field."""
        from rdetoolkit.errors import RdeError

        # When: constructing with detail
        err = RdeError(code="E005", message="Type mismatch", detail={"expected": "int", "got": "str"})

        # Then: detail is preserved
        assert err.detail == {"expected": "int", "got": "str"}
        d = err.to_dict()
        assert d["detail"] == {"expected": "int", "got": "str"}

    def test_empty_message__tc_bv_004(self) -> None:
        """TC-BV-004: RdeError with empty message."""
        from rdetoolkit.errors import RdeError

        # When: constructing with empty message
        err = RdeError(code="E001", message="")

        # Then: constructed ok
        assert err.message == ""

    def test_none_detail_default__tc_bv_005(self) -> None:
        """TC-BV-005: RdeError detail defaults to None."""
        from rdetoolkit.errors import RdeError

        # When: constructing without detail
        err = RdeError(code="E001", message="test")

        # Then: detail is None
        assert err.detail is None


class TestErrorSubclasses:
    """Tests for specific error subclasses."""

    def test_subclasses_are_rde_error__tc_ep_018(self) -> None:
        """TC-EP-018: Specific error types are RdeError subclasses."""
        from rdetoolkit.errors import (
            RdeError,
            RdeGraphError,
            RdeCompileError,
            RdeExecutionError,
            RdeConfigError,
            RdeIOError,
        )

        # When: creating each subclass
        graph_err = RdeGraphError(code="E001", message="cycle")
        compile_err = RdeCompileError(code="E006", message="type mismatch")
        exec_err = RdeExecutionError(code="E011", message="node failed")
        config_err = RdeConfigError(code="E016", message="invalid config")
        io_err = RdeIOError(code="E021", message="file not found")

        # Then: all are RdeError instances
        assert isinstance(graph_err, RdeError)
        assert isinstance(compile_err, RdeError)
        assert isinstance(exec_err, RdeError)
        assert isinstance(config_err, RdeError)
        assert isinstance(io_err, RdeError)

        # And: all are Exception instances
        assert isinstance(graph_err, Exception)


class TestErrorCodes:
    """Tests for error code definitions."""

    def test_error_codes_e001_to_e025_exist__tc_ep_019(self) -> None:
        """TC-EP-019: Error codes E001-E025 are all defined."""
        from rdetoolkit.errors import ErrorCode

        # Then: all 25 codes exist
        for i in range(1, 26):
            code_name = f"E{i:03d}"
            assert hasattr(ErrorCode, code_name), f"ErrorCode.{code_name} not found"

    def test_error_codes_have_string_values(self) -> None:
        """Error code values are strings matching E### pattern."""
        from rdetoolkit.errors import ErrorCode

        # Then: each code's value is the string form
        assert ErrorCode.E001.value == "E001"
        assert ErrorCode.E025.value == "E025"
