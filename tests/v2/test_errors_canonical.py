"""Canonical v2 error API after the pre-GA draft cleanup (issue #646).

EP Table:
| API                         | Partition                         | Rationale                         | Expected                                   | Test ID        |
|-----------------------------|-----------------------------------|-----------------------------------|--------------------------------------------|----------------|
| canonical RdeError subtypes | catalogued int code, no name      | name coerced from ERROR_CATALOG   | name == catalog name, str "[name] message" | TC646-EP-001   |
| canonical RdeError subtypes | explicit name                     | explicit name wins over catalog   | name == explicit                           | TC646-EP-002   |
| RdeError                    | int code not in catalog           | fallback display name             | name == "E{code}"                          | TC646-EP-003   |
| RdeError                    | string code (pre-GA tolerance)    | name falls back to the code       | name == code                               | TC646-EP-004   |
| RdeError.to_dict            | with / without detail             | serialization shape               | detail key only when detail is not None    | TC646-EP-005   |
| raise ... from              | canonical subtype                 | cause chain retained              | __cause__ is the original                  | TC646-EP-006   |
| RdeExecutionError           | call_id given / omitted           | call identifier carried           | call_id == given / None                    | TC646-EP-007   |
| RdeError / RdeExecutionError| method definition site            | no post-definition monkey-patching| methods live in the class body             | TC646-EP-008   |
| rdetoolkit.errors / pkg     | retired draft names               | pre-GA removal inventory          | not attributes, not exported               | TC646-EP-009   |
| errors.pyi                  | retired names / Incomplete        | stub in sync with module          | absent                                     | TC646-EP-010   |
| v1 StructuredError          | passthrough via handler decorator | v1 behaviour unchanged            | ecode / emsg / cause preserved             | TC646-EP-011   |

BV Table:
| API          | Boundary                 | Rationale             | Expected                         | Test ID      |
|--------------|--------------------------|-----------------------|----------------------------------|--------------|
| RdeError     | empty message            | minimal               | str == "[name] "                 | TC646-BV-001 |
| RdeError     | detail == {}             | falsy but not None    | detail key present in to_dict    | TC646-BV-002 |
| RdeError     | keyword-only constructor | positional rejected   | TypeError                        | TC646-BV-003 |
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

import rdetoolkit
import rdetoolkit.errors as errors_module
from rdetoolkit.errors import (
    ERROR_CATALOG,
    RdeConfigError,
    RdeError,
    RdeExecutionError,
    RdeInternalError,
    RdeRegistryError,
    RdeValidationError,
)
from rdetoolkit.exceptions import StructuredError

#: Supported canonical types (Design §9.2) paired with a catalogued code of their band.
_CANONICAL_CASES: list[tuple[type[RdeError], int]] = [
    (RdeConfigError, 1002),
    (RdeRegistryError, 2001),
    (RdeExecutionError, 3001),
    (RdeValidationError, 4001),
    (RdeInternalError, 5001),
]

#: Pre-GA draft identifiers removed by issue #646. They were never in a v1 release.
_RETIRED_NAMES = (
    "ErrorCode",
    "RdeGraphError",
    "RdeCompileError",
    "RdeIOError",
    "UnconnectedInputError",
    "E_CYCLE",
    "E_UNCONNECTED_INPUT",
    "E_DUPLICATE_ID",
    "E_AMBIGUOUS_DEPENDENCY",
)

_STUB_PATH = Path(errors_module.__file__).with_suffix(".pyi")


@pytest.mark.parametrize(("error_cls", "code"), _CANONICAL_CASES, ids=lambda v: getattr(v, "__name__", str(v)))
def test_canonical_error_constructs_and_serializes__tc646_ep_001(error_cls: type[RdeError], code: int) -> None:
    """TC646-EP-001: every canonical type carries the int code and the catalog name."""
    detail: dict[str, Any] = {"key": "value"}
    err = error_cls(code=code, message="something failed", detail=detail)

    assert err.code == code
    assert isinstance(err.code, int)
    assert err.name == ERROR_CATALOG[code].name
    assert err.message == "something failed"
    assert err.detail == detail
    assert str(err) == f"[{ERROR_CATALOG[code].name}] something failed"
    assert err.args == (f"[{ERROR_CATALOG[code].name}] something failed",)
    assert err.to_dict() == {
        "code": code,
        "name": ERROR_CATALOG[code].name,
        "message": "something failed",
        "detail": detail,
    }
    assert isinstance(err, RdeError)


def test_explicit_name_wins_over_catalog__tc646_ep_002() -> None:
    """TC646-EP-002: an explicit name is kept even for a catalogued code."""
    err = RdeRegistryError(code=2001, name="CustomName", message="m")

    assert err.name == "CustomName"
    assert str(err) == "[CustomName] m"


def test_uncatalogued_int_code_falls_back_to_display_name__tc646_ep_003() -> None:
    """TC646-EP-003: an int code missing from the catalog is displayed as E{code}."""
    assert 9999 not in ERROR_CATALOG
    err = RdeError(code=9999, message="m")

    assert err.name == "E9999"
    assert err.to_dict() == {"code": 9999, "name": "E9999", "message": "m"}


def test_string_code_name_falls_back_to_the_code__tc646_ep_004() -> None:
    """TC646-EP-004: the pre-GA string-code tolerance keeps its runtime behaviour."""
    err = RdeError(code="CUSTOM", message="m")

    assert err.code == "CUSTOM"
    assert err.name == "CUSTOM"
    assert str(err) == "[CUSTOM] m"


def test_to_dict_omits_detail_when_none__tc646_ep_005() -> None:
    """TC646-EP-005: detail is omitted from to_dict() only when it is None."""
    err = RdeValidationError(code=4001, message="bad schema")

    assert err.detail is None
    assert err.to_dict() == {"code": 4001, "name": "InvoiceSchemaInvalid", "message": "bad schema"}


@pytest.mark.parametrize(("error_cls", "code"), _CANONICAL_CASES, ids=lambda v: getattr(v, "__name__", str(v)))
def test_cause_chain_is_retained__tc646_ep_006(error_cls: type[RdeError], code: int) -> None:
    """TC646-EP-006: ``raise ... from`` keeps the original exception as __cause__."""
    original = ValueError("root cause")

    with pytest.raises(error_cls) as exc_info:
        try:
            raise original
        except ValueError as exc:
            raise error_cls(code=code, message="wrapped") from exc

    assert exc_info.value.__cause__ is original
    assert exc_info.value.__suppress_context__ is True


def test_execution_error_carries_call_id__tc646_ep_007() -> None:
    """TC646-EP-007: RdeExecutionError keeps call_id and the base fields."""
    err = RdeExecutionError(code=3001, message="node failed", call_id="call-0001", detail={"a": 1})

    assert err.call_id == "call-0001"
    assert err.code == 3001
    assert err.name == "NodeExecutionFailed"
    assert err.detail == {"a": 1}
    assert str(err) == "[NodeExecutionFailed] node failed"
    assert RdeExecutionError(code=3001, message="m").call_id is None


def test_methods_are_defined_in_the_class_body__tc646_ep_008() -> None:
    """TC646-EP-008: no assignment-based replacement of __init__ / to_dict."""
    assert "__init__" in RdeError.__dict__
    assert "to_dict" in RdeError.__dict__
    assert RdeError.__init__.__qualname__.startswith("RdeError.")
    assert RdeError.to_dict.__qualname__.startswith("RdeError.")
    assert "__init__" in RdeExecutionError.__dict__
    assert RdeExecutionError.__init__.__qualname__.startswith("RdeExecutionError.")
    for helper in ("_rde_error_init", "_rde_error_to_dict", "_rde_execution_error_init"):
        assert not hasattr(errors_module, helper), helper


@pytest.mark.parametrize("name", _RETIRED_NAMES)
def test_retired_draft_names_are_not_published__tc646_ep_009(name: str) -> None:
    """TC646-EP-009: retired pre-GA draft identifiers are gone from the module and the package."""
    assert not hasattr(errors_module, name)
    assert name not in getattr(rdetoolkit, "__all__", ())
    assert not hasattr(rdetoolkit, name)


def test_stub_has_no_retired_names_or_incomplete__tc646_ep_010() -> None:
    """TC646-EP-010: errors.pyi matches the module and types the core attributes precisely."""
    stub = _STUB_PATH.read_text(encoding="utf-8")

    for name in _RETIRED_NAMES:
        assert re.search(rf"\b{name}\b", stub) is None, name
    assert "Incomplete" not in stub
    for attribute in ("code", "name", "message", "detail"):
        assert re.search(rf"^    {attribute}: ", stub, flags=re.MULTILINE), attribute


def test_v1_structured_error_passthrough_is_unchanged__tc646_ep_011() -> None:
    """TC646-EP-011: the v1 decorator still passes StructuredError code/message through."""
    original = StructuredError("boom", ecode=42, eobj={"x": 1})

    @errors_module.catch_exception_with_message(error_message="fallback", error_code=7)
    def fails() -> None:
        raise original

    with pytest.raises(StructuredError) as exc_info:
        fails()

    raised = exc_info.value
    assert not isinstance(raised, RdeError)
    assert raised.ecode == 42
    assert raised.emsg == "Error: boom"
    assert raised.eobj == {"x": 1}
    assert raised.__cause__ is original


def test_empty_message__tc646_bv_001() -> None:
    """TC646-BV-001: an empty message still renders the name prefix."""
    err = RdeInternalError(code=5001, message="")

    assert str(err) == "[InternalInvariantViolation] "


def test_empty_detail_is_serialized__tc646_bv_002() -> None:
    """TC646-BV-002: an empty (falsy) detail dict is still serialized."""
    assert RdeConfigError(code=1002, message="m", detail={}).to_dict()["detail"] == {}


def test_constructor_is_keyword_only__tc646_bv_003() -> None:
    """TC646-BV-003: positional construction is rejected."""
    with pytest.raises(TypeError):
        RdeError(1002, "m")  # type: ignore[misc]
