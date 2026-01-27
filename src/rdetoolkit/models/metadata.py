from __future__ import annotations

from typing import Any, Final

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, RootModel, field_validator

MAX_VALUE_SIZE: Final[int] = 1024


class Variable(BaseModel):
    """Metadata class for the 'variable' attribute."""

    variable: dict[str, Any]

    @field_validator("variable")
    @classmethod
    def check_value_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validator that verifies that the size of the 'variable' type metadata value does not exceed 1024 bytes.

        Args:
            v (dict[str, Any]): Metadata of 'variable'

        Raises:
            ValueError: Exception error if the value of the metadata is more than 1024 bytes
        """
        for value in v.values():
            if not isinstance(v, str):
                continue
            if len(str(value).encode("utf-8")) > MAX_VALUE_SIZE:
                emsg = f"Value size exceeds {MAX_VALUE_SIZE} bytes: {v}"
                raise ValueError(emsg)
        return v


class MetaValue(BaseModel):
    """Metadata class for the 'value' and 'unit' attributes."""

    value: Any
    unit: str | None = None

    @field_validator("value")
    @classmethod
    def check_value_size(cls, v: Any) -> Any:
        """Validator that verifies that the size of the 'value' does not exceed 1024 bytes if it is a string.

        Args:
            v (dict[str, Any]): Value of the metadata

        Raises:
            ValueError: Exception error if the value of the metadata is more than 1024 bytes
        """
        if not isinstance(v, str):
            return v
        if len(str(v).encode("utf-8")) > MAX_VALUE_SIZE:
            emsg = f"Value size exceeds {MAX_VALUE_SIZE} bytes"
            raise ValueError(emsg)
        return v


class ValidableItems(RootModel):
    """A class representing validatable items of metadata.

    This class inherits from `RootModel`, and the `root` attribute holds a list of dictionaries,
    where each dictionary has a string as a key and a `MetaValue` as a value.

    Attributes:
        root (list[dict[str, MetaValue]]): A list of validatable items of metadata.
    """

    root: list[dict[str, MetaValue]]


class MetadataItem(BaseModel):
    """metadata.json class.

    Stores metadata extracted by the data structuring process.

    Attributes:
        constant (dict[str, MetaValue]): A set of metadata common to all measurements.
        variable (ValidableItems): An array of metadata sets that vary with each measurement.
    """

    constant: dict[str, MetaValue]
    variable: ValidableItems


class NameField(BaseModel):
    """Multilingual name field for metadata definition.

    Attributes:
        ja: Japanese name
        en: English name
    """

    ja: str
    en: str


class SchemaField(BaseModel):
    """Schema field for metadata definition.

    Attributes:
        type: Type of the metadata value. One of "array", "boolean", "integer", "number", "string"
        format: Optional format specifier. One of "date-time" or "duration"
    """

    type: str  # "array", "boolean", "integer", "number", "string"
    format: str | None = None  # "date-time", "duration"


class MetadataDefEntry(BaseModel):
    """Single metadata definition entry in metadata-def.json.

    Represents one metadata item definition. This is used for metadata-def.json,
    not for metadata.json (which uses MetadataItem instead).

    Attributes:
        name: Multilingual name (ja/en required)
        schema_field: Type and format definition (type required, serialized as "schema")
        unit: Optional unit for the metadata value
        description: Optional description
        uri: Optional URI/URL for the metadata key
        mode: Optional measurement mode
        order: Optional display order
        original_name: Optional original name (serialized as "originalName")

    Example:
        ```json
        {
            "temperature": {
                "name": {"ja": "温度", "en": "Temperature"},
                "schema": {"type": "number"},
                "unit": "K"
            }
        }
        ```
    """

    name: NameField
    schema_field: SchemaField = Field(alias="schema")
    unit: str | None = None
    description: str | None = None
    uri: AnyUrl | None = None
    mode: str | None = None
    order: int | None = None
    original_name: str | None = Field(default=None, alias="originalName")

    model_config = ConfigDict(
        # Allow undefined fields (e.g., "variable" field is ignored per docs)
        extra="allow",
        # Enable alias for JSON parsing and serialization
        populate_by_name=True,
    )


class MetadataDefinition(RootModel):
    """metadata-def.json root model.

    Represents the entire metadata definition file as a dictionary
    mapping metadata keys to their definitions. This is used for
    metadata-def.json, not for metadata.json (which uses MetadataItem instead).

    Example:
        ```json
        {
            "temperature": {
                "name": {"ja": "温度", "en": "Temperature"},
                "schema": {"type": "number"},
                "unit": "K"
            },
            "operator": {
                "name": {"ja": "測定者", "en": "Operator"},
                "schema": {"type": "string"}
            }
        }
        ```
    """

    root: dict[str, MetadataDefEntry]
