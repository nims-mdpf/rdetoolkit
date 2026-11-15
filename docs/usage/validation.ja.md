# バリデーション機能

## 概要

RDEToolKitには、RDE関連ファイルの整合性と品質を確保するための包括的なバリデーション機能が実装されています。ローカル環境での開発時に事前チェックを行うことで、RDEへの登録時のエラーを防ぐことができます。

## 前提条件

- RDEToolKitのインストール
- テンプレートファイルの基本的な理解
- Python 3.10以上

## バリデーション対象ファイル

RDEToolKitでバリデーションの対象となる主要なファイル：

- **invoice.schema.json**: 送り状スキーマファイル
- **invoice.json**: 送り状データファイル
- **metadata-def.json**: メタデータ定義ファイル
- **metadata.json**: メタデータファイル

!!! warning "重要"
    これらのファイルは構造化処理内で内容を変更できるため、事前のバリデーションが重要です。

!!! note "関連ドキュメント"
    [テンプレートファイルについて](metadata_definition_file.ja.md)

## invoice.schema.json のバリデーション

### 概要

`invoice.schema.json`は、RDEの画面を構成するスキーマファイルです。構造化処理中での変更やローカルでの定義ファイル作成において、必要なフィールドが定義されているかを確認するためのチェック機能を提供します。

### 基本的な使用方法

```python title="invoice.schema.json バリデーション"
import json
from pydantic import ValidationError

from rdetoolkit.validation import InvoiceValidator
from rdetoolkit.exceptions import InvoiceSchemaValidationError

# スキーマ定義
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
    "description": "RDEデータセットテンプレートサンプル固有情報invoice",
    "type": "object",
    "required": ["custom", "sample"],
    "properties": {
        "custom": {
            "type": "object",
            "label": {"ja": "固有情報", "en": "Custom Information"},
            "required": ["sample1"],
            "properties": {
                "sample1": {
                    "label": {"ja": "サンプル１", "en": "sample1"},
                    "type": "string",
                    "format": "date",
                    "options": {"unit": "A"}
                },
                "sample2": {
                    "label": {"ja": "サンプル２", "en": "sample2"},
                    "type": "number",
                    "options": {"unit": "b"}
                },
            },
        },
        "sample": {
            "type": "object",
            "label": {"ja": "試料情報", "en": "Sample Information"},
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
                    ],
                },
                "specificAttributes": {"type": "array", "items": []},
            },
        },
    },
}

# データ例
data = {
    "datasetId": "1s1199df4-0d1v-41b0-1dea-23bf4dh09g12",
    "basic": {
        "dateSubmitted": "",
        "dataOwnerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
        "dataName": "test-dataset",
        "instrumentId": None,
        "experimentId": None,
        "description": None,
    },
    "custom": {"sample1": "2023-01-01", "sample2": 1.0},
    "sample": {
        "sampleId": "",
        "names": ["test"],
        "composition": None,
        "referenceUrl": None,
        "description": None,
        "generalAttributes": [
            {"termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "value": None}
        ],
        "specificAttributes": [],
        "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439",
    },
}

# スキーマファイルを保存
with open("temp/invoice.schema.json", "w") as f:
    json.dump(schema, f, ensure_ascii=False, indent=2)

# バリデーション実行
validator = InvoiceValidator("temp/invoice.schema.json")
try:
    validator.validate(obj=data)
    print("バリデーション成功")
except ValidationError as validation_error:
    raise InvoiceSchemaValidationError from validation_error
```

### バリデーションエラーの対処

`invoice.schema.json`のバリデーションエラーが発生した場合、`pydantic_core._pydantic_core.ValidationError`が発生します。

!!! note "参考資料"
    [pydantic_core._pydantic_core.ValidationError - Pydantic](https://docs.pydantic.dev/latest/errors/validation_errors/)

#### エラーメッセージの読み方

エラーメッセージには以下の情報が表示されます：

- **エラー原因となったフィールド**
- **エラータイプ**
- **エラーメッセージ**

```shell title="エラー例"
1. Field: required.0
   Type: literal_error
   Context: Input should be 'custom' or 'sample'
```

この例では、`required`フィールドに`custom`または`sample`が含まれている必要があることを示しています。

#### よくあるエラーと修正方法

**エラー例：**
```json title="問題のあるスキーマ"
{
    "required": ["custom"], // sampleが定義されているのに含まれていない
    "properties": {
        "custom": { /* ... */ },
        "sample": { /* ... */ }
    }
}
```

**修正方法：**
```json title="修正後のスキーマ"
{
    "required": ["custom", "sample"], // 両方を含める
    "properties": {
        "custom": { /* ... */ },
        "sample": { /* ... */ }
    }
}
```

## invoice.json のバリデーション

### 概要

`invoice.json`のバリデーションには、対応する`invoice.schema.json`が必要です。スキーマに定義された制約に従ってデータの整合性をチェックします。

### 基本的な使用方法

```python title="invoice.json バリデーション"
# 上記のschemaとdataを使用
validator = InvoiceValidator("temp/invoice.schema.json")
try:
    validator.validate(obj=data)
    print("invoice.json バリデーション成功")
except ValidationError as validation_error:
    print(f"バリデーションエラー: {validation_error}")
```

### 試料情報のバリデーション

ローカル環境で構造化処理を開発する場合、`invoice.json`（送り状）を事前に用意する必要があります。試料情報を定義する場合、以下の2つのケースが想定されます：

#### 1. 試料情報を新規に追加する場合

この場合、`sample`フィールドの`sampleId`、`names`、`ownerId`が必須になります。

```json title="新規試料情報"
"sample": {
    "sampleId": "de1132316439",
    "names": ["test"],
    "composition": null,
    "referenceUrl": null,
    "description": null,
    "generalAttributes": [
        {"termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "value": null}
    ],
    "specificAttributes": [],
    "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439"
}
```

#### 2. 既存の試料情報を参照する場合

この場合、`sample`フィールドの`sampleId`が必須になります。

```json title="既存試料情報参照"
"sample": {
    "sampleId": "de1132316439",
    "names": [],
    "composition": null,
    "referenceUrl": null,
    "description": null,
    "generalAttributes": [
        {"termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "value": null}
    ],
    "specificAttributes": [],
    "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439"
}
```

### 試料情報バリデーションエラー

上記の2つのケースのいずれかを満たしていない場合、バリデーションエラーが発生します。

```shell title="試料情報エラー例"
Error: Error in validating system standard field.
Please correct the following fields in invoice.json
Field: sample
Type: anyOf
Context: {'sampleId': '', 'names': 'test', 'generalAttributes': [...], 'specificAttributes': [], 'ownerId': ''} is not valid under any of the given schemas
```

### その他のバリデーションエラー

`invoice.json`の`basic`項目に過不足や値が不正な場合、`jsonschema`のバリデーションエラーが発生します。

```shell title="基本情報エラー例"
Error: Error in validating system standard item in invoice.schema.json.
Please correct the following fields in invoice.json
Field: basic.dataOwnerId
Type: pattern
Context: String does not match expected pattern
```

## metadata-def.json のバリデーション

### 概要

`metadata-def.json`は、メタデータの構造と制約を定義するファイルです。このファイルのバリデーションにより、メタデータスキーマの整合性を確保できます。

### 基本的な使用方法

```python title="metadata-def.json バリデーション"
from rdetoolkit.validation import MetadataValidator

# メタデータ定義ファイルのバリデーション
metadata_validator = MetadataValidator("path/to/metadata-def.json")
try:
    metadata_validator.validate_schema()
    print("metadata-def.json バリデーション成功")
except ValidationError as e:
    print(f"メタデータ定義バリデーションエラー: {e}")
```

## metadata.json のバリデーション

### 概要

`metadata.json`は、`metadata-def.json`で定義されたスキーマに基づく実際のメタデータファイルです。

### 基本的な使用方法

```python title="metadata.json バリデーション"
# メタデータファイルのバリデーション
try:
    metadata_validator.validate_data("path/to/metadata.json")
    print("metadata.json バリデーション成功")
except ValidationError as e:
    print(f"メタデータバリデーションエラー: {e}")
```

## 統合バリデーション

### ワークフロー内での自動バリデーション

RDEToolKitのワークフロー実行時には、自動的にバリデーションが実行されます：

```python title="ワークフロー統合バリデーション"
from rdetoolkit import workflows

def my_dataset_function(rde):
    # データ処理ロジック
    rde.set_metadata({"status": "processed"})
    return 0

# ワークフロー実行時に自動バリデーションが実行される
try:
    result = workflows.run(my_dataset_function)
    print("ワークフロー実行成功")
except Exception as e:
    print(f"ワークフロー実行エラー（バリデーション含む）: {e}")
```

### 読み込み時に検証される設定値

v2 の設定は、入力を読む前の読み込み時に検証されます。
未知のキーや不正な値は `ConfigLoadFailed`（エラーコード 1002）で失敗し、
メッセージには問題のキー名が示されます。

`execution.type_check` に指定できるのは `off`（既定値）、`warn`、`strict` のいずれかだけです。
綴り誤り（`strcit`）、大文字小文字の違い（`Strict`）、前後の空白、`null`、数値、リストは
すべて拒否されます：

```text
[ConfigLoadFailed] Failed to load RDE configuration: 1 validation error for RdeConfig
execution.type_check
  Input should be 'off', 'warn' or 'strict' ...
```

この検証は `rdeconfig.yaml`、`pyproject.toml` の `[tool.rdetoolkit]`、`--config` による上書き、
明示的に渡した `RdeConfig` のいずれにも適用されます。
`rdetoolkit run REF --validate-only` と `rdetoolkit doctor` は、フローを実行せずにこのエラーを報告します。

## CLIバリデーションコマンド

RDEToolKitは、CI/CD統合のための標準化された終了コードを持つコマンドラインバリデーションツールを提供します。

### 利用可能なバリデーションコマンド

`validate`コマンドは、包括的なバリデーションのための5つのサブコマンドを提供します：

- `invoice-schema` - インボイススキーマJSONの構造を検証
- `metadata-def` - メタデータ定義JSONの構造を検証
- `invoice` - invoice.jsonをスキーマに対して検証
- `metadata` - metadata.jsonをmetadata-def.jsonに対して検証
- `all` - プロジェクト内のすべての標準RDEファイルを検出して検証

### 終了コード

すべてのバリデーションコマンドは、CI/CDパイプラインおよび自動化スクリプトとの統合を可能にする標準化された終了コードを使用します：

| 終了コード | ステータス | 説明 |
|-----------|--------|-------------|
| 0 | 成功 | すべてのバリデーションが正常に完了 |
| 1 | バリデーション失敗 | データまたはスキーマの問題により1つ以上のバリデーションが失敗 |
| 2 | 使用エラー | 無効なコマンド引数、ファイル不足、または設定エラー |

### CI/CDパイプラインでの使用

終了コードにより、シェルスクリプトおよびCI/CDパイプラインで堅牢なエラーハンドリングが可能になります：

```bash title="CI/CDバリデーションスクリプトの例"
#!/bin/bash
# CI/CDバリデーションスクリプトの例

rdetoolkit validate all ./rde-project

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ バリデーション成功 - デプロイを続行します"
    exit 0
elif [ $EXIT_CODE -eq 1 ]; then
    echo "✗ バリデーション失敗 - データ/スキーマのエラーを確認してください"
    exit 1
elif [ $EXIT_CODE -eq 2 ]; then
    echo "✗ 設定エラー - コマンド引数とファイルパスを確認してください"
    exit 2
else
    echo "✗ 予期しない終了コード: $EXIT_CODE"
    exit $EXIT_CODE
fi
```

### CLI使用例

#### インボイススキーマの検証（成功 - 終了コード0）

```bash
$ rdetoolkit validate invoice-schema tasksupport/invoice.schema.json
✓ VALID: tasksupport/invoice.schema.json

$ echo $?
0
```

#### インボイスデータの検証（バリデーション失敗 - 終了コード1）

```bash
$ rdetoolkit validate invoice raw/invoice.json --schema tasksupport/invoice.schema.json
✗ INVALID: raw/invoice.json

Errors:
  1. Field: basic.dataOwnerId
     Type: pattern
     Message: String does not match pattern ^[a-zA-Z0-9]{56}$

$ echo $?
1
```

#### ファイル不足（使用エラー - 終了コード2）

```bash
$ rdetoolkit validate invoice-schema /nonexistent/schema.json
Error: Schema file not found: /nonexistent/schema.json

$ echo $?
2
```

#### プロジェクト内のすべてのファイルを検証

```bash
$ rdetoolkit validate all ./rde-project
✓ Validating invoice schema...
✓ Validating metadata definition...
✓ Validating invoice data...
✓ Validating metadata...
✓ All validations passed

$ echo $?
0
```

#### 検証対象ファイルの存在を必須にする（`--require-files`）

既定では、`validate all` は標準 RDE ファイルが 1 つも見つからなくても終了コード 0 で終わります。
対話的な探索にはこれで十分ですが、CI ではパスの誤りや不完全なチェックアウトでも、
何も検証しないまま成功してしまいます。`--require-files` を付けると、検証対象が 1 つもない場合は
検証失敗（終了コード 1）となり、固定のエラー種別 `no_target_files` と、探索したディレクトリの一覧を表示します：

```bash
$ rdetoolkit validate all ./wrong-dir --strict --require-files
✗ INVALID: /abs/path/wrong-dir

Errors:
  1. Field:
     Type: no_target_files
     Message: No standard RDE file was found to validate (--require-files). Searched under the project directory: container/data/tasksupport/, template/tasksupport/, input/invoice/, input/metadata/. Remediation: ...

$ echo $?
1
```

`--format json` では、通常の JSON 配列に要素が 1 つ追加されます（`"valid": false`、エラーの `"type": "no_target_files"`）。
`--strict` 単独の意味（警告を失敗扱いにする）は変わらず、ファイルの存在は要求しません。
v1 の `templates/` レイアウトに対する非推奨の通知は、検証したファイルとして数えません。
Runner の `data/` ディレクトリ（`data/tasksupport`、`data/invoice`）を確認する場合は `rdetoolkit doctor` を使用してください。

CI では `--strict --require-files` を指定してください。

### CI/CD統合の例

#### GitHub Actionsの例

```yaml title="GitHub Actionsワークフロー"
name: RDE Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Pythonのセットアップ
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: rdetoolkitのインストール
        run: pip install rdetoolkit

      - name: RDEプロジェクトの検証
        run: |
          set +e
          rdetoolkit validate all ./rde-project --strict --require-files
          status=$?
          if [ $status -eq 1 ]; then
            echo "::error::RDEバリデーション失敗（または検証対象なし） - データとスキーマを確認してください"
          elif [ $status -eq 2 ]; then
            echo "::error::RDEバリデーション設定エラー"
          fi
          exit $status
```

#### GitLab CIの例

```yaml title="GitLab CI設定"
validate:
  stage: test
  image: python:3.12
  script:
    - pip install rdetoolkit
    - rdetoolkit validate all ./rde-project --strict --require-files
  allow_failure: false
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
```

#### シェルスクリプトの例

```bash title="スタンドアロンバリデーションスクリプト"
#!/bin/bash
set -e

validate_rde_project() {
    local project_dir="$1"

    echo "RDEプロジェクトを検証中: $project_dir"
    rdetoolkit validate all "$project_dir"

    local exit_code=$?
    case $exit_code in
        0)
            echo "✓ バリデーション成功"
            return 0
            ;;
        1)
            echo "✗ バリデーション失敗 - データまたはスキーマのエラー"
            return 1
            ;;
        2)
            echo "✗ 設定エラー - 引数とファイルを確認してください"
            return 2
            ;;
        *)
            echo "✗ 予期しない終了コード: $exit_code"
            return $exit_code
            ;;
    esac
}

validate_rde_project "./rde-project"
```

## ベストプラクティス

### 開発時のバリデーション戦略

1. **段階的バリデーション**
   - スキーマファイルを先にバリデーション
   - データファイルを後でバリデーション

2. **継続的チェック**
   - ファイル変更時に自動バリデーション
   - 終了コードを使用したCI/CDパイプラインでのバリデーション

3. **エラーハンドリング**
   - 詳細なエラーメッセージの活用
   - 段階的なエラー修正
   - バリデーション失敗（終了コード1）と設定エラー（終了コード2）の区別

### トラブルシューティング

#### よくある問題と解決方法

1. **スキーマ構文エラー**
   - JSON構文の確認
   - 必須フィールドの確認

2. **データ型不一致**
   - スキーマで定義された型との照合
   - デフォルト値の確認

3. **参照エラー**
   - ファイルパスの確認
   - ファイル存在の確認

## 実践例

### 完全なバリデーションワークフロー

```python title="完全バリデーション例"
import json
from pathlib import Path
from rdetoolkit.validation import InvoiceValidator, MetadataValidator
from rdetoolkit.exceptions import InvoiceSchemaValidationError

def validate_all_files(project_dir: Path):
    """プロジェクト内の全ファイルをバリデーション"""
    
    # 1. invoice.schema.json のバリデーション
    schema_path = project_dir / "tasksupport" / "invoice.schema.json"
    invoice_path = project_dir / "invoice" / "invoice.json"
    
    try:
        invoice_validator = InvoiceValidator(schema_path)
        print("✓ invoice.schema.json バリデーション成功")
        
        # 2. invoice.json のバリデーション
        with open(invoice_path) as f:
            invoice_data = json.load(f)
        
        invoice_validator.validate(obj=invoice_data)
        print("✓ invoice.json バリデーション成功")
        
    except ValidationError as e:
        print(f"✗ Invoice バリデーションエラー: {e}")
        return False
    
    # 3. metadata-def.json のバリデーション
    metadata_def_path = project_dir / "tasksupport" / "metadata-def.json"
    metadata_path = project_dir / "metadata.json"
    
    try:
        metadata_validator = MetadataValidator(metadata_def_path)
        metadata_validator.validate_schema()
        print("✓ metadata-def.json バリデーション成功")
        
        # 4. metadata.json のバリデーション
        if metadata_path.exists():
            metadata_validator.validate_data(metadata_path)
            print("✓ metadata.json バリデーション成功")
        
    except ValidationError as e:
        print(f"✗ Metadata バリデーションエラー: {e}")
        return False
    
    print("🎉 全ファイルのバリデーション完了")
    return True

# 使用例
project_directory = Path("./my_rde_project")
validate_all_files(project_directory)
```

## 次のステップ

- [テンプレートファイル](metadata_definition_file.ja.md)でスキーマ定義の詳細を学ぶ
- [構造化処理](../user-guide/structured-processing.ja.md)でバリデーションの活用方法を理解する
- [APIリファレンス](../rdetoolkit/validation.md)で詳細なバリデーション機能を確認する
