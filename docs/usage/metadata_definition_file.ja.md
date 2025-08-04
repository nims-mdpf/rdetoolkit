# テンプレートファイル

## 概要

RDEでは、データセットの構造と検証ルールを定義するためのテンプレートファイルを使用します。これらのファイルは、RDE構造化処理の実行時に重要な役割を果たし、データの整合性と品質を保証します。

## 前提条件

- JSON Schema の基本的な理解
- RDEデータセット構造の知識
- テキストエディタまたはJSON編集ツール

## テンプレートファイルの種類

RDEで扱う主要なテンプレートファイル：

- **invoice.schema.json**: 送り状のスキーマ定義
- **invoice.json**: 送り状データの実体
- **metadata-def.json**: メタデータ定義
- **metadata.json**: メタデータの実体

## invoice.schema.json について

### 概要

送り状のスキーマを定義するファイルです。JSON Schemaの標準仕様に準拠し、送り状の画面生成とバリデーションに使用されます。

!!! note "参考資料"
    [Creating your first schema - json-schema.org](https://json-schema.org/learn/getting-started-step-by-step)

### 基本構造

```json title="invoice.schema.json の基本構造"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
  "description": "RDEデータセットテンプレートサンプル固有情報invoice",
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

### フィールド定義

| 項目名 (JSONポインタ) | 型 | フォーマット | 必須 | 固定値 | 説明 |
|---------------------|----|-----------|----|-------|------|
| (ドキュメントルート) | object | - | ○ | - | JSONドキュメントのルート |
| /$schema | string | uri | ○ | `https://json-schema.org/draft/2020-12/schema` | メタスキーマのID |
| /$id | string | uri | ○ | - | このスキーマのユニークID |
| /description | string | - | - | - | スキーマの説明 |
| /type | string | - | ○ | "object" | 値は固定 |
| /required | array | - | ○ | - | 必須フィールドの配列 |
| /properties | object | - | ○ | - | プロパティ定義 |

### カスタム情報の定義

固有情報セクションの詳細構造：

```json title="カスタム情報の例"
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

### データ型とオプション

#### 利用可能なデータ型

| 型 | 説明 | 例 |
|----|------|-----|
| `string` | 文字列 | "sample text" |
| `number` | 数値（小数点含む） | 3.14 |
| `integer` | 整数 | 42 |
| `boolean` | 真偽値 | true, false |

#### オプション設定

```json title="オプション設定例"
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

### 試料情報の定義

試料情報セクションの構造：

```json title="試料情報の例"
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

## invoice.json について

### 概要

invoice.schema.jsonで定義されたスキーマに基づく実際のデータファイルです。

### 基本構造

```json title="invoice.json の例"
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

## metadata-def.json について

### 概要

メタデータの構造と制約を定義するファイルです。データセットに付随するメタデータの形式を規定します。

### 基本構造

```json title="metadata-def.json の例"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rde.nims.go.jp/rde/dataset-templates/metadata-def.json",
  "description": "メタデータ定義スキーマ",
  "type": "object",
  "properties": {
    "measurement": {
      "type": "object",
      "properties": {
        "temperature": {
          "type": "number",
          "unit": "K",
          "description": "測定温度"
        },
        "pressure": {
          "type": "number",
          "unit": "Pa",
          "description": "測定圧力"
        }
      }
    }
  }
}
```

## ベストプラクティス

### スキーマ設計のガイドライン

1. **一意性の確保**
   - `$id`フィールドは必ずユニークにする
   - キー名はファイル全体でユニークにする

2. **多言語対応**
   - `label`フィールドで日本語と英語の両方を提供
   - `placeholder`も多言語対応する

3. **バリデーション強化**
   - 適切な`required`フィールドを設定
   - データ型制約を明確に定義

4. **ユーザビリティ向上**
   - 分かりやすい`description`を記述
   - 適切な`placeholder`を設定

### 一般的な問題と対処法

#### スキーマエラー

```json title="よくあるエラー例"
{
  "required": ["custom"], // sampleが定義されているのに含まれていない
  "properties": {
    "custom": { /* ... */ },
    "sample": { /* ... */ }
  }
}
```

**修正方法:**
```json title="修正後"
{
  "required": ["custom", "sample"], // 両方を含める
  "properties": {
    "custom": { /* ... */ },
    "sample": { /* ... */ }
  }
}
```

#### 型定義エラー

```json title="エラー例"
{
  "sample1": {
    "type": "string",
    "format": "date",
    "default": 123 // 型が一致しない
  }
}
```

**修正方法:**
```json title="修正後"
{
  "sample1": {
    "type": "string",
    "format": "date",
    "default": "2023-01-01" // 正しい型
  }
}
```

## 実践例

### 完全なテンプレートファイルセット

実際のプロジェクトで使用する完全なテンプレートファイルの例：

```json title="完全な invoice.schema.json"
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rde.nims.go.jp/rde/dataset-templates/material_analysis/invoice.schema.json",
  "description": "材料分析データセット用送り状スキーマ",
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

## 次のステップ

- [バリデーション機能](validation.ja.md)でテンプレートファイルの検証方法を学ぶ
- [構造化処理](../user-guide/structured-processing.ja.md)でテンプレートファイルの活用方法を理解する
- [APIリファレンス](../rdetoolkit/validation.md)で詳細なバリデーション機能を確認する
