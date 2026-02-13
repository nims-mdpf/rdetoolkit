# Invoice Generator Module

## Purpose

このモジュールは`invoice.schema.json`から`invoice.json`を生成するAPIを提供します。CLIコマンドからもPythonコードからも利用可能な柔軟なインターフェースを持ちます。

## Key Features

### 生成機能
- JSONスキーマからinvoice構造を自動生成
- カスタムフィールドとサンプルフィールドの処理
- generalAttributes/specificAttributesのサポート
- InvoiceValidatorによる自動検証

### カスタマイズオプション
- デフォルト値の自動埋め込み
- 必須フィールドのみの生成
- ファイル出力または辞書返却の選択

---

::: src.rdetoolkit.invoice_generator.generate_invoice_from_schema

---

## Practical Usage

### 基本的なAPI使用

```python title="basic_api_usage.py"
from rdetoolkit.invoice_generator import generate_invoice_from_schema

# スキーマからinvoice.jsonを生成（ファイル出力）
invoice_data = generate_invoice_from_schema(
    schema_path="tasksupport/invoice.schema.json",
    output_path="invoice/invoice.json",
)

print(f"生成されたフィールド数: {len(invoice_data.get('basic', {}))}")
```

### 辞書として取得（ファイル出力なし）

```python title="dict_output.py"
from rdetoolkit.invoice_generator import generate_invoice_from_schema

# 辞書として取得（ファイルを生成しない）
invoice_data = generate_invoice_from_schema(
    schema_path="tasksupport/invoice.schema.json",
    # output_pathを省略するとファイル出力なし
)

# データを加工して使用
invoice_data["basic"]["dataName"] = "My Experiment Data"
invoice_data["basic"]["experimentId"] = "EXP-2024-001"

# 加工後のデータを保存
import json
from pathlib import Path

output_path = Path("invoice/invoice.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(invoice_data, f, ensure_ascii=False, indent=2)
```

### 必須フィールドのみ生成

```python title="required_only.py"
from rdetoolkit.invoice_generator import generate_invoice_from_schema

# 必須フィールドのみを含む最小構成のinvoiceを生成
invoice_data = generate_invoice_from_schema(
    schema_path="tasksupport/invoice.schema.json",
    output_path="invoice/invoice_minimal.json",
    required_only=True,
    fill_defaults=False,
)

print("最小構成のinvoice.jsonを生成しました")
```

### バリデーションエラーのハンドリング

```python title="validation_handling.py"
from rdetoolkit.invoice_generator import generate_invoice_from_schema
from rdetoolkit.exceptions import InvoiceSchemaValidationError

try:
    invoice_data = generate_invoice_from_schema(
        schema_path="tasksupport/invoice.schema.json",
        output_path="invoice/invoice.json",
    )
    print("✓ invoice.jsonを正常に生成しました")
except FileNotFoundError as e:
    print(f"✗ スキーマファイルが見つかりません: {e}")
except InvoiceSchemaValidationError as e:
    print(f"✗ 生成されたinvoiceの検証に失敗しました: {e}")
except Exception as e:
    print(f"✗ 予期しないエラー: {e}")
```

### ワークフロー統合例

```python title="workflow_integration.py"
from pathlib import Path
from rdetoolkit.invoice_generator import generate_invoice_from_schema
from rdetoolkit.workflows import run

def prepare_and_run_workflow():
    """invoiceを生成してワークフローを実行"""

    # 1. スキーマからinvoiceを生成
    schema_path = Path("tasksupport/invoice.schema.json")
    invoice_path = Path("invoice/invoice.json")

    invoice_data = generate_invoice_from_schema(
        schema_path=schema_path,
        output_path=invoice_path,
        fill_defaults=True,
    )

    # 2. 生成されたinvoiceを確認
    print(f"Invoice生成完了: {invoice_path}")
    print(f"  - basic fields: {len(invoice_data.get('basic', {}))}")
    print(f"  - custom fields: {len(invoice_data.get('custom', {}))}")

    # 3. ワークフローを実行
    def my_dataset_processor(srcpaths, resource_paths):
        # カスタムデータセット処理
        pass

    run(custom_dataset_function=my_dataset_processor)

if __name__ == "__main__":
    prepare_and_run_workflow()
```

## Default Value Strategy

デフォルト値は以下の優先順位で決定されます：

| 優先度 | ソース | 例 |
|--------|--------|-----|
| 1 | スキーマの`default`フィールド | `"default": "sample"` |
| 2 | スキーマの`examples`配列の最初の値 | `"examples": ["example1", "example2"]` |
| 3 | 型ベースのデフォルト値 | string→"", number→0.0, etc. |

### 型ベースのデフォルト値

| 型 | デフォルト値 |
|----|-------------|
| string | `""` |
| number | `0.0` |
| integer | `0` |
| boolean | `false` |
| array | `[]` |
| object | `{}` |
| null | `null` |

## See Also

- [GenerateInvoiceCommand](cmd/gen_invoice.md) - CLIコマンドクラス
- [InvoiceValidator](validation.md) - バリデーション
- [Invoice Models](models/invoice.md) - Invoiceデータモデル
