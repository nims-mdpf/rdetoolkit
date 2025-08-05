# Magic Variable機能とは

## 目的

RDEToolKitのMagic Variable機能について説明します。ファイル名やタイムスタンプなどの動的な値を自動的に置換する仕組みと設定方法を理解できます。

## 課題と背景

構造化処理において、以下のような課題がありました：

- **ファイル名の手動入力**: メタデータにファイル名を手動で記入する必要があった
- **一貫性の維持**: 複数のエントリで同じファイル名を正確に記入することが困難
- **効率性の問題**: 大量のファイルを処理する際の作業時間の増大
- **動的値の管理**: タイムスタンプや計算値などの動的な値の管理が複雑

これらの課題を解決するために、Magic Variable機能が開発されました。

## 主要コンセプト

### Magic Variableの仕組み

```mermaid
flowchart LR
    A[JSONファイル] --> B[${filename}]
    C[実際のファイル名] --> D[sample.csv]
    B --> E[置換処理]
    D --> E
    E --> F[sample.csv]
```

### サポートされる変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `${filename}` | 拡張子を除いたファイル名 | `sample.csv` → `sample` |
| `${filename_with_ext}` | 拡張子を含むファイル名 | `sample.csv` → `sample.csv` |
| `${timestamp}` | 現在のタイムスタンプ | `2023-01-01T12:00:00Z` |
| `${date}` | 現在の日付 | `2023-01-01` |
| `${time}` | 現在の時刻 | `12:00:00` |

## 設定方法

### 1. 設定ファイルでの有効化

`rdeconfig.yaml`でMagic Variable機能を有効にします：

```yaml title="rdeconfig.yaml"
system:
  magic_variable: true
```

### 2. JSONファイルでの使用

メタデータファイルやその他のJSONファイルで変数を使用します：

```json title="metadata.json"
{
  "data_name": "${filename}",
  "original_file": "${filename_with_ext}",
  "processing_date": "${date}",
  "processing_time": "${timestamp}",
  "output_file": "${filename}_processed.csv"
}
```

### 3. 処理結果の確認

Magic Variable機能が有効な場合、以下のように置換されます：

```json title="処理後のmetadata.json"
{
  "data_name": "sample",
  "original_file": "sample.csv",
  "processing_date": "2023-01-01",
  "processing_time": "2023-01-01T12:00:00Z",
  "output_file": "sample_processed.csv"
}
```

## 実践的な使用例

### 実験データの自動命名

```json title="実験メタデータ例"
{
  "experiment_id": "EXP_${date}_${filename}",
  "sample_name": "${filename}",
  "data_file": "${filename_with_ext}",
  "analysis_date": "${date}",
  "result_file": "analysis_${filename}_${timestamp}.json"
}
```

### バッチ処理での活用

```json title="バッチ処理設定例"
{
  "batch_id": "BATCH_${date}",
  "input_files": [
    "${filename_with_ext}"
  ],
  "output_directory": "results_${date}",
  "log_file": "processing_${filename}_${timestamp}.log"
}
```

### 複数ファイル処理

```python title="複数ファイル処理例"
def process_multiple_files(srcpaths, resource_paths):
    input_files = os.listdir(srcpaths.inputdata)
    
    for file in input_files:
        if file.endswith('.csv'):
            # Magic Variableを使用したメタデータ生成
            metadata = {
                "source_file": "${filename_with_ext}",
                "processed_by": "RDEToolKit",
                "processing_timestamp": "${timestamp}",
                "output_name": "${filename}_structured.csv"
            }
            
            # ファイル固有のメタデータを保存
            meta_file = Path(resource_paths.meta) / f"{file}_metadata.json"
            with open(meta_file, 'w') as f:
                json.dump(metadata, f, indent=2)
```

## 高度な機能

### カスタム変数の定義

```python title="カスタム変数例"
def dataset_with_custom_variables(srcpaths, resource_paths):
    # カスタム変数の定義
    custom_vars = {
        "project_id": "PROJECT_2023",
        "researcher": "Dr. Smith",
        "version": "v1.0"
    }
    
    # Magic Variableと組み合わせたメタデータ
    metadata = {
        "file_name": "${filename}",
        "project": custom_vars["project_id"],
        "researcher": custom_vars["researcher"],
        "version": custom_vars["version"],
        "created_at": "${timestamp}"
    }
    
    return metadata
```

### 条件付き置換

```json title="条件付き置換例"
{
  "data_type": "${filename}",
  "quality_check": {
    "status": "pending",
    "checked_at": "${timestamp}",
    "file_reference": "${filename_with_ext}"
  },
  "backup_location": "backup/${date}/${filename_with_ext}"
}
```

## トラブルシューティング

### よくある問題と解決方法

#### 変数が置換されない

```python title="設定確認"
def check_magic_variable_config():
    from rdetoolkit.models.config import Config
    
    config = Config.from_file("data/tasksupport/rdeconfig.yaml")
    
    if not config.system.magic_variable:
        print("❌ Magic Variable機能が無効です")
        print("rdeconfig.yamlでmagic_variable: trueに設定してください")
    else:
        print("✅ Magic Variable機能が有効です")
```

#### 不正な変数名

```json title="正しい変数名の使用"
{
  "correct": "${filename}",
  "incorrect": "$filename",
  "also_incorrect": "{filename}",
  "wrong_case": "${FILENAME}"
}
```

### デバッグ方法

```python title="Magic Variable動作確認"
def debug_magic_variables(srcpaths, resource_paths):
    import logging
    
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    # 置換前のメタデータ
    original_metadata = {
        "file": "${filename}",
        "timestamp": "${timestamp}"
    }
    
    logger.debug(f"置換前: {original_metadata}")
    
    # 実際の処理でMagic Variableがどう動作するかログ出力
    logger.info("Magic Variable処理を実行中...")
```

## パフォーマンス考慮事項

### 大量ファイル処理時の注意点

```python title="効率的な処理"
def efficient_magic_variable_processing(srcpaths, resource_paths):
    # タイムスタンプを一度だけ生成
    current_timestamp = datetime.now().isoformat()
    current_date = datetime.now().date().isoformat()
    
    # 共通メタデータテンプレート
    metadata_template = {
        "processing_date": current_date,
        "processing_timestamp": current_timestamp,
        "processor": "RDEToolKit"
    }
    
    # ファイル固有の情報のみMagic Variableを使用
    for file in input_files:
        file_metadata = metadata_template.copy()
        file_metadata.update({
            "source_file": "${filename_with_ext}",
            "output_file": "${filename}_processed.csv"
        })
```

## まとめ

Magic Variable機能の主要な特徴：

- **自動化**: ファイル名やタイムスタンプの自動置換
- **一貫性**: 複数エントリでの情報の一貫性確保
- **効率性**: 手動入力作業の大幅削減
- **動的値**: タイムスタンプや日付の動的生成

## 次のステップ

Magic Variable機能をさらに活用するために、以下のドキュメントを参照してください：

- [設定ファイル](config.ja.md)で詳細な設定方法を学ぶ
- [構造化処理の概念](../structured_process/structured.ja.md)で処理フローを理解する
- [メタデータ定義ファイル](../metadata_definition_file.ja.md)でメタデータ設計を確認する
