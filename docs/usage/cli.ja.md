# コマンドライン機能について

## 概要

RDEToolKitは、RDE構造化処理の開発ワークフロー全体を支援するコマンドラインインターフェースを提供します。プロジェクトの作成、設定ファイルやインボイスの生成、検証、構造化処理の実行、実行結果の確認、提出用アーカイブの作成までをサポートします。

コマンドは `rdetoolkit <名詞> <動詞>` の形式です(例: `rdetoolkit new config`、`rdetoolkit report show`)。典型的なプロジェクトでは `init` → `new config` → `validate all` → `run` → `package` の順に実行します。

!!! tip "各コマンドのヘルプ"
    すべてのコマンドの `--help` に、入力、出力と副作用、使用例、終了コードが記載されています。`rdetoolkit --help` でグループ化されたコマンド一覧を、`rdetoolkit <コマンド> --help`(例: `rdetoolkit new config --help`)で個々のコマンドの詳細を確認できます。このページは概要であり、インストールしているバージョンの正確な仕様は `--help` を参照してください。

## 前提条件

- Python 3.10以上
- rdetoolkitパッケージのインストール

## コマンド一覧

`rdetoolkit --help` はコマンドを次のパネルに分けて表示します。

| パネル | コマンド | 用途 |
| ------ | -------- | ---- |
| Scaffold | `init` | プロジェクトの雛形を作成 |
| Generate | `new config`、`new invoice`、`new excelinvoice`、`new processing`、`plot` | プロジェクトファイルやグラフを生成 |
| Validate | `validate invoice`、`validate invoice-schema`、`validate metadata`、`validate metadata-def`、`validate all` | RDEのスキーマとデータファイルを検証 |
| Run | `run` | 構造化処理を実行(v2 flow、または `--legacy` で v1 のデータセット関数) |
| Inspect | `report show`、`report trace`、`nodes list/show/lint`、`flows list/show`、`skeletons list/show`、`formats list` | 実行レポートの確認と登録済みコンポーネントの一覧 |
| Package | `package`、`repro export`、`repro import` | 提出用アーカイブの作成、実行の書き出しと再取り込み |
| Migrate | `migrate check`、`migrate apply` | v2 移行が必要な v1 コードと CLI 呼び出しの検出・変換 |
| Info | `agent-guide`、`version` | AIエージェントガイドとインストール済みバージョンの表示 |
| Deprecated (removed in v2.1) | v1 のコマンド名 | 警告を表示する別名として残っています。[v2.0 でのコマンド名の変更](#renamed-commands)を参照してください |

## 利用可能なコマンド

### init: スタートアッププロジェクトの作成

カレントディレクトリにRDE構造化処理のスタートアッププロジェクトを作成します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit init [PATHオプション]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit init [PATHオプション]
    ```

以下のディレクトリとファイル群が生成されます。

```shell
container
├── data
│   ├── inputdata
│   ├── invoice
│   │   └── invoice.json
│   └── tasksupport
│       ├── invoice.schema.json
│       └── metadata-def.json
├── main.py
├── modules
├── requirements.txt
└── Dockerfile
```

`container/` と同じ階層に `input/`(`inputdata/`、`invoice/invoice.json`)と `template/tasksupport/` も作成されます。

各ファイルの説明は以下の通りです。

- **requirements.txt**: 構造化プログラム構築で使用したいPythonパッケージを追加してください。必要に応じて`pip install`を実行してください。
- **modules**: 構造化処理で使用したいプログラムを格納してください。
- **main.py**: 構造化プログラムの起動処理を定義
- **data/inputdata**: 構造化処理対象データファイルを配置してください。
- **data/invoice**: ローカル実行させるためには空ファイルでも必要になります。
- **data/tasksupport**: 構造化処理の補助するファイル群を配置してください。

!!! tip "ファイル上書きについて"
    すでに存在するファイルは残されます(`Skip: ... already exists.` と表示)。上書きはされません。

!!! note "スケルトンから処理コードを生成する"
    登録済みの処理スケルトンから `processing.py`、`main.py`、サンプルテストを生成するには [`new processing`](#new-processing) を使用します。

#### テンプレートを用いた初期化

`--template <path>` を付けると独自のスタータープロジェクトを流用できます。指定できるのは以下のいずれかです。

- `pyproject.toml` または `rdeconfig.yaml` / `rdeconfig.yml` そのもの
- 上記ファイルが格納されたディレクトリ（`--template .` ならカレントディレクトリ内の `pyproject.toml` を優先）

設定ファイルには `[tool.rdetoolkit.init]`（pyproject）または `init`（rdeconfig）セクションを追加し、コピー元を記述します。

```toml
[tool.rdetoolkit.init]
entry_point = "tpl/main.py"
modules = "tpl/modules"
tasksupport = "tpl/tasksupport"
inputdata = "tpl/inputdata"
```

キーの意味:

- `entry_point`: `container/main.py` としてコピーされるファイル。
- `modules`: `container/modules/` 配下に展開されるファイルまたはディレクトリ。
- `tasksupport`: `container/data/tasksupport/` と `template/tasksupport/` の両方へ複製されるファイル/ディレクトリ。
- `inputdata`: `container/data/inputdata/` と `input/inputdata/` に展開されるディレクトリ。

相対パスは設定ファイルが置かれたディレクトリから解決されるため、テンプレート用リポジトリを別環境でも共有できます。

#### PATHオプションで直接コピー元を指定する

設定ファイルにパスを書きたくない場合は、`--template` なしで次のPATHオプションを渡せます（複数併用可）。指定したパスは初期化に使われ、存在する `pyproject.toml` / `rdeconfig.yaml(yml)` があれば上書き追記されます（無ければ `pyproject.toml` を新規作成）。

| オプション        | 役割・コピー先                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------- |
| `--entry-point`   | `container/main.py` としてコピー（ファイル限定）                                            |
| `--modules`       | `container/modules/` 以下にコピー（ファイル/ディレクトリ対応）                              |
| `--tasksupport`   | `container/data/tasksupport/` と `template/tasksupport/` の両方にコピー（ファイル/ディレクトリ対応） |
| `--inputdata`     | `container/data/inputdata/` と `input/inputdata/` にコピー（ディレクトリ推奨）              |
| `--other` (複数可) | `container/` 以下に任意のファイル/ディレクトリをコピー                                      |

相対パスはカレントディレクトリ基準で保存されます。CLIオプションで渡したパスが設定ファイルより優先されます。

##### CLI出力例（PATHオプション使用時）

以下のように `tpl/` 配下にテンプレートを置き、PATHオプションを付けて実行した場合の出力例です。

```shell
python3 -m rdetoolkit init \
  --entry-point tpl/custom_main.py \
  --modules tpl/modules \
  --tasksupport tpl/tasksupport \
  --inputdata tpl/inputdata \
  --other tpl/extra.txt --other tpl/extras
```

出力（パスは実行環境に依存します）:

```
Ready to develop a structured program for RDE.
Created from template: /private/tmp/rdt-init-check/container/main.py
Created: /private/tmp/rdt-init-check/container/requirements.txt
Created: /private/tmp/rdt-init-check/container/Dockerfile
Populated /private/tmp/rdt-init-check/container/modules from template directory: /private/tmp/rdt-init-check/tpl/modules
Created: /private/tmp/rdt-init-check/container/data/invoice/invoice.json
Populated /private/tmp/rdt-init-check/container/data/tasksupport from template directory: /private/tmp/rdt-init-check/tpl/tasksupport
Populated /private/tmp/rdt-init-check/template/tasksupport from template directory: /private/tmp/rdt-init-check/tpl/tasksupport
Populated /private/tmp/rdt-init-check/container/data/inputdata from template directory: /private/tmp/rdt-init-check/tpl/inputdata
Populated /private/tmp/rdt-init-check/input/inputdata from template directory: /private/tmp/rdt-init-check/tpl/inputdata
Copied template file /private/tmp/rdt-init-check/tpl/extra.txt into /private/tmp/rdt-init-check/container
Populated /private/tmp/rdt-init-check/container/extras from template directory: /private/tmp/rdt-init-check/tpl/extras
Created: /private/tmp/rdt-init-check/input/invoice/invoice.json
```

処理後、`pyproject.toml`（または既存の`rdeconfig.yaml`）に `[tool.rdetoolkit.init]` が追記され、渡したパスが相対パスで保存されます。

### new config: rdeconfig.yamlの生成 { #new-config }

用意されているプリセット、または対話形式の質問に基づいて`rdeconfig.yaml`を生成します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new config [-o <出力ディレクトリ>] [--preset <preset>] [--force] [--lang <en|ja>]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new config [-o <出力ディレクトリ>] [--preset <preset>] [--force] [--lang <en|ja>]
    ```

利用できるプリセットは以下の通りです。

- `minimal`（デフォルト）: システム設定とトレースバック設定のみを含む最小構成。
- `full`: `multidata_tile`設定を含む完全なテンプレート。
- `multitile`: `extended_mode: "MultiDataTile"`を有効化したテンプレート。
- `rdeformat`: `extended_mode: "rdeformat"`を有効化したテンプレート。
- `smarttable`: SmartTable設定を追加し、`save_table_file: false`を設定。
- `interactive`: 対話形式で各設定項目を確認。`--lang ja`で日本語プロンプトに切り替え可能。

#### オプション

| オプション       | 説明                                                                                                  | 必須 |
| ---------------- | ----------------------------------------------------------------------------------------------------- | ---- |
| -o(--output)     | `rdeconfig.yaml`を出力するディレクトリ。省略時はカレントディレクトリ。存在しなければ作成されます。    | -    |
| --preset         | プリセット名（`minimal`, `full`, `multitile`, `rdeformat`, `smarttable`, `interactive`）。デフォルト: `minimal` | -    |
| --force          | 既存の`rdeconfig.yaml`がある場合に確認なしで置き換えます。未指定なら既存時のみ確認を表示します。     | -    |
| --lang           | プロンプトの言語（`en` または `ja`）。`--preset interactive`選択時のみ利用できます。デフォルト: `en`  | -    |

#### 使用例

```bash title="カレントディレクトリにデフォルト(minimal)プリセットで生成"
python3 -m rdetoolkit new config
```

```bash title="MultiDataTileプリセットをtasksupportディレクトリに生成"
python3 -m rdetoolkit new config --preset multitile -o container/data/tasksupport
```

```bash title="日本語の対話形式で生成し、既存ファイルを置き換え"
python3 -m rdetoolkit new config --preset interactive --lang ja --force
```

!!! tip "インタラクティブモード"
    `--preset interactive`を指定すると、システム設定、MultiDataTile設定、SmartTable設定、トレースバック設定について
    対話形式で質問されます。回答は`rdeconfig.yaml`に反映され、プロジェクト開始時から整合した初期値を共有できます。

終了コード: `0` 成功、`1` 書き込みの失敗または上書きを拒否した場合、`2` コマンドラインが不正。

### new invoice: invoice.jsonの生成

`invoice.schema.json`から`invoice.json`を自動生成します。スキーマ定義に基づいてデフォルト値を設定し、生成後に自動検証を行います。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new invoice <invoice.schema.json path> [OPTIONS]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new invoice <invoice.schema.json path> [OPTIONS]
    ```

#### オプション

| オプション | 説明 | 必須 |
| ---------- | ---- | ---- |
| -o(--output) | 出力ファイルパス。省略時はカレントディレクトリに`invoice.json`を作成。親ディレクトリは作成され、既存ファイルは上書きされます | - |
| --fill-defaults/--no-fill-defaults | デフォルト値を埋めるかどうか（デフォルト: 有効） | - |
| --required-only | 必須フィールドのみを含める | - |
| --format | 出力フォーマット（`pretty`または`compact`）。デフォルト: `pretty` | - |

#### 使用例

```bash title="基本的な使用"
python3 -m rdetoolkit new invoice tasksupport/invoice.schema.json
```

```bash title="出力先を指定"
python3 -m rdetoolkit new invoice tasksupport/invoice.schema.json -o container/data/invoice/invoice.json
```

```bash title="必須フィールドのみ、コンパクトフォーマット"
python3 -m rdetoolkit new invoice tasksupport/invoice.schema.json --required-only --format compact
```

#### デフォルト値の優先順位

1. スキーマの`default`フィールド
2. スキーマの`examples`配列の最初の値
3. 型ベースのデフォルト値: string→`""`、number→`0.0`、integer→`0`、boolean→`false`

!!! tip "詳細なAPIドキュメント"
    プログラムからの使用方法については、[Invoice Generator API](../rdetoolkit/cmd/gen_invoice.md)を参照してください。

終了コード: `0` 成功、`1` スキーマを読めない、またはインボイスを書き込めない場合、`2` コマンドラインが不正。

### new excelinvoice: ExcelInvoiceの生成

`invoice.schema.json`からExcelインボイス(`*_excel_invoice.xlsx`)を生成します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

#### オプション

| オプション   | 説明                                                                                     | 必須 |
| ------------ | ---------------------------------------------------------------------------------------- | ---- |
| -o(--output) | 出力ファイルパス。ファイル名の末尾は`_excel_invoice.xlsx`にすること。既存ファイルは上書きされます。 | -    |
| -m(--mode)   | 登録モードの選択。ファイルモード`file`（デフォルト、1ファイル1行）かフォルダモード`folder`（1フォルダ1行）を選択可能。 | -    |

!!! tip "デフォルト出力"
    `-o`を指定しない場合は、`template_excel_invoice.xlsx`というファイル名で、実行ディレクトリ配下に作成されます。

終了コード: `0` 成功、`1` スキーマが不正、ファイル名が誤っている、または書き込みに失敗した場合、`2` コマンドラインが不正。

### new processing: スケルトンから処理コードを生成 { #new-processing }

登録済みの処理スケルトン(`ProcessingTemplate` のサブクラス)から `processing.py`、`main.py`、サンプルテスト(`tests/test_processing.py`)を生成します。生成された TODO slot を実装したら、[`run`](#run) で実行します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new processing <skeleton> [--module <module>] [-o <出力ディレクトリ>] [--force]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new processing <skeleton> [--module <module>] [-o <出力ディレクトリ>] [--force]
    ```

| オプション / 引数 | 説明 | 必須 |
| ----------------- | ---- | ---- |
| SKELETON | `rdetoolkit skeletons list` が表示するスケルトン id、または一意に決まるクラス名 | ○ |
| --module | 検索前にスケルトンを宣言したモジュールを import します(複数指定可)。省略時はカレントディレクトリの `*.py`、その `modules/` パッケージ、インストール済みプラグインから探します | - |
| -o(--output) | 生成ファイルの出力先ディレクトリ。デフォルト: カレントディレクトリ | - |
| --force | 既存の生成ファイルを上書きします。未指定でいずれかが存在する場合は拒否します(終了コード `3`) | - |

```bash title="modules/skeletons.py で宣言したスケルトンからコードを生成"
python3 -m rdetoolkit new processing XrdTemplate --module modules.skeletons
```

終了コード: `0` 成功、`2` コマンドラインが不正、`3` 未知のスケルトン、モジュールの import 失敗、または出力ファイルが既に存在する場合。

### validate: RDEファイルの検証

CI/CD統合のための標準化された終了コードを使用して、RDE関連ファイルを検証します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit validate <サブコマンド> [OPTIONS]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit validate <サブコマンド> [OPTIONS]
    ```

#### 利用可能なサブコマンド

| サブコマンド | 説明 |
|------------|-------------|
| `invoice-schema` | インボイススキーマJSONの構造を検証 |
| `metadata-def` | メタデータ定義JSONの構造を検証 |
| `invoice` | invoice.jsonをスキーマに対して検証 |
| `metadata` | metadata.jsonをmetadata-def.jsonに対して検証 |
| `all` | プロジェクト内のすべての標準RDEファイルを検出して検証 |

#### 終了コード

すべてのvalidateサブコマンドは標準化された終了コードを返します：

| 終了コード | ステータス | 説明 |
|-----------|--------|-------------|
| 0 | 成功 | すべてのバリデーションが成功 |
| 1 | バリデーション失敗 | データまたはスキーマのエラーが見つかった(`--strict` 指定時は警告も含む) |
| 2 | 使用エラー | 無効な引数またはファイル不足 |

#### 使用例

```bash title="インボイススキーマの検証"
python3 -m rdetoolkit validate invoice-schema tasksupport/invoice.schema.json
```

```bash title="プロジェクト内のすべてのファイルを検証"
python3 -m rdetoolkit validate all ./rde-project
```

```bash title="CI/CD統合の例"
python3 -m rdetoolkit validate all ./rde-project
if [ $? -ne 0 ]; then
    echo "バリデーション失敗"
    exit 1
fi
```

!!! tip "詳細なドキュメント"
    CI/CD統合例を含む包括的なバリデーションドキュメントについては、[バリデーション機能](validation.ja.md)を参照してください。

### run: 構造化処理の実行 { #run }

プロジェクトのルートで構造化処理を実行します。Runner は `data/inputdata`、`data/invoice`、`data/tasksupport` を読み、`rdeconfig.yaml` を探して、すべてのタイルを処理します。

=== "Unix/macOS"

    ```shell
    # v2 flow(flow 関数または ProcessingTemplate のサブクラス)
    python3 -m rdetoolkit run <pkg.mod:callable> [--config <overrides.yaml>] [--validate-only]
    # v1 のデータセット関数 def f(srcpaths, resource_paths)
    python3 -m rdetoolkit run --legacy <module_or_file::attr>
    ```

=== "Windows"

    ```powershell
    # v2 flow(flow 関数または ProcessingTemplate のサブクラス)
    py -m rdetoolkit run <pkg.mod:callable> [--config <overrides.yaml>] [--validate-only]
    # v1 のデータセット関数 def f(srcpaths, resource_paths)
    py -m rdetoolkit run --legacy <module_or_file::attr>
    ```

| オプション / 引数 | 説明 |
| ----------------- | ---- |
| REF | v2 flow を指す `pkg.mod:callable`(カレントディレクトリは import 可能)、または `--legacy` 付きの `module_or_file::attr` |
| --legacy | v1 のデータセット関数(`workflows.run(custom_dataset_function=...)` に渡していた関数)を実行 |
| --config | 検出した `rdeconfig.yaml` に重ねる YAML の上書き設定(v2 flow のみ) |
| --validate-only | flow を呼ばずに設定、モード、インボイスだけを検証(v2 flow のみ)。ExcelInvoice / SmartTable モードでは行がインボイスを補うため、インボイスのファイルとスキーマだけを検証します。出力は書き込みません |

出力: `data/` 配下の RDE 出力ツリー(`structured/`、`meta/`、`raw/`、画像、`logs/`、失敗時は `job.failed`)。v2 の実行は実行レポートの JSON を表示し、`data/logs/run_report_<run_id>.json` として保存します。v1 の実行は従来のステータス JSON を表示します。

```bash title="v2 flow を実行"
python3 -m rdetoolkit run modules.processing:pipeline
```

```bash title="v1 のデータセット関数を実行"
python3 -m rdetoolkit run --legacy main.py::dataset
```

!!! note "--legacy なしの v1 形式"
    v2.0.x では、`--legacy` を付けない `module_or_file::attr` 形式の参照も v1 のデータセット関数として実行されます(出力を変えないため警告も出ません)。v2.1 からは `--legacy` が必須になるため、今のうちに付けてください。

| 終了コード | 説明 |
|-----------|------|
| 0 | すべてのタイルが成功(または `--validate-only` の検証が成功) |
| 1 | 実行が失敗(または検証が失敗) |
| 2 | 部分成功: 一部のタイルが失敗(未知のオプションなどパーサーのエラーでも使用) |
| 3 | REF が不正、flow を解決できない、`--config` を読めない、または `--legacy` に適用できないオプションを指定 |

### report show / report trace: 実行レポートの確認

`rdetoolkit run` が `data/logs/` に書き出す実行レポート(`run_report_<run_id>.json`)を読みます。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit report show <run_report.json>
    python3 -m rdetoolkit report trace <run_report.json> [--format json|mermaid|html]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit report show <run_report.json>
    py -m rdetoolkit report trace <run_report.json> [--format json|mermaid|html]
    ```

- `report show` は run id、ステータス、反復回数、失敗した node 呼び出しごとの `failed` 行、設定されていればエラーメッセージを表示します。
- `report trace` はレポートに記録された Call Sequence(実行順の node 呼び出し一覧。call id、親 flow、ステータス、引数のプレビュー)を描画します。これは呼び出しログであり、データの依存関係は描きません。`--format` で `json`(デフォルト)、`mermaid`(シーケンス図)、`html`(単体の HTML ページ)を選びます。結果は標準出力に出るので、ファイルに保存する場合はリダイレクトしてください。

```bash title="Call Sequence を HTML ページとして保存"
python3 -m rdetoolkit report trace data/logs/run_report_<id>.json --format html > trace.html
```

終了コード: `0` 成功、`2` コマンドラインが不正、`3` レポートファイルが存在しないか不正(`report trace` では未知の `--format` も含む)。

### plot: CSVからグラフを描画

CSVファイルからグラフ(PNG、必要に応じてインタラクティブな HTML)を描画します。オプションは Python の `csv2graph()` API と同じです。すべてのオプションは[csvをグラフ化する](structured_process/csv2graph.ja.md)と[サンプル集](structured_process/csv2graph_samples.ja.md)を参照してください。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit plot <csv path> [OPTIONS]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit plot <csv path> [OPTIONS]
    ```

```bash title="重ね描きと系列ごとの PNG を data/other_image に出力"
python3 -m rdetoolkit plot sample.csv -o data/other_image --title 'XRD pattern'
```

終了コード: `0` 成功、`1` CSV を読めない、または描画できない場合、`2` コマンドラインが不正。

### nodes / flows / skeletons / formats: 登録済みコンポーネントの一覧

現在の環境に登録されているものを一覧・表示します。`--module <module>`(複数指定可)で先にプロジェクトのモジュールを import し、`--json` で機械可読な出力にできます。

| コマンド | 説明 |
| -------- | ---- |
| `rdetoolkit nodes list` | 登録済み node id の一覧(`--plugin` で検出したプラグインの node のみ) |
| `rdetoolkit nodes show <node id>` | 1 つの node の id、バージョン、タグ、入出力スキーマを表示 |
| `rdetoolkit nodes lint` | 実行や再現性を損なう問題(id の重複や不安定な id、型注釈の欠落など)を node と flow について検査 |
| `rdetoolkit flows list` | 登録済み flow id の一覧 |
| `rdetoolkit flows show <flow id>` | 1 つの flow の id、バージョン、シグネチャを表示 |
| `rdetoolkit skeletons list` | 登録済みの処理スケルトン(`ProcessingTemplate` のサブクラス)の一覧 |
| `rdetoolkit skeletons show <skeleton>` | 1 つのスケルトンの id、slot、slot のシグネチャを表示 |
| `rdetoolkit formats list` | インストール済みプラグインが宣言するファイル形式ハンドラーの一覧 |

```bash title="プロジェクトのモジュールに含まれる node を一覧"
python3 -m rdetoolkit nodes list --module modules.processing
```

終了コード: `0` 成功、`2` コマンドラインが不正、`3` 未知の id、import に失敗したモジュール、または(`nodes lint` で)違反の検出。

### package: RDE提出用アーカイブの作成

RDEに提出するためのアーカイブ（.zip）を作成します。指定したソースディレクトリを圧縮し、除外パターンに一致するディレクトリを除外します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit package --source-dir <ソースディレクトリ> --output <出力アーカイブファイル> --exclude <除外パターン>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit package --source-dir <ソースディレクトリ> --output <出力アーカイブファイル> --exclude <除外パターン>
    ```

#### オプション

| オプション           | 説明                                                                            | 必須 |
| -------------------- | ------------------------------------------------------------------------------- | ---- |
| -s(--source-dir)     | 圧縮・スキャン対象のソースディレクトリ(通常は `container/`)                    | ○    |
| -o(--output)         | 出力アーカイブファイル（例：rde_submission.zip）。名前は `.zip` で終わる必要があり、既存ファイルは置き換えられます | -    |
| -e(--exclude)        | 除外するディレクトリ名(複数指定可)。デフォルトでは `.*`、`venv`、`.venv`、`site-packages` が除外されます | -    |

#### 実行レポート

アーカイブが作成されると、zip と同じ場所に同名の `.md` ファイルとして以下のような実行レポートが生成されます：

- Dockerfileやrequirements.txtの存在確認
- 含まれるディレクトリとファイルのリスト
- コードスキャン結果（セキュリティリスクの検出）
- 外部通信チェック結果

実行レポートのサンプル：

```markdown
# Execution Report

**Execution Date:** 2025-04-08 02:58:44

- **Dockerfile:** [Exists]: 🐳　container/Dockerfile
- **Requirements:** [Exists]: 🐍 container/requirements.txt

## Included Directories

- container/requirements.txt
- container/Dockerfile
- container/vuln.py
- container/external.py

## Code Scan Results

### container/vuln.py

**Description**: Usage of eval() poses the risk of arbitrary code execution.

```python
def insecure():
    value = eval("1+2")
    print(value)
```

## External Communication Check Results

### **container/external.py**

```python
1:
2: import requests
3: def fetch():
4:     response = requests.get("https://example.com")
5:     return response.text
```

!!! tip "オプション詳細"
    - `-o/--output`を指定しない場合、ソースディレクトリと同じ階層に `<YYYYMMDD>_<id>_rde_artifact.zip` という名前でアーカイブが作成されます。
    - `--exclude`オプションは複数回指定することができます（例：`--exclude venv --exclude .git`）。

終了コード: `0` 成功、`1` 出力名が `.zip` でない、またはアーカイブ作成やレポート作成に失敗した場合、`2` コマンドラインが不正。

### repro: 実行の書き出しと再実行

`repro export` は実行レポート、実行時の入力ディレクトリ(`data/inputdata`、`data/invoice`、`data/tasksupport`)、実際に使われた `rdeconfig.yaml` を 1 つの zip にまとめます。`repro import` はその zip を新規または空のディレクトリに展開し、`rdetoolkit run` を実行できる状態にします。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit repro export <run_report.json> -o <archive.zip> [--config <overrides.yaml>]
    python3 -m rdetoolkit repro import <archive.zip> <展開先ディレクトリ>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit repro export <run_report.json> -o <archive.zip> [--config <overrides.yaml>]
    py -m rdetoolkit repro import <archive.zip> <展開先ディレクトリ>
    ```

- 実行時に `rdetoolkit run --config` を使った場合は `--config` が必須です。設定はレポートの `config_digest` を再現できる場合にだけアーカイブされます。
- `repro import` は上書きしません。空でない展開先は拒否されます。

終了コード: `0` 成功、`2` コマンドラインが不正、`3` レポートや zip を読めない、入力ディレクトリがない、設定が digest を再現しない、展開先が空でない、または安全でないメンバーパスを含む場合。

### migrate: v1 コードの検出と変換

- `migrate check [PATH]` は v2 移行が必要な行を 1 行 1 件(`path:line: finding`)で報告し、ファイルは変更しません。Python ファイルでは `custom_dataset_function=` による入口呼び出し、`RdeOutputResourcePath` の参照、v1 のハンドラー形のクラス、v2.0 で名前が変わった CLI コマンドを検出します。シェル、CI、コンテナ関連のファイル(`*.sh`、`*.yml`、`*.yaml`、`*.toml`、`*.cfg`、`Makefile`、`Dockerfile`)では名前が変わった CLI コマンドだけを検出します。
- `migrate apply [PATH]` は v1 の `custom_dataset_function` コールバックを v2 flow に変換します。デフォルトはプレビュー(`--dry-run`)で、`--no-dry-run` を付けると変換結果を `-o/--output DIR`(デフォルト: 入力の隣の `<PATH>_migrated`)に書き出します。入力ファイルは変更しません。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit migrate check [PATH]
    python3 -m rdetoolkit migrate apply [PATH] [--no-dry-run] [-o <出力ディレクトリ>]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit migrate check [PATH]
    py -m rdetoolkit migrate apply [PATH] [--no-dry-run] [-o <出力ディレクトリ>]
    ```

```bash title="container/ の変換結果を container_v2/ に書き出す"
python3 -m rdetoolkit migrate apply container --no-dry-run -o container_v2
```

終了コード: `0` 成功、`2` コマンドラインが不正(`migrate apply` では入力パスが存在しない場合も含む)、`3` パスが存在しない(`migrate check`)、または Python ファイルが見つからない、出力ディレクトリが既に存在するか入力の内側にある(`migrate apply`)。

移行手順は [v1 から v2 への移行](../migration_v1_to_v2.md) を参照してください。

### agent-guide: AIエージェントガイドの表示

AIコーディングアシスタント（Claude Code、GitHub Copilot、Cursor等）向けの組み込みガイドを表示します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit agent-guide [--detailed]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit agent-guide [--detailed]
    ```

このコマンドはrdetoolkitの使用方法、アーキテクチャ、ベストプラクティスに関するガイドテキストを Markdown で出力します。`--detailed` を付けると応用パターンと API リファレンス全体が加わります。AIアシスタントのコンテキストに追加して、rdetoolkitを使用したコード生成の精度を向上させることができます。

#### Pythonからの使用

```python
import rdetoolkit

# エージェントガイドを取得
guide = rdetoolkit.agent_guide()
print(guide)
```

### version: バージョン確認

rdetoolkitのバージョンを確認します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit version
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit version
    ```

## v2.0 でのコマンド名の変更 { #renamed-commands }

v2.0 で CLI は `rdetoolkit <名詞> <動詞>` 形式に再編されました。v1 のコマンドは v2.0.x では警告を表示する非推奨の別名として動作し、v2.1 で削除されます。v2 のリリース候補版にだけ存在した名前は別名なしで削除されました。`rdetoolkit migrate check` は、スクリプト、CI、コンテナ関連ファイルに残っている旧コマンド名を報告します。

| 旧 | 新 | 由来 |
|---|---|---|
| `gen-config [OUTPUT_DIR] [--template X] [--overwrite]` | `new config [-o DIR] [--preset X] [--force]` | v1 — v2.0.x では非推奨の別名として残り、警告を表示、v2.1 で削除 |
| `gen-invoice` | `new invoice` | v1 — 非推奨の別名 |
| `make-excelinvoice` | `new excelinvoice` | v1 — 非推奨の別名 |
| `csv2graph` | `plot` | v1 — 非推奨の別名 |
| `artifact --output-archive` | `package -o/--output` | v1 — 非推奨の別名 |
| `run TARGET` (`module::attr`) | `run --legacy TARGET` | v1 — `--legacy` なしの `::` 形式も実行される(出力互換のため警告なし)。v2.1 で `--legacy` が必須 |
| `init --processing-template X` | `new processing X` | v2 rc のみ — 別名なしで削除 |
| `run --flow X` | `run X` | v2 rc のみ — 削除 |
| `graph REPORT` | `report trace REPORT` | v2 rc のみ — 削除 |
| `templates list/describe` | `skeletons list/show` | v2 rc のみ — 削除 |
| `nodes describe`, `flows describe` | `nodes show`, `flows show` | v2 rc のみ — 削除 |
| `migrate apply --out DIR` | `migrate apply -o/--output DIR` | v2 rc のみ — 削除 |

## シェル補完機能

コマンドやオプションの入力を補完するシェル補完機能を利用できます。Tabキーを押すことでコマンド名やオプション名の候補を表示できます。

### 対応シェル

- Bash
- Zsh
- Fish
- PowerShell

### インストール方法

`--install-completion` オプションを使用して、現在使用中のシェルに補完機能をインストールできます：

```bash
python -m rdetoolkit --install-completion
```

実行後、シェルを再起動することで補完機能が有効になります。

```bash
# シェルの再起動
exec $SHELL
```

### 手動インストール

補完スクリプトの内容を確認してから手動でインストールする場合は、`--show-completion` オプションを使用します：

```bash
python -m rdetoolkit --show-completion
```

表示されたスクリプトを、シェルの設定ファイルに追加してください。

#### Bashの場合

```bash
python -m rdetoolkit --show-completion >> ~/.bashrc
source ~/.bashrc
```

#### Zshの場合

```bash
python -m rdetoolkit --show-completion >> ~/.zshrc
source ~/.zshrc
```

### 使用例

補完機能をインストールした後、Tabキーを押すことで候補を表示できます。

```bash
# コマンド名の補完
python -m rdetoolkit <Tab>
# → init, new, plot, validate, run, report, package などが表示される

# サブコマンドの補完
python -m rdetoolkit new <Tab>
# → config, invoice, excelinvoice, processing が表示される

# オプション名の補完
python -m rdetoolkit new config --<Tab>
# → --output, --preset, --force, --lang などが表示される

# オプション値: --preset はプリセット名を受け取ります(候補は表示されません)
python -m rdetoolkit new config --preset <Tab>
# → minimal, full, multitile, rdeformat, smarttable, interactive のいずれかを入力
```

### アンインストール

補完機能を削除する場合は、シェルの設定ファイルから該当する行を削除してください。

Bashの場合は `~/.bashrc` から、Zshの場合は `~/.zshrc` から以下のような行を削除します：

```bash
eval "$(_RDETOOLKIT_COMPLETE=bash_source python -m rdetoolkit)"
```

削除後、シェルを再起動してください。

## 次のステップ

- [構造化処理の概念](../user-guide/structured-processing.ja.md)を理解する
- [設定ファイル](../user-guide/config.ja.md)の作成方法を学ぶ
- [APIリファレンス](../api/index.ja.md)で詳細な機能を確認する
