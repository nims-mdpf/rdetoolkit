from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class TemplateParameterSpec:
    name: str
    type_name: str

@dataclass(frozen=True, slots=True)
class TemplateMethodSpec:
    name: str
    parameters: tuple[TemplateParameterSpec, ...]
    return_type: str

@dataclass(frozen=True, slots=True)
class TemplateSpec:
    id: str
    name: str
    slots: tuple[TemplateMethodSpec, ...]
    hooks: tuple[TemplateMethodSpec, ...]
    domain_types: tuple[str, ...]

def register_template(template_cls: type[Any]) -> None: ...
def register_concrete_template(template_cls: type[Any]) -> None: ...
def list_templates() -> tuple[TemplateSpec, ...]: ...
def get_template(template_id_or_name: str) -> TemplateSpec: ...
def get_template_class(template_id_or_name: str) -> type[Any]: ...
def list_concrete_templates() -> tuple[type[Any], ...]: ...
