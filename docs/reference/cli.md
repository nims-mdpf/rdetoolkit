# CLI リファレンス

rdetoolkit のすべてのコマンドとオプションの一覧です。コマンドは `rdetoolkit` でも
`python -m rdetoolkit` でも実行できます。各コマンドは `--help` で同じ内容を表示します。

v1 から引き継いだコマンド(`init`・`gen-invoice` など)の使い方の詳細は
[コマンドライン操作](../usage/cli.md) を、`csv2graph` は [csvをグラフ化する](../usage/structured_process/csv2graph.md)
を参照してください。

## 終了コード

v2 のコマンド(`run`・`nodes`・`flows`・`templates`・`formats`・`graph`・`report`・`repro`・`migrate`)は
共通の終了コードを使います(`validate` は独自の終了コードを使います。後述)。

| コード | 意味 |
|--------|------|
| 0 | 成功(`run` では `success`) |
| 1 | 実行の失敗(`run` では `failed`) |
| 2 | 一部のデータタイルだけが失敗(`run` では `partial`) |
| 3 | 使い方の誤り(引数の不足・矛盾、フローやノードを解決できない、`nodes lint` の違反を含む) |

`run` の終了コードは `job.failed` に書くエラーコードとは独立しています。

## 構造化処理の実行

### `rdetoolkit run`

構造化処理を実行します。v1 のコールバック関数(`TARGET`)か、v2 のフロー(`--flow`)の
**どちらか一方**を指定します。両方を指定した場合や、どちらも指定しない場合は終了コード 3 です。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `TARGET` | — | v1 のコールバック関数。`module_or_file::attr` の形式 |
| `--flow` | — | v2 のフローまたは `ProcessingTemplate` サブクラス。`pkg.mod:attr` の形式 |
| `--validate-only` | 無効 | 設定・モード・事前検証だけを行い、フローを呼ばない |
| `--config` | — | 設定を上書きする YAML ファイル。探索した設定の上に再帰的に適用する |

`--flow` で実行すると、RunReport の JSON を標準出力に書き、`data/logs/run_report_<run_id>.json`
にも保存します。カレントディレクトリは import パスに加えられるため、プロジェクト内の
モジュールをそのまま指定できます。

<!-- illustration: cli-run -->
```bash
$ rdetoolkit run --flow modules.flow:pipeline
$ rdetoolkit run --flow modules.processing:MyProcessing --validate-only
$ rdetoolkit run --flow modules.flow:pipeline --config overrides.yaml
$ rdetoolkit run main.py::dataset
```

## ノード・フロー・テンプレートの検査

`--module` は検査の前に import するモジュールで、複数回指定できます。プロジェクトのノードや
フローを一覧に含めたいときに指定します。

### `rdetoolkit nodes list`

登録されているノードの ID を一覧表示します。組込ノードは常に含まれます。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--json` | 無効 | 機械可読な JSON で出力する |
| `--plugin` | 無効 | プラグインが登録したノードだけを表示する |
| `--module` | — | 一覧の前に import するモジュール(複数指定可) |

### `rdetoolkit nodes describe`

ノードの NodeSpec(引数・戻り値の型、デフォルト値、タグ、バージョン、定義位置)を表示します。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `NODE_ID` | — | ノード ID |
| `--json` | 無効 | 機械可読な JSON で出力する |
| `--module` | — | 表示の前に import するモジュール(複数指定可) |

### `rdetoolkit nodes lint`

ノード・フロー・テンプレートの登録を静的に検査します。型注釈の欠落、不安定なノード ID
(`E2005`)、予約型の重複注釈(`E2006`)、テンプレートの誤用などを報告し、違反があれば
終了コード 3 を返します。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--module` | — | 検査の前に import するモジュール(複数指定可) |

### `rdetoolkit flows list`

登録されているフローの ID を一覧表示します。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--json` | 無効 | 機械可読な JSON で出力する |
| `--module` | — | 一覧の前に import するモジュール(複数指定可) |

### `rdetoolkit flows describe`

フローの登録情報を表示します。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `FLOW_ID` | — | フロー ID |
| `--json` | 無効 | 機械可読な JSON で出力する |
| `--module` | — | 表示の前に import するモジュール(複数指定可) |

### `rdetoolkit templates list`

登録されているテンプレートの骨格クラスを一覧表示します。`--module` を指定しない場合は、
カレントディレクトリの `*.py` と `modules/` 以下から骨格を宣言したモジュールを探し、
インストール済みのプラグインも読み込みます。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--json` | 無効 | 機械可読な JSON で出力する |
| `--module` | — | 一覧の前に import するモジュール(複数指定可) |

### `rdetoolkit templates describe`

テンプレートの slot・hook・ドメイン型を表示します。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `TEMPLATE_ID` | — | テンプレートの ID またはクラス名 |
| `--json` | 無効 | 機械可読な JSON で出力する |
| `--module` | — | 表示の前に import するモジュール(複数指定可) |

### `rdetoolkit formats list`

インストール済みのプラグインが宣言したファイル形式を一覧表示します。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--json` | 無効 | 機械可読な JSON で出力する |

## 実行記録

### `rdetoolkit report show`

RunReport の状態、データタイル数、失敗した呼び出しとエラーを表示します。

| 引数 | 説明 |
|------|------|
| `RUN_REPORT` | `run_report_<run_id>.json` のパス |

### `rdetoolkit graph`

RunReport に記録されたノードの呼び出し順(Call Sequence)を出力します。データフローの図では
ありません。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `RUN_REPORT` | — | `run_report_<run_id>.json` のパス |
| `--format` | `json` | `json`・`mermaid`・`html` のいずれか |

### `rdetoolkit repro export`

RunReport、その run の入力、実際に使われた設定を 1 つの zip にまとめます。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `RUN_REPORT` | — | `run_report_<run_id>.json` のパス |
| `--output` | —(必須) | 出力する zip ファイル |
| `--config` | — | その run で使った上書き YAML(`run --config` と同じ形式) |

設定が RunReport の `config_digest` と一致しない場合は、アーカイブを作らずに終了コード 3 で終わります。

### `rdetoolkit repro import`

`repro export` のアーカイブを、新しいディレクトリの下に展開して入力を再構成します。

| 引数 | 説明 |
|------|------|
| `ARCHIVE_PATH` | `repro export` で作った zip |
| `TARGET` | 展開先のディレクトリ |

## 移行

### `rdetoolkit migrate check`

1 つの Python ファイル、またはディレクトリ以下のすべての Python ファイルから、v1 から
v2 への移行が必要な箇所を報告します。

| 引数 | 既定値 | 説明 |
|------|--------|------|
| `PATH` | カレントディレクトリ | 検査するファイルまたはディレクトリ |

### `rdetoolkit migrate apply`

v1 のコールバックを v2 のフローに変換します。入力ファイルは変更しません。既定では変換結果を
表示するだけで、`--no-dry-run` を指定したときだけ書き出します。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `PATH` | カレントディレクトリ | 変換するファイルまたはディレクトリ |
| `--out` | — | 書き出し先のディレクトリ(入力とは別の場所) |
| `--dry-run` / `--no-dry-run` | `--dry-run` | プレビューだけにするか、書き出すか |

詳しい手順は [v1 から v2 への移行](../migration_v1_to_v2.md) を参照してください。

## プロジェクトの作成と RDE ファイル

### `rdetoolkit init`

構造化処理のプロジェクトの雛形を作ります。オプションなしでは v1 と同じ雛形を作ります。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--processing-template` | — | 登録済みテンプレートの名前。slot を TODO にした利用者クラス・サンプルテスト・`main.py` を作る |
| `--module` | — | テンプレートを提供するモジュール(複数指定可) |
| `--force` | 無効 | `--processing-template` で作るファイルが既にあれば上書きする |
| `--template` | — | 雛形の設定ファイル(`pyproject.toml` / `rdeconfig.yaml`)またはそれを含むディレクトリ |
| `--entry-point` | — | `container/main.py` にコピーするファイル |
| `--modules` | — | `container/modules/` にコピーするファイルまたはディレクトリ |
| `--tasksupport` | — | `tasksupport/` にコピーするファイルまたはディレクトリ |
| `--inputdata` | — | `inputdata/` にコピーするディレクトリ |
| `--other` | — | `container/` にコピーする追加ファイル(複数指定可) |

### `rdetoolkit version`

rdetoolkit のバージョンを表示します。

### `rdetoolkit gen-config`

`rdeconfig.yaml` の雛形を作ります。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `OUTPUT_DIR` | カレントディレクトリ | 出力先のディレクトリ |
| `--template` | `minimal` | 雛形の種類 |
| `--overwrite` | 無効 | 既存の `rdeconfig.yaml` を置き換える |
| `--lang` | `en` | 対話形式の雛形で使う言語 |

### `rdetoolkit gen-invoice`

`invoice.schema.json` から `invoice.json` を作ります。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `SCHEMA_PATH` | — | `invoice.schema.json` のパス |
| `--output` / `-o` | `./invoice.json` | 出力先 |
| `--fill-defaults` / `--no-fill-defaults` | 有効 | 型に応じた既定値を埋める |
| `--required-only` | 無効 | 必須項目だけを出力する |
| `--format` | `pretty` | `pretty` または `compact` |

### `rdetoolkit make-excelinvoice`

`invoice.schema.json` から ExcelInvoice を作ります。

| 引数・オプション | 既定値 | 説明 |
|-----------------|--------|------|
| `INVOICE_SCHEMA_JSON_PATH` | — | `invoice.schema.json` のパス |
| `--output` / `-o` | `./template_excel_invoice.xlsx` | 出力先 |
| `--mode` / `-m` | `file` | 登録モード。`file` または `folder` |

### `rdetoolkit validate invoice-schema`

`invoice.schema.json`(引数 `SCHEMA_PATH`)の構造と内容を検証します。

### `rdetoolkit validate metadata-def`

`metadata-def.json`(引数 `METADATA_DEF_PATH`)の構造を検証します。

### `rdetoolkit validate invoice`

`invoice.json`(引数 `INVOICE_PATH`)を `invoice.schema.json` で検証します。`--schema` / `-s` で
スキーマを指定します(必須)。

### `rdetoolkit validate metadata`

`metadata.json`(引数 `METADATA_PATH`)をメタデータ定義で検証します。`--schema` / `-s` で
定義ファイルを指定します(必須)。

### `rdetoolkit validate all`

プロジェクト内の標準的な RDE ファイルを探してすべて検証します。引数 `PROJECT_DIR` の既定値は
カレントディレクトリです。

`validate` の各サブコマンドは共通して次のオプションを持ちます。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--format` / `-f` | `text` | `text`(人向け)または `json`(機械可読) |
| `--strict` / `--no-strict` | 無効 | 警告も失敗として扱う |
| `--quiet` / `-q` | 無効 | エラーだけを表示する(`text` のみ) |

`validate` の終了コードは v2 のコマンドと異なり、0 = 検証成功、1 = 検証エラー、
2 = 使い方の誤り(引数の誤り・ファイルがない)です。

### `rdetoolkit artifact`

RDE に提出するアーカイブ(zip)を作り、ソースコードの検査結果をレポートとして出力します。

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--source-dir` / `-s` | —(必須) | アーカイブ・検査するディレクトリ |
| `--output-archive` / `-o` | — | 出力する zip ファイル |
| `--exclude` / `-e` | `venv`, `site-packages` | 除外するディレクトリ名 |

### `rdetoolkit csv2graph`

CSV ファイルからグラフを作ります。オプションは [csvをグラフ化する](../usage/structured_process/csv2graph.md)
を参照してください。

### `rdetoolkit agent-guide`

AI コーディングアシスタント向けのガイドを表示します。`--detailed` を付けると、詳細なパターンと
API リファレンスを含む版を表示します。

## シェル補完

`--install-completion` で現在のシェルに補完を設定し、`--show-completion` で補完スクリプトを
表示します。
