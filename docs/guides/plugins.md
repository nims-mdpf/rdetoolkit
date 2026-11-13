# プラグイン開発ガイド

プラグインは、ノード・テンプレート・ファイル形式の宣言を独立したパッケージとして配布する
仕組みです。インストールするだけで `nodes list --plugin`・`templates list`・`formats list` に
現れ、他のプロジェクトから利用できます。

## プラグインが提供できるもの

| 提供物 | 書き方 | 発見するコマンド |
|--------|--------|-----------------|
| ノード | node デコレータを付けた関数 | `rdetoolkit nodes list --plugin` |
| テンプレート | `ProcessingTemplate` を継承した骨格クラス | `rdetoolkit templates list` |
| ファイル形式 | モジュール変数 `FORMAT_HANDLERS`(`FormatHandler` のタプル) | `rdetoolkit formats list` |

プラグインは Runner のライフサイクルに処理を差し込むことはできません。プラグインの
ノードやテンプレートは、ユーザーが書いたものと同じ仕組みで動き、特別な権限を持ちません。

## 1. 提供モジュールを書く

プラグインの入口になるモジュールに、提供するノード・テンプレート・`FORMAT_HANDLERS` を
置きます。ここでは `rdetoolkit_example_plugin.py` とします。

<!-- test: plugin-provider -->
```python
from typing import final

from rdetoolkit import node
from rdetoolkit.plugin import FormatHandler
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths


@node(id="example_plugin.count_lines")
def count_lines(text: str) -> int:
    """Count the lines of a text file's content."""
    return len(text.splitlines())


class LineCountTemplate(ProcessingTemplate):
    """Skeleton for instruments that write plain-text logs."""

    @slot
    def read(self, paths: InputPaths) -> str: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        count_lines(self.read(paths))


FORMAT_HANDLERS = (
    FormatHandler(
        name="Example text log",
        extensions=(".log",),
        target="rdetoolkit_example_plugin:LineCountTemplate",
    ),
)
```

- ノード ID には、他のパッケージと衝突しないようにパッケージ名を接頭辞として付けてください。
  同じ ID の二重登録は `E2001` になります。
- `FORMAT_HANDLERS` は宣言(名前・拡張子・利用者に示す参照先)であり、Runner が自動的に
  呼び出すものではありません。

## 2. エントリポイントを登録する

パッケージの `pyproject.toml` で、`rdetoolkit.plugins` グループに提供モジュールを登録します。

<!-- test: plugin-entry-point -->
```toml
[project.entry-points."rdetoolkit.plugins"]
example = "rdetoolkit_example_plugin"
```

## 3. インストールして確認する

パッケージをインストールすると(開発中は `pip install -e .`)、次のコマンドで提供物が
見えるようになります。

<!-- test: plugin-discovery -->
```bash
$ python -m rdetoolkit nodes list --plugin
$ python -m rdetoolkit templates list
$ python -m rdetoolkit formats list
```

<!-- illustration: plugin-discovery-output -->
```text
example_plugin.count_lines
rdetoolkit_example_plugin.LineCountTemplate
Example text log (.log) -> rdetoolkit_example_plugin:LineCountTemplate [example]
```

`formats list` は、ファイル形式ごとに名前・拡張子・参照先と、提供元のプラグイン名
(エントリポイント名)を表示します。`--json` を付けると機械可読な形式で出力します。

import に失敗したプラグインや、`FORMAT_HANDLERS` の形式が誤っているプラグインは、標準エラー
出力に理由を表示して読み飛ばされます。他のプラグインやコマンドの動作には影響しません。
Python から発見結果を調べる場合は `rdetoolkit.plugin.discover_plugins()` を使います。

## 4. 利用者側から使う

利用者はプラグインのノードを普通の関数として import してフローから呼び、テンプレートは
継承して slot を実装します。テンプレートから雛形を作るには `init --processing-template` を使います。

<!-- test: plugin-usage -->
```bash
$ python -m rdetoolkit templates describe LineCountTemplate
$ python -m rdetoolkit init --processing-template LineCountTemplate --module rdetoolkit_example_plugin
```

`templates describe` は slot の名前・引数・戻り値の型を表示します。`init` は slot を TODO として
残した利用者クラス(`processing.py`)、サンプルテスト(`tests/test_processing.py`)、
エントリポイント(`main.py`)を生成します。

## プラグインをテストする

提供モジュールのノードとテンプレートは、[テストガイド](testing.md) と同じ方法で
テストできます。`nodes lint --module rdetoolkit_example_plugin` を CI で実行すると、
型注釈の欠落やテンプレートの誤用を配布前に検出できます。

## 関連ページ

- [ノード](../concepts/node.md)・[フロー](../concepts/flow.md) — ノードとテンプレートの規則
- [API リファレンス: rdetoolkit.plugin](../rdetoolkit/v2/plugin.md)
