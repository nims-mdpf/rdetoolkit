# Template Files

## Overview

RDE uses template files to define dataset structure and validation rules. These files play a crucial role during RDE structured processing execution, ensuring data consistency and quality.

## Prerequisites

- Basic understanding of JSON Schema
- Knowledge of RDE dataset structure
- Text editor or JSON editing tools

## Types of Template Files

Main template files used in RDE:

- **invoice.schema.json**: Invoice schema definition
- **invoice.json**: Actual invoice data
- **metadata-def.json**: Metadata definition
- **metadata.json**: Actual metadata

## About invoice.schema.json

### Overview

This file defines the invoice schema. It complies with JSON Schema standard specifications and is used for invoice screen generation and validation.

!!! note "Reference"
    [Creating your first schema - json-schema.org](https://json-schema.org/learn/getting-started-step-by-step)

### Basic Structure

```json title="Basic structure of invoice.schema.json"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
  "description": "RDE dataset template sample custom information invoice",
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

### Field Definitions

| Field Name (JSON Pointer) | Type | Format | Required | Fixed Value | Description |
|---------------------------|------|--------|----------|-------------|-------------|
| (Document Root) | object | - | ○ | - | JSON document root |
| /$schema | string | uri | ○ | `https://json-schema.org/draft/2020-12/schema` | Meta-schema ID |
| /$id | string | uri | ○ | - | Unique ID for this schema |
| /description | string | - | - | - | Schema description |
| /type | string | - | ○ | "object" | Fixed value |
| /required | array | - | ○ | - | Array of required fields |
| /properties | object | - | ○ | - | Property definitions |

### Custom Information Definition

Detailed structure of the custom information section:

```json title="Custom information example"
"custom": {
  "type": "object",
  "label": {
    "ja": "固有情報",
    "en": "Custom Information"
  },
  "required": ["sample1"],
  "properties": {
    "sample1": {
      "label": {
        "ja": "サンプル１",
        "en": "sample1"
      },
      "type": "string",
      "format": "date",
      "options": {
        "unit": "A",
        "placeholder": {
          "ja": "日付を入力してください",
          "en": "Please enter date"
        }
      }
    }
  }
}
```

### Data Types and Options

#### Available Data Types

| Type | Description | Example |
|------|-------------|---------|
| `string` | Text string | "sample text" |
| `number` | Number (including decimals) | 3.14 |
| `integer` | Integer | 42 |
| `boolean` | Boolean value | true, false |

#### Option Settings

```json title="Option settings example"
"options": {
  "widget": "textarea",
  "rows": 5,
  "unit": "mm",
  "placeholder": {
    "ja": "値を入力してください",
    "en": "Please enter value"
  }
}
```

### Sample Information Definition

Structure of the sample information section:

```json title="Sample information example"
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
      "items": [
        {
          "type": "object",
          "required": ["classId", "termId"],
          "properties": {
            "classId": {
              "const": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b"
            },
            "termId": {
              "const": "3250c45d-0ed6-1438-43b5-eb679918604a"
            }
          }
        }
      ]
    }
  }
}
```

## About invoice.json

### Overview

This is the actual data file based on the schema defined in invoice.schema.json.

### Basic Structure

```json title="invoice.json example"
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

This file defines the structure and constraints of metadata. It specifies the format of metadata accompanying datasets.

### Basic Structure

```json title="metadata-def.json example"
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

## Best Practices

### Schema Design Guidelines

1. **Ensure Uniqueness**
   - Make `$id` field always unique
   - Make key names unique throughout the file

2. **Multilingual Support**
   - Provide both Japanese and English in `label` fields
   - Make `placeholder` multilingual as well

3. **Strengthen Validation**
   - Set appropriate `required` fields
   - Clearly define data type constraints

4. **Improve Usability**
   - Write clear `description`
   - Set appropriate `placeholder`

### Common Issues and Solutions

#### Schema Errors

```json title="Common error example"
{
  "required": ["custom"], // sample is defined but not included
  "properties": {
    "custom": { /* ... */ },
    "sample": { /* ... */ }
  }
}
```

**Solution:**
```json title="After correction"
{
  "required": ["custom", "sample"], // Include both
  "properties": {
    "custom": { /* ... */ },
    "sample": { /* ... */ }
  }
}
```

#### Type Definition Errors

```json title="Error example"
{
  "sample1": {
    "type": "string",
    "format": "date",
    "default": 123 // Type mismatch
  }
}
```

**Solution:**
```json title="After correction"
{
  "sample1": {
    "type": "string",
    "format": "date",
    "default": "2023-01-01" // Correct type
  }
}
```

## Practical Example

### Complete Template File Set

Example of complete template files used in actual projects:

```json title="Complete invoice.schema.json"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rde.nims.go.jp/rde/dataset-templates/material_analysis/invoice.schema.json",
  "description": "Invoice schema for material analysis dataset",
  "type": "object",
  "required": ["custom", "sample"],
  "properties": {
    "custom": {
      "type": "object",
      "label": {
        "ja": "測定条件",
        "en": "Measurement Conditions"
      },
      "required": ["temperature", "measurement_time"],
      "properties": {
        "temperature": {
          "label": {
            "ja": "測定温度",
            "en": "Measurement Temperature"
          },
          "type": "number",
          "minimum": 0,
          "maximum": 1000,
          "options": {
            "unit": "K",
            "placeholder": {
              "ja": "温度を入力してください",
              "en": "Enter temperature"
            }
          }
        },
        "measurement_time": {
          "label": {
            "ja": "測定時間",
            "en": "Measurement Time"
          },
          "type": "integer",
          "minimum": 1,
          "options": {
            "unit": "min",
            "placeholder": {
              "ja": "測定時間を入力してください",
              "en": "Enter measurement time"
            }
          }
        },
        "notes": {
          "label": {
            "ja": "備考",
            "en": "Notes"
          },
          "type": "string",
          "options": {
            "widget": "textarea",
            "rows": 3,
            "placeholder": {
              "ja": "特記事項があれば入力してください",
              "en": "Enter any special notes"
            }
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

## Next Steps

- Learn validation methods in [Validation Features](validation.en.md)
- Understand how to use template files in [Structured Processing](../user-guide/structured-processing.en.md)
- Check detailed validation features in [API Reference](../rdetoolkit/validation.md)
