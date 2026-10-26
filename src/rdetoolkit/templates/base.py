"""Thin ProcessingTemplate layer over eager flows and ordinary nodes."""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeGuard, TypeVar, cast

from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, RdeRegistryError
from rdetoolkit.templates import registry

F = TypeVar("F", bound=Callable[..., Any])


def slot(func: F) -> F:
    """Mark a skeleton method as a required template slot.

    The marker deliberately does not register a node. Concrete overrides are
    registered only when a depth-2 user class is defined.

    Args:
        func: Required slot declaration on a template skeleton.

    Returns:
        The declaration unchanged apart from private marker metadata.
    """
    func.__rdetoolkit_slot__ = True  # type: ignore[attr-defined]
    func.__rdetoolkit_slot_signature__ = inspect.signature(func)  # type: ignore[attr-defined]
    return func


def _template_error(code: int, **values: str) -> RdeRegistryError:
    error_def = ERROR_CATALOG[code]
    message = error_def.message_template.format(**values)
    message = f"{message} Remediation: {error_def.remediation}"
    error_cls: Any = RdeRegistryError
    return error_cls(code=code, name=error_def.name, message=message)


def _declared_slots(skeleton: type[Any]) -> dict[str, Callable[..., Any]]:
    return {
        name: cast(Callable[..., Any], method)
        for name, method in vars(skeleton).items()
        if callable(method) and getattr(method, "__rdetoolkit_slot__", False)
    }


def _declared_hooks(skeleton: type[Any]) -> set[str]:
    return {
        name
        for name, method in vars(skeleton).items()
        if callable(method)
        and not name.startswith("_")
        and not getattr(method, "__rdetoolkit_slot__", False)
    }


def _annotations_match(declared: Any, implemented: Any) -> bool:
    if declared is inspect.Signature.empty or implemented is inspect.Signature.empty:
        return declared is implemented
    return declared == implemented


def _resolved_hints(fn: Callable[..., Any]) -> dict[str, Any]:
    """Evaluate a function's annotations; empty when they cannot be resolved.

    Both the skeleton and a generated implementation usually carry string
    annotations (``from __future__ import annotations``), and the same type
    can be spelled differently (``Optional[Path]`` / ``Path | None``), so the
    shallow check compares the resolved objects, not the text (K4-F6 review).
    """
    try:
        return typing.get_type_hints(fn, include_extras=False)
    except Exception:  # noqa: BLE001
        return {}


def _signatures_match(declared: Callable[..., Any], implemented: Callable[..., Any]) -> bool:
    declared_signature = inspect.signature(declared)
    implemented_signature = inspect.signature(implemented)
    declared_parameters = tuple(declared_signature.parameters.values())
    implemented_parameters = tuple(implemented_signature.parameters.values())
    if len(declared_parameters) != len(implemented_parameters):
        return False
    declared_hints = _resolved_hints(declared)
    implemented_hints = _resolved_hints(implemented)
    for expected, actual in zip(declared_parameters, implemented_parameters, strict=True):
        if expected.name != actual.name or expected.kind is not actual.kind:
            return False
        if not _annotations_match(
            declared_hints.get(expected.name, expected.annotation),
            implemented_hints.get(actual.name, actual.annotation),
        ):
            return False
    return _annotations_match(
        declared_hints.get("return", declared_signature.return_annotation),
        implemented_hints.get("return", implemented_signature.return_annotation),
    )


def _validate_concrete_class(cls: type[Any], skeleton: type[Any]) -> None:
    members = vars(cls)
    if "__flow__" in members:
        raise _template_error(2103, method_name="__flow__")
    for slot_name, declaration in _declared_slots(skeleton).items():
        implementation = members.get(slot_name)
        if not callable(implementation):
            raise _template_error(2101, slot_name=slot_name)
        if not _signatures_match(declaration, implementation):
            raise _template_error(2102, slot_name=slot_name)
    try:
        cls()
    except TypeError as exc:
        raise _template_error(2105, class_name=cls.__name__) from exc


def _register_implementations(cls: type[Any], skeleton: type[Any]) -> None:
    member_names = set(_declared_slots(skeleton)) | _declared_hooks(skeleton)
    for method_name in member_names:
        implementation = vars(cls).get(method_name, getattr(skeleton, method_name, None))
        if not callable(implementation):
            continue
        annotations = dict(getattr(implementation, "__annotations__", {}))
        annotations.setdefault("self", cls)
        implementation.__annotations__ = annotations
        node_id = f"{cls.__module__}.{cls.__qualname__}.{method_name}"
        wrapped = node(id=node_id, tags=["template"])(implementation)
        setattr(cls, method_name, wrapped)


class ProcessingTemplate:
    """Base class for one-level domain processing template skeletons."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate and register template subclasses at definition time."""
        super().__init_subclass__(**kwargs)
        if ProcessingTemplate in cls.__bases__:
            registry.register_template(cls)
            return
        immediate_base = cls.__bases__[0]
        if ProcessingTemplate not in immediate_base.__bases__:
            raise _template_error(2104, class_name=cls.__name__)
        _validate_concrete_class(cls, immediate_base)
        _register_implementations(cls, immediate_base)
        registry.register_concrete_template(cls)


def flow_from_template(template_cls: type[ProcessingTemplate]) -> Callable[..., Any]:
    """Instantiate a concrete template and expose its skeleton flow as a callable.

    Args:
        template_cls: Valid depth-2 concrete template class.

    Returns:
        Callable with the bound flow's DI signature and concrete class identity.
    """
    instance = template_cls()
    bound_flow = instance.__flow__  # type: ignore[attr-defined]

    @wraps(bound_flow)
    def _flow(*args: Any, **kwargs: Any) -> Any:
        return bound_flow(*args, **kwargs)

    _flow.__module__ = template_cls.__module__
    _flow.__qualname__ = template_cls.__qualname__
    _flow.__name__ = template_cls.__name__
    _flow.__signature__ = inspect.signature(bound_flow)  # type: ignore[attr-defined]
    return _flow


def is_template_class(value: Any) -> TypeGuard[type[ProcessingTemplate]]:
    """Return whether a value is a ProcessingTemplate subclass class."""
    return inspect.isclass(value) and issubclass(value, ProcessingTemplate)


def is_concrete_template_class(value: Any) -> TypeGuard[type[ProcessingTemplate]]:
    """Return whether a value is a registered depth-2 template class."""
    return is_template_class(value) and value in registry.list_concrete_templates()
