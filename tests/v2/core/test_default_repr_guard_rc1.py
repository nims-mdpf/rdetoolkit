"""A default whose ``__repr__`` raises does not break node registration.

``@node`` records ``repr(default)`` for each parameter in the NodeSpec. That
call was unguarded, so a default object whose ``__repr__`` raised made the
decorator raise, the defining module failed to import, and the user saw an
error unrelated to their node (seen in rc1 when importing a generated
template subclass). The repr is descriptive metadata, so a failing one is
replaced by a placeholder naming the class.

EP / BV table:

| TC-ID          | Class    | Input                                           | Expected                                               |
|----------------|----------|-------------------------------------------------|--------------------------------------------------------|
| TC-CN1-EP-001  | EP inval | default whose ``__repr__`` raises ValueError    | registration succeeds; ``default_repr`` = placeholder  |
| TC-CN1-EP-002  | EP valid | node with that default is called                | runs normally with the default                         |
| TC-CN1-EP-003  | EP valid | ordinary default (``3``)                        | ``default_repr`` = ``"3"`` (unchanged)                 |
| TC-CN1-BV-001  | BV       | no default                                      | ``default_repr`` is ``None``, ``has_default`` False    |
| TC-CN1-BV-002  | BV       | ``__repr__`` returns a non-str (TypeError)      | placeholder                                            |
| TC-CN1-NEG-001 | EP inval | ``__repr__`` raises KeyboardInterrupt           | propagates (only ``Exception`` is absorbed)            |
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from rdetoolkit.core.node import node
from rdetoolkit.core import registry


class _BrokenRepr:
    def __repr__(self) -> str:
        msg = "repr is not available"
        raise ValueError(msg)


class _NonStrRepr:
    def __repr__(self) -> Any:  # noqa: PLE0307 -- deliberately wrong
        return 42


class _InterruptRepr:
    def __repr__(self) -> str:
        raise KeyboardInterrupt


_BROKEN = _BrokenRepr()
_PLACEHOLDER = f"<{__name__}._BrokenRepr object>"


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterator[None]:
    """Drop the nodes each case registers, so ids can repeat across runs."""
    saved = dict(registry._node_specs)
    yield
    registry._node_specs.clear()
    registry._node_specs.update(saved)


def _spec_entry(func: Any, name: str) -> dict[str, Any]:
    return dict(func.__node_spec__.input_schema[name])


def test_raising_repr_default_registers_with_placeholder__tc_cn1_ep_001() -> None:
    """TC-CN1-EP-001: the decorator does not raise; the spec carries a class-named placeholder."""

    # Given / When: a node whose default's __repr__ raises
    @node(id="tests.v2.core.cn1.broken_default")
    def with_broken_default(value: int, marker: object = _BROKEN) -> int:
        return value

    # Then: registration succeeded and the repr is the placeholder
    entry = _spec_entry(with_broken_default, "marker")
    assert entry["has_default"] is True
    assert entry["default_repr"] == _PLACEHOLDER


def test_node_with_raising_repr_default_runs__tc_cn1_ep_002() -> None:
    """TC-CN1-EP-002: the node is callable and uses its default."""

    @node(id="tests.v2.core.cn1.broken_default_call")
    def returns_marker(marker: object = _BROKEN) -> object:
        return marker

    assert returns_marker() is _BROKEN


def test_ordinary_default_repr_unchanged__tc_cn1_ep_003() -> None:
    """TC-CN1-EP-003: a normal default keeps its real repr."""

    @node(id="tests.v2.core.cn1.ordinary_default")
    def with_default(value: int = 3) -> int:
        return value

    assert _spec_entry(with_default, "value")["default_repr"] == "3"


def test_no_default_has_no_repr__tc_cn1_bv_001() -> None:
    """TC-CN1-BV-001: a parameter without a default records no repr."""

    @node(id="tests.v2.core.cn1.no_default")
    def without_default(value: int) -> int:
        return value

    entry = _spec_entry(without_default, "value")
    assert entry["has_default"] is False
    assert entry["default_repr"] is None


def test_non_str_repr_uses_placeholder__tc_cn1_bv_002() -> None:
    """TC-CN1-BV-002: ``repr()`` raising TypeError for a non-str result is absorbed too."""

    @node(id="tests.v2.core.cn1.non_str_repr")
    def with_non_str(marker: object = _NonStrRepr()) -> object:  # noqa: B008
        return marker

    assert _spec_entry(with_non_str, "marker")["default_repr"] == f"<{__name__}._NonStrRepr object>"


def test_keyboard_interrupt_from_repr_propagates__tc_cn1_neg_001() -> None:
    """TC-CN1-NEG-001: only ordinary exceptions are absorbed."""
    with pytest.raises(KeyboardInterrupt):

        @node(id="tests.v2.core.cn1.interrupt_repr")
        def with_interrupt(marker: object = _InterruptRepr()) -> object:  # noqa: B008
            return marker
