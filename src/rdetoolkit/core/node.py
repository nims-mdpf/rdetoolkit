"""V2 @node decorator and NodeSpec definition.

The ``@node`` decorator attaches a ``NodeSpec`` to a function without
altering its runtime behavior — decorated functions remain directly callable.
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar, overload

F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """Immutable specification describing a node in a DAG workflow.

    Attributes:
        id: Unique node identifier (defaults to function name).
        name: Display name (function name).
        fn: Reference to the original unwrapped function.
        input_schema: Mapping of parameter names to actual type objects.
        output_schema: Mapping of output port names to actual type objects.
        tags: Tuple of classification tags.
        version: Semantic version string.
        idempotent: Whether repeated execution yields the same result.
        source_location: "module:qualname" string identifying the function.
    """

    id: str
    name: str
    fn: Callable[..., Any]
    input_schema: dict[str, type]
    output_schema: dict[str, type]
    tags: tuple[str, ...]
    version: str
    idempotent: bool
    source_location: str


def _resolve_type_hints(func: Callable[..., Any]) -> dict[str, Any]:
    """Resolve type hints to actual type objects.

    Uses ``typing.get_type_hints`` which evaluates string annotations
    (from ``__future__.annotations``) against the function's global namespace.
    Falls back to an empty dict on failure.
    """
    try:
        return typing.get_type_hints(func, include_extras=False)
    except Exception:  # noqa: BLE001
        return {}


def _build_output_schema(return_type: Any) -> dict[str, type]:
    """Build an output_schema dict from a resolved return type annotation.

    - ``None`` / ``NoneType`` -> ``{}``
    - ``tuple[X, Y, ...]``   -> ``{"_0": X, "_1": Y, ...}``
    - any other type          -> ``{"_return": <type>}``
    """
    if return_type is type(None) or return_type is None:
        return {}

    origin = typing.get_origin(return_type)
    if origin is tuple:
        args = typing.get_args(return_type)
        if args:
            return {f"_{i}": t for i, t in enumerate(args)}

    if isinstance(return_type, type):
        return {"_return": return_type}

    # For generic aliases like list[int], store as-is
    return {"_return": return_type}


def _build_node_spec(
    func: Callable[..., Any],
    *,
    tags: tuple[str, ...],
    version: str,
    idempotent: bool,
) -> NodeSpec:
    """Build a NodeSpec by inspecting the function signature."""
    sig = inspect.signature(func)
    hints = _resolve_type_hints(func)

    # Build input_schema with actual type objects
    input_schema: dict[str, type] = {}
    for name in sig.parameters:
        if name in hints:
            input_schema[name] = hints[name]
        else:
            input_schema[name] = Any

    # Build output_schema as dict[str, type]
    return_type = hints.get("return")
    output_schema = _build_output_schema(return_type)

    # Source location
    source_location = f"{func.__module__}:{func.__qualname__}"

    return NodeSpec(
        id=func.__name__,
        name=func.__name__,
        fn=func,
        input_schema=input_schema,
        output_schema=output_schema,
        tags=tags,
        version=version,
        idempotent=idempotent,
        source_location=source_location,
    )


@overload
def node(func: F, /) -> F: ...


@overload
def node(
    *,
    tags: list[str] | None = None,
    version: str = "0.0.0",
    idempotent: bool = False,
) -> Callable[[F], F]: ...


def node(
    func: F | None = None,
    /,
    *,
    tags: list[str] | None = None,
    version: str = "0.0.0",
    idempotent: bool = False,
) -> F | Callable[[F], F]:
    """Decorator that attaches a ``NodeSpec`` to a function.

    Can be used as ``@node``, ``@node()``, or ``@node(tags=[...], ...)``.
    The decorated function remains directly callable (transparency).

    Args:
        func: The function to decorate (when used without parentheses).
        tags: Optional classification tags.
        version: Semantic version string.
        idempotent: Whether the node is idempotent.

    Returns:
        The original function with ``__node_spec__`` attribute attached.
    """
    tags_tuple = tuple(tags) if tags else ()

    def _decorator(fn: F) -> F:
        spec = _build_node_spec(fn, tags=tags_tuple, version=version, idempotent=idempotent)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Deferred import to avoid circular dependency (node <-> flow)
            from rdetoolkit.core.flow import _is_tracing, _trace_node_call  # noqa: PLC0415

            if _is_tracing():
                return _trace_node_call(wrapper, *args, **kwargs)
            return fn(*args, **kwargs)

        wrapper.__node_spec__ = spec  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    if func is not None:
        return _decorator(func)
    return _decorator
