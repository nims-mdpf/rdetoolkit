from _typeshed import Incomplete
from pydantic import BaseModel, RootModel
from typing import Any, Literal

class LangLabels(BaseModel):
    ja: str
    en: str

class Placeholder(BaseModel):
    ja: str
    en: str

class Options(BaseModel):
    widget: Literal['textarea'] | None
    rows: int | None
    unit: str | None
    placeholder: Placeholder | None

class MetaProperty(BaseModel):
    model_config: Incomplete
    label: LangLabels
    value_type: Literal['boolean', 'integer', 'number', 'string']
    description: str | None
    examples: list[bool | int | float | str] | None
    default: bool | int | float | str | None
    const: bool | int | float | str | None
    enum: list[bool | int | float | str] | None
    maximum: int | None
    exclusiveMaximum: int | None
    minimum: int | None
    exclusiveMinimum: int | None
    maxLength: int | None
    minLength: int | None
    pattern: str | None
    format: Literal['date', 'time', 'uri', 'uuid', 'markdown'] | None

class CustomItems(RootModel):
    root: dict[str, MetaProperty]
    def __iter__(self): ...
    def __getitem__(self, item): ...

class CustomField(BaseModel):
    obj_type: Literal['object']
    label: LangLabels
    required: list[str]
    properties: CustomItems

class TermId(BaseModel):
    const: str

class ClassId(BaseModel):
    const: str

class GeneralChildProperty(BaseModel):
    term_id: TermId

class GeneralProperty(BaseModel):
    object_type: Literal['object']
    required: list[Literal['termId', 'value']]
    properties: GeneralChildProperty

class SampleGeneralItems(RootModel):
    root: list[GeneralProperty] | None

class GeneralAttribute(BaseModel):
    obj_type: Literal['array']
    items: SampleGeneralItems

class SpecificChildProperty(BaseModel):
    term_id: TermId
    class_id: ClassId

class SpecificProperty(BaseModel):
    object_type: Literal['object']
    required: list[Literal['classId', 'termId', 'value']]
    properties: SpecificChildProperty

class SampleSpecificItems(RootModel):
    root: list[SpecificProperty]

class SpecificAttribute(BaseModel):
    obj_type: Literal['array']
    items: SampleSpecificItems

class BasicItemsValue(BaseModel):
    value_type: str | list | None
    format: Literal['date'] | None
    pattern: str | None
    description: str | None

class SamplePropertiesWhenAdding(BaseModel):
    sample_id: str | None
    ownerId: str
    composition: str | None
    referenceUrl: str | None
    description: str | None
    generalAttributes: GeneralAttribute | None
    specificAttributes: SpecificAttribute | None

class SampleProperties(BaseModel):
    generalAttributes: GeneralAttribute | None
    specificAttributes: SpecificAttribute | None

class SampleField(BaseModel):
    obj_type: Literal['object']
    label: LangLabels
    required: list[Literal['names', 'sampleId']]
    properties: SampleProperties

class BasicItems(BaseModel):
    dateSubmitted: BasicItemsValue
    dataOwnerId: BasicItemsValue
    dateName: BasicItemsValue
    instrumentId: BasicItemsValue | None
    experimentId: BasicItemsValue | None
    description: BasicItemsValue | None

class DatasetId(BaseModel):
    value_type: str

class Properties(BaseModel):
    custom: CustomField | None
    sample: SampleField | None

class InvoiceSchemaJson(BaseModel):
    model_config: Incomplete
    version: str
    schema_id: str
    description: str | None
    value_type: Literal['object']
    required: list[Literal['custom', 'sample']] | None
    properties: Properties
    def find_field(self, key: str, custom_only: bool = False) -> dict[str, Any] | None: ...
