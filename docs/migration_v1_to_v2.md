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

測定メタデータには公開ノード `build_meta(values, metadef_path)` を使い、
`save_meta(metadata, out)` で保存します。metadata-def に従ってキーを絞り、
型変換、キー順、単位（`$Key` 参照を含む）、variable 行を揃えます。
繰り返し値は `repeated={key: values}` で渡せます。variable 定義に対するスカラー値は
1 行にまとめます。`Metadata.units` は constant の単位、`Metadata.variable` は
value/unit セルの行を保持します。`parse_invoice_meta` も invoice の `custom` に
同じ規則を適用します。flow で `rde2util.Meta` や v1 オブジェクトの変換層を使う必要はありません。

値のキーには定義キーと `originalName` のどちらも使えます。v1 の `Meta.assign_vals` と
同じく、両方がある場合は定義キーを優先し、`originalName` は定義キーが無いときだけ
参照します（定義キーが `None` で存在する場合は `originalName` を参照せず除外します）。
`match="original_name"` は宣言された別名だけを使い、`originalName` が未指定または
`null` の定義は定義キーを使います。明示的な空文字の別名は入力キーとして維持します。
`match="key"` は別名の照合を無効にします。既定の `match="both"` は上記の優先規則を保ちます。
`save_meta` は v1 の `Meta.writefile` と同じ 4 スペースのインデントで書き出し、
`indent=` で変更できます。

第2引数には定義の Mapping も渡せます。共有定義をメモリ上で絞り込んで直接渡せるため、
一時 JSON ファイルは不要です。文字列は空かどうかを判定する前に前後の空白を除去します。
`build_meta` は `""` と空白だけの文字列に、次の同じ規則を適用します。

| スキーマ型 | 既定 | `keep_empty_strings=True` |
|---|---|---|
| `string` | 値を除外 | format が許す場合に `""` を保持 |
| `number`、`integer`、`boolean` | 型変換の前に除外 | `StructuredError`（`ecode=1`） |

繰り返しセルにも同じ規則を適用し、行位置は維持します。空でない不正な値は、
どちらの設定でも型変換エラーになります。この正規化は `build_meta` に適用します。
v1 の `Meta.assign_vals` と `parse_invoice_meta` の既存規則は維持し、空白だけの
数値・整数・真偽値は従来どおり型変換エラーになります。

v1 の `castval` / `_assign_invoice_val` のように `invoice.custom` を更新するには
`set_custom_fields(invoice, updates, schema=...)` を使います(#603)。新しい
`InvoiceData` を返し、各値を `invoice.schema.json` の `type` と `format` で変換します。

| スキーマ | 受け付ける値 | 格納される値 |
|---|---|---|
| `integer` | 数字(単位付き `"12 mm"` も可)、整数値の float(`3.0`) | `int` |
| `number` | 数値の文字列(単位付きも可) | 整数なら `int`、それ以外は `float` |
| `boolean` | `"true"` / `"false"`(大文字小文字を区別しない)、それ以外は真偽値として評価 | `bool` |
| `string` + `date` / `date-time` / `time` | dateutil で解釈できる文字列、`date` / `datetime` オブジェクト | `2023-07-19` / ISO 8601 / `13:04:05` |
| `string`(他の format、または format なし) | 任意 | そのまま |
| すべての型 | `None`、NaN、`NaT`、`pd.NA`(NumPy の NaN / NaT も含む) | `None` |

`dtype_backend="numpy_nullable"` で読んだ空セル(`pd.NA`)も `None` になります。NumPy のスカラー
(`np.int64` など)は対応する Python の値として変換するので、そのまま `save_invoice` で保存できます。

スキーマにないキーや型に合わない値は `StructuredError`(コード 1)になります。型の不一致は
v1 と同じメッセージです。`schema=paths.tasksupport / "invoice.schema.json"` を渡して
ください。注入される invoice がスキーマを持つのは ExcelInvoice と SmartTable の行タイル
だけです。結果は `save_invoice(invoice, out)` で保存します。表計算の列から値を
埋める場合は、`resolve_custom_key(schema, label)` が `label.ja` または `label.en` が
一致するキーを返します(`lang="ja"` / `"en"` で言語を限定できます)。該当しないラベルや
2 つの項目に共通するラベルは `StructuredError` になります。

<!-- test: ga603-custom-fields -->
```python
from rdetoolkit.nodes import resolve_custom_key, set_custom_fields
from rdetoolkit.types import InvoiceData

schema = {"properties": {"custom": {"properties": {
    "measured_date": {"type": "string", "format": "date", "label": {"ja": "測定日", "en": "Measured date"}},
    "cycles": {"type": "integer", "label": {"ja": "サイクル数", "en": "Cycles"}},
}}}}
invoice = InvoiceData(raw={"custom": {"measured_date": None, "cycles": None}}, schema=schema)
row = {"測定日": "2023/07/19", "Cycles": "12"}
updates = {resolve_custom_key(schema, label): value for label, value in row.items()}
invoice = set_custom_fields(invoice, updates)
assert invoice.raw["custom"] == {"measured_date": "2023-07-19", "cycles": 12}
```

ファイル・画像の保存では、`read_excel` にシート・ヘッダー・行・列の選択を、
`save_csv` に数値書式・ヘッダー・index の指定を渡せます。`save_csv` の `preamble=` には
表の前に書く `#title` / `#legend` などのヘッダー行(フィールド数は行ごとに異なってよく、
表と同じ CSV 形式で書かれます)か、そのまま書く文字列を渡せ、
`blank_line_after_preamble=True` でヘッダー行と表の間に空行を 1 行入れます。`save_json` と `save_text` は
出力先の `kind` を選べます。文字コードを検出する `read_json`、タイルの invoice を
所定の書式で保存する `save_invoice`、利用者が作った Figure を保存する `save_figure`
も利用できます。`plot_lines` は x/y 列または列ペア、ラベル・タイトル・軸スケール・
凡例・サイズ・DPI・出力先を指定できます。
列ペアは `(x, y, label)` でも指定でき、`labels=` で全系列の凡例名を指定することもできます。
`grid=True` でグリッドを描き、軸ラベルの文字サイズは `label_fontsize` を指定しない限り
matplotlib の rcParams に従います。2 つの描画ノードは既定で tight な bounding box で保存します。
v1 の `fig.savefig(path)` と同じ画像には `bbox_inches=None` を、
`savefig(path, bbox_inches="tight", pad_inches=0)` と同じ画像には `pad_inches=0` を指定してください。
セルの塗りつぶし色で行を選ぶテンプレートでは、`read_excel` と同じシート・行指定で
`read_excel_fills(path, column="A", ...)` を呼ぶと、データフレームの各行に対応する
塗りつぶし色（ARGB 16 進文字列、`theme:<n>`、または `None`）を返します。
`OutputContext` には v1 の `resource_paths.temp` に当たる一時ディレクトリはありません。
作業用ファイルには `tempfile.TemporaryDirectory()` を使ってください（ブロック終了時に削除されます）。

`unzip_inputs` は展開したファイルの絶対パスをアーカイブ順で返します。
ディレクトリエントリーと危険な展開先は含めず、重複メンバーは重複したパスを返します。
外向きシンボリックリンクを含む展開先の境界チェックは維持します。
戻り値を使用していなかった呼び出し方も継続できます。
アーカイブ構造を列挙する場合は `include_dirs=True` で空ディレクトリを含むディレクトリエントリーも返します。

### main.py で設定を読み込み、モードを上書きする

flow 入口の設定を事前に用意する場合は、`rdetoolkit.runner.load_run_config(root=None, *, overrides=None)`
を使います。`root` はプロジェクトルートまたは data ルートで、`Path` と文字列を受け付けます。
省略時はカレントディレクトリです。Runner と同じ data ルート解決・設定探索を使い、
プロジェクト直下の `rdeconfig.yaml`、`pyproject.toml`、解決した data ルートの
`tasksupport/{rdeconfig.yaml,rdeconfig.yml,pyproject.toml}` の順に探索します。
tasksupport の設定は v1 形式として解釈します（Design §6.3）。

`overrides` は発見した設定へ再帰的にマージします。戻り値の `RdeConfig` を
`run(flow=..., config=...)` に渡すと、そのオブジェクト全体を設定として使います。
マッピングを直接渡す場合も、発見した設定に対する上書きになります。
以下の例は tasksupport の他の値を保ったままモードを変更します。

<!-- test: load-run-config -->
```python
from rdetoolkit import flow, workflows
from rdetoolkit.runner import load_run_config
from rdetoolkit.types import RdeConfig


@flow
def pipeline(config: RdeConfig) -> None:
    print(config.system.extended_mode)


config = load_run_config(overrides={"system": {"extended_mode": "MultiDataTile"}})
report = workflows.run(flow=pipeline, config=config)
if report.status != "success":
    raise SystemExit(1)
```

`RdeConfig.model_validate({"system": {"extended_mode": None}})` も受理します。
YAML の `null` や上書きの `None` はモード未指定として正規化され、
値は既定の `"invoice"` になります。SmartTable / ExcelInvoice の検出で
W1001 は出ません。文字列で明示したモードと検出結果が競合する場合は、
引き続き W1001 を出します（Design §6.2）。

## 実行時の変更点

本番の `main.py` では、失敗・一部失敗をプロセスの終了コードへ反映する指定を追加してください。
RunReport、失敗時の `job.failed`、完了済み成果物を確定してから、失敗は1、一部失敗は2で終了します。
成功時は通常どおり戻ります。ライブラリからの既定の呼び出しは RunReport を返す契約を維持します。
公開の `report.exit_code` も CLI と同じ値を返すため、`SystemExit` に渡せます。
この値は派生プロパティであり、JSON のフィールドやスキーマバージョンは増やしません。

<!-- test: ga572-main -->
```python
from rdetoolkit import workflows
from processing import pipeline

workflows.run(flow=pipeline, exit_on_failure=True)
```

テンプレート探索では、`--module` を省略するとルートの Python モジュールと
`modules/` パッケージ内の骨格宣言を読み込みます。インストール済みプラグインも探索します。
別の場所の提供モジュールは `--module` で指定してください。
説明には slot のドキュメントとドメイン型を含め、標準ライブラリ型を除外します。
テンプレート用 init は `main.py`・実装・テスト雛形を生成し、3ファイルすべてを上書きから保護します。
slot の引数名と種類を含むシグネチャの一致、深さ2までの継承、flow 境界での DI は維持します。
公開済み骨格には任意 hook を追加して拡張し、必須 slot を追加する場合は具象実装も更新してください。

`migrate apply` は、未対応の別モジュール参照とヘルパーファイルを変更せず、
手動移行が必要なコールバックを報告します。そのコールバックと入口を一緒に移行してください。
変換可能なローカル関数ではコメントと文字列を保持し、旧入口を削除したことと
変換後の flow を CLI で実行する方法を明示します。

- flow デコレータの `error_code=7, error_message="Cannot process input"` で、本体の例外を
  両 v2 入口から同じコード・メッセージにまとめられます。コードだけなら元の
  メッセージを保ち、メッセージだけならコードは 3001 です。メッセージには例外の文字列
  `{error}` と例外クラス名 `{error_type}` を埋め込めます（例:
  `error_message="Cannot read sample: {error}"`）。それ以外の波括弧はそのまま残ります。
  本体で送出した
  `StructuredError` は v1 の `catch_exception_with_message` と同じく、そのコードと
  メッセージを保ちます。直接の関数呼び出しでは
  元の例外がそのまま送出されます。Runner では元の例外をチェーンに残し、
  `KeyboardInterrupt`・`SystemExit` などのプロセス制御例外は変換しません。
- **v1 の `catch_exception_with_message` を flow に書き換えるときは `error_code=1` を明示してください。**
  v1 のデコレータは素の例外を `ecode=1`、メッセージ先頭に `Error: ` を付けた
  `StructuredError` に変換します。flow の `error_message` だけを移すとコードは 3001 になり、
  `job.failed` の `ErrorCode` が 1 から変わります。v1 と同じ結果にする対応は次のとおりです。

  | v1 の `catch_exception_with_message` の引数 | flow デコレータの引数 |
  |---|---|
  | `error_message="m"` | `error_code=1, error_message="Error: m"` |
  | なし | `error_code=1, error_message="Error: {error}"` |
  | `error_code=c, error_message="m"` | `error_code=c, error_message="Error: m"` |

  `Error: ` 接頭辞が不要なら `error_code=1, error_message="m"`、
  引数なしの場合は `error_code=1` だけで構いません(コードは同じで、メッセージは
  それぞれ `m`、例外の文字列になります)。
- flow に注入される `InputPaths` は v1 と同じく作業ディレクトリからの相対パスです。
  入力パスを含むユーザーのエラーメッセージも v1 と同じ表記になります。
  Runner 内部では、開始時に一度確定した data root を引き続き使います。
- v2 の正準戻り値は `RunReport` です。`report.status` と
  `report.iterations` を起点に結果を処理してください。
- **flow 入口では `on_iteration_error` の既定値が `continue` です。** v1 の
  即時停止(fail-fast)が必要なら設定で `fail_fast` を明示してください。
  `run(custom_dataset_function=...)` の v1 入口は v1 の反復規則を保ちます
  (後述の「意図的な差分」を参照)。
- グラフは実行前 DAG ではなく、実行後の call sequence です。通常の Python
  制御構文をそのまま使えます。
- MultiDataTile のタイル(`data/`、`divided/0001`、…)は、v1 の MultiDataTile と
  同じくファイル名順に割り当てられます。v1 の構造化処理が
  `for f in inputdata.glob("*")` のように自前で `inputdata` を列挙してタイルを
  作っていた場合は、ディレクトリの列挙順になっていました。同じ順序が必要なら
  `multidata_tile.order: filesystem` を設定してください(既定は `name`)。
  列挙順はファイルシステムに依存します(#597)。

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

ヘッダーだけでデータ行がない Excel invoice はタイル実行前に検出します。
互換コールバック入口では v1 の汎用エラー（999）を保ち、flow 入口では
入力検証エラー `EmptyExcelInvoice`（4004）とデータ行を追加する案内を返します。
invoice シート自体がないブックについては既存のエラー契約を維持します。

| ケース | v1 | v2 |
|---|---|---|
| コールバックが `StructuredError(msg, ecode)` を送出 | `job.failed` に `ecode` と `msg` | 同じ |
| コールバックが素の例外を送出 | `ErrorCode=999`、`Unexpected error in <mode> mode: ...` | `ErrorCode=3001`。メッセージはエラーカタログ E3001 の文で、ユーザーの例外メッセージを含みます |
| コールバック失敗時の stderr トレースバック(`traceback:` 設定 / `TRACE_*`) | `errors.handle_exception` が `Config.traceback`、なければ `TRACE_*`、なければ python 形式で `compact` / `python` / `duplex` を出力 | v1 コールバック入口では同じフォーマッタ・同じ設定・同じ優先順で出力し、設定は警告を出しません。素の例外では、最外の例外が `StructuredError: Unexpected error in <mode> mode: ...` ではなく E3001 メッセージの `TileExecutionError`(ユーザーの例外から連鎖)になります。`run()` 自体を `except` ブロックの中から呼んだ場合も、例外の連鎖は Python が記録したとおりに表示します(1.7.1 はこの場合にコールバック自身の暗黙の連鎖を失っていました)。コールバック外の失敗(設定、invoice 検証、出力の検証など)でも、`job.failed` が報告するエラーのトレースバックを同じ形式で出力します。flow 入口(`run(flow=...)`、`rdetoolkit run --flow`)はこのトレースバックを出さず、プロジェクト直下の v2 形式 `rdeconfig.yaml` では `traceback:` はエラー(E1002)です |
| `invoice.schema.json` 自体が不正で、コールバックも失敗 | コールバック側のエラーコード(検証はコールバックの後) | `ErrorCode=4001`(スキーマ検証の理由付き)。コールバックは呼ばれません |
| invoice がスキーマに違反 | モードごとに異なるコード、一部モードではコールバック実行済み・出力も生成済み | `ErrorCode=4001`。コールバックは呼ばれず、タイルの成果物は作られません(`job.failed`・ログ・run report は残ります) |
| 設定ファイルの探索(`config=None`) | `data/tasksupport` から読み込み | 同じ。不正な設定ファイルは v1 と同じく `ErrorCode=999` |
| `rdesys_<タイムスタンプ>.log` の場所 | `data/logs` | 標準構成では同じ |
| 実行中の SIGTERM | プロセスが終了するだけで `job.failed` も記録も残らない | `job.failed` に `ErrorCode=3004`(`RunInterrupted`)、`RunReport` も書き出し、完了済みタイルの成果物は残ります。公開入口の終了コードは 1 |
| `rdetoolkit run` CLI の終了コード | v1 に `run` コマンドはなし | `0` 成功 / `1` 失敗 / `2` 一部失敗 / `3` 使い方の誤り。Python の v1 コールバック入口は失敗で `SystemExit(1)` を維持。flow 入口は `exit_on_failure=True` で失敗1・一部失敗2を反映し、同じ値を `RunReport.exit_code` でも公開 |
| `multidata_tile.ignore_errors: true` で全タイルが失敗 | MultiDataTile のみ全件 `failed` の JSON を返し終了コード 0。他モードではフラグは無視され最初の失敗で停止 | v1 コールバック入口は全モードで v1 と同じ。flow 入口では全タイル失敗は `failed` となり `job.failed` を書きます |
| `rde2util.Meta.assign_vals` が値 `None` を受け取る(#570) | `None` を文字列 `"None"` として変換します。`number` / `integer` / `boolean` の項目は `StructuredError`(`ERROR: failed to cast metaDef value` など)。コールバックが捕捉しなければ `job.failed` に `ErrorCode=1` となり、`metadata.json` など以降の出力は作られません。`string` の項目は値 `"None"`、`$` 参照の単位は `"unit": "None"` として書き出されます | そのキーは代入されず、`metadata.json` はそのキー(参照単位なら `unit`)を含めずに書き出されます。コールバックの他の出力もそのまま作られます。`None` 以外の変換できない値は従来どおり `ErrorCode=1` |
| `invoice.custom` の値の変換: v1 の `castval` / `_assign_invoice_val` と v2 の `set_custom_fields`(#603) | format が `uri` / `uuid` / `markdown` の `string` 項目も日付として解釈しようとして失敗します。解釈できない日付や日付 format への文字列以外の値は dateutil の `ValueError` / `TypeError` になります。`boolean` 項目の `None` は `False`、`integer` / `number` 項目の `None` は失敗します。スキーマにないキーは `KeyError`。`3.0` のような整数値の float は `integer` で失敗します | `date` / `date-time` / `time` 以外の format は値をそのまま保持します。不一致はすべて v1 と同じメッセージの `StructuredError`(コード 1)で、原因の例外を連鎖します。`None`・NaN・`NaT`・`pd.NA`(NumPy の NaN / NaT を含む)はすべての型で `None` として格納し、NumPy のスカラーは Python の値として変換します。スキーマにないキーは `StructuredError`(コード 1)。`3.0` は `3` になり、`date` / `datetime` オブジェクトも受け付けます。v1 の関数自体は変更していません |
| コールバックや flow が処理中に run 単位の invoice(`paths.invoice_org`。MultiDataTile / ExcelInvoice / RDEformat では `temp/invoice_org.json`)へ書き込む(#603) | 後続タイルは書き換え後のファイルから作られるため、前のタイルが書いた値がタイル順に依存して後続へ引き継がれました | サポートしません。`paths.invoice_org` は読み取り専用の入力です。Runner は各タイルの invoice を登録時の invoice から作り(ExcelInvoice と SmartTable はその行を上書き)、タイル固有の値は flow が `save_invoice` で上書きします。各タイルは登録時の状態から始まります。`invoice_org` への書き込みが後続タイルに届くかどうかは v2 では定めていません |

`Meta.assign_vals` の行は Tier 1 API の不具合修正です。そのため v1 コールバック入口にも
適用されます。この不具合は 1.7 系にもありますが、修正を含む 1.7.x はまだリリース
されていません。表の v1 列は最新の v1 リリース 1.7.1 の挙動で、1.7.1 に
ロールバックすると旧挙動に戻ります。今後 1.7.x に同じ修正が入った場合は、その版との
比較ではこの行の差分はなくなります。

run 単位の invoice の行について: 登録時の値は各タイルに用意された invoice を使い、
タイル固有の値はそのタイルの flow の中で求めて `save_invoice` で書き出してください。

### ロールバック

v2 で問題が出た場合は、v1 系の最新版 `1.7.1` を固定してください(例:
`requirements.txt` に `rdetoolkit==1.7.1`)。旧経路を含む開発版は PyPI にはなく、
git タグ `v2.0.0a1` からのソースインストールのみ可能です(切り分け用途。この
タグの `__version__` は `2.0.0` と表示されます)。

### スケジュール

`2.0.0rc1` → GA `2.0.1` の順に公開します。版番号 `2.0.0` は欠番で、
正式版としては公開しません。
