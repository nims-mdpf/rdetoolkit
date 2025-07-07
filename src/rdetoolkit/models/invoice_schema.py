from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class LangLabels(BaseModel):
    """A class representing labels in different languages."""

    ja: str
    en: str


class Placeholder(BaseModel):
    """A class representing placeholders in different languages.

    This class inherits from `BaseModel`, and the `ja` and `en` attributes hold the placeholders in Japanese and English, respectively.

    `properties.custom.properties.<custom key>.options.placeholder` is an instance of this class.
    """

    ja: str
    en: str


class Options(BaseModel):
    """Represents the options for a widget in the invoice schema.

    `properties.custom.properties.<custom key>.options` is an instance of this class.

    Attributes:
        widget (Optional[Literal["textarea"]]): The type of widget. Defaults to None.
        rows (Optional[int]): The number of rows for a textarea widget. Defaults to None.
        unit (Optional[str]): The unit of measurement for the widget. Defaults to None.
        placeholder (Optional[Placeholder]): The placeholder text for the widget. Defaults to None.
    """

    widget: Optional[Literal["textarea"]] = Field(default=None)
    rows: Optional[int] = Field(default=None)
    unit: Optional[str] = Field(default=None)
    placeholder: Optional[Placeholder] = Field(default=None)

    @model_validator(mode="after")
    def __check_row_for_widget_textarea(self) -> "Options":
        """Validates that the 'row' field is set when the 'widget' field is set to 'textarea'.

        Raises:
            ValueError: If the widget is set to 'textarea' and the 'row' is not set (None or not provided).

        Returns:
            Options: The validated value of the 'row' field. Returns the input value (v) if there are no issues.
        """
        if self.rows is None and self.widget is not None:
            raise ValueError('rows must be set when widget is "textarea"')
        return self


class MetaProperty(BaseModel):
    """Represents a meta property in the invoice schema.

    Attributes:
        label (LangLabels): The label of the meta property.
        value_type (Literal["boolean", "integer", "number", "string"]): The type of the value for the meta property.
        description (Optional[str]): The description of the meta property.
        examples (Optional[str]): Examples of the meta property.
        default (Optional[Union[bool, int, float, str]]): The default value for the meta property.
    """

    model_config = ConfigDict(extra="allow")

    label: LangLabels
    value_type: Literal["boolean", "integer", "number", "string"] = Field(..., alias="type")
    description: Optional[str] = Field(default=None)
    examples: Optional[list[Union[bool, int, float, str]]] = Field(default=None)
    default: Optional[Union[bool, int, float, str]] = Field(default=None)
    const: Optional[Union[bool, int, float, str]] = Field(default=None)
    enum: Optional[list[Union[bool, int, float, str]]] = Field(default=None)
    maximum: Optional[int] = Field(
        default=None,
        description="Declare that the number is less than or equal to the specified value. Only applicable when the type is a numeric type (integer, number).",
    )
    exclusiveMaximum: Optional[int] = Field(
        default=None,
        description="Declare that the number is less than the specified value. Only applicable when the type is a numeric type (integer, number).",
    )
    minimum: Optional[int] = Field(
        default=None,
        description="Declare that the number is greater than or equal to the specified value. Only applicable when the type is a numeric type (integer, number).",
    )
    exclusiveMinimum: Optional[int] = Field(
        default=None,
        description="Declare that the number is greater than the specified value. Only applicable when the type is a numeric type (integer, number).",
    )
    maxLength: Optional[int] = Field(default=None, description="Specify the maximum length of the string.")
    minLength: Optional[int] = Field(default=None, description="Specify the minimum length of the string. Must be 0 or more.")
    pattern: Optional[str] = Field(default=None, description="Declare that it has a pattern specified by a regular expression.")
    format: Optional[Literal["date", "time", "uri", "uuid", "markdown"]] = Field(
        default=None, description="Specify the format of the string. Refer to date, time, uri, uuid, markdown for possible values."
    )

    @model_validator(mode="after")
    def __check_numeric_type(self):
        # If any of the maximum, exclusiveMaximum, minimum, or exclusiveMinimum fields are set, the value_type must be either integer or number.
        if (self.maximum or self.exclusiveMaximum or self.minimum or self.exclusiveMinimum) and self.value_type not in ["integer", "number"]:
            raise ValueError("Custom Validation: The field must be of type integer or number.")
        return self

    @model_validator(mode="after")
    def __check_string_type(self):
        if (self.maxLength or self.minLength) and self.value_type != "string":
            raise ValueError("Custom Validation: The field must be of type string.")
        return self

    @model_validator(mode="after")
    def __check_const_type(self):
        if self.const is not None:
            # If the value of 'const' is different from 'value_type', raise an error.
            if not isinstance(self.value_type, type(self.const)):
                raise ValueError("Custom Validation: The two objects are of different types.")
        return self


class CustomItems(RootModel):
    """A class representing custom items in an invoice schema.

    `properties.custom.properties.<custom key>` is an instance of this class.

    Attributes:
        root (dict[str, MetaProperty]): A dictionary containing the custom items.
    """

    root: dict[str, MetaProperty]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class CustomField(BaseModel):
    """Represents a custom field in an invoice schema.

    `properties.custom.` is an instance of this class.
    """

    obj_type: Literal["object"] = Field(..., alias="type")
    label: LangLabels
    required: list[str]
    properties: CustomItems


class TermId(BaseModel):
    """Represents a term identifier.

    `properties.sample.properties.generalAtttirbutes.items.properties.termId` is an instance of this class.
    """

    const: str


class ClassId(BaseModel):
    """Represents the ClassId for an invoice.

    `properties.sample.properties.specificAttributes.items.properties.classId` is an instance of this class.
    """

    const: str


class GeneralChildProperty(BaseModel):
    """Represents a general child property.

    `properties.sample.properties.generalAtttirbutes.items.properties` is an instance of this class.
    """

    term_id: TermId = Field(..., alias="termId")


class GeneralProperty(BaseModel):
    """Represents a general property in the invoice schema.

    `properties.sample.properties.generalAtttirbutes.items` is an instance of this class.
    """

    object_type: Literal["object"] = Field(..., alias="type")
    required: list[Literal["termId", "value"]]
    properties: GeneralChildProperty


class SampleGeneralItems(RootModel):
    """Represents a sample general item.

    This class is used as the instance for `properties.sample.properties.generalAtttirbutes.items`.

    Attributes:
        root (Optional[list[GeneralProperty]]): The list of general properties. Defaults to None.
    """

    root: Optional[list[GeneralProperty]] = Field(default=None)


class GeneralAttribute(BaseModel):
    """Represents a general attribute in the invoice schema.

    `properties.sample.properties.generalAttribute` is an instance of this class.
    """

    obj_type: Literal["array"] = Field(..., alias="type")
    items: SampleGeneralItems


class SpecificChildProperty(BaseModel):
    """Represents a specificAttirbutes child property.

    `properties.sample.properties.specificAttributes.items.properties` is an instance of this class.
    """

    term_id: TermId = Field(..., alias="termId")
    class_id: ClassId = Field(..., alias="classId")


class SpecificProperty(BaseModel):
    """Represents a specificAttirbutes child property.

    `properties.sample.properties.specificAttributes.itemss` is an instance of this class.
    """

    object_type: Literal["object"] = Field(..., alias="type")
    required: list[Literal["classId", "termId", "value"]]
    properties: SpecificChildProperty


class SampleSpecificItems(RootModel):
    """Represents a specificAttirbutes child property.

    `properties.sample.properties.specificAttributes.itemss` is an instance of this class.
    """

    root: list[SpecificProperty]


class SpecificAttribute(BaseModel):
    """Represents a specific attribute in the invoice schema.

    `properties.sample.properties.specificAttribute` is an instance of this class.
    """

    obj_type: Literal["array"] = Field(..., alias="type")
    items: SampleSpecificItems


class BasicItemsValue(BaseModel):
    value_type: Union[str, list, None] = Field(default=None, alias="type")
    format: Optional[Literal["date"]] = Field(default=None)
    pattern: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class SamplePropertiesWhenAdding(BaseModel):
    """Represents the properties of a sample.

    `properties.sample.properties` is an instance of this class.
    """

    sample_id: Optional[str] = Field(default=None, alias="sampleId")
    ownerId: str = Field(pattern="^([0-9a-zA-Z]{56})$", description="sample ownere id", alias="ownerId")
    composition: Optional[str] = Field(default=None, alias="composition")
    referenceUrl: Optional[str] = Field(default=None, alias="referenceUrl")
    description: Optional[str] = Field(default=None, alias="description")
    generalAttributes: Optional[GeneralAttribute] = Field(default=None, alias="generalAttributes")
    specificAttributes: Optional[SpecificAttribute] = Field(default=None, alias="specificAttributes")


class SampleProperties(BaseModel):
    """Represents the properties of a sample.

    `properties.sample.properties` is an instance of this class.
    """

    generalAttributes: Optional[GeneralAttribute] = Field(default=None, alias="generalAttributes")
    specificAttributes: Optional[SpecificAttribute] = Field(default=None, alias="specificAttributes")


class SampleField(BaseModel):
    """Represents a sample field in the invoice schema.

    `properties.sample` is an instance of this class.
    """

    obj_type: Literal["object"] = Field(..., alias="type")
    label: LangLabels
    required: list[Literal["names", "sampleId"]] = Field(default=["names", "sampleId"])
    properties: SampleProperties


class BasicItems(BaseModel):
    """Represents the basic items of an invoice.

    `properties.basic` is an instance of this class.
    """

    dateSubmitted: BasicItemsValue = Field(default=BasicItemsValue(type="string", format="date"))
    dataOwnerId: BasicItemsValue = Field(default=BasicItemsValue(type="string", pattern="^([0-9a-zA-Z]{56})$"))
    dateName: BasicItemsValue = Field(default=BasicItemsValue(type="string", pattern="^([0-9a-zA-Z]{56})$"))
    instrumentId: Optional[BasicItemsValue] = Field(
        default=BasicItemsValue(type="string", pattern="^$|^([0-9a-zA-Z]{8}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{12})$")
    )
    experimentId: Optional[BasicItemsValue] = Field(default=None)
    description: Optional[BasicItemsValue] = Field(default=None)


class DatasetId(BaseModel):
    """Represents the dataset ID for an invoice.

    `properties.datasetId` is an instance of this class.
    """

    value_type: str = Field(default="string", alias="type")


class Properties(BaseModel):
    """Represents the properties of an invoice.

    `properties` is an instance of this class.

    Attributes:
        custom (Optional[CustomField]): The custom field of the invoice.
        sample (Optional[str]): A sample field of the invoice.
    """

    custom: Optional[CustomField] = Field(default=None)
    sample: Optional[SampleField] = Field(default=None)


class InvoiceSchemaJson(BaseModel):
    """Invoice schema class.

    Example:
        To generate invoice.schema.json from the model, do as follows:
        ```python
        obj = InvoiceSchemaJson(
            version="https://json-schema.org/draft/2020-12/schema",
            schema_id="https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
            description="RDEデータセットテンプレートテスト用ファイル",
            type="object",
            properties=Properties()
        )
        print(obj.model_dump_json())
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    version: str = Field(default="https://json-schema.org/draft/2020-12/schema", validation_alias="$schema", serialization_alias="$schema")
    schema_id: str = Field(default="https://rde.nims.go.jp/rde/dataset-templates/", validation_alias="$id", serialization_alias="$id")
    description: Optional[str] = Field(default=None)
    value_type: Literal["object"] = Field(default="object", alias="type")
    required: Optional[list[Literal["custom", "sample"]]] = Field(default=None)
    properties: Properties

    @model_validator(mode="after")
    def __check_required_fields(self):
        if self.required is None:
            return self
        if "custom" in self.required and self.properties.custom is None:
            raise ValueError("custom is required but is None")
        elif "sample" in self.required and self.properties.sample is None:
            raise ValueError("sample is required but is None")
        return self

    @model_validator(mode="after")
    def __check_custom_fields(self):
        if not self.properties.custom:
            return self
        if "custom" not in self.required:
            raise ValueError("custom is required but is None")
        return self

    @model_validator(mode="after")
    def __check_smaple_field(self):
        if not self.properties.sample:
            return self
        if "sample" not in self.required:
            raise ValueError("sample is required but is None")
        return self
