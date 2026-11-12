"""V2 eager ``@flow`` decorator."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, overload

from rdetoolkit._interrupt import is_run_interrupted
from rdetoolkit.core.registry import FlowSpec, register_flow
from rdetoolkit.exceptions import StructuredError

if TYPE_CHECKING:
    from rdetoolkit.types import RdeConfig

F = TypeVar("F", bound=Callable[..., Any])
_flow_stack_var: ContextVar[tuple[str, ...]] = ContextVar("rdetoolkit_flow_stack", default=())
#: The only placeholders of ``@flow(error_message=...)``. Every other brace is
#: literal text, so existing fixed messages never hit ``str.format`` errors.
_MESSAGE_PLACEHOLDER = re.compile(r"\{(error|error_type)\}")
#: ``@flow(prepare=...)``: called by the Runner with the run's ``inputdata``
#: directory and effective config, after config load and before mode discovery.
PrepareFn = Callable[[Path, "RdeConfig"], None]


def current_flow_id() -> str | None:
    """Return the currently executing immediate flow id, if any."""
    stack = _flow_stack_var.get()
    return stack[-1] if stack else None


@contextmanager
def push_flow(flow_id: str) -> Iterator[None]:
    """Make ``flow_id`` the immediate parent of every ``@node`` call in the body.

    This is the only writer of the flow stack. ``@flow`` uses it, and so does
    the v1 callback adapter, which records a dataset callback as a flow
    (Session J1 ruling #2): duplicating the ``ContextVar`` bookkeeping in two
    places is what the shared helper exists to prevent.

    Args:
        flow_id: Identifier recorded as ``NodeCallRecord.parent_flow``. It must
            be derived by :func:`derive_flow_id` so it equals the run's
            ``RunReport.flow_id`` (Design §3.4 addendum).

    Yields:
        ``None``; the stack entry lives for the duration of the ``with`` block
        and is removed even when the body raises.
    """
    stack = _flow_stack_var.get()
    token = _flow_stack_var.set((*stack, flow_id))
    try:
        yield
    finally:
        _flow_stack_var.reset(token)


def _qualified_name(fn: Callable[..., Any]) -> str:
    """Return the dotted ``module.qualname`` reference for a callable."""
    module = getattr(fn, "__module__", "")
    qualname = getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
    return f"{module}.{qualname}" if module else qualname


def derive_flow_id(fn: Callable[..., Any]) -> str:
    """Return the stable flow identifier for an executable entry point.

    One derivation serves both the flow stack and the run report, which is what
    keeps the Design §3.4 invariant ``parent_flow == RunReport.flow_id`` true:

    1. a callable decorated with ``@flow`` reports its ``FlowSpec.id``, so an
       explicit ``@flow(id=...)`` is honoured instead of being recomputed;
    2. anything else — a plain v1 dataset callback, a template wrapper — reports
       the default ``module.qualname`` form.

    Args:
        fn: Flow, callback, or wrapper selected for execution.

    Returns:
        The dotted stable reference. Colon-separated spellings belong to
        ``FlowSpec.source_location``, not to identifiers.
    """
    spec_id = getattr(getattr(fn, "__flow_spec__", None), "id", None)
    if isinstance(spec_id, str) and spec_id:
        return spec_id
    return _qualified_name(fn)


def _build_flow_spec(fn: Callable[..., Any], flow_id: str | None) -> FlowSpec:
    return FlowSpec(
        id=flow_id or _qualified_name(fn),
        name=fn.__name__,
        source_location=f"{fn.__module__}:{fn.__qualname__}",
    )


@overload
def flow(func: F, /) -> F: ...


@overload
def flow(
    *,
    id: str | None = None,
    error_code: int | None = None,
    error_message: str | None = None,
    prepare: PrepareFn | None = None,
) -> Callable[[F], F]: ...


def flow(  # noqa: PLR0913
    func: F | None = None,
    /,
    *,
    id: str | None = None,  # noqa: A002
    error_code: int | None = None,
    error_message: str | None = None,
    prepare: PrepareFn | None = None,
) -> F | Callable[[F], F]:
    """Decorate a plain Python function as a registered eager flow.

    Args:
        func: Function supplied by the bare decorator form.
        id: Optional stable flow identifier.
        error_code: User error code applied by the Runner to exceptions
            raised by the body or by ``prepare``. With only a message
            supplied, the default code is 3001. A ``StructuredError`` keeps
            its own code and message. v1 ``catch_exception_with_message`` used code 1, so a
            rewrite of it passes ``error_code=1`` explicitly (see the
            migration guide).
        error_message: Runner failure message. ``{error}`` is replaced by the
            body exception's text and ``{error_type}`` by its class name; all
            other text, including other braces, is kept verbatim. With only a
            code supplied, the original exception's message is retained.
        prepare: Optional run-level input preparation, called by the Runner
            as ``prepare(inputdata, config)`` once per run, after the config
            is loaded and before the mode is resolved -- so files it writes
            to ``inputdata`` (a split instrument file, a SmartTable CSV and
            its zip) decide the mode and the tiles. Both v2 entries
            (``workflows.run(flow=...)`` and ``rdetoolkit run --flow``) run
            it, ``--validate-only`` included, and it is recorded as
            ``prepare.*`` run events. ``--validate-only`` therefore may
            modify ``inputdata``, and a re-run (or ``rdetoolkit repro``) sees
            the already-prepared inputs, so it must be idempotent. ``config``
            is a copy: changing it does not change the run. The error options
            apply to its failures as to the body's; without them an ordinary
            exception fails the run with 3001 before any tile. Only the flow
            the Runner executes is prepared: ``prepare`` on a flow called from
            inside another flow is not run.

    Returns:
        A transparent decorated function, or its decorator. Direct calls retain
        ordinary exception semantics, including when error options are set,
        and never run ``prepare``.

    Raises:
        TypeError: If ``prepare`` is given and is not callable.
    """
    if prepare is not None and not callable(prepare):
        msg = (
            "flow prepare must be callable or None. Remediation: pass the "
            "preparation function itself, e.g. @flow(prepare=split_inputs)."
        )
        raise TypeError(msg)

    def _decorator(fn: F) -> F:
        spec = _build_flow_spec(fn, id)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with push_flow(spec.id):
                return fn(*args, **kwargs)

        wrapper.__flow_spec__ = spec  # type: ignore[attr-defined]
        wrapper.__flow_error_code__ = error_code  # type: ignore[attr-defined]
        wrapper.__flow_error_message__ = error_message  # type: ignore[attr-defined]
        wrapper.__flow_prepare__ = prepare  # type: ignore[attr-defined]
        register_flow(spec, wrapper)
        return wrapper  # type: ignore[return-value]

    if func is not None:
        return _decorator(func)
    return _decorator


def flow_prepare(fn: Callable[..., Any]) -> PrepareFn | None:
    """Return the input preparation a flow declared, if any.

    Args:
        fn: Registered or plain flow callable selected for execution.

    Returns:
        The ``@flow(prepare=...)`` callable, or ``None`` when none is declared.
    """
    prepare: PrepareFn | None = getattr(fn, "__flow_prepare__", None)
    return prepare


def flow_error(fn: Callable[..., Any], error: Exception) -> StructuredError | None:
    """Return the error a flow's error declaration publishes for ``error``.

    The declaration covers the flow's whole run: its body (``flow_for_runner``)
    and its ``prepare`` (the Runner, #573).

    Args:
        fn: Registered or plain flow callable selected for execution.
        error: Ordinary exception raised by the body or the preparation.

    Returns:
        The mapped ``StructuredError``, or ``None`` when the flow declares no
        error options or ``error`` keeps its own identity -- a
        ``StructuredError`` (v1 ``catch_exception_with_message`` parity) or
        the Runner's SIGTERM interruption.
    """
    code = getattr(fn, "__flow_error_code__", None)
    message = getattr(fn, "__flow_error_message__", None)
    if code is None and message is None:
        return None
    if isinstance(error, StructuredError) or is_run_interrupted(error):
        return None
    text = str(error) if message is None else _format_message(message, error)
    return StructuredError(text, 3001 if code is None else code)


def flow_for_runner(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Apply an optional flow error declaration at the Runner boundary.

    Args:
        fn: Registered or plain flow callable selected for execution.

    Returns:
        A callable preserving the signature and exception chain. Only ordinary
        exceptions raised by the body are mapped; a ``StructuredError`` keeps
        its own code and message (v1 ``catch_exception_with_message`` parity),
        and process-control exceptions and the Runner's SIGTERM interruption
        propagate unchanged.
    """
    code = getattr(fn, "__flow_error_code__", None)
    message = getattr(fn, "__flow_error_message__", None)
    if code is None and message is None:
        return fn

    @wraps(fn)
    def mapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as error:
            # A user-raised StructuredError already carries its own ecode/emsg
            # (v1 catch_exception_with_message parity, #589); flow_error
            # leaves it, and the SIGTERM interruption, unmapped.
            mapped_error = flow_error(fn, error)
            if mapped_error is None:
                raise
            raise mapped_error from error

    return mapped


def _format_message(message: str, error: BaseException) -> str:
    # One substitution pass: placeholder-like text in the exception's own
    # message is inserted literally, never expanded again.
    values = {"error": str(error), "error_type": type(error).__name__}
    return _MESSAGE_PLACEHOLDER.sub(lambda match: values[match.group(1)], message)
