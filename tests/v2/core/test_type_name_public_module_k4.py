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
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from rdetoolkit.core import calllog
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
