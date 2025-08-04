# ディレクトリパスを取得する方法

## 目的

RDE構造化処理でファイルの読み書きを行うために必要なディレクトリパスの取得方法について説明します。`RdeInputDirPaths`と`RdeOutputResourcePath`を使用した効率的なパス管理を学べます。

## 前提条件

- RDEToolKitの基本的な使用方法の理解
- Pythonのファイル操作の基本知識
- 構造化処理のディレクトリ構造の理解

## 手順

### 1. 入力パスを取得する

`RdeInputDirPaths`を使用して入力データのパス情報を取得します：

```python title="入力パスの取得"
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # 入力データディレクトリ
    input_dir = srcpaths.inputdata
    print(f"入力データディレクトリ: {input_dir}")
    
    # 送り状ディレクトリ
    invoice_dir = srcpaths.invoice
    print(f"送り状ディレクトリ: {invoice_dir}")
    
    # タスクサポートディレクトリ
    tasksupport_dir = srcpaths.tasksupport
    print(f"タスクサポートディレクトリ: {tasksupport_dir}")
```

### 2. 出力パスを取得する

`RdeOutputResourcePath`を使用して出力先のパス情報を取得します：

```python title="出力パスの取得"
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # 構造化データディレクトリ
    structured_dir = resource_paths.struct
    print(f"構造化データディレクトリ: {structured_dir}")
    
    # メタデータディレクトリ
    meta_dir = resource_paths.meta
    print(f"メタデータディレクトリ: {meta_dir}")
    
    # 生データディレクトリ
    raw_dir = resource_paths.raw
    print(f"生データディレクトリ: {raw_dir}")
    
    # 画像ディレクトリ
    main_image_dir = resource_paths.main_image
    other_image_dir = resource_paths.other_image
    thumbnail_dir = resource_paths.thumbnail
    
    print(f"メイン画像ディレクトリ: {main_image_dir}")
    print(f"その他画像ディレクトリ: {other_image_dir}")
    print(f"サムネイル画像ディレクトリ: {thumbnail_dir}")
```

### 3. ファイルを読み込む

取得したパスを使用してファイルを読み込みます：

```python title="ファイル読み込み"
import os
import pandas as pd
from pathlib import Path

def read_input_files(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # 入力ディレクトリのファイル一覧を取得
    input_files = os.listdir(srcpaths.inputdata)
    print(f"入力ファイル: {input_files}")
    
    # CSVファイルを読み込み
    for file in input_files:
        if file.endswith('.csv'):
            file_path = Path(srcpaths.inputdata) / file
            df = pd.read_csv(file_path)
            print(f"読み込み完了 {file}: {df.shape}")
            
            # データ処理
            processed_df = process_dataframe(df)
            
            # 構造化データとして保存
            output_path = Path(resource_paths.struct) / f"processed_{file}"
            processed_df.to_csv(output_path, index=False)
```

### 4. ファイルを保存する

処理結果を適切なディレクトリに保存します：

```python title="ファイル保存"
import json
from pathlib import Path

def save_processing_results(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # 処理結果データ
    results = {
        "status": "completed",
        "processed_files": 5,
        "timestamp": "2023-01-01T12:00:00Z"
    }
    
    # 構造化データとして保存
    structured_file = Path(resource_paths.struct) / "results.json"
    with open(structured_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # メタデータとして保存
    metadata = {
        "processing_version": "1.0",
        "input_file_count": len(os.listdir(srcpaths.inputdata)),
        "processing_date": "2023-01-01"
    }
    
    meta_file = Path(resource_paths.meta) / "metadata.json"
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
```

## 結果の確認

パス取得と操作が正しく行われたかを確認します：

### ファイル操作の確認

```python title="操作結果確認"
def verify_file_operations(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # 入力ファイル数の確認
    input_count = len(os.listdir(srcpaths.inputdata))
    print(f"入力ファイル数: {input_count}")
    
    # 出力ファイル数の確認
    output_dirs = {
        "structured": resource_paths.struct,
        "meta": resource_paths.meta,
        "raw": resource_paths.raw,
        "main_image": resource_paths.main_image
    }
    
    for name, path in output_dirs.items():
        if Path(path).exists():
            file_count = len(os.listdir(path))
            print(f"{name}ディレクトリのファイル数: {file_count}")
        else:
            print(f"⚠️ {name}ディレクトリが存在しません")
```

## 関連情報

ディレクトリパスの取得についてさらに学ぶには、以下のドキュメントを参照してください：

- [構造化処理の概念](structured.ja.md)でパスが使用される処理フローを理解する
- [ディレクトリ構造仕様](directory.ja.md)で各ディレクトリの役割を確認する
- [エラーハンドリング](errorhandling.ja.md)でパス関連エラーの対処法を学ぶ
