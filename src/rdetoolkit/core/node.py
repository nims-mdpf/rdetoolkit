"""V2 @node decorator and NodeSpec definition."""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar, overload

from rdetoolkit.core.calllog import get_active_recorder, type_name_of
from rdetoolkit.core.registry import register_node

F = TypeVar("F", bound=Callable[..., Any])
InputSchemaEntry = dict[str, str | bool | None]


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """Immutable, JSON-serializable node metadata.

    Attributes:
        id: Unique node identifier.
        name: Display name (function name).
        input_schema: Parameter names mapped to serializable type/default info.
        output_schema: Return type names in positional order.
        tags: Tuple of classification tags.
        version: Semantic version string.
        idempotent: Whether repeated execution yields the same result.
        source_location: "module:qualname" string identifying the function.
    """

    id: str
    name: str
    input_schema: dict[str, InputSchemaEntry]
    output_schema: tuple[str, ...]
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


def type_name(value: Any) -> str:
    """Return the C1 canonical type-name string for annotations and values."""
    target = type(value) if not isinstance(value, type) else value
    return type_name_of(target)


def _annotation_type_name(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return "typing.Any"
    if annotation is None:
        return "None"
    if isinstance(annotation, str):
        return annotation
    if isinstance(annotation, type):
        return type_name(annotation)
    return str(annotation).replace("typing.", "")


def _build_output_schema(return_type: Any) -> tuple[str, ...]:
    """Build the serializable output schema from a return annotation."""
    if return_type is type(None) or return_type is None:
        return ()

    origin = typing.get_origin(return_type)
    if origin is tuple:
        args = typing.get_args(return_type)
        if args:
            return tuple(_annotation_type_name(t) for t in args)

    return (_annotation_type_name(return_type),)


def _build_node_spec(
    func: Callable[..., Any],
    *,
    node_id: str | None,
    tags: tuple[str, ...],
    version: str,
    idempotent: bool,
) -> NodeSpec:
    """Build a NodeSpec by inspecting the function signature."""
    sig = inspect.signature(func)
    hints = _resolve_type_hints(func)

    input_schema: dict[str, InputSchemaEntry] = {}
    for name, param in sig.parameters.items():
        default = param.default
        input_schema[name] = {
            "type_name": _annotation_type_name(hints.get(name, Any)),
            "has_default": default is not inspect.Signature.empty,
            "default_repr": None if default is inspect.Signature.empty else repr(default),
        }

    return_type = hints.get("return", sig.return_annotation)
    output_schema = _build_output_schema(return_type)
    source_location = f"{func.__module__}:{func.__qualname__}"

    return NodeSpec(
        id=node_id or f"{func.__module__}.{func.__qualname__}",
        name=func.__name__,
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
    id: str | None = None,
    tags: list[str] | None = None,
    version: str = "0.0.0",
    idempotent: bool = False,
) -> Callable[[F], F]: ...


def node(
    func: F | None = None,
    /,
    *,
    id: str | None = None,  # noqa: A002
    tags: list[str] | None = None,
    version: str = "0.0.0",
    idempotent: bool = False,
) -> F | Callable[[F], F]:
    """Decorate a plain function as a registered, optionally recorded node."""
    tags_tuple = tuple(tags) if tags else ()

    def _decorator(fn: F) -> F:
        spec = _build_node_spec(fn, node_id=id, tags=tags_tuple, version=version, idempotent=idempotent)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            recorder = get_active_recorder()
            if recorder is None:
                return fn(*args, **kwargs)
            return recorder.call_node(spec, fn, args, kwargs)

        wrapper.__node_spec__ = spec  # type: ignore[attr-defined]
        register_node(spec, wrapper, fn)
        return wrapper  # type: ignore[return-value]

    if func is not None:
        return _decorator(func)
    return _decorator
