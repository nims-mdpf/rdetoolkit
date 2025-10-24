# Template Files

## Overview

In RDE, template files are used to define the structure of datasets and their validation rules. These files play a crucial role when running RDE structuring processes and ensure data consistency and quality.

## Prerequisites

* Basic understanding of JSON Schema
* Knowledge of the RDE dataset structure
* A text editor or JSON editing tool

## Types of Template Files

Main template files handled by RDE:

* **invoice.schema.json**: Schema definition for the invoice
* **invoice.json**: Actual invoice data
* **metadata-def.json**: Metadata definition
* **metadata.json**: Actual metadata

## About invoice.schema.json

### Overview

This file defines the schema for the invoice. It conforms to the standard JSON Schema specification and is used for invoice screen generation and validation.

!!! note "References"
[Creating your first schema - json-schema.org](https://json-schema.org/learn/getting-started-step-by-step)

### Basic Structure

```json title="Basic structure of invoice.schema.json"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
  "description": "RDE dataset template sample specific information invoice",
  "type": "object",
  "required": ["custom", "sample"],
  "properties": {
    "custom": {
      "type": "object",
      "label": {
        "ja": "固有情報",
        "en": "Custom Information"
      },
      "required": ["sample1", "sample2"],
      "properties": {
        "sample1": {
          "label": {
            "ja": "サンプル１",
            "en": "sample1"
          },
          "type": "string",
          "format": "date",
          "options": {
            "unit": "A"
          }
        },
        "sample2": {
          "label": {
            "ja": "サンプル２",
            "en": "sample2"
          },
          "type": "number",
          "options": {
            "unit": "b"
          }
        }
      }
    },
    "sample": {
      "type": "object",
      "label": {
        "ja": "試料情報",
        "en": "Sample Information"
      },
      "properties": {
        "generalAttributes": {
          "type": "array",
          "items": [
            {
              "type": "object",
              "required": ["termId"],
              "properties": {
                "termId": {
                  "const": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e"
                }
              }
            }
          ]
        },
        "specificAttributes": {
          "type": "array",
          "items": []
        }
      }
    }
  }
}
```

### Definition of invoice.schema.json

| Field name (JSON Pointer)      | Type    | Format | Req. | Fixed value                                    | Description                                                                                                                                      |
| ------------------------------ | ------- | ------ | ---- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| (Document root)                | object  | -      | ●    | -                                              | Root of the JSON document.                                                                                                                       |
| /$schema                       | string  | uri    | ●    | `https://json-schema.org/draft/2020-12/schema` | ID of the meta-schema (schema of schemas).                                                                                                       |
| /$id                           | string  | uri    | ●    | -                                              | ID of this schema. Must be unique.                                                                                                               |
| /description                   | string  | -      | -    | -                                              | Description of the schema.                                                                                                                       |
| /type                          | string  | -      | ●    | "object"                                       | Value is fixed.                                                                                                                                  |
| /required                      | array   | -      | ●    | -                                              | Include "custom" when entering custom information; include "sample" when entering sample information.                                            |
| /properties                    | object  | -      | ●    | -                                              |                                                                                                                                                  |
|   /custom                      | object  | -      | -    | -                                              | Object that stores invoice-specific custom information. Omit if custom information is not entered.                                               |
|     /type                      | string  | -      | ●    | "object"                                       | Value is fixed.                                                                                                                                  |
|     /label                     | object  | -      | ●    | -                                              | String used as the heading for custom information. Specify per language.                                                                         |
|       /ja                      | string  | -      | ●    | -                                              | Japanese label for the heading.                                                                                                                  |
|       /en                      | string  | -      | ●    | -                                              | English label for the heading.                                                                                                                   |
|     /required                  | object  | -      | ●    | -                                              | Specify required key names. Multiple allowed.                                                                                                    |
|     /properties                | object  | -      | ●    | -                                              | Map of custom information fields. The display/input order follows the order described in this schema.                                            |
|      /{name of the first key}  | object  | -      | -    | -                                              | Key name of the first field. Key names must be unique across the file.                                                                           |
|       /type                    | string  | -      | ●    | -                                              | Data type of the field value. Specify one of "boolean", "integer", "number", or "string". None of these allow null. *Note 1*                     |
|       /description             | string  | -      | -    | -                                              | Description of the field. Not shown on screen.                                                                                                   |
|       /examples                | array   | -      | -    | -                                              | Example values. Not shown on screen.                                                                                                             |
|       /default                 | any     | -      | -    | -                                              | Specify the initial value.                                                                                                                       |
|       /{first schema keyword}  | depends | -      | -    | -                                              | Keywords specifying constraints on the field value.                                                                                              |
|       /{second schema keyword} | depends | -      | -    | -                                              | Same as above.                                                                                                                                   |
|       /...                     | -       | -      | -    | -                                              |                                                                                                                                                  |
|       /label                   | object  | -      | ●    | -                                              | Label displayed on the screen for the field. Specify per language.                                                                               |
|         /ja                    | string  | -      | ●    | -                                              | Label when displayed in Japanese.                                                                                                                |
|         /en                    | string  | -      | ●    | -                                              | Label when displayed in English.                                                                                                                 |
|       /options                 | object  | -      | -    | -                                              | Options related to the field.                                                                                                                    |
|         /widget                | string  | -      | -    | -                                              | Used when explicitly specifying a UI widget. Only "textarea" can be specified. Normally, a widget is generated according to the value of `type`. |
|         /rows                  | integer | -      | -    | -                                              | Number of rows when the widget is a textarea.                                                                                                    |
|         /unit                  | string  | -      | -    | -                                              | Unit displayed on the screen.                                                                                                                    |
|         /placeholder           | object  | -      | -    | -                                              | Placeholder set on the UI widget. Specify per language. Optional.                                                                                |
|           /ja                  | string  | -      | -    | -                                              | Placeholder when displayed in Japanese.                                                                                                          |
|           /en                  | string  | -      | -    | -                                              | Placeholder when displayed in English.                                                                                                           |
|      /{name of the second key} | object  | -      | -    | -                                              | Key name of the second field.                                                                                                                    |
|      (repeat below)            | -       | -      | -    | -                                              |                                                                                                                                                  |
|   /sample                      | object  | -      | -    | -                                              | Object that stores sample information for the invoice. Omit if sample information is not entered.                                                |
|     /type                      | string  | -      | ●    | "object"                                       | Value is fixed.                                                                                                                                  |
|     /label                     | object  | -      | ●    | -                                              | String used as the heading for sample information. Specify per language.                                                                         |
|       /ja                      | string  | -      | ●    | -                                              | Japanese label for the heading.                                                                                                                  |
|       /en                      | string  | -      | ●    | -                                              | English label for the heading.                                                                                                                   |
|     /properties                | object  | -      | ●    | -                                              | Properties of the sample.                                                                                                                        |
|       /generalAttributes       | object  | -      | -    | -                                              | General attributes. Can be omitted if not entering general attributes.                                                                           |
|          /type                 | string  | -      | ●    | "array"                                        |                                                                                                                                                  |
|          /items                | array   | -      | ●    | -                                              |                                                                                                                                                  |
|            /0                  | object  | -      | -    | -                                              | First general attribute.                                                                                                                         |
|              /type             | string  | -      | ●    | "object"                                       |                                                                                                                                                  |
|              /required         | array   | -      | ●    | ["termId"]                                     | Required properties of a general attribute. Fixed.                                                                                               |
|              /properties       | object  | -      | ●    | -                                              |                                                                                                                                                  |
|                /termId         | object  | -      | ●    | -                                              |                                                                                                                                                  |
|                  /const        | string  | -      | ●    | -                                              | Term ID for this general attribute.                                                                                                              |
|            /1                  | object  | -      | -    | -                                              | Second general attribute.                                                                                                                        |
|            (repeat below)      | -       | -      | -    | -                                              |                                                                                                                                                  |
|       /specificAttributes      | object  | -      | -    | -                                              | Class-specific attributes. Can be omitted if not entering class-specific attributes.                                                             |
|          /type                 | string  | -      | ●    | "array"                                        |                                                                                                                                                  |
|          /items                | array   | -      | ●    | "string"                                       |                                                                                                                                                  |
|            /0                  | object  | -      | -    | -                                              | First class-specific attribute.                                                                                                                  |
|              /type             | string  | -      | ●    | "object"                                       |                                                                                                                                                  |
|              /required         | array   | -      | ●    | ["classId","termId"]                           | Required properties of a class-specific attribute. Fixed.                                                                                        |
|              /properties       | object  | -      | ●    | -                                              |                                                                                                                                                  |
|                /classId        | object  | -      | ●    | -                                              |                                                                                                                                                  |
|                  /const        | string  | uuid   | ●    | -                                              | Sample class ID for this class-specific attribute.                                                                                               |
|                /termId         | object  | -      | ●    | -                                              |                                                                                                                                                  |
|                  /const        | string  | -      | ●    | -                                              | Term ID for this class-specific attribute.                                                                                                       |
|            /1                  | object  | -      | -    | -                                              | Second class-specific attribute.                                                                                                                 |
|            (repeat below)      | -       | -      | -    | -                                              |                                                                                                                                                  |

### List of Available Schema Keywords in invoice.schema.json

The following table shows schema keywords that can be specified as constraints on field values.

| type              | Keyword          | Value type | Description                                                                                | Value constraints                    |
| ----------------- | ---------------- | ---------- | ------------------------------------------------------------------------------------------ | ------------------------------------ |
| All               | type             | string     | Specifies the value type. Possible values are "boolean", "integer", "number", or "string". | Only one type can be specified.      |
|                   | const            | depends    | Specifies a constant. When this keyword exists, input/edit is not allowed.                 |                                      |
|                   | enum             | array      | Specifies the allowed values.                                                              |                                      |
| number or integer | maximum          | number     | Declares that the number is less than or equal to the specified value.                     |                                      |
|                   | exclusiveMaximum | number     | Declares that the number is less than the specified value.                                 |                                      |
|                   | minimum          | number     | Declares that the number is greater than or equal to the specified value.                  |                                      |
|                   | exclusiveMinimum | number     | Declares that the number is greater than the specified value.                              |                                      |
| string            | maxLength        | integer    | Specifies the maximum length of the string.                                                | Value must be 2,147,483,647 or less. |
|                   | minLength        | integer    | Specifies the minimum length of the string (0 or more).                                    |                                      |
|                   | pattern          | string     | Declares that the string matches the specified regular expression pattern.                 | Limit to language-agnostic patterns. |
|                   | format           | string     | Specifies the string format. See `List of Formats` for allowable values.                   |                                      |

### List of Available Formats in invoice.schema.json

The following table shows values that the `format` schema keyword can take.

| type     | Keyword                                                                         |
| -------- | ------------------------------------------------------------------------------- |
| date     | Date. RFC 3339 full-date.                                                       |
| time     | Time. RFC 3339 full-time.                                                       |
| uri      | URI                                                                             |
| uuid     | UUID. A raw UUID, not in URN form.                                              |
| markdown | Markdown-formatted string. This format is not part of the JSON Schema standard. |

### About Options in invoice.schema.json

Various options related to fields can be specified using the `options` keyword. The following table shows keywords that can be specified as options.

| Keyword     | Value type | Description                                                                    |
| ----------- | ---------- | ------------------------------------------------------------------------------ |
| format      | string     | Explicitly specify the type of UI widget to generate. Only “textarea” allowed. |
| widget      | string     | Explicitly specify the type of UI widget to generate. Only “textarea” allowed. |
| rows        | integer    | The `rows` attribute value when the widget value is “textarea”.                |
| unit        | string     | Specifies the unit displayed.                                                  |
| placeholder | object     | Placeholder set on the UI widget. Can specify both Japanese and English.       |

## About invoice.json

### Overview

This is the actual data file based on the schema defined in `invoice.schema.json`.

### Basic Structure

```json title="Example of invoice.json"
{
  "datasetId": "1s1199df4-0d1v-41b0-1dea-23bf4dh09g12",
  "basic": {
    "dateSubmitted": "",
    "dataOwnerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
    "dataName": "test-dataset",
    "instrumentId": null,
    "experimentId": null,
    "description": null
  },
  "custom": {
    "sample1": "2023-01-01",
    "sample2": 1.0
  },
  "sample": {
    "sampleId": "",
    "names": ["test"],
    "composition": null,
    "referenceUrl": null,
    "description": null,
    "generalAttributes": [
      {
        "termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e",
        "value": null
      }
    ],
    "specificAttributes": [],
    "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439"
  }
}
```

## About metadata-def.json

### Overview

This file defines the structure and constraints of metadata. It specifies the format of metadata associated with datasets.

### Basic Structure

```json title="Example of metadata-def.json"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rde.nims.go.jp/rde/dataset-templates/metadata-def.json",
  "description": "Metadata definition schema",
  "type": "object",
  "properties": {
    "measurement": {
      "type": "object",
      "properties": {
        "temperature": {
          "type": "number",
          "unit": "K",
          "description": "Measurement temperature"
        },
        "pressure": {
          "type": "number",
          "unit": "Pa",
          "description": "Measurement pressure"
        }
      }
    }
  }
}
```

### Definition of invoice.json

| Field (JSON Pointer)  | Value type | Format | Req. | Description                                                                                                                                                                                                                                                 |
| --------------------- | ---------- | ------ | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (Document root)       | object     | -      | ●    |                                                                                                                                                                                                                                                             |
| /datasetId            | string     | uuid   | ●    | ID of the dataset where the data will be registered.                                                                                                                                                                                                        |
| /basic                | object     | -      | ●    | Object that stores the basic information of the invoice.                                                                                                                                                                                                    |
|   /dateSubmitted      | string     | date   | ●    | Date when the invoice was submitted. Read-only.                                                                                                                                                                                                             |
|   /dataOwnerId        | string     | -      | -    | ID of the user who owns the data.                                                                                                                                                                                                                           |
|   /dataName           | string     | -      | ●    | Name of the data.                                                                                                                                                                                                                                           |
|   /instrumentId       | string     | uuid   | -    | Instrument ID.                                                                                                                                                                                                                                              |
|   /experimentId       | string     | -      | -    | Experiment ID. Users can freely assign this.                                                                                                                                                                                                                |
|   /description        | string     | -      | -    | Description of the dataset.                                                                                                                                                                                                                                 |
| /custom               | object     | -      | -    | Object that stores invoice-specific custom information. The properties contained in the object vary depending on the invoice schema.                                                                                                                        |
|   …                   | -          | -      | -    |                                                                                                                                                                                                                                                             |
| /sample               | object     | -      | -    | Object that stores sample information for the invoice. Properties match the sample attributes of the Sample API except for `sampleId` and `ownerId`. If you do not have permission to view the sample, exclude its child properties from the output fields. |
|   /sampleId           | string     | uuid   | -    | Sample ID. If specified at the initial submission of the invoice, the following properties are unnecessary.                                                                                                                                                 |
|   /names              | array      | -      | ●    | List of sample names.                                                                                                                                                                                                                                       |
|     /0                | string     | -      | ●    | Primary name of the sample.                                                                                                                                                                                                                                 |
|     …                 | -          | -      | -    | Secondary and subsequent names.                                                                                                                                                                                                                             |
|   /composition        | string     | -      | -    | Composition of the sample.                                                                                                                                                                                                                                  |
|   /referenceUrl       | string     | uri    | -    | Reference URL of the sample.                                                                                                                                                                                                                                |
|   /description        | string     | -      | -    | Description of the sample.                                                                                                                                                                                                                                  |
|   /generalAttributes  | array      | -      | -    | List of general sample attributes. Corresponds to the “General” items on screen.                                                                                                                                                                            |
|     /0                | object     | -      | -    | First attribute. *Note 1:* For "boolean", "integer", "number", and "string", do not output if no value is set. Same applies below.                                                                                                                          |
|       /termId         | string     | uuid   | ●    | Term ID serving as the attribute name.                                                                                                                                                                                                                      |
|       /value          | string     | -      | -    | Attribute value.                                                                                                                                                                                                                                            |
|     …                 | -          | -      | ●    | Second and subsequent attributes.                                                                                                                                                                                                                           |
|   /specificAttributes | array      | -      | -    | List of specific sample attributes. Corresponds to the “Class-specific” items on screen.                                                                                                                                                                    |
|     /0                | object     | -      | -    | First attribute.                                                                                                                                                                                                                                            |
|       /classId        | string     | uuid   | ●    | Sample class ID.                                                                                                                                                                                                                                            |
|       /termId         | string     | uuid   | ●    | Term ID serving as the attribute name.                                                                                                                                                                                                                      |
|       /value          | string     | -      | -    | Attribute value.                                                                                                                                                                                                                                            |
|     …                 | -          | -      | -    | Second and subsequent attributes.                                                                                                                                                                                                                           |
|   /ownerId            | string     | -      | -    | ID of the sample owner.                                                                                                                                                                                                                                     |

## metadata-def.json

A file that declares the names and data types of metadata output by data structuring. Metadata entered in invoices and similar forms does **not** need to be defined in `metadata-def.json`.

### Example Construction of metadata-def.json

<details>
<summary>Example construction of metadata-def.json</summary>

```json
{
    "operator_identifier": {
        "name": {
            "ja": "測定者",
            "en": "Operator identifier"
        },
        "schema": {
            "type": "string"
        },
        "order": 1,
        "originalName": "Operator"
    },
    "comment": {
        "name": {
            "ja": "コメント",
            "en": "Comment"
        },
        "schema": {
            "type": "string"
        },
        "order": 2,
        "originalName": "Comment"
    },
    "memo": {
        "name": {
            "ja": "メモ",
            "en": "Memo"
        },
        "schema": {
            "type": "string"
        },
        "order": 3,
        "originalName": "Memo",
        "variable": 1
    },
    "measurement_operator": {
        "name": {
            "ja": "測定実施者",
            "en": "Measurement Operator"
        },
        "schema": {
            "type": "string"
        },
        "order": 4,
        "originalName": "Operator",
        "variable": 1
    },
    "specimen": {
        "name": {
            "ja": "試料",
            "en": "Specimen"
        },
        "schema": {
            "type": "string"
        },
        "order": 5,
        "originalName": "SampleName",
        "variable": 1
    },
    "peak": {
        "name": {
            "ja": "ピーク値",
            "en": "peak value"
        },
        "schema": {
            "type": "number"
        },
        "unit": "V"
        "order": 6,
        "variable": 1
    }
}
```

</details>

### Definition of metadata-def.json

| Field (JSON Pointer)      | Value type | Format | Req. | Description                                                                                                                                           |
| ------------------------- | ---------- | ------ | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| (Root)                    | object     | -      | ●    | Root of the JSON document.                                                                                                                            |
| /{name of the first key}  | object     | -      | ●    | Key name of the first metadata item. All key names must be unique within the file.                                                                    |
|   /name                   | object     | -      | ●    | -                                                                                                                                                     |
|     /ja                   | string     | -      | ●    | Japanese representation of the metadata item name.                                                                                                    |
|     /en                   | string     | -      | ●    | English representation of the metadata item name.                                                                                                     |
|   /schema                 | object     | -      | ●    | Use the JSON Schema (2020-12) keywords `type` and `format`. Definitions of these keywords follow JSON Schema.                                         |
|     /type                 | string     | -      | ●    | "s Type of the metadata value. Possible values are "array", "boolean", "integer", "number", "string". For "array", the element type is not specified. |
|     /format               | string     | -      | -    | "d Format of the metadata value. Possible values are "date-time", "duration".                                                                         |
|   /unit                   | string     | -      | -    | Unit appended to the metadata value. Omit if there is no unit.                                                                                        |
|   /description            | string     | -      | -    | Description of the metadata item.                                                                                                                     |
|   /uri                    | string     | uri    | -    | URI/URL associated with the key of the metadata item.                                                                                                 |
|   /mode                   | string     | -      | -    | "S Measurement modes in which this metadata item is valid. If no measurement mode is specified, this may be omitted.                                  |
|   /order                  | integer    | -      | -    | Display order of the metadata item. Displayed in ascending order; display order is unspecified when values are equal.                                 |
| /{name of the second key} | object     | -      | -    | Key name of the second metadata item.                                                                                                                 |
|   (repeat below)          |            | -      | -    |                                                                                                                                                       |

!!! Note
In the construction example, `metadata-def.json` includes an attribute `variable` that is not defined. In such cases, RDE ignores `variable` when importing.

## metadata.json

metadata-def.jso is the file that stores metadata extracted by the data structuring process.

### Example Construction of metadata.json

<details>
<summary>Example construction of metadata.json</summary>

```json
{
  "constatn": {
    "operator_identifier": {
      "value": "Mike",
    },
    "comment": {
      "value": "sample data",
    },
    "memo": {
      "value": "test",
    },
    "measurement_operator": {
      "value": "Alice",
    },
  },
  "variable": [
    {
      "specimen": {
        "value": "C",
      },
      "peak": {
        "value": 120,
        "unit": "V"
      }
    },
    {
      "specimen": {
        "value": "H",
      },
      "peak": {
        "value": 58,
        "unit": "V"
      }
    },
    {
      "specimen": {
        "value": "O",
      },
      "peak": {
        "value": 190,
        "unit": "V"
      }
    },
  ]
}
```

</details>

### Definition of metadata.json

| Field (JSON Pointer) | Value type | Format | Req. | Description                                                                                                   |
| -------------------- | ---------- | ------ | ---- | ------------------------------------------------------------------------------------------------------------- |
| /constant            | object     | -      | ●    | Set of metadata common to all measurements. “Measurement” in this file definition includes computations, etc. |
|   /{key name}        | object     | -      | ●    | Key name of the metadata.                                                                                     |
|     /value           | depends    | -      | ●    | Metadata value.                                                                                               |
|     /unit            | string     | -      | -    | Unit of the metadata value. Optional if there is no unit.                                                     |
|   /{key name}        | object     | -      | ●    | Key name of the metadata.                                                                                     |
| ...                  | -          | -      | ●    |                                                                                                               |
| /variable            | array      | -      | ●    | Array of metadata sets that differ by measurement.                                                            |
|   /0                 | object     | -      | ●    | Set of metadata specific to the first measurement.                                                            |
|     /{key name}      | object     | -      | -    | Key name of the metadata. If a key does not exist in an array element, it may be omitted.                     |
|       /value         | depends    | -      | ●    | Metadata value.                                                                                               |
|       /unit          | string     | -      | -    | Unit of the metadata value. Optional if there is no unit.                                                     |
|     /{key name}      | object     | -      | -    | Key name of the metadata.                                                                                     |
|     ...              | -          | -      | ●    |                                                                                                               |
|   /1                 | object     | -      | ●    | Set of metadata specific to the second measurement.                                                           |
|   (repeat below)     | -          | -      | ●    |                                                                                                               |

### About Repeating Metadata

In RDE, repeating metadata can be defined as metadata sets that differ by measurement. When registering as repeating metadata, add a field `variable: 1`. In the RDE system, `variable` is not imported.

However, for metadata set to `variable: 1` in `metadata-def.json`, entries will be added under `variable` in `metadata.json`.

## catalog.schema.json

Schema file for the data catalog. The schema format conforms to the JSON Schema standard.

### Example Construction of catalog.schema.json

```json
{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/catalog.schema.json",
    "type": "object",
    "required": [
        "catalog"
    ],
    "description": "dataset_template_custom_sample",
    "properties": {
        "catalog": {
            "type": "object",
            "label": {
                "ja": "RDEデータセットテンプレートサンプル固有情報",
                "en": "dataset_template__custom_sample"
            },
            "required": [],
            "properties": {
                "dataset_title": {
                    "label": {
                        "ja": "データセット名",
                        "en": "Dataset Title"
                    },
                    "type": "string"
                },
                "abstract": {
                    "label": {
                        "ja": "概要",
                        "en": "Abstract"
                    },
                    "type": "string"
                },
                "data_creator": {
                    "label": {
                        "ja": "作成者",
                        "en": "Data Creator"
                    },
                    "type": "string"
                },
                "language": {
                    "label": {
                        "ja": "言語",
                        "en": "Language"
                    },
                    "type": "string"
                },
                "experimental_apparatus": {
                    "label": {
                        "ja": "使用装置",
                        "en": "Experimental Apparatus"
                    },
                    "type": "string"
                },
                "data_distribution": {
                    "label": {
                        "ja": "データの再配布",
                        "en": "Data Distribution"
                    },
                    "type": "string"
                },
                "raw_data_type": {
                    "label": {
                        "ja": "データの種類",
                        "en": "Raw Data Type"
                    },
                    "type": "string"
                },
                "stored_data": {
                    "label": {
                        "ja": "格納データ",
                        "en": "Stored Data"
                    },
                    "type": "string",
                    "options": {
                        "widget": "textarea",
                        "rows": 5
                    }
                },
                "remarks": {
                    "label": {
                        "ja": "備考",
                        "en": "Remarks"
                    },
                    "type": "string",
                    "options": {
                        "widget": "textarea",
                        "rows": 5
                    }
                },
                "references": {
                    "label": {
                        "ja": "参考論文",
                        "en": "References"
                    },
                    "type": "string"
                }
            }
        }
    }
}
```

### Definition of catalog.schema.json

| Field (JSON Pointer representation) | Value type | Format | Req. | Description                                                                                                                                      |
| ----------------------------------- | ---------- | ------ | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| (Document root)                     |            | object | -    | ●                                                                                                                                                |
| /$schema                            | string     | uri    | ●    | ID of the meta-schema (schema of schemas). Specify the fixed string `https://json-schema.org/draft/2020-12/schema`.                              |
| /$id                                | string     | uri    | ●    | ID of this schema. Must be unique.                                                                                                               |
| /description                        | string     | -      | -    | Description of this schema.                                                                                                                      |
| /type                               | string     | -      | ●    | Value is fixed.                                                                                                                                  |
| /required                           | array      | -      | -    | Value is fixed.                                                                                                                                  |
| /properties                         | object     | -      | ●    |                                                                                                                                                  |
|   /catalog                          | object     | -      | ●    | Object that stores data catalog items.                                                                                                           |
|     /type                           | string     | -      | ●    | Value is fixed.                                                                                                                                  |
|     /label                          | object     | -      | ●    | String used as a heading. Specify per language.                                                                                                  |
|       /ja                           | string     | -      | ●    | Japanese label for the heading.                                                                                                                  |
|       /en                           | string     | -      | ●    | English label for the heading.                                                                                                                   |
|     /required                       | object     | -      | ●    | Specify required key names. Multiple allowed.                                                                                                    |
|     /properties                     | object     | -      | ●    | Map of data catalog items. The display/input order follows the order described in this schema.                                                   |
|       /{name of the first key}      | object     | -      | ●    | Key name of the first item. Key names must be unique across the file.                                                                            |
|         /type                       | string     | -      | ●    | Data type of the field value. Specify one of "boolean", "integer", "number", or "string".                                                        |
|         /description                | string     | -      | -    | Description of the field. Not shown on screen.                                                                                                   |
|         /examples                   | array      | -      | -    | Example values. Not shown on screen.                                                                                                             |
|         /default                    | any        | -      | -    | Specify the initial value.                                                                                                                       |
|         /{first schema keyword}     | depends    | -      | -    | Keywords specifying constraints on the item’s value.                                                                                             |
|         /{second schema keyword}    | depends    | -      | -    | Same as above.                                                                                                                                   |
|         …       -                   | -          | -      |      |                                                                                                                                                  |
|         /label                      | object     | -      | ●    | Label for the item displayed on screen. Specify per language.                                                                                    |
|           /ja                       | string     | -      | ●    | Label when displayed in Japanese.                                                                                                                |
|           /en                       | string     | -      | ●    | Label when displayed in English.                                                                                                                 |
|         /options                    | object     | -      | -    | Options related to the item.                                                                                                                     |
|           /widget                   | string     | -      | -    | Used when explicitly specifying a UI widget. Only "textarea" can be specified. Normally, a widget is generated according to the value of `type`. |
|           /rows                     | integer    | -      | -    | Number of rows when the widget is a textarea.                                                                                                    |
|           /unit                     | string     | -      | -    | Unit displayed on the screen.                                                                                                                    |
|           /placeholder              | object     | -      | -    | Placeholder set on the UI widget. Specify per language. Optional.                                                                                |
|             /ja                     | string     | -      | -    | Placeholder when displayed in Japanese.                                                                                                          |
|             /en                     | string     | -      | -    | Placeholder when displayed in English.                                                                                                           |
|       /{name of the second key}     | object     | -      | ●    | Key name of the second item.                                                                                                                     |
|         (repeat below)-             | -          | -      |      |                                                                                                                                                  |

### List of Available Schema Keywords in catalog.schema.json

The following table shows schema keywords that can be specified as constraints on field values.

| type              | Keyword          | Value type | Description                                                                                | Value constraints                    |
| ----------------- | ---------------- | ---------- | ------------------------------------------------------------------------------------------ | ------------------------------------ |
| All               | type             | string     | Specifies the value type. Possible values are "boolean", "integer", "number", or "string". | Only one type can be specified.      |
|                   | const            | depends    | Specifies a constant. When this keyword exists, input/edit is not allowed.                 |                                      |
|                   | enum             | array      | Specifies the allowed values.                                                              |                                      |
| number or integer | maximum          | number     | Declares that the number is less than or equal to the specified value.                     |                                      |
|                   | exclusiveMaximum | number     | Declares that the number is less than the specified value.                                 |                                      |
|                   | minimum          | number     | Declares that the number is greater than or equal to the specified value.                  |                                      |
|                   | exclusiveMinimum | number     | Declares that the number is greater than the specified value.                              |                                      |
| string            | maxLength        | integer    | Specifies the maximum length of the string.                                                | Value must be 2,147,483,647 or less. |
|                   | minLength        | integer    | Specifies the minimum length of the string (0 or more).                                    |                                      |
|                   | pattern          | string     | Declares that the string matches the specified regular expression pattern.                 | Limit to language-agnostic patterns. |
|                   | format           | string     | Specifies the string format. See `List of Formats` for allowable values.                   |                                      |

### About Options in catalog.schema.json

Various options related to items can be specified using the `options` keyword. The following table shows keywords that can be specified as options.

| Keyword     | Value type | Description                                                                    |
| ----------- | ---------- | ------------------------------------------------------------------------------ |
| format      | string     | Explicitly specify the type of UI widget to generate. Only “textarea” allowed. |
| widget      | string     | Explicitly specify the type of UI widget to generate. Only “textarea” allowed. |
| rows        | integer    | The `rows` attribute value when the widget value is “textarea”.                |
| unit        | string     | Specifies the unit displayed.                                                  |
| placeholder | object     | Placeholder set on the UI widget. Can specify both Japanese and English.       |
