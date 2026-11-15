# v2 をはじめる

このページでは、rdetoolkit v2 で最初の構造化処理を作り、実行し、実行記録を確認する
ところまでを一通り体験します。作るのは「CSV を読み込み、正規化して、構造化 CSV と
グラフを保存する」小さな flow です。

v1 の `run(custom_dataset_function=...)` で書かれた既存プログラムは、v2 でも
そのまま動きます。既存プログラムを移行する場合は [v1 から v2 への移行](migration_v1_to_v2.md)
を参照してください。

## 前提条件

- Python 3.10 以上
- rdetoolkit 2.x

<!-- illustration: gs-install -->
```bash
$ pip install rdetoolkit
$ python -m rdetoolkit version
```

## 1. プロジェクトの雛形を作る

空のディレクトリで `init` を実行します。

<!-- test: gs-init -->
```bash
$ python -m rdetoolkit init
```

RDE の構造化処理に必要なファイル一式が `container/` 以下に作られます
(`container/` の外にある `input/` と `templates/` は、このページでは使いません)。

<!-- illustration: gs-init-tree -->
```text
container/
├── Dockerfile
├── main.py
├── requirements.txt
├── modules/
└── data/
    ├── inputdata/
    ├── invoice/
    │   └── invoice.json
    └── tasksupport/
        ├── invoice.schema.json
        └── metadata-def.json
```

`data/` は RDE 上でのディレクトリ配置と同じ形です。`inputdata/` には入力データ、
`invoice/` には送り状、`tasksupport/` にはスキーマとメタデータ定義が置かれます。

## 2. 入力データを置く

`container/data/inputdata/sample.csv` を作り、次の内容を書き込みます。

<!-- test: gs-sample-csv -->
```csv
time,intensity
0,1.0
1,2.5
2,4.0
```

## 3. flow を書く

`container/modules/` に空の `__init__.py` と、次の `flow.py` を置きます。

<!-- test: gs-flow -->
```python
import pandas as pd

from rdetoolkit import flow, node
from rdetoolkit.nodes import plot_lines, read_csv_with_header, save_csv
from rdetoolkit.types import InputPaths, OutputContext


@node(id="quickstart.normalize")
def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Scale the intensity column to its maximum."""
    df = df.copy()
    df["intensity"] = df["intensity"] / df["intensity"].max()
    return df


@flow(id="quickstart.pipeline")
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    for csv_path in paths.rawfiles:
        df = read_csv_with_header(csv_path)
        df = normalize(df)
        save_csv(df, out, csv_path.name)
        plot_lines(df, out, f"{csv_path.stem}.png", x="time", y="intensity")
```

ポイントは 3 つです。

- `pipeline` は**普通の Python 関数**としてそのまま実行されます。`for` 文も
  f-string も Python の通常の意味で動きます。
- 引数の型注釈 `InputPaths` / `OutputContext` を見て、Runner が現在の
  データタイルの入力パスと出力先を渡します(引数名は自由です)。
- `read_csv_with_header` / `save_csv` / `plot_lines` は rdetoolkit の
  **組込ノード**です。自作の `normalize` と同じくノードとして呼び出しが記録されます。

## 4. エントリポイントを書く

`container/main.py` を次の内容に置き換えます。

<!-- test: gs-main -->
```python
import rdetoolkit
from modules.flow import pipeline

report = rdetoolkit.workflows.run(flow=pipeline)
print(report.status)
```

`workflows.run(flow=...)` は実行結果を `RunReport` として返します。

## 5. 実行する

<!-- test: gs-run -->
```bash
$ cd container
$ python main.py
```

`success` と表示されれば成功です。`container/data/` 以下に成果物と実行記録が
作られます。

<!-- illustration: gs-run-tree -->
```text
data/
├── inputdata/sample.csv
├── structured/sample.csv          # 正規化した CSV
├── main_image/sample.png          # グラフ
├── nonshared_raw/sample.csv       # 入力ファイルのコピー
└── logs/
    ├── run_report_<run_id>.json   # RunReport
    ├── events_<run_id>.jsonl      # イベントログ
    └── iterations/iteration_0.json
```

処理が失敗した場合は、RDE の規約どおり `data/job.failed` にエラーコードと
メッセージが書き出されます。

## 6. 実行記録を確認する

`report show` で RunReport の要約を、`graph` でノードの呼び出し順(Call Sequence)を
表示できます。

<!-- test: gs-inspect -->
```bash
$ python -m rdetoolkit report show data/logs/run_report_<run_id>.json
$ python -m rdetoolkit graph data/logs/run_report_<run_id>.json --format mermaid
```

<!-- illustration: gs-inspect-output -->
```text
run_id: 550956f7318c414eb15a5f9175309f22
status: success
iterations: 1
```

`graph` が出力するのはノードが**呼ばれた順序**の記録であり、値の受け渡しを復元した
データフロー図ではありません。

## 7. CLI から実行する・検査する

`main.py` を使わずに、CLI から flow を直接実行することもできます。登録された
ノードの静的検査には `nodes lint` を使います。

<!-- test: gs-cli -->
```bash
$ python -m rdetoolkit run --flow modules.flow:pipeline
$ python -m rdetoolkit nodes lint --module modules.flow
```

`run --flow` は RunReport の JSON を標準出力に書き、終了コードで結果を返します
(0 = success、1 = failed、2 = partial、3 = 引数の誤り)。

## 次のステップ

- [v2 チュートリアル](tutorial_v2.md) — テンプレート・flow・`run_flow` の 3 段階
- [ノード](concepts/node.md)・[フロー](concepts/flow.md)・[Runner](concepts/runner.md) — v2 の中核概念
- [テストガイド](guides/testing.md) — `rdetoolkit.testing` によるテストの書き方
- [CLI リファレンス](reference/cli.md) — 全コマンドとオプション
