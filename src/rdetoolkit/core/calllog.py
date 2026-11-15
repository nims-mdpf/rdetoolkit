"""Call-log recording for eager v2 node execution."""

from __future__ import annotations

import inspect
import time
import types
import typing
import warnings
from collections.abc import Callable, Iterable
from contextvars import ContextVar, Token
from dataclasses import dataclass
import sys
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, cast

from rdetoolkit._interrupt import is_run_interrupted
from rdetoolkit.core.flow import current_flow_id
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self



@dataclass(frozen=True, slots=True)
class TypeSummary:
    """Serializable summary of a runtime value's type and optional repr."""

    type_name: str
    repr_head: str | None


@dataclass(frozen=True, slots=True)
class NodeCallRecord:
    """One observed ``@node`` call in an active run."""

    call_id: str
    node_id: str
    parent_flow: str | None
    seq: int
    iteration_index: int
    started_at: str
    duration_ms: float
    status: Literal["completed", "failed"]
    inputs: dict[str, TypeSummary]
    outputs: tuple[TypeSummary, ...]
    error: dict[str, Any] | None


class CallSequence:
    """Run-scoped counter that hands out the run-global call order (Design §3.4).

    The Runner creates one per run and every tile's ``CallLogRecorder`` draws
    from it, so ``seq`` keeps increasing across tiles and ``call_id`` (which
    embeds ``seq``) stays unique within the run.
    """

    def __init__(self) -> None:
        self._last = 0
        self._last_invocation = 0

    def next(self) -> int:
        """Return the next sequence number, starting at 1."""
        self._last += 1
        return self._last

    def next_invocation(self) -> int:
        """Return the next invocation number, starting at 1 (#689).

        Invocations are numbered at call *entry* (pre-order) on a counter of
        their own: drawing them from ``seq`` would reserve sequence numbers
        before nested calls append, which the post-order ``seq`` contract
        forbids.
        """
        self._last_invocation += 1
        return self._last_invocation


@dataclass(frozen=True, slots=True)
class NodeInvocation:
    """One node invocation observed at call entry (#689).

    Attributes:
        invocation_id: Run-unique correlation id (``inv-<n>``), independent
            of ``seq`` / ``call_id``.
        node_id: Invoked node's identifier.
        iteration_index: Tile index of the invocation.
        parent_invocation_id: Invocation of the enclosing node call when this
            call is nested, else ``None``.
    """

    invocation_id: str
    node_id: str
    iteration_index: int
    parent_invocation_id: str | None


class InvocationListener(Protocol):
    """Observer notified when a node body starts and when it ends (#689).

    The recorder treats a listener as diagnostics: a listener that raises is
    muted for the rest of the recorder and never changes the call's outcome.
    """

    def invocation_started(self, invocation: NodeInvocation) -> None:
        """Receive an invocation whose body is about to run.

        Args:
            invocation: The in-flight invocation.
        """
        ...

    def invocation_finished(self, invocation: NodeInvocation, record: NodeCallRecord) -> None:
        """Receive the call record of an invocation whose body returned or raised.

        Args:
            invocation: The invocation that ended.
            record: Its call-log record (``completed`` or ``failed``).
        """
        ...


_active_recorder: ContextVar[CallLogRecorder | None] = ContextVar("rdetoolkit_calllog_recorder", default=None)


def get_active_recorder() -> CallLogRecorder | None:
    """Return the current active recorder, if any."""
    return _active_recorder.get()


def _public_module(target: type) -> str:
    """Return the public module a class is exported from.

    Some stdlib classes live in a private submodule that differs between
    Python versions (``pathlib.Path`` is ``pathlib._local.Path`` on 3.13 and
    ``pathlib.Path`` elsewhere). Type names are recorded in node specs and
    call logs, so they must not change with the interpreter: when a public
    ancestor module re-exports the class under its qualname, that module is
    reported instead.
    """
    module = getattr(target, "__module__", "") or ""
    qualname = getattr(target, "__qualname__", "")
    parts = module.split(".")
    for index in range(1, len(parts)):
        if not parts[index].startswith("_"):
            continue
        public = ".".join(parts[:index])
        exported = sys.modules.get(public)
        if exported is not None and "." not in qualname and getattr(exported, qualname, None) is target:
            return public
    return module


def type_name_of(target: type) -> str:
    """Return the canonical type-name string of a class (C1 convention)."""
    if target is type(None):
        return "None"
    module = _public_module(target)
    # No repr() fallback: this runs for every recorded input and output, and a
    # class whose metaclass __repr__ raises must not turn a completed node
    # into a failure (PR #554 review R1). Every class has __qualname__.
    qualname = getattr(target, "__qualname__", None) or getattr(target, "__name__", None) or "<anonymous>"
    if module == "builtins":
        return qualname
    return f"{module}.{qualname}"


def _type_name(value: Any) -> str:
    return type_name_of(type(value))


def _safe_repr_head(value: Any, *, enabled: bool, length: int) -> str | None:
    if not enabled:
        return None
    try:
        return repr(value)[:length]
    except Exception as exc:  # noqa: BLE001
        # A repr that cannot be taken is "no repr"; the run interruption is
        # the run being stopped and must reach the Runner (review rc1 F01).
        if is_run_interrupted(exc):
            raise
        return None


def _summarize(value: Any, *, repr_head: str, repr_head_len: int) -> TypeSummary:
    return TypeSummary(
        type_name=_type_name(value),
        repr_head=_safe_repr_head(value, enabled=repr_head == "on", length=repr_head_len),
    )


def _summarize_outputs(value: Any, *, repr_head: str, repr_head_len: int) -> tuple[TypeSummary, ...]:
    """Summarize a return value: ``None`` -> none, a tuple -> one per element.

    This is the only summary implementation (#641): node records here and the
    Runner's tile outputs (``runner/execute.py``) both call it, so a value
    reads the same on either path. Internal; not public API.
    """
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(_summarize(item, repr_head=repr_head, repr_head_len=repr_head_len) for item in value)
    return (_summarize(value, repr_head=repr_head, repr_head_len=repr_head_len),)


#: ``RdeError.detail["kind"]`` of an argument rejection. The same literal is
#: ``rdetoolkit.report.failure.NODE_ARGUMENT_REJECTION``; core does not import
#: the report layer.
_ARGUMENT_REJECTION_KIND = "node_argument_rejection"
#: Characters kept of an annotation's text; annotations are code, not data.
_MAX_ANNOTATION_TEXT = 200
#: Sentinel for "every bound value matched"; ``None`` is a legal argument.
_ACCEPTED: Any = object()


def _mismatch_error(node_id: str, param_name: str, detail: dict[str, Any] | None = None) -> RdeExecutionError:
    error_def = ERROR_CATALOG[3002]
    error_cls: Any = RdeExecutionError
    return error_cls(
        code=3002,
        name=error_def.name,
        message=error_def.message_template.format(node_id=node_id, param_name=param_name),
        detail=detail,
    )


def _annotation_text(annotation: Any) -> str:
    """Render an annotation as type text (``int``, ``str | None``, ``pathlib.Path``)."""
    if isinstance(annotation, type):
        return type_name_of(annotation)
    try:
        text = str(annotation)
    except Exception as exc:  # noqa: BLE001
        if is_run_interrupted(exc):
            raise
        text = type(annotation).__name__
    return text[:_MAX_ANNOTATION_TEXT]


def _rejection_detail(node_id: str, param_name: str, annotation: Any, value: Any, iteration_index: int) -> dict[str, Any]:
    """Describe an argument rejection by names only, never by the value (#688).

    The call never ran, so this detail -- not a ``NodeCallRecord`` -- is how
    the Runner attributes the failure to its node and parameter.
    """
    return {
        "kind": _ARGUMENT_REJECTION_KIND,
        "node_id": node_id,
        "parameter": param_name,
        "expected_type": _annotation_text(annotation),
        "actual_type": _type_name(value),
        "iteration_index": iteration_index,
    }


def _matches_annotation(value: Any, annotation: Any) -> bool:
    """Check one value against one resolved annotation, shallowly (Design §4.4).

    "isinstance-based, generics checked shallowly up to origin": container
    elements are never inspected, only the runtime class the annotation names.

    * ``Any``, an empty annotation, an unresolved string / ``ForwardRef``, a
      ``TypeVar``, a ``NewType`` and ``Literal[...]`` accept every value.
      ``Literal`` value checks are deliberately out of scope.
    * ``None`` means ``NoneType``.
    * A union (``typing.Union``, ``X | Y``, ``Optional``) accepts when any
      member matches by these same rules.
    * A parametrized generic whose origin is a class (``list[int]``,
      ``dict[str, int]``, ``type[int]``, ``collections.abc.Sequence[int]``, a
      user ``Generic``) is ``isinstance(value, origin)``.
    * A plain class is ``isinstance``; a class ``isinstance`` cannot use (a
      Protocol that is not ``runtime_checkable``) accepts.

    Args:
        value: Runtime value bound to the parameter or returned.
        annotation: Resolved annotation (``Annotated`` already stripped).

    Returns:
        Whether the value satisfies the shallow check.
    """
    if annotation is inspect.Signature.empty or annotation is Any:
        return True
    if annotation is None:
        return value is None
    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        return any(_matches_annotation(value, member) for member in typing.get_args(annotation))
    target = annotation if origin is None else origin
    if not isinstance(target, type):
        return True
    try:
        return isinstance(value, target)
    except TypeError:
        return True


def _bound_values(value: Any, kind: object) -> Iterable[Any]:
    """Return the values one bound parameter carries (C04).

    ``*args: T`` annotates each positional element and ``**kwargs: T`` each
    keyword value, so the bound tuple / dict itself is never compared with
    ``T``.
    """
    if kind is inspect.Parameter.VAR_POSITIONAL:
        return cast("tuple[Any, ...]", value)
    if kind is inspect.Parameter.VAR_KEYWORD:
        return cast("dict[str, Any]", value).values()
    return (value,)


class CallLogRecorder:
    """Context manager that records ``@node`` calls in one active run."""

    def __init__(
        self,
        *,
        repr_head: Literal["on", "off"] = "off",
        repr_head_len: int = 80,
        type_check: Literal["off", "warn", "strict"] = "off",
        iteration_index: int = 0,
        sequence: CallSequence | None = None,
        invocation_listener: InvocationListener | None = None,
    ) -> None:
        """Create a recorder.

        Args:
            repr_head: Whether value reprs are captured in the call log.
            repr_head_len: Maximum captured repr length.
            type_check: Opt-in runtime type-check mode.
            iteration_index: Tile index stamped on every record.
            sequence: Run-scoped counter shared by every tile of one run.
                ``None`` gives this recorder a private counter, which is what
                a standalone recorder outside a Runner run wants.
            invocation_listener: Optional observer of in-flight invocations
                (#689). ``None`` -- a standalone recorder -- notifies nobody.
        """
        self.repr_head = repr_head
        self.repr_head_len = repr_head_len
        self.type_check = type_check
        self.iteration_index = iteration_index
        self._records: list[NodeCallRecord] = []
        self._sequence = sequence if sequence is not None else CallSequence()
        self._token: Token[CallLogRecorder | None] | None = None
        self._listener = invocation_listener
        # Invocation ids of the node calls currently on the stack, innermost
        # last; the top is the parent of the next nested invocation.
        self._open_invocations: list[str] = []

    @property
    def records(self) -> tuple[NodeCallRecord, ...]:
        """Recorded calls as an immutable tuple."""
        return tuple(self._records)

    def __enter__(self) -> Self:
        self._token = _active_recorder.set(self)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._token is not None:
            _active_recorder.reset(self._token)
            self._token = None

    def _check_types(self, node_id: str, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        if self.type_check == "off":
            return
        signature = inspect.signature(fn)
        hints = self._resolve_hints(fn)
        bound = signature.bind_partial(*args, **kwargs)
        for name, value in bound.arguments.items():
            parameter = signature.parameters[name]
            annotation = hints.get(name, parameter.annotation)
            rejected = next((item for item in _bound_values(value, parameter.kind) if not _matches_annotation(item, annotation)), _ACCEPTED)
            if rejected is _ACCEPTED:
                continue
            message = f"Node argument type mismatch for {node_id}.{name}"
            if self.type_check == "warn":
                warnings.warn(message, UserWarning, stacklevel=3)
                continue
            raise _mismatch_error(node_id, name, _rejection_detail(node_id, name, annotation, rejected, self.iteration_index))

    def _check_return_type(self, node_id: str, fn: Callable[..., Any], result: Any) -> None:
        """Validate the return value against the return annotation (Design §4.4).

        strict mode raises the cataloged mismatch error; warn mode emits a
        UserWarning; off is never reached (guarded by the caller).
        """
        if self.type_check == "off":
            return
        hints = self._resolve_hints(fn)
        annotation = hints.get("return", inspect.signature(fn).return_annotation)
        if _matches_annotation(result, annotation):
            return
        message = f"Node argument type mismatch for {node_id}.return"
        if self.type_check == "warn":
            # 4: _check_return_type <- _run_body <- call_node <- node wrapper.
            warnings.warn(message, UserWarning, stacklevel=4)
            return
        raise _mismatch_error(node_id, "return")

    @staticmethod
    def _resolve_hints(fn: Callable[..., Any]) -> dict[str, Any]:
        try:
            return typing.get_type_hints(fn, include_extras=False)
        except Exception as exc:  # noqa: BLE001
            if is_run_interrupted(exc):
                raise
            return {}

    def _summarize_inputs(self, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, TypeSummary]:
        signature = inspect.signature(fn)
        bound = signature.bind_partial(*args, **kwargs)
        return {
            name: _summarize(value, repr_head=self.repr_head, repr_head_len=self.repr_head_len)
            for name, value in bound.arguments.items()
        }

    def call_node(self, spec: Any, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        """Execute ``fn`` and append a call-log record.

        The argument check runs before the body, so an argument mismatch
        leaves no record: nothing was executed, and the call log records
        executed calls only. Once the body has run, every failure -- its own
        exception or a strict return-type mismatch -- is recorded as a
        ``failed`` call before it propagates (review rc1 F06), so the run
        error and the node events can name the call that produced it.

        Right before the body runs the invocation listener is told that the
        call is in flight, and once the record exists it is told how the call
        ended (#689). A ``BaseException`` that is not an ``Exception`` (a
        ``KeyboardInterrupt``, a process exit) leaves the start unmatched.
        """
        self._check_types(spec.id, fn, args, kwargs)
        started_at = datetime.now(timezone.utc).isoformat()
        start = time.perf_counter()
        inputs = self._summarize_inputs(fn, args, kwargs)
        invocation = NodeInvocation(
            invocation_id=f"inv-{self._sequence.next_invocation()}",
            node_id=spec.id,
            iteration_index=self.iteration_index,
            parent_invocation_id=self._open_invocations[-1] if self._open_invocations else None,
        )
        self._open_invocations.append(invocation.invocation_id)
        try:
            self._notify(lambda listener: listener.invocation_started(invocation))
            return self._run_body(spec, fn, args, kwargs, started_at=started_at, start=start, inputs=inputs, invocation=invocation)
        finally:
            self._open_invocations.pop()

    def _run_body(
        self,
        spec: Any,
        fn: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        started_at: str,
        start: float,
        inputs: dict[str, TypeSummary],
        invocation: NodeInvocation,
    ) -> Any:
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            record = self._append_failed(spec, started_at=started_at, duration_ms=_elapsed_ms(start), inputs=inputs, exc=exc)
            self._notify(lambda listener: listener.invocation_finished(invocation, record))
            raise
        duration_ms = _elapsed_ms(start)
        try:
            self._check_return_type(spec.id, fn, result)
        except Exception as exc:
            record = self._append_failed(spec, started_at=started_at, duration_ms=duration_ms, inputs=inputs, exc=exc)
            self._notify(lambda listener: listener.invocation_finished(invocation, record))
            raise
        record = self._append(
            spec,
            started_at=started_at,
            duration_ms=duration_ms,
            status="completed",
            inputs=inputs,
            outputs=_summarize_outputs(result, repr_head=self.repr_head, repr_head_len=self.repr_head_len),
            error=None,
        )
        self._notify(lambda listener: listener.invocation_finished(invocation, record))
        return result

    def _notify(self, notification: Callable[[InvocationListener], None]) -> None:
        """Deliver one listener notification without touching the call's outcome.

        The listener is observability (#689): an ordinary failure mutes it for
        the rest of this recorder, so the node still returns or raises exactly
        as it would without a listener. The run interruption (3004) is the run
        being stopped and propagates (review rc1 F01).
        """
        listener = self._listener
        if listener is None:
            return
        try:
            notification(listener)
        except Exception as exc:  # noqa: BLE001
            if is_run_interrupted(exc):
                raise
            self._listener = None

    def _append_failed(
        self,
        spec: Any,
        *,
        started_at: str,
        duration_ms: float,
        inputs: dict[str, TypeSummary],
        exc: Exception,
    ) -> NodeCallRecord:
        return self._append(
            spec,
            started_at=started_at,
            duration_ms=duration_ms,
            status="failed",
            inputs=inputs,
            outputs=(),
            error={"type": type(exc).__name__, "message": str(exc)},
        )

    def _append(
        self,
        spec: Any,
        *,
        started_at: str,
        duration_ms: float,
        status: Literal["completed", "failed"],
        inputs: dict[str, TypeSummary],
        outputs: tuple[TypeSummary, ...],
        error: dict[str, Any] | None,
    ) -> NodeCallRecord:
        # seq is allocated at append time: nested @node calls append their
        # records first, so pre-computing seq would duplicate numbers (R2:
        # the call log must be a deterministic, uniquely-ordered sequence).
        seq = self._sequence.next()
        record = NodeCallRecord(
            call_id=f"{spec.id}#{seq}",
            node_id=spec.id,
            parent_flow=current_flow_id(),
            seq=seq,
            iteration_index=self.iteration_index,
            started_at=started_at,
            duration_ms=duration_ms,
            status=status,
            inputs=inputs,
            outputs=outputs,
            error=error,
        )
        self._records.append(record)
        return record


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
