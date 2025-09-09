# エラーハンドリングする方法

## 目的

RDE構造化処理で発生する可能性のあるエラーの対処方法について説明します。よくあるエラーパターンと効果的なトラブルシューティング手順を学べます。

## 前提条件

- RDEToolKitの基本的な使用方法の理解
- Pythonの基本的なエラーハンドリングの知識
- ログファイルの読み方の理解

## 手順

### 1. エラーの種類を特定する

まず、発生したエラーの種類を特定します：

```python title="エラー情報の取得"
import traceback

def identify_error():
    try:
        # 構造化処理の実行
        result = workflows.run(custom_dataset_function)
    except Exception as e:
        print(f"エラータイプ: {type(e).__name__}")
        print(f"エラーメッセージ: {str(e)}")
        print(f"詳細なトレースバック:")
        traceback.print_exc()
```

### 2. ファイル関連エラーを解決する

#### ファイルが見つからないエラー

```python title="ファイル存在確認"
import os

def check_file_exists(file_path):
    if not os.path.exists(file_path):
        print(f"ファイルが見つかりません: {file_path}")
        # 代替ファイルパスを提案
        alternatives = [
            file_path.replace('.csv', '.xlsx'),
            os.path.join('data', os.path.basename(file_path))
        ]
        for alt in alternatives:
            if os.path.exists(alt):
                print(f"代替ファイルが見つかりました: {alt}")
                return alt
        return None
    return file_path
```

#### 権限エラーの解決

```shell title="権限の修正"
# ディレクトリの権限を設定
chmod 755 data/
chmod 755 data/structured/
chmod 755 data/logs/

# ファイルの権限を設定
chmod 644 data/invoice/invoice.json
chmod 644 data/tasksupport/*.json
```

### 3. 設定ファイルエラーを解決する

#### JSON形式の検証

```python title="JSON検証"
import json

def validate_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ {file_path} は有効なJSONです")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON形式エラー in {file_path}:")
        print(f"   行 {e.lineno}, 列 {e.colno}: {e.msg}")
        return None
    except FileNotFoundError:
        print(f"❌ ファイルが見つかりません: {file_path}")
        return None
```

#### スキーマ検証エラーの対処

```python title="スキーマ検証"
def validate_against_schema(data, schema_path):
    try:
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        # 必須フィールドの確認
        if 'required' in schema:
            for field in schema['required']:
                if field not in data:
                    print(f"❌ 必須フィールドが不足: {field}")
                    return False
        
        print("✅ スキーマ検証に合格しました")
        return True
    except Exception as e:
        print(f"❌ スキーマ検証エラー: {e}")
        return False
```

### 4. RDEToolKitのエラーハンドリング機能を使用する

#### StructuredErrorの使用

```python title="構造化エラーの実装"
from rdetoolkit.exceptions import StructuredError

def dataset_with_error_handling(srcpaths, resource_paths):
    try:
        # ファイル読み込み処理
        config = read_config_file("config.json")
    except FileNotFoundError as e:
        # RDE用のエラー情報を設定
        raise StructuredError(
            "設定ファイルが見つかりません", 
            ecode=3, 
            eobj=e
        ) from e
    except json.JSONDecodeError as e:
        raise StructuredError(
            "設定ファイルの形式が正しくありません", 
            ecode=4, 
            eobj=e
        ) from e
    
    # 正常処理
    return process_data(config)
```

#### エラーデコレーターの使用

```python title="エラーデコレーター"
from rdetoolkit.errors import catch_exception_with_message

@catch_exception_with_message(
    error_message="予期しないエラーが発生しました", 
    error_code=100, 
    verbose=False
)
def dataset_with_decorator(srcpaths, resource_paths):
    # 処理ロジック
    return process_data()
```

### 5. ログを活用したデバッグ

#### 詳細ログの設定

```python title="ログ設定"
import logging

def setup_detailed_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('debug.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    return logger

def debug_processing(srcpaths, resource_paths):
    logger = setup_detailed_logging()
    
    logger.info("構造化処理を開始します")
    logger.debug(f"入力パス: {srcpaths}")
    logger.debug(f"出力パス: {resource_paths}")
    
    try:
        # 処理実行
        result = your_processing_logic()
        logger.info("処理が正常に完了しました")
        return result
    except Exception as e:
        logger.error(f"処理中にエラーが発生: {e}")
        logger.debug("詳細なトレースバック:", exc_info=True)
        raise
```

## 結果の確認

エラー解決後は以下を確認してください：

### job.failedファイルの確認

```python title="エラーファイル確認"
def check_error_file():
    error_file = "job.failed"
    if os.path.exists(error_file):
        with open(error_file, 'r') as f:
            content = f.read()
        print(f"エラー情報:\n{content}")
        return False
    else:
        print("✅ エラーファイルは存在しません（正常終了）")
        return True
```

### ログファイルの確認

```shell title="ログ確認コマンド"
# 最新のログエントリを確認
tail -n 20 data/logs/rdesys.log

# エラーメッセージを検索
grep -i "error" data/logs/rdesys.log

# 警告メッセージを検索
grep -i "warning" data/logs/rdesys.log
```

## トラブルシューティングチェックリスト

### 実行前チェック

- [ ] 必要なファイルがすべて存在する
- [ ] ファイルの権限が適切に設定されている
- [ ] 必要なPythonパッケージがインストールされている
- [ ] 設定ファイルの形式が正しい
- [ ] 入力データの形式が期待される形式と一致している

### エラー発生時チェック

- [ ] エラーメッセージを詳細に読む
- [ ] job.failedファイルを確認する
- [ ] ログファイルを確認する
- [ ] 入力データの内容を確認する
- [ ] 設定ファイルの内容を確認する
- [ ] ディスク容量が十分にある

### 解決後チェック

- [ ] 同じエラーが再発しないか確認
- [ ] 他の機能に影響がないか確認
- [ ] ログに適切な情報が記録されているか確認
- [ ] job.failedファイルが生成されていないか確認

## 関連情報

エラーハンドリングについてさらに学ぶには、以下のドキュメントを参照してください：

- [構造化処理の概念](structured.ja.md)でエラーが発生する処理フェーズを理解する
- [設定ファイル](../config/config.ja.md)で設定関連エラーの対処法を学ぶ
- [バリデーション](../validation.ja.md)でデータ検証エラーの対処法を確認する
- [LLM/AI向けトレースバック機能](traceback.ja.md)でスタックトレース機能を学ぶ
