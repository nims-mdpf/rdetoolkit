# v2 チュートリアル: 必要な概念だけ段階的に使う

最短経路は、対応する ProcessingTemplate があるならレベル 1、なければレベル 2
です。どちらも同じ Runner、call log、`RunReport` を使います。Runner 結合まで
テストしたくなったときだけレベル 3 に進みます。

## レベル 1: テンプレートの slot を埋める

ドメインパッケージの作者が、処理骨格と必須 slot を宣言します。ここでは実行可能な
最小パッケージを例示します。

<!-- test: level-1-template-package -->
```python
from typing import final

from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths, InvoiceData


class InstrumentTemplate(ProcessingTemplate):
    @slot
    def read(self, paths: InputPaths) -> None: ...

    @slot
    def extract_meta(self, invoice: InvoiceData) -> None: ...

    @final
    def __flow__(self, paths: InputPaths, invoice: InvoiceData) -> None:
        self.read(paths)
        self.extract_meta(invoice)
```

利用者は `templates list` / `templates describe` でテンプレートを発見し、次の
コマンドで雛形とサンプルテストを生成します。

<!-- test: level-1-init -->
```bash
$ python -m rdetoolkit init --processing-template InstrumentTemplate --module instrument_template
```

生成されたクラスの `read` と `extract_meta`、つまり 2 つの TODO slot を実装し、
生成されたテストを通したら `python -m rdetoolkit run --flow <module>:<class>` で
実行します。`--processing-template` はドメイン処理テンプレート名を受け取ります。

## レベル 2: plain `@flow` を書く

対応テンプレートがない処理は `@flow` から始めます。decorated flow は plain
Python 関数なので、直接呼び出して小さくテストできます。

<!-- test: level-2-flow -->
```python
from rdetoolkit import flow


@flow(id="docs.tutorial.eager_flow")
def label_even(values: list[int], prefix: str = "sample") -> list[str]:
    labels = []
    for value in values:
        if value % 2 == 0:
            labels.append(f"{prefix}-{value}")
    return labels


result = label_even([1, 2, 3, 4], prefix="sample")
assert result == ["sample-2", "sample-4"]
```

分岐、ループ、デフォルト引数、リテラル、f-string はすべて Python の通常の
意味で評価されます。再利用する処理だけを後から `@node` に分けてください。

## レベル 3: Runner 結合を `run_flow` でテストする

単体テストを越えて、予約型の注入、DataTile、出力、`RunReport` まで確認する場合は
`rdetoolkit.testing.run_flow` を使います。

<!-- test: level-3-run-flow -->
```python
from rdetoolkit import flow
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths


@flow(id="docs.tutorial.runner_flow")
def count_inputs(paths: InputPaths) -> None:
    assert len(list(paths.inputdata.glob("*.txt"))) == 1


fixture_dir.mkdir(parents=True)
(fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
report = run_flow(count_inputs, fixture_dir)
assert report.status == "success"
```

`run_flow` は実データを模した一時 RDE ツリーを作り、正規の Runner 経路を実行して
`RunReport` を返します。これにより直接呼び出しのテストと Runner 結合テストを
目的に応じて使い分けられます。

## スコープ

rdetoolkit v2 は RDE 構造化処理のバッチハーネスであり、汎用ワークフローエンジン
ではありません。スケジューリング、ノード並列、途中再開、キャッシュは提供せず、
将来の性能拡張も DataTile 単位の並列化を対象にします。
