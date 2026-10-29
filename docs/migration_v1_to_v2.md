# v1 から v2 への移行

v2 の正準入口は eager に実行される flow デコレータ付き関数と ProcessingTemplate です。
実行結果は `RunReport` で受け取り、`status`、タイルごとの結果、警告、エラーを
同じスキーマから確認します。このガイドでは既存のハンドラークラスを一度に
捨てず、機械変換と小さな手作業を組み合わせて移行します。

## 1. 既存コードを検査する

例として、次の v1 形式のファイルを `legacy.py` とします。

<!-- test: legacy-source -->
```python
import rdetoolkit.workflows as legacy_workflows


class TextHandler:
    def process(self, srcpaths, resource_paths):
        source = next(srcpaths.inputdata.glob("*.txt"))
        destination = resource_paths.struct / "structured.txt"
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def custom_dataset_function(srcpaths, resource_paths):
    TextHandler().process(srcpaths, resource_paths)


if __name__ == "__main__":
    legacy_workflows.run(custom_dataset_function=custom_dataset_function)
```

`migrate check` は移行点を報告する読み取り専用コマンドです。`migrate apply` は
既定で dry-run になり、変換後の flow 関数を表示します。内容を確認した後だけ
`--no-dry-run --out <別ディレクトリ>` を指定してください。入力ファイルを
直接書き換えることはありません。

<!-- test: migration-commands -->
```bash
$ python -m rdetoolkit migrate check legacy.py
$ python -m rdetoolkit migrate apply legacy.py
```

変換不能な動的ディスパッチなどは `TODO(rdetoolkit-migrate)` として残ります。
TODO がない場合でも、生成物のテストと出力ディレクトリを確認してから採用します。

## 2. ハンドラーを `as_node` でつなぐ中間形

付録 M の Protocol に適合する既存ハンドラーは、移行期間中だけ `as_node` で
メソッドを通常の node にできます。Protocol はこの移行判断の補助であり、DI や
新規設計の入口ではありません。

<!-- test: as-node-bridge -->
```python
from rdetoolkit import as_node


class LegacyReader:
    def read(self, name: str) -> str:
        return name.upper()


read_legacy = as_node(LegacyReader(), method="read", id="docs.migration.legacy_reader")
result = read_legacy("sample.txt")
assert result == "SAMPLE.TXT"
```

この段階ではクラスを残せますが、node 間の値は明示引数で渡し、`self.df` のような
隠れ状態を増やさないでください。

## 3. 最終形を選ぶ

対応するドメインテンプレートがある場合は、`templates describe <name>` で slot を
確認し、`init --processing-template <name>` が生成したクラスの TODO slot だけを
実装します。骨格、保存順序、出力規約はテンプレートが所有します。

テンプレートがない非定型処理では flow デコレータ付きの関数を 1 つ書きます。`if`、ループ、
f-string、リテラル引数、デフォルト引数は通常の Python と同じです。処理を再利用
したくなった時点でだけ node デコレータ付きの関数に分割します。保存処理には `rdetoolkit.nodes` の
組込ノードを使います。

## 実行時の変更点

- v2 の正準戻り値は `RunReport` です。`report.status` と
  `report.iterations` を起点に結果を処理してください。
- **flow 入口では `on_iteration_error` の既定値が `continue` です。** v1 の
  即時停止(fail-fast)が必要なら設定で `fail_fast` を明示してください。
  `run(custom_dataset_function=...)` の v1 入口は v1 の反復規則を保ちます
  (後述の「意図的な差分」を参照)。
- グラフは実行前 DAG ではなく、実行後の call sequence です。通常の Python
  制御構文をそのまま使えます。

## v1 ユーザー向け互換範囲とスケジュール

この節は 2.0.0rc1 時点の確定内容です。v1 の実行経路(反復ループとモード別処理)は
削除され、すべての入口が単一の Runner を通ります。v1 の**契約**(入口・成果物・
終了の仕方)は、v1.7.1 の契約を取り込んだ v1 実行経路から凍結した契約スナップショットとの比較テストで守られて
います。

### 維持されるもの

- **入口**: `rdetoolkit.workflows.run(custom_dataset_function=...)` のシグネチャ。
  コールバックは従来どおり `(srcpaths, resource_paths)` を受け取ります。
- **v1 契約**: 戻り値の JSON(各タイルの status 一覧)、失敗時の
  `SystemExit(1)`、既定の fail-fast、`data/job.failed` の書式、出力
  ディレクトリ構成(`raw/`、`structured/`、`divided/NNNN/` など)、
  `data/logs/rdesys_<タイムスタンプ>.log`。
- **Tier 1 API**: `rdetoolkit.models.rde2types`、`rdetoolkit.rde2util`、
  `rdetoolkit.invoicefile`、`rdetoolkit.errors`、`rdetoolkit.exceptions`、
  `workflows.check_files` / `check_files_result`、
  `workflows.generate_folder_paths_iterator`。
- `rdetoolkit init` / `gen-invoice` / `make-excelinvoice` / `artifact` などの
  既存 CLI コマンド。

### 削除されたもの(2.0.0rc1)

- `rdetoolkit.modeproc` モジュール。
- `rdetoolkit.processing` パッケージ(`Pipeline`、`ProcessingContext`、
  `Processor` とその派生クラス一式)。
- `rdetoolkit.workflows` のモード別関数 `invoice_mode_process`、
  `excel_invoice_mode_process`、`multifile_mode_process`、
  `rdeformat_mode_process`、`smarttable_invoice_mode_process`。
- `rdetoolkit` パッケージからの `impl` と `interfaces` の公開 export。両モジュールは
  Runner の内部実装として残りますが、公開 API ではありません。

これらを直接 import しているコードは、`run(custom_dataset_function=...)` 経由の
呼び出しに戻すか、flow 関数へ移行してください。

**非推奨(呼び出し元なし、互換のためだけに残存)**:
`rdetoolkit.errors.handle_and_exit_on_structured_error` と
`rdetoolkit.models.result.WorkflowResultManager`。新しいコードでは使わないで
ください。`RdeOutputResourcePath` の `smarttable_rowfile=` 引数も、v1.7 と同じく
`smarttable_rawfile` への非推奨エイリアスです。

### 挙動の変更

**v1.7 系で入った変更(v2 でもそのまま)**

- SmartTable モードの行 CSV(`fsmarttable_*.csv`)は `rawfiles` に含まれません
  (#503)。行 CSV が必要な場合は `smarttable_rawfile` を使います
  (旧名 `smarttable_rowfile` は誤記の改名)。
- `smarttable.save_table_file: true` のとき、元の SmartTable ファイルは
  `divided/0001` として先頭に登録され、データ行は `divided/0002` 以降に
  ずれます(#503)。
- SmartTable の `meta/<key>` 列を使うには `tasksupport/metadata-def.json` が
  必須です。ない場合は無視されず `StructuredError` で失敗します(#496)。

**2.0.0rc1 で入った変更**

- 実行ごとのイベントログ `data/logs/events_<run_id>.jsonl` が既定で出力されます。
  ファイルは 1 実行あたり 64 MiB が上限で、超えた時点で警告 **W1002**
  (`EventsLogTruncated`)を 1 回記録し、以降のノード単位イベントだけを
  省きます(実行・タイル単位のイベントと警告は残ります)。
  `data/logs/**` は v1 の成果物契約の対象外です。
- `data/logs/iterations/` はタイル反復の開始時に空にされます。
  `job.failed`、`run_report_*`、`events_*` は従来どおり実行をまたいで残ります。

### 意図的な差分(v1 と結果が異なるケース)

| ケース | v1 | v2 |
|---|---|---|
| コールバックが `StructuredError(msg, ecode)` を送出 | `job.failed` に `ecode` と `msg` | 同じ |
| コールバックが素の例外を送出 | `ErrorCode=999`、`Unexpected error in <mode> mode: ...` | `ErrorCode=3001`。メッセージはエラーカタログ E3001 の文で、ユーザーの例外メッセージを含みます |
| `invoice.schema.json` 自体が不正で、コールバックも失敗 | コールバック側のエラーコード(検証はコールバックの後) | `ErrorCode=4001`(スキーマ検証の理由付き)。コールバックは呼ばれません |
| invoice がスキーマに違反 | モードごとに異なるコード、一部モードではコールバック実行済み・出力も生成済み | `ErrorCode=4001`。コールバックは呼ばれず、タイルの成果物は作られません(`job.failed`・ログ・run report は残ります) |
| 設定ファイルの探索(`config=None`) | `data/tasksupport` から読み込み | 同じ。不正な設定ファイルは v1 と同じく `ErrorCode=999` |
| `rdesys_<タイムスタンプ>.log` の場所 | `data/logs` | 標準構成では同じ |
| 実行中の SIGTERM | プロセスが終了するだけで `job.failed` も記録も残らない | `job.failed` に `ErrorCode=3004`(`RunInterrupted`)、`RunReport` も書き出し、完了済みタイルの成果物は残ります。公開入口の終了コードは 1 |
| `rdetoolkit run` CLI の終了コード | v1 に `run` コマンドはなし | `0` 成功 / `1` 失敗 / `2` 一部失敗 / `3` 使い方の誤り。Python API の `run()` は v1 どおり(失敗で `SystemExit(1)`) |
| `multidata_tile.ignore_errors: true` で全タイルが失敗 | MultiDataTile のみ全件 `failed` の JSON を返し終了コード 0。他モードではフラグは無視され最初の失敗で停止 | v1 コールバック入口は全モードで v1 と同じ。flow 入口では全タイル失敗は `failed` となり `job.failed` を書きます |

### ロールバック

v2 で問題が出た場合は、v1 系の最新版 `1.7.1` を固定してください(例:
`requirements.txt` に `rdetoolkit==1.7.1`)。旧経路を含む開発版は PyPI にはなく、
git タグ `v2.0.0a1` からのソースインストールのみ可能です(切り分け用途。この
タグの `__version__` は `2.0.0` と表示されます)。

### スケジュール

`2.0.0rc1` → GA `2.0.1` の順に公開します。版番号 `2.0.0` は欠番で、
正式版としては公開しません。
