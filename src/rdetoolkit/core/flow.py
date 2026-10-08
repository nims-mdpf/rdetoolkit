"""V2 eager ``@flow`` decorator."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, TypeVar, overload

from rdetoolkit.core.registry import FlowSpec, register_flow

F = TypeVar("F", bound=Callable[..., Any])
_flow_stack_var: ContextVar[tuple[str, ...]] = ContextVar("rdetoolkit_flow_stack", default=())


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
def flow(*, id: str | None = None) -> Callable[[F], F]: ...


def flow(func: F | None = None, /, *, id: str | None = None) -> F | Callable[[F], F]:  # noqa: A002
    """Decorate a plain Python function as a registered eager flow."""

    def _decorator(fn: F) -> F:
        spec = _build_flow_spec(fn, id)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with push_flow(spec.id):
                return fn(*args, **kwargs)

        wrapper.__flow_spec__ = spec  # type: ignore[attr-defined]
        register_flow(spec, wrapper)
        return wrapper  # type: ignore[return-value]

    if func is not None:
        return _decorator(func)
    return _decorator
