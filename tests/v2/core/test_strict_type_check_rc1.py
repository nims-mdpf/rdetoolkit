"""Shallow origin-level strict type checking and variadic parameters (RC1 F05 + C04).

Review ``interrogate_v2.0.0rc1`` F05: ``_matches_annotation`` accepted any
annotation that has ``__origin__``, so ``list[int]`` admitted a ``dict`` or a
``str`` in strict mode, for arguments and for return values alike. Design
§4.4 promises "isinstance-based, generics checked shallowly up to origin".
C04: ``*values: int`` compared the bound tuple itself against ``int``, so the
correct call ``total(1, 2)`` was rejected.

Rules pinned here (shallow; container elements are never inspected):
``Any`` / empty / unresolved string / ``TypeVar`` / ``NewType`` / ``Literal``
accept; ``None`` is ``NoneType``; a union accepts when any member matches; a
parametrized generic whose origin is a class is ``isinstance(value, origin)``;
a plain class is ``isinstance``, and a class ``isinstance`` cannot use (a
non-runtime-checkable Protocol) accepts.

EP table:
| TC | Annotation | Value | Expected |
|----|------------|-------|----------|
| TC-RC1-F05-EP-001 | list[int] | [] | ok |
| TC-RC1-F05-EP-002 | dict[str, int] | {} | ok |
| TC-RC1-F05-EP-003 | int | None | None / 1 | ok |
| TC-RC1-F05-EP-004 | Optional[list[int]] | None / [] | ok |
| TC-RC1-F05-EP-005 | tuple[int, ...] | () / (1, "x") | ok (no element check) |
| TC-RC1-F05-EP-006 | Sequence[int] | [] / () | ok |
| TC-RC1-F05-EP-007 | *values: int | total(1, 2) / total() | ok |
| TC-RC1-F05-EP-008 | **kw: int | a=1, b=2 | ok |
| TC-RC1-F05-EP-009 | accept-always family | Any, TypeVar, NewType, Literal, str ref | ok for anything |
| TC-RC1-F05-EP-010 | warn mode | list[int] given {} | UserWarning, call completes |

BV / negative table:
| TC | Annotation | Value | Expected |
|----|------------|-------|----------|
| TC-RC1-F05-NEG-001 | list[int] | {} / "s" | 3002 |
| TC-RC1-F05-NEG-002 | dict[str, int] | [] | 3002 |
| TC-RC1-F05-NEG-003 | int | None | "x" | 3002 |
| TC-RC1-F05-NEG-004 | Optional[list[int]] | {} | 3002 |
| TC-RC1-F05-NEG-005 | tuple[int, ...] | [] | 3002 |
| TC-RC1-F05-NEG-006 | Sequence[int] | {} | 3002 |
| TC-RC1-F05-NEG-007 | *values: int | total(1, "x") | 3002 on ``values`` |
| TC-RC1-F05-NEG-008 | **kw: int | a=1, b="x" | 3002 on ``kw`` |
| TC-RC1-F05-NEG-009 | -> list[int] | returns {} | 3002 on ``return`` |
| TC-RC1-F05-NEG-010 | None | 1 | 3002 |
| TC-RC1-F05-NEG-011 | type[int] / Callable / user generic | wrong origin | 3002 |
| TC-RC1-F05-NEG-012 | Annotated[int, ...] | "x" | 3002 (metadata stripped) |
| TC-RC1-F05-BV-001 | non-runtime-checkable Protocol | anything | ok (isinstance unusable) |
| TC-RC1-F05-BV-002 | off mode | {} for list[int] | no check, no hint resolution |
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Any, Generic, Literal, NewType, Optional, Protocol, TypeVar, Union

import pytest

from rdetoolkit.core import calllog
from rdetoolkit.core.calllog import CallLogRecorder, _matches_annotation
from rdetoolkit.core.node import node
from rdetoolkit.errors import RdeExecutionError

T = TypeVar("T")
UserId = NewType("UserId", int)


class Box(Generic[T]):
    """User generic used to check the parametrized-origin rule."""


class Greeter(Protocol):
    """Not runtime-checkable: isinstance() raises TypeError for it."""

    def greet(self) -> str: ...


def _strict_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    with CallLogRecorder(type_check="strict"):
        return fn(*args, **kwargs)


def _assert_mismatch(fn: Callable[..., Any], param: str, *args: Any, **kwargs: Any) -> None:
    with pytest.raises(RdeExecutionError) as exc_info:
        _strict_call(fn, *args, **kwargs)
    assert exc_info.value.code == 3002
    node_id = fn.__node_spec__.id  # type: ignore[attr-defined]
    assert f"Node argument type mismatch for {node_id}.{param}" in str(exc_info.value)


@node(id="tests.v2.core.rc1_f05.list_int")
def takes_list(xs: list[int]) -> int:
    return len(xs)


@node(id="tests.v2.core.rc1_f05.dict_str_int")
def takes_dict(mapping: dict[str, int]) -> int:
    return len(mapping)


@node(id="tests.v2.core.rc1_f05.optional_int")
def takes_optional_int(value: int | None) -> None:
    _ = value


@node(id="tests.v2.core.rc1_f05.optional_list")
def takes_optional_list(value: Optional[list[int]]) -> None:  # noqa: UP045 -- the typing spelling is under test
    _ = value


@node(id="tests.v2.core.rc1_f05.tuple_var")
def takes_tuple(value: tuple[int, ...]) -> None:
    _ = value


@node(id="tests.v2.core.rc1_f05.sequence")
def takes_sequence(value: Sequence[int]) -> None:
    _ = value


@node(id="tests.v2.core.rc1_f05.total")
def total(*values: int) -> int:
    return sum(values)


@node(id="tests.v2.core.rc1_f05.count")
def count(*values: int) -> int:
    return len(values)


@node(id="tests.v2.core.rc1_f05.keywords")
def keywords(**kw: int) -> int:
    return sum(kw.values())


@node(id="tests.v2.core.rc1_f05.bad_return")
def bad_return() -> list[int]:
    return {}  # type: ignore[return-value]


@node(id="tests.v2.core.rc1_f05.annotated")
def takes_annotated(value: Annotated[int, "unit"]) -> None:
    _ = value


class TestContainerOrigins:
    def test_list_accepts_list__tc_rc1_f05_ep_001(self) -> None:
        # Given / When / Then: an empty list satisfies list[int]
        assert _strict_call(takes_list, []) == 0

    @pytest.mark.parametrize("value", [{}, "s"], ids=["dict", "str"])
    def test_list_rejects_other_origins__tc_rc1_f05_neg_001(self, value: object) -> None:
        # Given / When / Then: a dict or a str is not a list
        _assert_mismatch(takes_list, "xs", value)

    def test_dict_accepts_dict__tc_rc1_f05_ep_002(self) -> None:
        # Given / When / Then
        assert _strict_call(takes_dict, {}) == 0

    def test_dict_rejects_list__tc_rc1_f05_neg_002(self) -> None:
        # Given / When / Then
        _assert_mismatch(takes_dict, "mapping", [])

    def test_tuple_accepts_any_tuple__tc_rc1_f05_ep_005(self) -> None:
        # Given / When / Then: only the origin is checked, not the elements
        _strict_call(takes_tuple, ())
        _strict_call(takes_tuple, (1, "x"))

    def test_tuple_rejects_list__tc_rc1_f05_neg_005(self) -> None:
        # Given / When / Then
        _assert_mismatch(takes_tuple, "value", [])

    @pytest.mark.parametrize("value", [[], (1,), "abc"], ids=["list", "tuple", "str"])
    def test_sequence_accepts_sequences__tc_rc1_f05_ep_006(self, value: object) -> None:
        # Given / When / Then: collections.abc origins use isinstance too
        _strict_call(takes_sequence, value)

    def test_sequence_rejects_dict__tc_rc1_f05_neg_006(self) -> None:
        # Given / When / Then
        _assert_mismatch(takes_sequence, "value", {})


class TestUnions:
    @pytest.mark.parametrize("value", [None, 1], ids=["none", "int"])
    def test_pep604_union_accepts_members__tc_rc1_f05_ep_003(self, value: object) -> None:
        # Given / When / Then
        _strict_call(takes_optional_int, value)

    def test_pep604_union_rejects_non_member__tc_rc1_f05_neg_003(self) -> None:
        # Given / When / Then
        _assert_mismatch(takes_optional_int, "value", "x")

    @pytest.mark.parametrize("value", [None, [], [1]], ids=["none", "empty", "list"])
    def test_optional_generic_accepts_members__tc_rc1_f05_ep_004(self, value: object) -> None:
        # Given / When / Then
        _strict_call(takes_optional_list, value)

    def test_optional_generic_rejects_wrong_origin__tc_rc1_f05_neg_004(self) -> None:
        # Given / When / Then
        _assert_mismatch(takes_optional_list, "value", {})


class TestVariadicParameters:
    @pytest.mark.parametrize("args", [(1, 2), (), (3,)], ids=["two", "none", "one"])
    def test_var_positional_checks_each_element__tc_rc1_f05_ep_007(self, args: tuple[int, ...]) -> None:
        # Given / When / Then: C04 -- the bound tuple is not compared with int
        assert _strict_call(total, *args) == sum(args)

    def test_var_positional_rejects_a_bad_element__tc_rc1_f05_neg_007(self) -> None:
        # Given / When / Then: the error names the parameter
        _assert_mismatch(total, "values", 1, "x")

    def test_var_keyword_checks_each_value__tc_rc1_f05_ep_008(self) -> None:
        # Given / When / Then
        assert _strict_call(keywords, a=1, b=2) == 3
        assert _strict_call(keywords) == 0

    def test_var_keyword_rejects_a_bad_value__tc_rc1_f05_neg_008(self) -> None:
        # Given / When / Then
        _assert_mismatch(keywords, "kw", a=1, b="x")

    def test_var_positional_error_names_the_parameter__tc_rc1_f05_neg_007b(self) -> None:
        # Given: the catalogued 3002 message embeds the parameter name
        with pytest.raises(RdeExecutionError) as exc_info:
            _strict_call(total, 1, "x")

        # Then: it is the declared name, not an element index
        assert str(exc_info.value).count("total.values") == 1
        assert "values[" not in str(exc_info.value)


class TestReturnCheck:
    def test_return_wrong_origin_is_rejected__tc_rc1_f05_neg_009(self) -> None:
        # Given / When / Then: the same rules apply to the return value
        _assert_mismatch(bad_return, "return")


class TestAnnotatedThroughHints:
    def test_annotated_metadata_is_stripped__tc_rc1_f05_neg_012(self) -> None:
        # Given / When / Then: get_type_hints strips Annotated, so int is checked
        _assert_mismatch(takes_annotated, "value", "x")
        _strict_call(takes_annotated, 1)


class TestWarnAndOffModes:
    def test_warn_mode_warns_instead_of_raising__tc_rc1_f05_ep_010(self) -> None:
        # Given: warn mode and a wrong origin
        with CallLogRecorder(type_check="warn") as recorder, pytest.warns(UserWarning, match="xs"):
            # When: the node is called
            result = takes_list({})

        # Then: the call completes and is recorded as completed
        assert result == 0
        assert [record.status for record in recorder.records] == ["completed"]

    def test_warn_mode_variadic_warns_per_parameter__tc_rc1_f05_ep_010b(self) -> None:
        # Given / When: a bad *args element in warn mode
        with CallLogRecorder(type_check="warn") as recorder, pytest.warns(UserWarning, match=r"count\.values"):
            result = count(1, "x")

        # Then: the call still runs to completion
        assert result == 2
        assert [record.status for record in recorder.records] == ["completed"]

    def test_off_mode_never_resolves_or_matches__tc_rc1_f05_bv_002(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the hint resolver and the matcher would explode if consulted
        def explode(*_args: Any, **_kwargs: Any) -> Any:
            msg = "type checking ran in off mode"
            raise AssertionError(msg)

        monkeypatch.setattr(CallLogRecorder, "_resolve_hints", staticmethod(explode))
        monkeypatch.setattr(calllog, "_matches_annotation", explode)

        # When: wrong values flow through in off mode
        with CallLogRecorder(type_check="off") as recorder, warnings.catch_warnings():
            warnings.simplefilter("error")
            assert takes_list({}) == 0
            assert bad_return() == {}

        # Then: nothing was checked and both calls completed
        assert [record.status for record in recorder.records] == ["completed", "completed"]


_ACCEPT_ALWAYS: tuple[tuple[str, object], ...] = (
    ("any", Any),
    ("typevar", T),
    ("newtype", UserId),
    ("literal", Literal["a"]),
    ("forward-ref-string", "NotDefinedAnywhere"),
    ("protocol", Greeter),
)


class TestMatcherTable:
    @pytest.mark.parametrize(("label", "annotation"), _ACCEPT_ALWAYS, ids=[label for label, _ in _ACCEPT_ALWAYS])
    @pytest.mark.parametrize("value", [None, 1, "b", [], {}], ids=["none", "int", "str", "list", "dict"])
    def test_accept_always_family__tc_rc1_f05_ep_009(self, label: str, annotation: object, value: object) -> None:
        # Given / When / Then: these annotations are out of the runtime-check scope
        assert _matches_annotation(value, annotation) is True, label

    @pytest.mark.parametrize(
        ("annotation", "good", "bad"),
        [
            (None, None, 1),
            (type(None), None, 0),
            (int, 1, "1"),
            (type[int], int, 1),
            (Callable[[int], int], len, 1),
            (Box[int], Box(), [1]),
            (Mapping[str, int], {}, []),
            (Union[int, str], "s", 1.5),  # noqa: UP007 -- typing.Union spelling under test
            (list[int] | dict[str, int], {}, "s"),
            (Optional[Sequence[int]], None, 1),  # noqa: UP045
        ],
        ids=[
            "none",
            "nonetype",
            "plain-class",
            "type-origin",
            "callable-origin",
            "user-generic",
            "abc-mapping",
            "typing-union",
            "union-of-generics",
            "optional-abc",
        ],
    )
    def test_origin_and_class_rules__tc_rc1_f05_neg_010_011(self, annotation: object, good: object, bad: object) -> None:
        # Given / When / Then: the matching member/origin accepts, anything else is rejected
        assert _matches_annotation(good, annotation) is True
        assert _matches_annotation(bad, annotation) is False

    def test_empty_annotation_accepts__tc_rc1_f05_ep_009b(self) -> None:
        # Given / When / Then
        import inspect

        assert _matches_annotation(object(), inspect.Signature.empty) is True

    def test_non_runtime_checkable_protocol_accepts__tc_rc1_f05_bv_001(self) -> None:
        # Given: isinstance() raises TypeError for this Protocol
        with pytest.raises(TypeError):
            isinstance(1, Greeter)  # type: ignore[misc]

        # When / Then: the matcher accepts rather than crashing the node call
        assert _matches_annotation(1, Greeter) is True
