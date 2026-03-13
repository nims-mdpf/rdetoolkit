"""V2 @node decorator and NodeSpec definition.

The ``@node`` decorator attaches a ``NodeSpec`` to a function without
altering its runtime behavior — decorated functions remain directly callable.
"""

from __future__ import annotations

import contextlib
import inspect
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
        func_name: Original function name.
        input_schema: Mapping of parameter names to type annotation strings.
        output_schema: Return type annotation string, or None.
        tags: Tuple of classification tags.
        version: Semantic version string.
        idempotent: Whether repeated execution yields the same result.
    """

    id: str
    func_name: str
    input_schema: dict[str, str]
    output_schema: str | None
    tags: tuple[str, ...]
    version: str
    idempotent: bool


def _build_node_spec(
    func: Callable[..., Any],
    *,
    tags: tuple[str, ...],
    version: str,
    idempotent: bool,
) -> NodeSpec:
    """Build a NodeSpec by inspecting the function signature."""
    sig = inspect.signature(func)
    hints: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        hints = {
            k: v
            for k, v in inspect.get_annotations(func, eval_str=False).items()
            if k != "return"
        }

    input_schema: dict[str, str] = {}
    for name, param in sig.parameters.items():
        if param.annotation is not inspect.Parameter.empty:
            ann = hints.get(name, param.annotation)
            input_schema[name] = ann if isinstance(ann, str) else getattr(ann, "__name__", str(ann))
        else:
            input_schema[name] = "Any"

    return_ann = sig.return_annotation
    output_schema: str | None = None
    if return_ann is not inspect.Signature.empty:
        output_schema = return_ann if isinstance(return_ann, str) else getattr(return_ann, "__name__", str(return_ann))

    return NodeSpec(
        id=func.__name__,
        func_name=func.__name__,
        input_schema=input_schema,
        output_schema=output_schema,
        tags=tags,
        version=version,
        idempotent=idempotent,
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
            return fn(*args, **kwargs)

        wrapper.__node_spec__ = spec  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    if func is not None:
        return _decorator(func)
    return _decorator
