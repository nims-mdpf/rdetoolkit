from pydantic import AnyUrl, BaseModel, RootModel
from typing import Any, Final

MAX_VALUE_SIZE: Final[int]

class Variable(BaseModel):
    variable: dict[str, Any]
    @classmethod
    def check_value_size(cls, v: dict[str, Any]) -> dict[str, Any]: ...

class MetaValue(BaseModel):
    value: Any
    unit: str | None
    @classmethod
    def check_value_size(cls, v: Any) -> Any: ...

class ValidableItems(RootModel):
    root: list[dict[str, MetaValue]]

class MetadataItem(BaseModel):
    constant: dict[str, MetaValue]
    variable: ValidableItems

class NameField(BaseModel):
    ja: str
    en: str

class SchemaField(BaseModel):
    type: str
    format: str | None

class MetadataDefEntry(BaseModel):
    name: NameField
    schema_field: SchemaField
    unit: str | None
    description: str | None
    uri: AnyUrl | None
    mode: str | None
    order: int | None
    original_name: str | None

class MetadataDefinition(RootModel):
    root: dict[str, MetadataDefEntry]
