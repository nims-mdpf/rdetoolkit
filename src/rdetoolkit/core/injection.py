"""Flow-boundary dependency injection for v2 workflows."""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from typing import Any

from rdetoolkit.core.context import RunContext, get_reserved_mapping
from rdetoolkit.errors import ERROR_CATALOG, RdeRegistryError

_TYPE_TO_SLOT: dict[type, str] | None = None


def _get_type_to_slot() -> dict[type, str]:
    """Return the reserved type to ``RunContext`` slot mapping."""
    global _TYPE_TO_SLOT  # noqa: PLW0603
    if _TYPE_TO_SLOT is None:
        _TYPE_TO_SLOT = {reserved_type: name for name, reserved_type in get_reserved_mapping().items()}
    return dict(_TYPE_TO_SLOT)


def _resolve_type_hints(func: Callable[..., Any]) -> dict[str, Any]:
    """Resolve annotations for ``func`` without failing signature inspection."""
    try:
        return typing.get_type_hints(func, include_extras=False)
    except Exception:  # noqa: BLE001
        return {}


def _error_message(code: int, **fields: str) -> str:
    """Build an error message with catalog remediation embedded."""
    error_def = ERROR_CATALOG[code]
    message = error_def.message_template.format(**fields)
    if error_def.remediation:
        return f"{message}. {error_def.remediation}"
    return message  # pragma: no cover - current v2 catalog entries all carry remediation.


def _reserved_type_name(reserved_type: type) -> str:
    return getattr(reserved_type, "__name__", str(reserved_type))


def find_duplicate_reserved_annotations(flow_fn: Callable[..., Any]) -> dict[type, tuple[str, ...]]:
    """Find reserved types annotated on more than one flow parameter.

    Args:
        flow_fn: Flow-like callable whose signature is inspected.

    Returns:
        Mapping of duplicated reserved types to the parameter names carrying
        that annotation.
    """
    signature = inspect.signature(flow_fn)
    hints = _resolve_type_hints(flow_fn)
    reserved_types = set(_get_type_to_slot())
    names_by_type: dict[type, list[str]] = {}

    for name, parameter in signature.parameters.items():
        if parameter.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue
        annotation = hints.get(name, parameter.annotation)
        if annotation in reserved_types:
            names_by_type.setdefault(annotation, []).append(name)

    return {reserved_type: tuple(names) for reserved_type, names in names_by_type.items() if len(names) > 1}


def resolve_flow_kwargs(flow_fn: Callable[..., Any], run_context: RunContext) -> dict[str, Any]:
    """Resolve reserved flow parameters from a ``RunContext`` by type annotation.

    DI happens exactly once at the flow boundary. Parameter names are not used
    for matching; only the five reserved type annotations are injectible.

    Args:
        flow_fn: Flow-like callable whose parameters should be resolved.
        run_context: Runtime context containing reserved values.

    Returns:
        Keyword arguments to pass to ``flow_fn``.

    Raises:
        RdeRegistryError: If a required parameter is not resolvable or if a
            reserved type is annotated on more than one parameter.
    """
    duplicates = find_duplicate_reserved_annotations(flow_fn)
    if duplicates:
        reserved_type, param_names = next(iter(duplicates.items()))
        error_cls: Any = RdeRegistryError
        raise error_cls(
            code=2006,
            message=_error_message(
                2006,
                type_name=_reserved_type_name(reserved_type),
                param_names=", ".join(param_names),
            ),
            detail={"type_name": _reserved_type_name(reserved_type), "param_names": list(param_names)},
        )

    signature = inspect.signature(flow_fn)
    hints = _resolve_type_hints(flow_fn)
    type_to_slot = _get_type_to_slot()
    kwargs: dict[str, Any] = {}

    for name, parameter in signature.parameters.items():
        if parameter.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue
        annotation = hints.get(name, parameter.annotation)
        if annotation in type_to_slot:
            kwargs[name] = getattr(run_context, type_to_slot[annotation])
        elif parameter.default is inspect.Signature.empty:
            error_cls = RdeRegistryError
            raise error_cls(
                code=2003,
                message=_error_message(2003, param_name=name),
                detail={"param_name": name},
            )

    return kwargs
