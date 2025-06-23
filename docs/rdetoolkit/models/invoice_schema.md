# Invoice Schema Module

The `rdetoolkit.models.invoice_schema` module provides Pydantic models for validating and managing RDE invoice schema JSON structures. This module defines a comprehensive set of models that correspond to the JSON schema format used in RDE (Research Data Exchange) systems.

## Overview

The invoice schema module implements a hierarchical validation system for dataset templates using Pydantic models. The module supports:

- **Multi-language Labels**: Support for Japanese and English labels
- **Custom Field Validation**: Flexible custom property definitions with type validation
- **Sample Data Management**: Structured handling of general and specific sample attributes
- **Schema Validation**: Comprehensive validation rules for JSON schema compliance
- **Type Safety**: Strong typing with runtime validation

## Core Classes

### InvoiceSchemaJson

The main class representing the complete invoice schema structure.

#### InvoiceSchemaJson Constructor

```python
InvoiceSchemaJson(
    version: str = "https://json-schema.org/draft/2020-12/schema",
    schema_id: str = "https://rde.nims.go.jp/rde/dataset-templates/",
    description: Optional[str] = None,
    value_type: Literal["object"] = "object",
    required: Optional[list[Literal["custom", "sample"]]] = None,
    properties: Properties
)
```

**Parameters:**

- `version` (str): JSON schema version (default: "<https://json-schema.org/draft/2020-12/schema>")
- `schema_id` (str): Schema identifier URL (default: "<https://rde.nims.go.jp/rde/dataset-templates/>")
- `description` (Optional[str]): Description of the schema
- `value_type` (Literal["object"]): Schema type, must be "object"
- `required` (Optional[list]): List of required top-level properties
- `properties` (Properties): Schema properties definition

#### Validation Rules (MetaProperty)

- If `"custom"` is in `required`, `properties.custom` must not be None
- If `"sample"` is in `required`, `properties.sample` must not be None
- If `properties.custom` exists, `"custom"` must be in `required`
- If `properties.sample` exists, `"sample"` must be in `required`

#### InvoiceSchemaJson Usage Example

```python
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson, Properties

# Create a basic invoice schema
schema = InvoiceSchemaJson(
    description="RDEデータセットテンプレートテスト用ファイル",
    properties=Properties()
)

# Generate JSON output
json_output = schema.model_dump_json()
print(json_output)
```

### Properties

Container for top-level schema properties.

#### Properties Constructor

```python
Properties(
    custom: Optional[CustomField] = None,
    sample: Optional[SampleField] = None
)
```

**Parameters:**

- `custom` (Optional[CustomField]): Custom field definitions
- `sample` (Optional[SampleField]): Sample field definitions

#### Properties Usage Example

```python
from rdetoolkit.models.invoice_schema import Properties, CustomField, SampleField

properties = Properties(
    custom=CustomField(...),
    sample=SampleField(...)
)
```

## Language Support

### LangLabels

Represents labels in multiple languages (Japanese and English).

#### LangLabels Constructor

```python
LangLabels(ja: str, en: str)
```

**Parameters:**

- `ja` (str): Japanese label
- `en` (str): English label

#### Placeholder Example

```python
from rdetoolkit.models.invoice_schema import LangLabels

label = LangLabels(
    ja="サンプル名",
    en="Sample Name"
)
```

### Placeholder

Represents placeholder text in multiple languages.

#### Placeholder Constructor

```python
Placeholder(ja: str, en: str)
```

**Parameters:**

- `ja` (str): Japanese placeholder text
- `en` (str): English placeholder text

#### LangLabels Example

```python
from rdetoolkit.models.invoice_schema import Placeholder

placeholder = Placeholder(
    ja="ここに入力してください",
    en="Please enter here"
)
```

## Custom Fields

### CustomField

Represents a custom field definition in the invoice schema.

#### CustomField Constructor

```python
CustomField(
    obj_type: Literal["object"],
    label: LangLabels,
    required: list[str],
    properties: CustomItems
)
```

**Parameters:**

- `obj_type` (Literal["object"]): Field type, must be "object"
- `label` (LangLabels): Multi-language label
- `required` (list[str]): List of required property names
- `properties` (CustomItems): Custom property definitions

### CustomItems

A dictionary-like container for custom property definitions.

#### CustomItems Constructor

```python
CustomItems(root: dict[str, MetaProperty])
```

**Parameters:**

- `root` (dict[str, MetaProperty]): Dictionary mapping property names to MetaProperty instances

#### Methods

##### \_\_iter\_\_()

```python
def __iter__()
```

Returns an iterator over the custom items.

##### \_\_getitem\_\_(item)

```python
def __getitem__(item: str) -> MetaProperty
```

Access a custom property by name.

#### CustomItems Example

```python
from rdetoolkit.models.invoice_schema import CustomItems, MetaProperty, LangLabels

# Create custom properties
custom_items = CustomItems(root={
    "temperature": MetaProperty(
        label=LangLabels(ja="温度", en="Temperature"),
        value_type="number",
        description="Sample temperature"
    )
})

# Access properties
temp_prop = custom_items["temperature"]
```

### MetaProperty

Defines a custom property with validation rules.

#### MetaProperty Constructor

```python
MetaProperty(
    label: LangLabels,
    value_type: Literal["boolean", "integer", "number", "string"],
    description: Optional[str] = None,
    examples: Optional[list[Union[bool, int, float, str]]] = None,
    default: Optional[Union[bool, int, float, str]] = None,
    const: Optional[Union[bool, int, float, str]] = None,
    enum: Optional[list[Union[bool, int, float, str]]] = None,
    maximum: Optional[int] = None,
    exclusiveMaximum: Optional[int] = None,
    minimum: Optional[int] = None,
    exclusiveMinimum: Optional[int] = None,
    maxLength: Optional[int] = None,
    minLength: Optional[int] = None,
    pattern: Optional[str] = None,
    format: Optional[Literal["date", "time", "uri", "uuid", "markdown"]] = None
)
```

**Parameters:**

- `label` (LangLabels): Multi-language property label
- `value_type` (Literal): Data type of the property value
- `description` (Optional[str]): Property description
- `examples` (Optional[list]): Example values
- `default` (Optional[Union]): Default value
- `const` (Optional[Union]): Constant value constraint
- `enum` (Optional[list]): Enumerated allowed values
- `maximum` (Optional[int]): Maximum value (for numeric types)
- `exclusiveMaximum` (Optional[int]): Exclusive maximum value
- `minimum` (Optional[int]): Minimum value (for numeric types)
- `exclusiveMinimum` (Optional[int]): Exclusive minimum value
- `maxLength` (Optional[int]): Maximum string length
- `minLength` (Optional[int]): Minimum string length
- `pattern` (Optional[str]): Regular expression pattern
- `format` (Optional[Literal]): String format constraint

#### CustomField Validation Rules

- Numeric constraints (`maximum`, `minimum`, etc.) only apply to `"integer"` or `"number"` types
- String length constraints (`maxLength`, `minLength`) only apply to `"string"` type
- If `const` is specified, its type must match `value_type`

#### MetaProperty Example

```python
from rdetoolkit.models.invoice_schema import MetaProperty, LangLabels

# Numeric property with constraints
temperature = MetaProperty(
    label=LangLabels(ja="温度", en="Temperature"),
    value_type="number",
    description="Sample temperature in Celsius",
    minimum=-273,
    maximum=1000,
    examples=[20.5, 25.0, 30.2]
)

# String property with pattern
sample_id = MetaProperty(
    label=LangLabels(ja="サンプルID", en="Sample ID"),
    value_type="string",
    pattern="^[A-Z]{2}[0-9]{4}$",
    examples=["AB1234", "CD5678"]
)

# Enumerated property
status = MetaProperty(
    label=LangLabels(ja="ステータス", en="Status"),
    value_type="string",
    enum=["active", "inactive", "pending"]
)
```

### Options

Represents widget options for custom properties.

#### Options Constructor

```python
Options(
    widget: Optional[Literal["textarea"]] = None,
    rows: Optional[int] = None,
    unit: Optional[str] = None,
    placeholder: Optional[Placeholder] = None
)
```

**Parameters:**

- `widget` (Optional[Literal["textarea"]]): Widget type
- `rows` (Optional[int]): Number of rows for textarea widget
- `unit` (Optional[str]): Unit of measurement
- `placeholder` (Optional[Placeholder]): Placeholder text

#### Validation Rules

- If `widget` is set to `"textarea"`, `rows` must be specified

#### Example

```python
from rdetoolkit.models.invoice_schema import Options, Placeholder

# Textarea widget options
textarea_options = Options(
    widget="textarea",
    rows=5,
    placeholder=Placeholder(
        ja="詳細を入力してください",
        en="Please enter details"
    )
)

# Numeric input with unit
numeric_options = Options(
    unit="°C",
    placeholder=Placeholder(
        ja="温度を入力",
        en="Enter temperature"
    )
)
```

## Sample Fields

### SampleField

Represents the sample field definition in the invoice schema.

#### SampleField Constructor

```python
SampleField(
    obj_type: Literal["object"],
    label: LangLabels,
    required: list[Literal["names", "sampleId"]] = ["names", "sampleId"],
    properties: SampleProperties
)
```

**Parameters:**

- `obj_type` (Literal["object"]): Field type, must be "object"
- `label` (LangLabels): Multi-language label
- `required` (list): Required property names (default: ["names", "sampleId"])
- `properties` (SampleProperties): Sample property definitions

### SampleProperties

Contains the properties for sample data.

#### SampleProperties Constructor

```python
SampleProperties(
    generalAttributes: Optional[GeneralAttribute] = None,
    specificAttributes: Optional[SpecificAttribute] = None
)
```

**Parameters:**

- `generalAttributes` (Optional[GeneralAttribute]): General sample attributes
- `specificAttributes` (Optional[SpecificAttribute]): Specific sample attributes

### SamplePropertiesWhenAdding

Extended sample properties used when adding new samples.

#### SamplePropertiesWhenAdding Constructor

```python
SamplePropertiesWhenAdding(
    sample_id: Optional[str] = None,
    ownerId: str,
    composition: Optional[str] = None,
    referenceUrl: Optional[str] = None,
    description: Optional[str] = None,
    generalAttributes: Optional[GeneralAttribute] = None,
    specificAttributes: Optional[SpecificAttribute] = None
)
```

**Parameters:**

- `sample_id` (Optional[str]): Sample identifier
- `ownerId` (str): Owner ID (must match pattern `^([0-9a-zA-Z]{56})$`)
- `composition` (Optional[str]): Sample composition
- `referenceUrl` (Optional[str]): Reference URL
- `description` (Optional[str]): Sample description
- `generalAttributes` (Optional[GeneralAttribute]): General attributes
- `specificAttributes` (Optional[SpecificAttribute]): Specific attributes

## Sample Attributes

### GeneralAttribute

Represents general attributes for samples.

#### GeneralAttribute Constructor

```python
GeneralAttribute(
    obj_type: Literal["array"],
    items: SampleGeneralItems
)
```

**Parameters:**

- `obj_type` (Literal["array"]): Attribute type, must be "array"
- `items` (SampleGeneralItems): General attribute items

### SampleGeneralItems

Container for general attribute items.

#### SampleGeneralItems Constructor

```python
SampleGeneralItems(root: Optional[list[GeneralProperty]] = None)
```

**Parameters:**

- `root` (Optional[list[GeneralProperty]]): List of general properties

### GeneralProperty

Defines a general property structure.

#### GeneralProperty Constructor

```python
GeneralProperty(
    object_type: Literal["object"],
    required: list[Literal["termId", "value"]],
    properties: GeneralChildProperty
)
```

**Parameters:**

- `object_type` (Literal["object"]): Property type, must be "object"
- `required` (list): Required fields (must include "termId" and "value")
- `properties` (GeneralChildProperty): Child properties

### GeneralChildProperty

Contains child properties for general attributes.

#### GeneralChildProperty Constructor

```python
GeneralChildProperty(term_id: TermId)
```

**Parameters:**

- `term_id` (TermId): Term identifier

### SpecificAttribute

Represents specific attributes for samples.

#### SpecificAttribute Constructor

```python
SpecificAttribute(
    obj_type: Literal["array"],
    items: SampleSpecificItems
)
```

**Parameters:**

- `obj_type` (Literal["array"]): Attribute type, must be "array"
- `items` (SampleSpecificItems): Specific attribute items

### SampleSpecificItems

Container for specific attribute items.

#### SampleSpecificItems Constructor

```python
SampleSpecificItems(root: list[SpecificProperty])
```

**Parameters:**

- `root` (list[SpecificProperty]): List of specific properties

### SpecificProperty

Defines a specific property structure.

#### SpecificProperty Constructor

```python
SpecificProperty(
    object_type: Literal["object"],
    required: list[Literal["classId", "termId", "value"]],
    properties: SpecificChildProperty
)
```

**Parameters:**

- `object_type` (Literal["object"]): Property type, must be "object"
- `required` (list): Required fields (must include "classId", "termId", and "value")
- `properties` (SpecificChildProperty): Child properties

### SpecificChildProperty

Contains child properties for specific attributes.

#### SpecificChildProperty Constructor

```python
SpecificChildProperty(
    term_id: TermId,
    class_id: ClassId
)
```

**Parameters:**

- `term_id` (TermId): Term identifier
- `class_id` (ClassId): Class identifier

## Identifier Classes

### TermId

Represents a term identifier with a constant value.

#### TermId Constructor

```python
TermId(const: str)
```

**Parameters:**

- `const` (str): Constant term identifier value

### ClassId

Represents a class identifier with a constant value.

#### ClassId Constructor

```python
ClassId(const: str)
```

**Parameters:**

- `const` (str): Constant class identifier value

## Basic Data Types

### DatasetId

Represents a dataset identifier.

#### DatasetId Constructor

```python
DatasetId(value_type: str = "string")
```

**Parameters:**

- `value_type` (str): Data type, defaults to "string"

### BasicItems

Contains basic invoice items with predefined structures.

#### BasicItems Constructor

```python
BasicItems(
    dateSubmitted: BasicItemsValue = BasicItemsValue(type="string", format="date"),
    dataOwnerId: BasicItemsValue = BasicItemsValue(type="string", pattern="^([0-9a-zA-Z]{56})$"),
    dateName: BasicItemsValue = BasicItemsValue(type="string", pattern="^([0-9a-zA-Z]{56})$"),
    instrumentId: Optional[BasicItemsValue] = BasicItemsValue(type="string", pattern="^$|^([0-9a-zA-Z]{8}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{12})$"),
    experimentId: Optional[BasicItemsValue] = None,
    description: Optional[BasicItemsValue] = None
)
```

### BasicItemsValue

Represents a basic value type with validation.

#### BasicItemsValue Constructor

```python
BasicItemsValue(
    value_type: Union[str, list, None] = None,
    format: Optional[Literal["date"]] = None,
    pattern: Optional[str] = None,
    description: Optional[str] = None
)
```

**Parameters:**

- `value_type` (Union[str, list, None]): Value type specification
- `format` (Optional[Literal["date"]]): Date format constraint
- `pattern` (Optional[str]): Regular expression pattern
- `description` (Optional[str]): Value description

## Complete Usage Examples

### Creating a Custom Field Schema

```python
from rdetoolkit.models.invoice_schema import (
    InvoiceSchemaJson, Properties, CustomField, CustomItems,
    MetaProperty, LangLabels, Options, Placeholder
)

# Define custom properties
temperature_prop = MetaProperty(
    label=LangLabels(ja="温度", en="Temperature"),
    value_type="number",
    description="Sample temperature in Celsius",
    minimum=-273,
    maximum=1000,
    unit="°C"
)

description_prop = MetaProperty(
    label=LangLabels(ja="説明", en="Description"),
    value_type="string",
    description="Detailed sample description",
    maxLength=1000,
    options=Options(
        widget="textarea",
        rows=5,
        placeholder=Placeholder(
            ja="サンプルの詳細説明を入力してください",
            en="Please enter detailed sample description"
        )
    )
)

# Create custom field
custom_field = CustomField(
    obj_type="object",
    label=LangLabels(ja="カスタムフィールド", en="Custom Fields"),
    required=["temperature"],
    properties=CustomItems(root={
        "temperature": temperature_prop,
        "description": description_prop
    })
)

# Create complete schema
schema = InvoiceSchemaJson(
    description="Custom sample analysis schema",
    required=["custom"],
    properties=Properties(custom=custom_field)
)

# Generate JSON
json_output = schema.model_dump_json(indent=2)
print(json_output)
```

### Creating a Sample Field Schema

```python
from rdetoolkit.models.invoice_schema import (
    SampleField, SampleProperties, GeneralAttribute, SpecificAttribute,
    SampleGeneralItems, SampleSpecificItems, GeneralProperty, SpecificProperty,
    GeneralChildProperty, SpecificChildProperty, TermId, ClassId, LangLabels
)

# Define general attribute
general_prop = GeneralProperty(
    object_type="object",
    required=["termId", "value"],
    properties=GeneralChildProperty(
        term_id=TermId(const="general_term_001")
    )
)

general_attr = GeneralAttribute(
    obj_type="array",
    items=SampleGeneralItems(root=[general_prop])
)

# Define specific attribute
specific_prop = SpecificProperty(
    object_type="object",
    required=["classId", "termId", "value"],
    properties=SpecificChildProperty(
        term_id=TermId(const="specific_term_001"),
        class_id=ClassId(const="class_001")
    )
)

specific_attr = SpecificAttribute(
    obj_type="array",
    items=SampleSpecificItems(root=[specific_prop])
)

# Create sample field
sample_field = SampleField(
    obj_type="object",
    label=LangLabels(ja="サンプル", en="Sample"),
    properties=SampleProperties(
        generalAttributes=general_attr,
        specificAttributes=specific_attr
    )
)

# Create complete schema
schema = InvoiceSchemaJson(
    description="Sample data schema",
    required=["sample"],
    properties=Properties(sample=sample_field)
)
```

### Validation and Error Handling

```python
from rdetoolkit.models.invoice_schema import MetaProperty, LangLabels
from pydantic import ValidationError

try:
    # This will raise a validation error
    invalid_prop = MetaProperty(
        label=LangLabels(ja="温度", en="Temperature"),
        value_type="string",  # String type
        minimum=0,           # But using numeric constraint
        maximum=100
    )
except ValidationError as e:
    print(f"Validation error: {e}")

try:
    # This will also raise a validation error
    invalid_options = Options(
        widget="textarea",  # Textarea widget
        # rows not specified - validation error
    )
except ValidationError as e:
    print(f"Options validation error: {e}")
```

### Working with Enum and Const Values

```python
from rdetoolkit.models.invoice_schema import MetaProperty, LangLabels

# Enumerated values
status_prop = MetaProperty(
    label=LangLabels(ja="ステータス", en="Status"),
    value_type="string",
    enum=["active", "inactive", "pending", "completed"],
    description="Current sample status"
)

# Constant value
version_prop = MetaProperty(
    label=LangLabels(ja="バージョン", en="Version"),
    value_type="string",
    const="1.0.0",
    description="Schema version"
)

# Boolean with default
published_prop = MetaProperty(
    label=LangLabels(ja="公開済み", en="Published"),
    value_type="boolean",
    default=False,
    description="Whether the sample data is published"
)
```

## Error Handling

### Common Validation Errors

The invoice schema models may raise `ValidationError` exceptions in the following cases:

#### Type Mismatch Errors

```python
try:
    MetaProperty(
        label=LangLabels(ja="テスト", en="Test"),
        value_type="string",
        minimum=0  # Invalid: minimum only applies to numeric types
    )
except ValidationError as e:
    print(f"Type mismatch: {e}")
```

#### Required Field Errors

```python
try:
    Options(
        widget="textarea"
        # Missing required 'rows' field
    )
except ValidationError as e:
    print(f"Missing required field: {e}")
```

#### Pattern Validation Errors

```python
try:
    SamplePropertiesWhenAdding(
        ownerId="invalid_id"  # Must match specific pattern
    )
except ValidationError as e:
    print(f"Pattern validation failed: {e}")
```

### Best Practices

1. **Use Type Hints**: Always use proper type hints for better IDE support and validation:

   ```python
   from typing import Optional
   from rdetoolkit.models.invoice_schema import MetaProperty, LangLabels

   def create_property(name: str, prop_type: str) -> MetaProperty:
       return MetaProperty(
           label=LangLabels(ja=f"{name}_ja", en=f"{name}_en"),
           value_type=prop_type
       )
   ```

2. **Validate Early**: Validate models as soon as they're created:

   ```python
   try:
       prop = MetaProperty(...)
       # Model is automatically validated on creation
   except ValidationError as e:
       # Handle validation errors immediately
       print(f"Invalid property: {e}")
   ```

3. **Use Model Validation**: Leverage Pydantic's validation features:

   ```python
   # Use model validation to ensure consistency
   schema = InvoiceSchemaJson(
       required=["custom"],
       properties=Properties(
           custom=custom_field  # This will be validated
       )
   )
   ```

4. **Handle Serialization**: Use proper serialization methods:

   ```python
   # Generate JSON with proper formatting
   json_str = schema.model_dump_json(indent=2, exclude_none=True)

   # Parse from JSON
   schema_dict = schema.model_dump()
   reconstructed = InvoiceSchemaJson(**schema_dict)
   ```

## Performance Notes

- All models use Pydantic v2 for optimal performance and validation
- Models support both dictionary and JSON serialization/deserialization
- Validation is performed at object creation time, not during access
- Use `model_dump()` for dictionary representation and `model_dump_json()` for JSON strings
- Large schemas with many custom properties are efficiently handled through lazy validation

## See Also

- [Pydantic Documentation](https://docs.pydantic.dev/) - For detailed information about Pydantic features
- [JSON Schema Specification](https://json-schema.org/) - For understanding JSON schema standards
- [RDE Documentation](https://rde.nims.go.jp/) - For RDE-specific schema requirements
