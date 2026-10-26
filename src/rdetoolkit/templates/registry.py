"""Registry metadata for ProcessingTemplate skeletons."""

from __future__ import annotations

import inspect
import types
import typing
from dataclasses import dataclass
from typing import Any

from rdetoolkit.core.calllog import type_name_of


@dataclass(frozen=True, slots=True)
class TemplateParameterSpec:
    """Serializable declaration of one template method parameter.

    Attributes:
        name: Parameter name from the skeleton declaration.
        type_name: Shallow, human-readable annotation.
    """

    name: str
    type_name: str


@dataclass(frozen=True, slots=True)
class TemplateMethodSpec:
    """Serializable declaration of a required slot or optional hook.

    Attributes:
        name: Declared method name.
        parameters: Parameters excluding ``self``.
        return_type: Shallow, human-readable return annotation.
    """

    name: str
    parameters: tuple[TemplateParameterSpec, ...]
    return_type: str


@dataclass(frozen=True, slots=True)
class TemplateSpec:
    """Discoverable metadata for one depth-1 template skeleton.

    Attributes:
        id: Fully qualified skeleton identifier.
        name: Skeleton class name.
        slots: Required slot declarations.
        hooks: Optional overridable hook declarations.
        domain_types: Non-builtin annotations referenced by slots.
    """

    id: str
    name: str
    slots: tuple[TemplateMethodSpec, ...]
    hooks: tuple[TemplateMethodSpec, ...]
    domain_types: tuple[str, ...]


_template_specs: dict[str, TemplateSpec] = {}
_template_classes: dict[str, type[Any]] = {}
_concrete_classes: list[type[Any]] = []


def _annotation_name(annotation: Any) -> str:
    """Render an annotation as a canonical, fully-qualified type expression.

    Unions and generics are rendered structurally (``pathlib.Path | None``,
    ``list[rdetoolkit.types.InputPaths]``, ``typing.Optional[...]`` becomes
    the union form) and every class is named through its public module
    (``pathlib.Path``, not the ``pathlib._local.Path`` Python 3.13 reports),
    so the generated template imports on every interpreter (K4-F6 review).
    """
    if annotation is inspect.Signature.empty:
        return "typing.Any"
    if annotation is None or annotation is type(None):
        return "None"
    if isinstance(annotation, str):
        return annotation
    composite = _composite_annotation_name(annotation)
    if composite is not None:
        return composite
    if isinstance(annotation, type):
        return type_name_of(annotation)
    return _fallback_annotation_name(annotation)


def _fallback_annotation_name(annotation: Any) -> str:
    """Name a non-class, non-composite annotation object (special forms, aliases)."""
    module = getattr(annotation, "__module__", "")
    qualname = getattr(annotation, "__qualname__", None)
    if qualname is not None:
        return qualname if module == "builtins" else f"{module}.{qualname}"
    return str(annotation)


def _composite_annotation_name(annotation: Any) -> str | None:
    """Render a union or a parametrized generic; ``None`` for anything else."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Union or origin is types.UnionType:
        return " | ".join(_annotation_name(arg) for arg in args)
    if origin is not None and args:
        rendered = ", ".join(_annotation_arg_name(arg) for arg in args)
        return f"{_annotation_name(origin)}[{rendered}]"
    return None


def _annotation_arg_name(arg: Any) -> str:
    """Render one generic argument; literals (``Literal["a"]``) keep their repr."""
    if arg is Ellipsis:
        return "..."
    if isinstance(arg, (str, bytes, int, float, bool)):
        return repr(arg)
    return _annotation_name(arg)


def _method_spec(name: str, method: Any) -> TemplateMethodSpec:
    signature = inspect.signature(method)
    try:
        hints = typing.get_type_hints(method, include_extras=False)
    except Exception:  # noqa: BLE001
        hints = {}
    parameters = tuple(
        TemplateParameterSpec(
            name=parameter_name,
            type_name=_annotation_name(hints.get(parameter_name, parameter.annotation)),
        )
        for parameter_name, parameter in signature.parameters.items()
        if parameter_name != "self"
    )
    return TemplateMethodSpec(
        name=name,
        parameters=parameters,
        return_type=_annotation_name(hints.get("return", signature.return_annotation)),
    )


def register_template(template_cls: type[Any]) -> None:
    """Register a depth-1 skeleton for CLI discovery.

    Args:
        template_cls: Direct ``ProcessingTemplate`` subclass.
    """
    members = vars(template_cls)
    slots = tuple(
        _method_spec(name, method)
        for name, method in members.items()
        if callable(method) and getattr(method, "__rdetoolkit_slot__", False)
    )
    hooks = tuple(
        _method_spec(name, method)
        for name, method in members.items()
        if callable(method)
        and not name.startswith("_")
        and not getattr(method, "__rdetoolkit_slot__", False)
    )
    domain_types = tuple(
        dict.fromkeys(
            parameter.type_name
            for method in slots
            for parameter in method.parameters
            if "." in parameter.type_name and not parameter.type_name.startswith("typing.")
        ),
    )
    template_id = f"{template_cls.__module__}.{template_cls.__qualname__}"
    _template_specs.setdefault(
        template_id,
        TemplateSpec(
            id=template_id,
            name=template_cls.__name__,
            slots=slots,
            hooks=hooks,
            domain_types=domain_types,
        ),
    )
    _template_classes.setdefault(template_id, template_cls)


def register_concrete_template(template_cls: type[Any]) -> None:
    """Track a concrete class for lint inspection without listing it."""
    _concrete_classes.append(template_cls)


def list_templates() -> tuple[TemplateSpec, ...]:
    """Return registered depth-1 skeleton specs in registration order."""
    return tuple(_template_specs.values())


def get_template(template_id_or_name: str) -> TemplateSpec:
    """Return a skeleton spec by full id or unambiguous class name.

    Raises:
        KeyError: If no registered skeleton matches.
    """
    if template_id_or_name in _template_specs:
        return _template_specs[template_id_or_name]
    matches = [spec for spec in _template_specs.values() if spec.name == template_id_or_name]
    if len(matches) == 1:
        return matches[0]
    raise KeyError(template_id_or_name)


def get_template_class(template_id_or_name: str) -> type[Any]:
    """Return a registered skeleton class by full id or class name."""
    spec = get_template(template_id_or_name)
    return _template_classes[spec.id]


def list_concrete_templates() -> tuple[type[Any], ...]:
    """Return concrete user classes tracked for internal lint inspection."""
    return tuple(_concrete_classes)
