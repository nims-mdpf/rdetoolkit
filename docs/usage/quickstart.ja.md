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
python3 -m rdetoolkit init sample_project
```

このコマンドを実行すると、以下のディレクトリ構造が作成されます：

```
sample_project/
├── main.py                    # メイン実行ファイル
├── requirements.txt           # 依存関係
├── modules/                   # カスタム処理モジュール
└── data/
    ├── inputdata/            # 入力データ
    ├── invoice/              # メタデータファイル
    └── tasksupport/          # 設定・スキーマファイル
```

## 2. カスタム処理を実装する

`modules/process.py`ファイルを開き、以下のようにカスタム処理を実装します：

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
    
    # 入力ファイルを構造化ディレクトリにコピー
    input_files = list(srcpaths.inputdata.glob("*"))
    for file_path in input_files:
        if file_path.is_file():
            dest_path = resource_paths.structured / file_path.name
            shutil.copy2(file_path, dest_path)
            print(f"ファイルをコピーしました: {file_path.name}")
    
    # メタデータの設定例
    metadata = {
        "processed_files": len(input_files),
        "processing_status": "completed"
    }
    
    # メタデータをJSONファイルとして保存
    import json
    metadata_file = resource_paths.meta / "processing_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print("カスタム処理が完了しました")
    return 0
```

## 3. サンプルデータを準備する

`data/inputdata/`ディレクトリにサンプルファイルを配置します：

```bash
# サンプルテキストファイルを作成
echo "これはサンプルデータです" > sample_project/data/inputdata/sample.txt
echo "実験データ: 温度 25°C, 湿度 60%" > sample_project/data/inputdata/experiment_data.txt
```

## 4. 構造化処理を実行する

プロジェクトディレクトリに移動して、構造化処理を実行します：

```bash
cd sample_project
python main.py
```

実行が成功すると、以下のような出力が表示されます：

```
入力データディレクトリ: /path/to/sample_project/data/inputdata
インボイスディレクトリ: /path/to/sample_project/data/invoice
ファイルをコピーしました: sample.txt
ファイルをコピーしました: experiment_data.txt
カスタム処理が完了しました
構造化処理が正常に完了しました
```

## 5. 結果を確認する

処理完了後、以下のディレクトリ構造が生成されます：

```
sample_project/
├── main.py
├── requirements.txt
├── modules/
│   └── process.py
├── data/
│   ├── inputdata/
│   │   ├── sample.txt
│   │   └── experiment_data.txt
│   ├── invoice/
│   │   └── invoice.json
│   └── tasksupport/
│       └── invoice.schema.json
└── output/                    # 新しく生成される出力ディレクトリ
    ├── raw/                   # 生データ
    ├── structured/            # 構造化データ
    │   ├── sample.txt
    │   └── experiment_data.txt
    ├── meta/                  # メタデータ
    │   └── processing_metadata.json
    ├── main_image/            # メイン画像
    ├── other_image/           # その他の画像
    ├── thumbnail/             # サムネイル画像
    └── logs/                  # ログファイル
```

## 6. 処理結果の詳細確認

生成されたファイルを確認してみましょう：

```bash
# 構造化データの確認
ls -la output/structured/

# メタデータの確認
cat output/meta/processing_metadata.json
```

メタデータファイルには以下のような内容が記録されています：

```json
{
  "processed_files": 2,
  "processing_status": "completed"
}
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

- [構造化処理の概念](../user-guide/structured-processing.ja.md)を理解する
- [設定オプション](../user-guide/config.ja.md)を探索する
- [CLIリファレンス](cli.ja.md)で高度なコマンドを確認する
