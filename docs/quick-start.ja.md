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

    # 必要なディレクトリを作成
    mkdir -p data/inputdata
    mkdir -p tasksupport
    mkdir -p modules
    ```

=== "Windows"
    ```cmd title="command_prompt"
    # プロジェクトディレクトリを作成
    mkdir my-rde-project
    cd my-rde-project

    # 必要なディレクトリを作成
    mkdir data\inputdata
    mkdir tasksupport
    mkdir modules
    ```

### 期待される結果
以下のディレクトリ構造が作成されます：
```
my-rde-project/
├── data/
│   └── inputdata/
├── tasksupport/
└── modules/
```

## 2. 依存関係を定義する

### 目的
プロジェクトで使用するPythonパッケージを定義します。

### 実行するコード

```text title="requirements.txt"
rdetoolkit>=1.0.0
```

### 期待される結果
`requirements.txt`ファイルが作成され、RDEToolKitの依存関係が定義されます。

## 3. カスタム構造化処理を作成する

### 目的
データ処理のロジックを含むカスタム関数を作成します。

### 実行するコード

```python title="modules/process.py"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
import json
import os

def display_message(message):
    """メッセージを表示する補助関数"""
    print(f"[INFO] {message}")

def create_sample_metadata(resource_paths):
    """サンプルメタデータを作成する"""
    metadata = {
        "title": "Sample Dataset",
        "description": "RDEToolKit tutorial sample",
        "created_at": "2024-01-01",
        "status": "processed"
    }

    # メタデータファイルを保存
    metadata_path = os.path.join(resource_paths.tasksupport, "sample_metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
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
    display_message(f"出力リソースディレクトリ: {resource_paths.root}")

    # サンプルメタデータを作成
    create_sample_metadata(resource_paths)

    # 入力ファイルの一覧を表示
    if os.path.exists(srcpaths.inputdata):
        files = os.listdir(srcpaths.inputdata)
        display_message(f"入力ファイル数: {len(files)}")
        for file in files:
            display_message(f"  - {file}")

    display_message("構造化処理が完了しました")
```

### 期待される結果
`modules/process.py`ファイルが作成され、構造化処理のロジックが定義されます。

## 4. メインスクリプトを作成する

### 目的
RDEToolKitのワークフローを起動するエントリーポイントを作成します。

### 実行するコード

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

### 期待される結果
`main.py`ファイルが作成され、構造化処理を実行する準備が整います。

## 5. サンプルデータを準備する

### 目的
構造化処理をテストするためのサンプルデータを作成します。

### 実行するコード

```text title="data/inputdata/sample_data.txt"
Sample Research Data
====================

This is a sample data file for RDEToolKit tutorial.
Created: 2024-01-01
Type: Text Data
Status: Ready for processing
```

### 期待される結果
`data/inputdata/sample_data.txt`ファイルが作成され、処理対象のサンプルデータが準備されます。

## 6. 構造化処理を実行する

### 目的
作成したプロジェクトでRDE構造化処理を実行し、動作を確認します。

### 実行するコード

```bash title="terminal"
# 依存関係をインストール
pip install -r requirements.txt

# 構造化処理を実行
python main.py
```

### 期待される結果

以下のような出力が表示されます：

```
=== RDEToolKit チュートリアル ===
[INFO] 構造化処理を開始します
[INFO] 入力データディレクトリ: /path/to/my-rde-project/data/inputdata
[INFO] 出力リソースディレクトリ: /path/to/my-rde-project
[INFO] メタデータを保存しました: /path/to/my-rde-project/tasksupport/sample_metadata.json
[INFO] 入力ファイル数: 1
[INFO]   - sample_data.txt
[INFO] 構造化処理が完了しました

=== 処理結果 ===
実行ステータス: {'statuses': [{'run_id': '0000', 'title': 'sample-dataset', 'status': 'success', ...}]}
```

## 7. 結果を確認する

### 目的
構造化処理の実行結果とファイル生成を確認します。

### 実行するコード

```bash title="terminal"
# 生成されたファイル構造を確認
find . -type f -name "*.json" | head -10
```

### 期待される結果

以下のようなファイルが生成されていることを確認できます：
- `tasksupport/sample_metadata.json` - 作成したメタデータファイル
- `raw/` または `nonshared_raw/` - 入力ファイルのコピー（設定による）

## おめでとうございます！

RDEToolKitを使用した最初の構造化処理が完了しました。

### 達成したこと

✅ RDEプロジェクトの基本構造を作成
✅ カスタム構造化処理関数を実装
✅ 構造化処理ワークフローを実行
✅ 処理結果の確認方法を習得

### 学んだ重要な概念

- **プロジェクト構造**: `data/inputdata/`, `tasksupport/`, `modules/`の役割
- **カスタム関数**: `RdeInputDirPaths`と`RdeOutputResourcePath`の使用方法
- **ワークフロー実行**: `rdetoolkit.workflows.run()`の基本的な使い方

## 次のステップ

さらに詳しく学ぶには：

1. [構造化処理の概念](user-guide/structured-processing.ja.md) - 処理フローの詳細理解
2. [設定ファイル](user-guide/config.ja.md) - 動作のカスタマイズ方法
3. [API リファレンス](api/index.ja.md) - 利用可能な全機能の確認

!!! tip "次の実践"
    実際の研究データを使用して、より複雑な構造化処理を試してみましょう。データの種類に応じて、適切な処理モードを選択することが重要です。
