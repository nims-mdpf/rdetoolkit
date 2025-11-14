# RDEToolKitを体験する

## 目的

このチュートリアルでは、RDEToolKitを使用して初めてのRDE構造化処理プロジェクトを作成し、実行する方法を学びます。約15分で基本的な構造化処理の流れを体験できます。

## 前提条件

- Python 3.9以上
- 基本的なPythonプログラミングの知識
- コマンドライン操作の基本的な理解

## 1. プロジェクトを初期化する

まず、RDEToolKitを使用して新しいプロジェクトを作成します。

```bash
mkdir sample_project
cd sample_project
python3 -m rdetoolkit init
```

このコマンドを実行すると、以下のディレクトリ構造が作成されます：

```
sample_project/
├── container
│   ├── data
│   │   ├── inputdata
│   │   ├── invoice
│   │   │   └── invoice.json
│   │   └── tasksupport
│   │       ├── invoice.schema.json
│   │       └── metadata-def.json
│   ├── Dockerfile
│   ├── main.py
│   ├── modules
│   └── requirements.txt
├── input
│   ├── inputdata
│   └── invoice
│       └── invoice.json
└── templates
    └── tasksupport
        ├── invoice.schema.json
        └── metadata-def.json
```

## 2. カスタム処理を実装する

`sample_project/container/modules/process.py`ファイルを開き、以下のようにカスタム処理を実装します：

```python title="modules/process.py"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    """
    カスタムデータ処理関数

    Args:
        srcpaths: 入力ディレクトリパス
        resource_paths: 出力リソースパス
    """
    # 入力データの確認
    print(f"入力データディレクトリ: {srcpaths.inputdata}")
    print(f"インボイスディレクトリ: {srcpaths.invoice}")

    # 簡単なファイル処理の例
    import shutil
    from pathlib import Path
    import pdb; pdb.set_trace()
    # 入力ファイルを構造化ディレクトリにコピー
    input_files = list(srcpaths.inputdata.glob("*"))
    for file_path in input_files:
        if file_path.is_file():
            dest_path = resource_paths.struct / file_path.name
            shutil.copy2(file_path, dest_path)
            print(f"ファイルをコピーしました: {file_path.name}")

    print("カスタム処理が完了しました")
    return 0
```

その後、`main.py`ファイルを以下のように編集して、カスタム処理関数を呼び出します：

```python title="main.py"
# The following script is a template for the source code.

import rdetoolkit
from modules.process import dataset

rdetoolkit.workflows.run(custom_dataset_function=dataset)
```

## 3. サンプルデータを準備する

`data/inputdata/`ディレクトリにサンプルファイルを配置します：

```bash
# サンプルテキストファイルを作成
echo "これはサンプルデータです" > sample_project/container/data/inputdata/sample.txt
echo "実験データ: 温度 25°C, 湿度 60%" > sample_project/container/data/inputdata/experiment_data.txt
```

## 4. 構造化処理を実行する

プロジェクトディレクトリに移動して、構造化処理を実行します：

```bash
cd sample_project/container
python main.py
```

実行が成功すると、以下のような出力が表示されます：

```
入力データディレクトリ: data/inputdata
インボイスディレクトリ: data/invoice
ファイルをコピーしました: experiment_data.txt
ファイルをコピーしました: sample.txt
カスタム処理が完了しました
```

## 5. 結果を確認する

処理完了後、以下のディレクトリ構造が生成されます：

```
sample_project/container
├── data
│   ├── attachment
│   ├── inputdata
│   │   ├── experiment_data.txt
│   │   └── sample.txt
│   ├── invoice
│   │   └── invoice.json
│   ├── invoice_patch
│   ├── job.failed
│   ├── logs
│   │   └── rdesys.log
│   ├── main_image
│   ├── meta
│   │   └── processing_metadata.json
│   ├── nonshared_raw
│   │   ├── experiment_data.txt
│   │   └── sample.txt
│   ├── other_image
│   ├── raw
│   ├── structured
│   │   ├── experiment_data.txt
│   │   └── sample.txt
│   ├── tasksupport
│   │   ├── invoice.schema.json
│   │   └── metadata-def.json
│   ├── temp
│   └── thumbnail
├── Dockerfile
├── main.py
├── modules
│   └── process.py
└── requirements.txt
```

## おめでとうございます！

初めてのRDE構造化処理プロジェクトが完了しました。このチュートリアルで学んだこと：

- **プロジェクト初期化**: `rdetoolkit init`コマンドでプロジェクト構造を作成
- **カスタム処理実装**: `dataset()`関数でデータ処理ロジックを定義
- **ファイル操作**: 入力データを構造化ディレクトリに整理
- **メタデータ管理**: 処理結果をJSONファイルとして記録
- **実行と確認**: 構造化処理の実行と結果の検証

## 次のステップ

基本的な構造化処理を体験したので、次は以下のトピックを学習してください：

- [実際のデータを用いた構造化処理の実装方法](../usage/structured_process/development_guide.ja.md)を理解する
- [設定オプション](../user-guide/config.ja.md)を探索する
- [CLIリファレンス](cli.ja.md)で高度なコマンドを確認する
