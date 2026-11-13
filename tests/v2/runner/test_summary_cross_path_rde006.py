"""RDE-006 (#641): the Runner and the call log summarize a value identically.

``runner/execute.py`` used to carry its own copies of the call-log summary
helpers. The copies drifted: the Runner built the type name straight from
``type(value).__module__`` while ``core/calllog.py`` reports the public module
(``pathlib._local.PosixPath`` vs ``pathlib.PosixPath`` on Python 3.13). These
tests pin one behaviour for both recording paths:

* call-log path -- a node's recorded outputs (``CallLogRecorder.call_node``),
* Runner path   -- a flow's tile outputs (``run_tile`` -> ``ExecutionResult.outputs``),

for the same value and the same ``provenance`` settings.

EP / BV table (positive):
| ID | Kind | Value | Settings | Expected (both paths) |
|----|------|-------|----------|-----------------------|
| TC-RDE006-EP-001 | EP | scalar ``42`` | on / 80 | one ``int`` summary, repr ``42`` |
| TC-RDE006-EP-002 | EP | tuple ``(1, "a", None)`` | on / 80 | three summaries, element-wise |
| TC-RDE006-EP-003 | EP | ``None`` | on / 80 | ``()`` (no summary) |
| TC-RDE006-EP-004 | EP | ``Path("x")`` | on / 80 | ``pathlib.<PlatformPath>`` on every interpreter |
| TC-RDE006-EP-005 | EP | custom class | on / 80 | ``<module>.<qualname>`` |
| TC-RDE006-EP-006 | EP | class re-exported from a private submodule | on / 80 | public module name |
| TC-RDE006-BV-007 | BV | repr longer than the limit | on / 5 | repr cut to exactly 5 chars |
| TC-RDE006-BV-008 | BV | repr exactly the limit | on / 2 | repr kept whole |

Negative table:
| ID | Kind | Value | Settings | Expected (both paths) |
|----|------|-------|----------|-----------------------|
| TC-RDE006-NEG-001 | NEG | ``__repr__`` raises ``ValueError`` | on | repr ``None``, call completes |
| TC-RDE006-NEG-002 | NEG | ``__repr__`` raises ``RdeExecutionError(3001)`` | on | tolerated, repr ``None`` |
| TC-RDE006-NEG-003 | NEG | ``__repr__`` raises the run interruption (3004) | on | the same 3004 object propagates |
| TC-RDE006-NEG-004 | NEG | ``__repr__`` raises ``KeyboardInterrupt`` | on | propagates (not an ``Exception``) |
| TC-RDE006-NEG-005 | NEG | ``__repr__`` raises | off | repr never evaluated, repr ``None`` |
| TC-RDE006-NEG-006 | NEG | metaclass ``__repr__`` raises | on | class repr never evaluated |
| TC-RDE006-NEG-007 | NEG | private class not re-exported | on | private module kept (no guessing) |
| TC-RDE006-NEG-008 | NEG | ``runner/execute.py`` source | -- | defines none of the summary helpers |
| TC-RDE006-NEG-009 | NEG | whole package source | -- | each summary helper is defined exactly once |
"""

from __future__ import annotations

import ast
import sys
import types
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import rdetoolkit
from rdetoolkit.core.calllog import CallLogRecorder, TypeSummary
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.execute import run_tile
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig

_SUMMARY_HELPERS = ("_summarize_outputs", "_summarize", "_type_name", "_safe_repr_head", "_public_module", "type_name_of")
_SRC_ROOT = Path(rdetoolkit.__file__).parent


# --------------------------------------------------------------------------
# Recording paths
# --------------------------------------------------------------------------


@node(id="tests.v2.runner.rde006.echo")
def _echo(obj: Any) -> Any:
    return obj


def _calllog_outputs(value: Any, *, repr_head: str, repr_head_len: int) -> tuple[TypeSummary, ...]:
    """Summaries the call log records for a node returning ``value``."""
    with CallLogRecorder(repr_head=repr_head, repr_head_len=repr_head_len) as recorder:  # type: ignore[arg-type]
        _echo(value)
    (record,) = recorder.records
    assert record.status == "completed"
    return record.outputs


def _context(tmp_path: Path, config: RdeConfig) -> RunContext:
    base = tmp_path / "data"
    names = ("struct", "meta", "main_image", "other_image", "thumbnail", "attachment", "nonshared_raw", "raw", "invoice", "logs")
    return RunContext(
        paths=InputPaths(inputdata=tmp_path / "inputdata", invoice=tmp_path / "invoice", tasksupport=tmp_path / "tasksupport"),
        out=OutputContext.from_resource_paths(SimpleNamespace(**{name: base / name for name in names})),
        config=config,
        invoice=None,
        iteration=IterationInfo(index=0, total=1, mode="invoice"),
    )


def _runner_outputs(tmp_path: Path, value: Any, *, repr_head: str, repr_head_len: int) -> tuple[TypeSummary, ...]:
    """Summaries the Runner records for a flow returning ``value``."""
    config = RdeConfig(provenance={"repr_head": repr_head, "repr_head_len": repr_head_len})

    @flow(id="tests.v2.runner.rde006.returning")
    def returning() -> Any:
        return value

    sink = MemoryEventSink()
    sink.open("run-rde006")
    result = run_tile(returning, _context(tmp_path, config), event_sink=sink, run_id="run-rde006", config=config)
    assert result.status == "completed"
    return result.outputs


def _both(tmp_path: Path, value: Any, *, repr_head: str = "on", repr_head_len: int = 80) -> tuple[TypeSummary, ...]:
    """Record ``value`` on both paths, assert they agree, return the shared summary."""
    via_calllog = _calllog_outputs(value, repr_head=repr_head, repr_head_len=repr_head_len)
    via_runner = _runner_outputs(tmp_path, value, repr_head=repr_head, repr_head_len=repr_head_len)
    assert via_runner == via_calllog
    return via_runner


# --------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------


class _Custom:
    def __repr__(self) -> str:
        return "_Custom()"


class _Long:
    def __repr__(self) -> str:
        return "abcdefghij"


class _CountingRepr:
    """Value whose ``repr`` raises the given exception and counts the calls."""

    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.calls = 0

    def __repr__(self) -> str:
        self.calls += 1
        raise self.error


class _ExplodingMeta(type):
    calls = 0

    def __repr__(cls) -> str:
        _ExplodingMeta.calls += 1
        message = "class repr must not be evaluated while recording"
        raise RuntimeError(message)


class _MetaHostile(metaclass=_ExplodingMeta):
    def __repr__(self) -> str:
        return "_MetaHostile()"


def _error(code: int) -> RdeExecutionError:
    error_def = ERROR_CATALOG[code]
    error_cls: Any = RdeExecutionError
    return error_cls(code=code, name=error_def.name, message=error_def.message_template)


@pytest.fixture
def private_class(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[bool], type]]:
    """Factory for a class defined in ``rde006pkg._impl``, optionally re-exported."""

    def make(exported: bool) -> type:  # noqa: FBT001
        package = types.ModuleType("rde006pkg")
        private = types.ModuleType("rde006pkg._impl")
        monkeypatch.setitem(sys.modules, "rde006pkg", package)
        monkeypatch.setitem(sys.modules, "rde006pkg._impl", private)
        cls = type("Thing", (), {"__module__": "rde006pkg._impl", "__repr__": lambda self: "Thing()"})
        private.Thing = cls  # type: ignore[attr-defined]
        if exported:
            package.Thing = cls  # type: ignore[attr-defined]
        return cls

    yield make


# --------------------------------------------------------------------------
# Positive cases
# --------------------------------------------------------------------------


class TestIdenticalSummaries:
    def test_scalar__tc_rde006_ep_001(self, tmp_path: Path) -> None:
        # Given: a bare scalar  /  When: both paths record it
        summaries = _both(tmp_path, 42)
        # Then: exactly one summary, identical on both paths
        assert summaries == (TypeSummary(type_name="int", repr_head="42"),)

    def test_tuple__tc_rde006_ep_002(self, tmp_path: Path) -> None:
        # Given: a tuple mixing builtins and None  /  When: both paths record it
        summaries = _both(tmp_path, (1, "a", None))
        # Then: one summary per element, None included
        assert summaries == (
            TypeSummary(type_name="int", repr_head="1"),
            TypeSummary(type_name="str", repr_head="'a'"),
            TypeSummary(type_name="None", repr_head="None"),
        )

    def test_none__tc_rde006_ep_003(self, tmp_path: Path) -> None:
        # Given: None  /  When: both paths record it  /  Then: no summary at all
        assert _both(tmp_path, None) == ()

    def test_path_uses_the_public_module__tc_rde006_ep_004(self, tmp_path: Path) -> None:
        # Given: a Path (platform subclass; pathlib._local on Python 3.13)
        value = Path("x")
        # When: both paths record it
        (summary,) = _both(tmp_path, value)
        # Then: the type name is the public pathlib name on every interpreter
        assert summary.type_name == f"pathlib.{type(value).__qualname__}"
        assert summary.repr_head == repr(value)

    def test_custom_class__tc_rde006_ep_005(self, tmp_path: Path) -> None:
        # Given: a user class  /  When: both paths record it
        (summary,) = _both(tmp_path, _Custom())
        # Then: module-qualified name and its repr
        assert summary == TypeSummary(type_name=f"{__name__}._Custom", repr_head="_Custom()")

    def test_reexported_private_class__tc_rde006_ep_006(self, tmp_path: Path, private_class: Callable[[bool], type]) -> None:
        # Given: a class from a private submodule that its package re-exports
        cls = private_class(True)  # noqa: FBT003
        # When: both paths record an instance
        (summary,) = _both(tmp_path, cls())
        # Then: the public module is reported (interpreter-independent form of EP-004)
        assert summary == TypeSummary(type_name="rde006pkg.Thing", repr_head="Thing()")

    def test_repr_truncated_to_the_limit__tc_rde006_bv_007(self, tmp_path: Path) -> None:
        # Given: a repr of 10 chars and a limit of 5  /  When: both paths record it
        (summary,) = _both(tmp_path, _Long(), repr_head_len=5)
        # Then: exactly the first 5 chars are kept
        assert summary.repr_head == "abcde"

    def test_repr_at_the_limit_is_kept_whole__tc_rde006_bv_008(self, tmp_path: Path) -> None:
        # Given: a 2-char repr and a limit of 2  /  When: both paths record it
        (summary,) = _both(tmp_path, 42, repr_head_len=2)
        # Then: nothing is cut
        assert summary.repr_head == "42"


# --------------------------------------------------------------------------
# Negative cases
# --------------------------------------------------------------------------


class TestHostileValues:
    @pytest.mark.parametrize(
        "error",
        [ValueError("no repr"), _error(3001)],
        ids=["TC-RDE006-NEG-001-valueerror", "TC-RDE006-NEG-002-rde3001"],
    )
    def test_ordinary_repr_failure_is_nonfatal__tc_rde006_neg_001_002(self, tmp_path: Path, error: Exception) -> None:
        # Given: a value whose repr raises an ordinary (non-interruption) error
        value = _CountingRepr(error)
        # When: both paths record it
        (summary,) = _both(tmp_path, value)
        # Then: the call completes with "no repr"; repr was attempted (input + output on the
        # call log, output on the Runner)
        assert summary == TypeSummary(type_name=f"{__name__}._CountingRepr", repr_head=None)
        assert value.calls == 3

    def test_interruption_in_repr_propagates_on_both_paths__tc_rde006_neg_003(self, tmp_path: Path) -> None:
        # Given: a value whose repr raises the run interruption (3004)
        interrupt = _error(3004)
        value = _CountingRepr(interrupt)

        # When / Then: the call-log path lets the very same object through
        with pytest.raises(RdeExecutionError) as via_calllog:
            _calllog_outputs(value, repr_head="on", repr_head_len=80)
        assert via_calllog.value is interrupt
        assert via_calllog.value.code == 3004

        # When / Then: and so does the Runner path
        with pytest.raises(RdeExecutionError) as via_runner:
            _runner_outputs(tmp_path, value, repr_head="on", repr_head_len=80)
        assert via_runner.value is interrupt
        assert via_runner.value.code == 3004

    def test_keyboard_interrupt_in_repr_propagates__tc_rde006_neg_004(self, tmp_path: Path) -> None:
        # Given: a value whose repr raises KeyboardInterrupt (a BaseException)
        value = _CountingRepr(KeyboardInterrupt())
        # When / Then: neither path swallows it
        with pytest.raises(KeyboardInterrupt):
            _calllog_outputs(value, repr_head="on", repr_head_len=80)
        with pytest.raises(KeyboardInterrupt):
            _runner_outputs(tmp_path, value, repr_head="on", repr_head_len=80)

    @pytest.mark.parametrize(
        "error",
        [ValueError("no repr"), _error(3004)],
        ids=["TC-RDE006-NEG-005-valueerror", "TC-RDE006-NEG-005-interrupt"],
    )
    def test_repr_head_off_never_calls_repr__tc_rde006_neg_005(self, tmp_path: Path, error: Exception) -> None:
        # Given: a hostile repr and repr_head off
        value = _CountingRepr(error)
        # When: both paths record it
        (summary,) = _both(tmp_path, value, repr_head="off")
        # Then: repr is never evaluated and no repr is recorded
        assert summary == TypeSummary(type_name=f"{__name__}._CountingRepr", repr_head=None)
        assert value.calls == 0

    def test_metaclass_repr_is_never_called__tc_rde006_neg_006(self, tmp_path: Path) -> None:
        # Given: a value whose class repr (metaclass __repr__) raises
        _ExplodingMeta.calls = 0
        # When: both paths record it
        (summary,) = _both(tmp_path, _MetaHostile())
        # Then: the summary is complete and the class repr was never asked
        assert summary == TypeSummary(type_name=f"{__name__}._MetaHostile", repr_head="_MetaHostile()")
        assert _ExplodingMeta.calls == 0

    def test_unexported_private_class_keeps_its_module__tc_rde006_neg_007(self, tmp_path: Path, private_class: Callable[[bool], type]) -> None:
        # Given: a class reachable only through the private submodule
        cls = private_class(False)  # noqa: FBT003
        # When: both paths record an instance
        (summary,) = _both(tmp_path, cls())
        # Then: the real module is kept on both paths
        assert summary.type_name == "rde006pkg._impl.Thing"


def _defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {item.name for item in ast.walk(tree) if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}


class TestSingleImplementation:
    def test_runner_execute_defines_no_summary_helper__tc_rde006_neg_008(self) -> None:
        # Given: the Runner's tile executor source
        defined = _defined_functions(_SRC_ROOT / "runner" / "execute.py")
        # When / Then: none of the summary helpers is re-implemented there
        assert defined.isdisjoint(_SUMMARY_HELPERS), sorted(defined.intersection(_SUMMARY_HELPERS))

    def test_each_summary_helper_is_defined_once__tc_rde006_neg_009(self) -> None:
        # Given: every source module of the package
        owners: dict[str, list[str]] = {name: [] for name in _SUMMARY_HELPERS}
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            for name in _defined_functions(path).intersection(_SUMMARY_HELPERS):
                owners[name].append(path.relative_to(_SRC_ROOT).as_posix())
        # When / Then: each helper has exactly one definition, in core/calllog.py
        assert owners == {name: ["core/calllog.py"] for name in _SUMMARY_HELPERS}
