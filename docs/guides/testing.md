# テストガイド

v2 のノードとフローは普通の Python 関数なので、pytest でそのままテストできます。
`rdetoolkit.testing` は、予約型の値や RDE のディレクトリ構成を用意する手間を省くための
フィクスチャとヘルパーを提供します。

## テストの 4 つのレベル

| レベル | 対象 | 方法 |
|--------|------|------|
| 1 | ノード・slot 単体 | 関数・メソッドとして直接呼ぶ |
| 2 | フロー単体 | フィクスチャで作った予約型の値を渡して直接呼ぶ |
| 3 | Runner との結合 | `run_flow()` で本物の Runner を通して実行する |
| 4 | 出力ツリー | `assert_output_tree()` でディレクトリ構成を比較する |

ほとんどのテストはレベル 1 と 2 で書けます。レベル 3 は、モード判定・送り状・`job.failed` を
含めた振る舞いを確認したいときに使います。

## 提供されるもの

rdetoolkit をインストールすると、pytest プラグインが自動的に登録されます。`conftest.py` を
書かなくても、次のフィクスチャを引数に書くだけで使えます。

| フィクスチャ | 型 | 内容 |
|-------------|----|------|
| `rde_paths` | `InputPaths` | 一時ディレクトリ上の最小の入力ツリー |
| `rde_out` | `OutputContext` | すべての出力ディレクトリを作成済みの出力先 |
| `rde_config` | `RdeConfig` | 既定の設定 |
| `rde_invoice` | `InvoiceData` | 最小限の送り状 |

| ヘルパー | 内容 |
|----------|------|
| `make_input_paths(tmp_path, files=...)` | 入力ツリーを作り、`files` を `inputdata/` に空ファイルとして作成し `rawfiles` に並べる |
| `make_output_context(tmp_path)` | 出力ディレクトリ一式を作った `OutputContext` を返す |
| `make_invoice(overrides=...)` | 送り状を作る。`basic` などのセクション以外のキーは `custom` に入る |
| `run_flow(flow, fixture_dir)` | `fixture_dir` のファイルを入力にした一時 RDE ツリーで Runner を実行し、RunReport を返す |
| `run_flow(flow, data_root=root)` | 既存の RDE ツリーをその場で実行し、出力と `job.failed` を残す |
| `assert_output_tree(out, golden_dir)` | 出力先のディレクトリ構成が `golden_dir` と一致することを確認する |

## 例: プロジェクトのテストを書く

次の `modules/processing.py` をテストします。CSV の最大値を求めるノード、それを使う
フロー、同じ処理をテンプレートの slot として書いたクラスを含みます。

<!-- test: testing-source -->
```python
from typing import final

import pandas as pd

from rdetoolkit import flow, node
from rdetoolkit.nodes import read_csv_with_header, save_csv
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths, OutputContext


@node(id="example.find_peak")
def find_peak(df: pd.DataFrame) -> float:
    """Return the largest intensity."""
    return float(df["intensity"].max())


@flow(id="example.pipeline")
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    for csv_path in paths.rawfiles:
        peak = find_peak(read_csv_with_header(csv_path))
        save_csv(pd.DataFrame({"peak": [peak]}), out, f"{csv_path.stem}_peak.csv")


class PeakTemplate(ProcessingTemplate):
    @slot
    def peak(self, df: pd.DataFrame) -> float: ...

    @final
    def __flow__(self, paths: InputPaths, out: OutputContext) -> None:
        for csv_path in paths.rawfiles:
            peak = self.peak(read_csv_with_header(csv_path))
            save_csv(pd.DataFrame({"peak": [peak]}), out, f"{csv_path.stem}_peak.csv")


class CsvPeak(PeakTemplate):
    def peak(self, df: pd.DataFrame) -> float:
        return float(df["intensity"].max())
```

テストは `tests/test_processing.py` に書きます。

<!-- test: testing-tests -->
```python
import pandas as pd

from rdetoolkit.testing import make_input_paths, run_flow

from modules.processing import CsvPeak, find_peak, pipeline

CSV = "time,intensity\n0,1.0\n1,3.0\n2,2.0\n"


def test_find_peak():
    # Level 1: a node is a plain function.
    assert find_peak(pd.DataFrame({"intensity": [1.0, 3.0, 2.0]})) == 3.0


def test_slot():
    # Level 1: a template slot is a plain method.
    assert CsvPeak().peak(pd.DataFrame({"intensity": [1.0, 3.0]})) == 3.0


def test_pipeline_direct(tmp_path, rde_out):
    # Level 2: call the flow with fixture-built reserved values.
    paths = make_input_paths(tmp_path / "input", files=["sample.csv"])
    paths.rawfiles[0].write_text(CSV, encoding="utf-8")
    pipeline(paths, rde_out)
    assert (rde_out.struct / "sample_peak.csv").read_text(encoding="utf-8").splitlines() == ["peak", "3.0"]


def test_pipeline_through_runner(tmp_path):
    # Level 3: run the real Runner on a temporary RDE tree.
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "sample.csv").write_text(CSV, encoding="utf-8")
    report = run_flow(pipeline, fixture_dir)
    assert report.status == "success"
    calls = [call["node_id"] for call in report.iterations[0]["node_calls"]]
    assert "example.find_peak" in calls


def test_template_through_runner(tmp_path):
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "sample.csv").write_text(CSV, encoding="utf-8")
    assert run_flow(CsvPeak, fixture_dir).status == "success"
```

プロジェクトのディレクトリで実行します。`python -m pytest` はカレントディレクトリを
import パスに加えるので、`modules` パッケージをそのまま import できます。

<!-- test: testing-run -->
```bash
$ python -m pytest tests
```

## `run_flow` の 2 つの使い方

- `run_flow(flow, fixture_dir)` は、`fixture_dir` のファイルを `inputdata/` に複製した一時
  ツリー(合成した送り状と空のスキーマ付き)で実行し、終了後にツリーを削除します。
  RunReport の状態や呼び出し記録を確認するのに向いています。
- `run_flow(flow, data_root=root)` は、本物の `invoice.json`・`invoice.schema.json`・
  `metadata-def.json` を持つ RDE ツリー(またはそれを `data/` に持つプロジェクト)を
  その場で実行します。成果物と `job.failed` が残るので、実行後に内容を検査できます。

どちらもカレントディレクトリは実行後に元に戻ります。

## 出力ツリーを比較する

`assert_output_tree(out, golden_dir)` は、`out` の出力ディレクトリ構成(ディレクトリの集合)を
`golden_dir` 以下の構成と比較し、過不足があれば `missing` / `extra` を示して失敗します。
期待するツリーは手で書かず、一度正しく動いた実行結果から作ってください。

## CI で検査する

ノードとテンプレートの登録は、実行しなくても検査できます。CI では pytest に加えて
`nodes lint` を実行すると、型注釈の欠落・不安定なノード ID・テンプレートの誤用を検出できます。

<!-- test: testing-lint -->
```bash
$ python -m rdetoolkit nodes lint --module modules.processing
```

## 関連ページ

- [フロー](../concepts/flow.md) — 予約型と依存性注入
- [v2 チュートリアル](../tutorial_v2.md) — `run_flow` を使うレベル 3
- [API リファレンス: rdetoolkit.testing](../rdetoolkit/v2/testing.md)
