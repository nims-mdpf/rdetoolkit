from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, overload

F = TypeVar('F', bound=Callable[..., Any])
InputSchemaEntry = dict[str, str | bool | None]

def type_name(value: Any) -> str: ...

@dataclass(frozen=True, slots=True)
class NodeSpec:
    id: str
    name: str
    input_schema: dict[str, InputSchemaEntry]
    output_schema: tuple[str, ...]
    tags: tuple[str, ...]
    version: str
    idempotent: bool
    source_location: str

@overload
def node(func: F, /) -> F: ...
@overload
def node(*, id: str | None = None, tags: list[str] | None = None, version: str = '0.0.0', idempotent: bool = False) -> Callable[[F], F]: ...
