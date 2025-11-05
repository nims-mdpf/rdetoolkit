# RDEToolKitクイックスタート

## 目的

このチュートリアルでは、RDEToolKitを使用して最初の構造化処理を実行し、基本的なワークフローを体験します。所要時間は約15分です。

完了時には、以下のことができるようになります：

- RDEプロジェクトの基本構造を理解する
- カスタム構造化処理関数を作成する
- 構造化処理を実行し、結果を確認する

## 1. プロジェクトを作成する

### 目的

RDE構造化処理用のプロジェクトディレクトリを作成し、必要なファイル構造を準備します。

### 実行するコード

=== "Unix/macOS"
    ```bash title="terminal"
    # プロジェクトディレクトリを作成
    mkdir my-rde-project
    cd my-rde-project
    ```

=== "Windows"
    ```cmd title="command_prompt"
    # プロジェクトディレクトリを作成
    mkdir my-rde-project
    cd my-rde-project
    ```

## 2. 依存関係を定義する

### 目的
プロジェクトで使用するPythonパッケージを定義します。

### rdetoolkitをインストールする

=== "Unix/macOS"
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install "rdetoolkit>=1.4.0"
    ```

=== "Windows"
    ```cmd
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install "rdetoolkit>=1.4.0"
    ```

### 期待される結果

`pip list`コマンドで`rdetoolkit`がインストールされていることを確認できます。

```bash
$ pip list
Package                   Version
------------------------- -----------------
rdetoolkit                1.4.0
```

## 3. プロジェクト構造を作成する

### 目的

プロジェクトの基本的なディレクトリ構造を作成します。

### 実行するコード
```bash
rdetoolkit init
```

### 期待される結果

```bash
Ready to develop a structured program for RDE.
Created: /Users/user1/my-rde-project/my-rde-project/container/requirements.txt
Created: /Users/user1/my-rde-project/my-rde-project/container/Dockerfile
Created: /Users/user1/my-rde-project/my-rde-project/container/data/invoice/invoice.json
Created: /Users/user1/my-rde-project/my-rde-project/container/data/tasksupport/invoice.schema.json
Created: /Users/user1/my-rde-project/my-rde-project/container/data/tasksupport/metadata-def.json
Created: /Users/user1/my-rde-project/my-rde-project/templates/tasksupport/invoice.schema.json
Created: /Users/user1/my-rde-project/my-rde-project/templates/tasksupport/metadata-def.json
Created: /Users/user1/my-rde-project/my-rde-project/input/invoice/invoice.json

Check the folder: /Users/user1/my-rde-project/my-rde-project
```

## 3. カスタム構造化処理を作成する

### 目的

データ処理のロジックを含むカスタム関数を作成します。

### 作成するファイル

`container/modules/process.py`を以下のように作成します。

```python title="container/modules/process.py"
from pathlib import Path
import json
import os

from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def display_message(message):
    """メッセージを表示する補助関数"""
    print(f"[INFO] {message}")

def create_sample_metadata(srcpaths: RdeInputDirPaths):
    """サンプルメタデータを作成する"""
    metadata = {
        "title": "Sample Dataset",
        "description": "RDEToolKit tutorial sample",
        "created_at": "2024-01-01",
        "status": "processed"
    }

    # メタデータファイルを保存
    metadata_path = Path(srcpaths.tasksupport) / "sample_metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open('w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    display_message(f"メタデータを保存しました: {metadata_path}")

def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    """
    メインの構造化処理関数

    Args:
        srcpaths: 入力ファイルのパス情報
        resource_paths: 出力リソースのパス情報
    """
    display_message("構造化処理を開始します")

    # 入力パス情報を表示
    display_message(f"入力データディレクトリ: {srcpaths.inputdata}")
    display_message(f"構造化データ出力ディレクトリ: {resource_paths.struct}")
    display_message(f"メタデータ出力ディレクトリ: {resource_paths.meta}")

    # サンプルメタデータを作成
    create_sample_metadata(srcpaths)

    # 入力ファイルの一覧を表示
    if os.path.exists(srcpaths.inputdata):
        files = os.listdir(srcpaths.inputdata)
        display_message(f"入力ファイル数: {len(files)}")
        for file in files:
            display_message(f"  - {file}")

    display_message("構造化処理が完了しました")
```

## 4. メインスクリプトを作成する

### 目的

RDEToolKitのワークフローを起動するエントリーポイントを作成します。

### 作成するファイル

`container/main.py` を以下のように書き換えます。



```python title="main.py"
import rdetoolkit

from modules import process

def main():
    """メイン実行関数"""
    print("=== RDEToolKit チュートリアル ===")

    # RDE構造化処理を実行
    result = rdetoolkit.workflows.run(custom_dataset_function=process.dataset)

    # 結果を表示
    print("\n=== 処理結果 ===")
    print(f"実行ステータス: {result}")

    return result

if __name__ == "__main__":
    main()
```

## 5. サンプルデータを準備する

### 目的

構造化処理をテストするためのサンプルデータ(`data/inputdata/sample_data.txt`)を作成します。

### 作成するファイル

```text title="container/data/inputdata/sample_data.txt"
Sample Research Data
====================

This is a sample data file for RDEToolKit tutorial.
Created: 2024-01-01
Type: Text Data
Status: Ready for processing
```

## 6. 構造化処理を実行する

### 目的
作成したプロジェクトでRDE構造化処理を実行し、動作を確認します。

### 実行するコード

dataディレクトリと同じディレクトリに移動しmain.pyを実行します。

```bash title="terminal"
# 構造化処理を実行
cd container
python main.py
```

### 期待される結果

以下のような出力が表示されます：

```
=== RDEToolKit チュートリアル ===
[INFO] 構造化処理を開始します
[INFO] 入力データディレクトリ: data/inputdata
[INFO] 構造化データ出力ディレクトリ: data/structured
[INFO] メタデータ出力ディレクトリ: data/meta
[INFO] メタデータを保存しました: data/tasksupport/sample_metadata.json
[INFO] 入力ファイル数: 1
[INFO]   - sample_data.txt
[INFO] 構造化処理が完了しました

=== 処理結果 ===
実行ステータス: {
  "statuses": [
    {
      "run_id": "0000",
      "title": "toy dataset",
      "status": "success",
      "mode": "invoice",
      "error_code": null,
      "error_message": null,
      "target": "data/inputdata",
      "stacktrace": null
    }
  ]
}
```

## 7. 結果を確認する

dataディレクトリを確認してください。

```bash
data
├── attachment
├── inputdata
│   └── sample_data.txt
├── invoice
│   └── invoice.json
├── invoice_patch
├── logs
│   └── rdesys.log
├── main_image
├── meta
├── nonshared_raw
│   └── sample_data.txt
├── other_image
├── raw
├── structured
├── tasksupport
│   ├── invoice.schema.json
│   ├── metadata-def.json
│   └── sample_metadata.json
├── temp
└── thumbnail
```

## おめでとうございます！

RDEToolKitを使用した最初の構造化処理が完了しました。

### 達成したこと

✅ RDEプロジェクトの基本構造を作成
✅ カスタム構造化処理関数を実装
✅ 構造化処理ワークフローを実行
✅ 処理結果の確認方法を習得

### 学んだ重要な概念

- **プロジェクト構造**: `data/inputdata/`, `data/tasksupport/`, `modules/`の役割
- **カスタム関数**: `RdeInputDirPaths`と`RdeOutputResourcePath`の使用方法
- **ワークフロー実行**: `rdetoolkit.workflows.run()`の基本的な使い方

## 次のステップ

さらに詳しく学ぶには：

1. [構造化処理の概念](user-guide/structured-processing.ja.md) - 処理フローの詳細理解
2. [設定ファイル](user-guide/config.ja.md) - 動作のカスタマイズ方法
3. [API リファレンス](api/index.ja.md) - 利用可能な全機能の確認

!!! tip "次の実践"
    実際の研究データを使用して、より複雑な構造化処理を試してみましょう。データの種類に応じて、適切な処理モードを選択することが重要です。
