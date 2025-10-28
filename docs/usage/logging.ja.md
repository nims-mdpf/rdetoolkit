# `get_logger`を使ったログ記録

## このドキュメントについて

`rdetoolkit.rdelogger.get_logger` を利用して、RDEToolKit の処理からログをファイルに残すための基本的な使い方をまとめます。RDE構造化処理における進捗やエラーを確実に追跡できるよう、ログの初期化・出力・保守のポイントを解説します。

## `get_logger` の振る舞い

- **名前 (`name`)**: ロガーを識別する名前。通常は `__name__` を渡し、モジュール単位でロガーを分けます。
- **ログレベル (`level`)**: 既定値は `logging.DEBUG`。INFO や WARNING など任意のレベルを指定できます。
- **出力先 (`file_path`)**: `RdeFsPath` もしくは文字列でログファイルのパスを渡すと、`LazyFileHandler` が必要になったタイミングでファイルとディレクトリを自動生成します。
- **ハンドラーの重複防止**: 同じ `name` と `file_path` の組み合わせで複数回 `get_logger` を呼び出しても、同じファイルハンドラーが二重に登録されないように保護されています。
- **ファイルパスなしの挙動**: `file_path=None` の場合はハンドラーが追加されません。標準出力などへの出力は、別途 `logging.basicConfig()` や任意のハンドラー設定が必要です。

ログフォーマットは既定で `%(asctime)s - [%(name)s](%(levelname)s) - %(message)s` です。タイムスタンプとモジュール名、レベルが一目で分かります。

## 1. 最小構成でログを書き出す

以下の例では、`data/logs` ディレクトリにアプリケーション固有のログファイルを作成し、INFO レベル以上のメッセージを記録します。

```python
from pathlib import Path
import logging

from rdetoolkit.rdelogger import get_logger
from rdetoolkit.models.rde2types import RdeFsPath

log_path = RdeFsPath(Path("data/logs/structured_process.log"))
logger = get_logger(__name__, file_path=log_path, level=logging.INFO)

logger.info("構造化処理を開始しました")
logger.warning("入力ファイルが不足しています")
```

実行すると、初回のログ出力時に `data/logs/structured_process.log` が作成され、次のような行が追記されます。

```
2024-06-14 10:21:35,147 - [my_module](INFO) - 構造化処理を開始しました
2024-06-14 10:21:35,148 - [my_module](WARNING) - 入力ファイルが不足しています
```

## 2. モジュールごとにロガーを共有する

同じモジュール内で繰り返しログを記録するときは、モジュールスコープでロガーを初期化しておきます。RDEToolKit の処理フローに組み込む場合も、以下のようにロガーを定義しておくと便利です。

```python
# modules/dataset.py
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/dataset.log")


def run(context: dict) -> int:
    logger.debug("構造化処理を開始します")
    try:
        # ... (処理本体)
        logger.info("構造化処理が完了しました")
        return 0
    except Exception as exc:
        logger.exception("構造化処理でエラーが発生しました")
        raise
```

- `logger.exception()` は例外情報を自動的に付加するため、原因追跡が容易になります。
- `LazyFileHandler` によって `data/logs/dataset.log` は必要になるまで作成されません。

## 3. ログレベルと運用上のヒント

| レベル          | 用途の目安                                     |
| ---------------- | ---------------------------------------------- |
| `DEBUG`          | 詳細なデバッグ情報。開発・検証時に有効。       |
| `INFO`           | 正常系の進捗や成果を記録。                     |
| `WARNING`        | 注意すべき事象。処理は継続できる軽微な問題。   |
| `ERROR`          | 処理継続が難しいエラー。自動リトライなどの検討。|
| `CRITICAL`       | 即時対応が必要な重大障害。                     |

- 運用環境では `INFO` または `WARNING` を基準に設定し、詳細な調査が必要なときにのみ `DEBUG` に切り替えます。
- `get_logger` は既存のハンドラー設定を尊重します。外部サービスへの転送やログローテーションが必要な場合は、標準の `logging` モジュールのハンドラー（`RotatingFileHandler` など）を追加で設定してください。

## 4. 標準出力へ出力したい場合

`file_path` を省略するとファイルハンドラーは登録されません。標準出力に出したい場合は、次のように `logging.basicConfig()` でハンドラーを用意してから `get_logger` を呼び出します。

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

logger.info("コンソールにログを出力します")
```

既にアプリケーション側でハンドラーを構成している場合は、その設定を再利用できるため便利です。

## 5. よくある質問

**Q. 同じロガーを複数回初期化すると二重に出力されませんか？**
A. `get_logger` は同一ファイルを指す `LazyFileHandler` が既に登録されているか確認してから追加するため、重複出力は発生しません。

**Q. `file_path` にディレクトリが存在しないときはどうなりますか？**
A. `LazyFileHandler` がディレクトリを自動で作成し、初回ログ出力時にファイルを生成します。

**Q. `RdeFsPath` 型をどう使えばよいですか？**
A. `Path` または文字列からラップできます。RDEToolKit では `RdeFsPath` を利用することで、プロジェクト内のパス表現を統一しています。

`get_logger` を適切に活用することで、RDE 構造化処理の挙動を時系列で追跡でき、トラブルシューティングや監査にも役立ちます。まずは各モジュールで共通化されたロガーの初期化パターンを整備し、運用に応じてログレベルやハンドラーを調整してください。
