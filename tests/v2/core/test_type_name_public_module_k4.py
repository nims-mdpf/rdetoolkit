"""K4-F5: canonical type names use the public module, whatever the interpreter.

On Python 3.13 ``pathlib.Path.__module__`` is ``pathlib._local``; on 3.10–3.12
and 3.14 it is ``pathlib``. Node specs and call-log records carry type names,
so the string must not depend on the interpreter (TC-EP-034 failed on 3.13).

| ID | Kind | Scenario | Expected |
|----|------|----------|----------|
| TC-K4F5-EP-001 | EP | class re-exported from a private submodule | public module name |
| TC-K4F5-EP-002 | EP | class in a private submodule, not re-exported | module unchanged |
| TC-K4F5-EP-003 | EP | pathlib.Path on the running interpreter | ``pathlib.Path`` in node spec and call-log summary |
| TC-K4F5-BV-004 | BV | builtins and None | unchanged (``int``, ``None``) |
| TC-K4F5-EP-005 | EP | unannotated node, value whose metaclass ``__repr__`` raises, repr_head off | call completes, record kept, class repr never invoked |
| TC-K4F5-EP-006 | EP | same value with repr_head on | call completes, record kept, class repr never invoked |
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from rdetoolkit.core import calllog
from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.node import node, type_name


def _private_class(monkeypatch: pytest.MonkeyPatch, *, exported: bool) -> type:
    package = types.ModuleType("k4f5pkg")
    private = types.ModuleType("k4f5pkg._impl")
    monkeypatch.setitem(sys.modules, "k4f5pkg", package)
    monkeypatch.setitem(sys.modules, "k4f5pkg._impl", private)
    cls = type("Thing", (), {"__module__": "k4f5pkg._impl"})
    private.Thing = cls  # type: ignore[attr-defined]
    if exported:
        package.Thing = cls  # type: ignore[attr-defined]
    return cls


def test_reexported_private_class_uses_public_module__tc_k4f5_ep_001(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K4F5-EP-001: a class the public package re-exports is named by the package."""
    # Given: a class defined in k4f5pkg._impl and re-exported by k4f5pkg
    cls = _private_class(monkeypatch, exported=True)

    # When / Then: both helpers report the public module
    assert calllog.type_name_of(cls) == "k4f5pkg.Thing"
    assert type_name(cls()) == "k4f5pkg.Thing"


def test_unexported_private_class_keeps_its_module__tc_k4f5_ep_002(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K4F5-EP-002: without a re-export the private module stays (no guessing)."""
    # Given: a class only reachable through the private submodule
    cls = _private_class(monkeypatch, exported=False)

    # When / Then: the real module is kept
    assert calllog.type_name_of(cls) == "k4f5pkg._impl.Thing"


def test_pathlib_path_is_named_pathlib_path__tc_k4f5_ep_003() -> None:
    """TC-K4F5-EP-003: pathlib.Path reads the same in a node spec and a call-log summary on every supported Python."""

    # Given: a node annotated with Path
    @node
    def typed_fn(paths: Path) -> None:
        return None

    # When / Then: the spec and the value summary both say pathlib.Path
    spec = typed_fn.__node_spec__  # type: ignore[attr-defined]
    assert spec.input_schema["paths"]["type_name"] == "pathlib.Path"
    # A Path instance is the platform subclass (PosixPath / WindowsPath); only the module is normalized.
    assert calllog._type_name(Path("x")) == f"pathlib.{type(Path('x')).__name__}"  # noqa: SLF001


def test_builtins_and_none_are_unchanged__tc_k4f5_bv_004() -> None:
    """TC-K4F5-BV-004: builtins keep their bare name and None stays None."""
    assert calllog.type_name_of(int) == "int"
    assert calllog.type_name_of(type(None)) == "None"
    assert type_name(None) == "None"


class _ExplodingMeta(type):
    """Metaclass whose class repr() raises and counts how often it was asked."""

    calls = 0

    def __repr__(cls) -> str:
        _ExplodingMeta.calls += 1
        message = "class repr must not be evaluated while recording"
        raise RuntimeError(message)


class _Payload(metaclass=_ExplodingMeta):
    def __repr__(self) -> str:
        return "_Payload()"


@pytest.mark.parametrize("repr_head", ["off", "on"], ids=["TC-K4F5-EP-005", "TC-K4F5-EP-006"])
def test_recording_never_calls_the_class_repr__tc_k4f5_ep_005_006(repr_head: str) -> None:
    """TC-K4F5-EP-005/006: recording a value's type never evaluates the class's repr().

    PR #554 review R1: the shared type-name helper carried a ``repr(target)``
    default argument that Python evaluates eagerly, so a class with a raising
    metaclass ``__repr__`` turned a completed node into a failure with no record.
    """
    _ExplodingMeta.calls = 0

    # Given: an unannotated node that receives and returns such a value
    @node(id=f"k4f5-passthrough-{repr_head}")  # one registry entry per parameter
    def passthrough(obj):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN202
        return obj

    payload = _Payload()

    # When: it runs under a recorder
    with CallLogRecorder(repr_head=repr_head) as recorder:  # type: ignore[arg-type]
        result = passthrough(payload)

    # Then: the node completed, the record is kept, and the class repr was never asked
    assert result is payload
    (record,) = recorder.records
    assert record.status == "completed"
    assert record.inputs["obj"].type_name.endswith("._Payload")
    assert _ExplodingMeta.calls == 0
