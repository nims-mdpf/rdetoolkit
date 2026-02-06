# Invoice Generator API

## Purpose

このモジュールは`invoice.schema.json`から`invoice.json`を生成するコマンドを定義します。スキーマ定義に基づいてinvoiceファイルを自動生成し、InvoiceValidatorによる検証を行います。

## Key Features

### Invoice生成
- invoice.schema.jsonからinvoice.jsonを自動生成
- デフォルト値の自動設定（スキーマのdefault → examples → 型ベース）
- 必須フィールドのみの生成オプション
- 生成後の自動バリデーション

### 出力オプション
- Pretty/Compact JSONフォーマット
- カスタム出力パス指定
- デフォルト値埋め込みの有無

---

::: src.rdetoolkit.cmd.gen_invoice.GenerateInvoiceCommand

---

## Practical Usage

### 基本的なコマンド実行

```python title="basic_invoice_generation.py"
from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand
from pathlib import Path

# Invoice生成コマンドを作成
command = GenerateInvoiceCommand(
    schema_path=Path("tasksupport/invoice.schema.json"),
    output_path=Path("invoice/invoice.json"),
)

# コマンドを実行
try:
    command.invoke()
    print("✓ Invoice生成が完了しました")
except Exception as e:
    print(f"✗ Invoice生成エラー: {e}")
```

### カスタムオプションでの生成

```python title="custom_invoice_generation.py"
from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand
from pathlib import Path

# 必須フィールドのみ、コンパクトフォーマットで生成
command = GenerateInvoiceCommand(
    schema_path=Path("tasksupport/invoice.schema.json"),
    output_path=Path("invoice/invoice.json"),
    fill_defaults=False,      # デフォルト値を埋めない
    required_only=True,       # 必須フィールドのみ
    output_format="compact",  # コンパクトJSON
)

try:
    command.invoke()
    print("✓ 最小構成のinvoice.jsonを生成しました")
except Exception as e:
    print(f"✗ 生成エラー: {e}")
```

### バッチ処理での使用

```python title="batch_invoice_generation.py"
from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand
from pathlib import Path

# 複数のスキーマからinvoiceを生成
schemas = [
    ("project_a/invoice.schema.json", "project_a/invoice.json"),
    ("project_b/invoice.schema.json", "project_b/invoice.json"),
    ("project_c/invoice.schema.json", "project_c/invoice.json"),
]

results = {"success": [], "failed": []}

for schema_path, output_path in schemas:
    try:
        command = GenerateInvoiceCommand(
            schema_path=Path(schema_path),
            output_path=Path(output_path),
        )
        command.invoke()
        results["success"].append(output_path)
        print(f"✓ {output_path}")
    except Exception as e:
        results["failed"].append((output_path, str(e)))
        print(f"✗ {output_path}: {e}")

print(f"\n成功: {len(results['success'])}, 失敗: {len(results['failed'])}")
```

## CLI Usage

コマンドラインから直接使用する場合：

```bash
# 基本的な使用方法
rdetoolkit gen-invoice tasksupport/invoice.schema.json

# 出力パスを指定
rdetoolkit gen-invoice tasksupport/invoice.schema.json -o invoice/invoice.json

# 必須フィールドのみ生成
rdetoolkit gen-invoice tasksupport/invoice.schema.json --required-only

# デフォルト値を埋めない
rdetoolkit gen-invoice tasksupport/invoice.schema.json --no-fill-defaults

# コンパクトフォーマットで出力
rdetoolkit gen-invoice tasksupport/invoice.schema.json --format compact
```

## Default Value Strategy

デフォルト値は以下の優先順位で決定されます：

1. スキーマの`default`フィールド
2. スキーマの`examples`配列の最初の値
3. 型ベースのデフォルト値：
   - string → `""`
   - number → `0.0`
   - integer → `0`
   - boolean → `false`
   - array → `[]`
   - object → `{}`
