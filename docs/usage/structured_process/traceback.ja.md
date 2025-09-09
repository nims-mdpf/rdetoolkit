# LLM/AI向けトレースバック機能

RDEToolkitには、LLMやAIエージェントが効率的に解析できる構造化されたスタックトレース形式を生成する機能が搭載されています。この機能により、エラーの自動分析、修正提案、バグレポート生成などの自動化が可能になります。

## 概要

この機能は「デュプレックス出力」システムを提供し、以下の2つの形式を同時に出力できます：

- **コンパクト形式**：LLMやAIエージェント向けの構造化された機械可読形式
- **Python形式**：開発者向けの従来の人間可読形式

## 基本的な使用方法

### デフォルト動作

**重要**：この機能は**デフォルトで無効**です。以下の方法で有効化できます：

### 1. 環境変数による制御

```bash
# 基本的な有効化
export TRACE_VERBOSE=context,locals,env

# 出力形式の選択
export TRACE_FORMAT=compact    # LLM向けのみ
export TRACE_FORMAT=python     # 従来形式のみ
export TRACE_FORMAT=duplex     # 両方（デフォルト）

# 機能を無効にする
export TRACE_VERBOSE=off       # 明示的にOFF
export TRACE_VERBOSE=""        # 空文字でもOFF
```

**オプション説明**：
- `context`：エラー発生行のソースコードを表示
- `locals`：ローカル変数の値を表示（機密情報は自動マスキング）
- `env`：実行環境情報（Pythonバージョン、OS）を表示

### 2. プログラム内での制御

```python
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.errors import handle_exception

# 設定を作成
config = Config(
    traceback=TracebackSettings(
        enabled=True,
        format="duplex",
        include_context=True,
        include_locals=False,  # セキュリティのためOFF
        include_env=False
    )
)

# エラーハンドリングで使用
try:
    # 処理
    process_data()
except Exception as e:
    structured_error = handle_exception(e, config=config)
    print(structured_error.traceback_info)
```

## 出力例

### コンパクト形式（AI向け）

```
<STACKTRACE>
CFG v=1 ctx=1 locals=0 env=0
E ts=2025-09-08T15:30:45Z type="ValueError" msg="Invalid input data"
F0 mod="myapp.processor" fn="validate_data" file="processor.py:45" in_app=1 context="if not data.get('required_field'):"
F1 mod="myapp.main" fn="main" file="main.py:12" in_app=1
RC frame="F0" hint="Invalid input data"
</STACKTRACE>
```

### デュプレックス出力

コンパクト形式に加えて、従来のPython形式も同時に出力：

```
<STACKTRACE>
CFG v=1 ctx=1 locals=0 env=0
E ts=2025-09-08T15:30:45Z type="ValueError" msg="Invalid input data"
F0 mod="myapp.processor" fn="validate_data" file="processor.py:45" in_app=1 context="if not data.get('required_field'):"
F1 mod="myapp.main" fn="main" file="main.py:12" in_app=1
RC frame="F0" hint="Invalid input data"
</STACKTRACE>

Traceback (simplified message):
Call Path:
   File: /path/to/myapp/main.py, Line: 12 in main()
    └─ File: /path/to/myapp/processor.py, Line: 45 in validate_data()
        └─> L45: if not data.get('required_field'): 🔥

Exception Type: ValueError
Error: Invalid input data
```

## AIエージェント向け活用例

### 自動エラー修正システム

```python
from rdetoolkit.models.config import Config, TracebackSettings

# AIエージェント向け設定
ai_config = Config(
    traceback=TracebackSettings(
        enabled=True,
        format="compact",           # 機械可読形式
        include_context=True,       # エラー行のコード
        include_locals=False,       # プライバシー保護
        include_env=False,          # 環境情報は不要
        max_locals_size=256
    )
)

def handle_error_with_ai(exception):
    structured_error = handle_exception(exception, config=ai_config)
    
    # AIエージェントに送信するメッセージ
    ai_prompt = f"""
    エラーが発生しました。以下の構造化トレース情報を解析し、
    修正方法を提案してください：

    {structured_error.traceback_info}
    """
    
    # LLM APIに送信、修正提案を取得
    response = call_llm_api(ai_prompt)
    return response

try:
    risky_operation()
except Exception as e:
    suggestion = handle_error_with_ai(e)
    print(f"AI修正提案: {suggestion}")
```

### 自動バグレポート生成

```python
def generate_bug_report(exception):
    structured_error = handle_exception(exception, config=ai_config)
    
    # GitHubイシュー自動作成
    issue_body = f"""
## エラー概要
{structured_error.emsg}

## 構造化トレース情報
```
{structured_error.traceback_info}
```

## AI分析結果
{analyze_with_ai(structured_error.traceback_info)}
"""
    
    create_github_issue("自動検出エラー", issue_body)
```

## 利用シーン

### 1. 開発・デバッグ
```bash
# 詳細なローカル変数を含む出力
export TRACE_VERBOSE=context,locals
export TRACE_FORMAT=duplex
python your_script.py
```

### 2. CI/CD パイプライン
```bash
# 構造化されたエラー情報でログ分析を効率化
export TRACE_VERBOSE=context
export TRACE_FORMAT=compact
python your_rde_script.py
```

### 3. 本番環境監視
```bash
# 機密情報を含まない最小構成
export TRACE_VERBOSE=""
export TRACE_FORMAT=compact
```

## セキュリティ機能

### 自動マスキング

以下のキーワードを含む変数は自動的に`***`でマスキングされます：

- `password`, `passwd`, `pwd`
- `token`, `auth`, `authorization`
- `secret`, `key`, `api_key`
- `cookie`, `session`
- `credential`, `cred`

### カスタムマスキング

```python
config = Config(
    traceback=TracebackSettings(
        enabled=True,
        sensitive_patterns=[
            "database_url",
            "private_key",
            "connection_string"
        ]
    )
)
```

## トラブルシューティング

### 設定が反映されない場合

1. 環境変数の確認
```bash
echo $TRACE_VERBOSE
echo $TRACE_FORMAT
```

2. 設定の優先順位を確認
   - プログラム内設定（最優先）
   - 設定ファイル
   - 環境変数
   - デフォルト値（無効）

### 出力が期待と異なる場合

1. `CFG`行で実際の設定を確認
2. `in_app=1`でアプリケーションコード範囲を確認
3. セキュリティマスキングによる情報隠蔽を確認

### パフォーマンス問題

1. `include_locals=false`で変数出力を無効化
2. `max_locals_size`を小さく設定
3. 本番環境では`format=compact`を使用

## 関連ドキュメント

- [設定詳細](../config/config.ja.md)
- [エラーハンドリング](./errorhandling.ja.md)
- [API仕様](../../rdetoolkit/traceback/index.md)