# コマンドライン機能について

## 概要

RDEToolKitは、RDE構造化処理の開発と実行を支援する包括的なコマンドラインインターフェースを提供します。プロジェクトの初期化から、Excelインボイスの生成、アーカイブの作成まで、開発ワークフロー全体をサポートします。

## 前提条件

- Python 3.10以上
- rdetoolkitパッケージのインストール

## 利用可能なコマンド

### init: スタートアッププロジェクトの作成

RDE構造化処理のスタートアッププロジェクトを作成します。

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
└── requirements.txt
```

各ファイルの説明は以下の通りです。

- **requirements.txt**: 構造化プログラム構築で使用したいPythonパッケージを追加してください。必要に応じて`pip install`を実行してください。
- **modules**: 構造化処理で使用したいプログラムを格納してください。
- **main.py**: 構造化プログラムの起動処理を定義
- **data/inputdata**: 構造化処理対象データファイルを配置してください。
- **data/invoice**: ローカル実行させるためには空ファイルでも必要になります。
- **data/tasksupport**: 構造化処理の補助するファイル群を配置してください。

!!! tip "ファイル上書きについて"
    すでに存在するファイルは上書きや生成がスキップされます。

#### テンプレートを用いた初期化

`--template <path>` を付けると独自のスタータープロジェクトを流用できます。指定できるのは以下のいずれかです。

- `pyproject.toml` または `rdeconfig.yaml` / `rdeconfig.yml` そのもの
- 上記ファイルが格納されたディレクトリ（`--template .` ならカレントディレクトリ内の `pyproject.toml` を優先）

設定ファイルには `[tool.rdetoolkit.init]`（pyproject）または `init`（rdeconfig）セクションを追加し、コピー元を記述します。

```toml
[tool.rdetoolkit.init]
entry_point = "templates/main.py"
modules = "templates/modules"
tasksupport = "templates/tasksupport"
inputdata = "templates/inputdata"
```

キーの意味:

- `entry_point`: `container/main.py` としてコピーされるファイル。
- `modules`: `container/modules/` 配下に展開されるファイルまたはディレクトリ。
- `tasksupport`: `container/data/tasksupport/` と `templates/tasksupport/` の両方へ複製されるファイル/ディレクトリ。
- `inputdata`: `container/data/inputdata/` と `input/inputdata/` に展開されるディレクトリ。

相対パスは設定ファイルが置かれたディレクトリから解決されるため、テンプレート用リポジトリを別環境でも共有できます。

#### PATHオプションで直接コピー元を指定する

設定ファイルにパスを書きたくない場合は、`--template` なしで次のPATHオプションを渡せます（複数併用可）。指定したパスは初期化に使われ、存在する `pyproject.toml` / `rdeconfig.yaml(yml)` があれば上書き追記されます（無ければ `pyproject.toml` を新規作成）。

| オプション        | 役割・コピー先                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------- |
| `--entry-point`   | `container/main.py` としてコピー（ファイル限定）                                            |
| `--modules`       | `container/modules/` 以下にコピー（ファイル/ディレクトリ対応）                              |
| `--tasksupport`   | `container/data/tasksupport/` と `templates/tasksupport/` の両方にコピー（ファイル/ディレクトリ対応） |
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
Populated /private/tmp/rdt-init-check/templates/tasksupport from template directory: /private/tmp/rdt-init-check/tpl/tasksupport
Populated /private/tmp/rdt-init-check/container/data/inputdata from template directory: /private/tmp/rdt-init-check/tpl/inputdata
Populated /private/tmp/rdt-init-check/input/inputdata from template directory: /private/tmp/rdt-init-check/tpl/inputdata
Copied template file /private/tmp/rdt-init-check/tpl/extra.txt into /private/tmp/rdt-init-check/container
Populated /private/tmp/rdt-init-check/container/extras from template directory: /private/tmp/rdt-init-check/tpl/extras
Created: /private/tmp/rdt-init-check/input/invoice/invoice.json
```

処理後、`pyproject.toml`（または既存の`rdeconfig.yaml`）に `[tool.rdetoolkit.init]` が追記され、渡したパスが相対パスで保存されます。

### make-excelinvoice: ExcelInvoiceの生成

`invoice.schema.json`からExcelインボイスを生成します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

#### オプション

| オプション   | 説明                                                                                     | 必須 |
| ------------ | ---------------------------------------------------------------------------------------- | ---- |
| -o(--output) | 出力ファイルパス。ファイルパスの末尾は`_excel_invoice.xlsx`を付与すること。              | ○    |
| -m           | モードの選択。登録モードの選択。ファイルモード`file`かフォルダモード`folder`を選択可能。 | -    |

!!! tip "デフォルト出力"
    `-o`を指定しない場合は、`template_excel_invoice.xlsx`というファイル名で、実行ディレクトリ配下に作成されます。

### gen-config: rdeconfig.yamlテンプレートの生成

用意されているテンプレート、または対話形式の質問に基づいて`rdeconfig.yaml`を生成します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit gen-config [OUTPUT_DIR] --template <template> [--overwrite] [--lang <ja|en>]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit gen-config [OUTPUT_DIR] --template <template> [--overwrite] [--lang <ja|en>]
    ```

利用できるテンプレートは以下の通りです。

- `minimal`（デフォルト）: システム設定とトレースバック設定のみを含む最小構成。
- `full`: `multidata_tile`設定を含む完全なテンプレート。
- `multitile`: `extended_mode: "MultiDataTile"`を有効化したテンプレート。
- `rdeformat`: `extended_mode: "rdeformat"`を有効化したテンプレート。
- `smarttable`: SmartTable設定を追加し、`save_table_file: true`を設定。
- `interactive`: 対話形式で各設定項目を確認。`--lang ja`で日本語プロンプトに切り替え可能。

#### オプション

| オプション       | 説明                                                                                                  | 必須 |
| ---------------- | ----------------------------------------------------------------------------------------------------- | ---- |
| OUTPUT_DIR       | `rdeconfig.yaml`を出力するディレクトリ。省略時はカレントディレクトリに作成されます。                  | -    |
| --template       | テンプレート名（`minimal`, `full`, `multitile`, `rdeformat`, `smarttable`, `interactive`）。           | -    |
| --overwrite      | 既存の`rdeconfig.yaml`がある場合に確認なしで強制上書きします。未指定なら既存時のみ確認を表示します。   | -    |
| --lang           | プロンプトの言語（`en` または `ja`）。`--template interactive`選択時のみ利用できます。               | -    |

!!! tip "インタラクティブモード"
    `--template interactive`を指定すると、システム設定、MultiDataTile設定、SmartTable設定、トレースバック設定について
    対話形式で質問されます。回答は`rdeconfig.yaml`に反映され、プロジェクト開始時から整合した初期値を共有できます。

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

### gen-invoice: invoice.jsonの生成

`invoice.schema.json`から`invoice.json`を自動生成します。スキーマ定義に基づいてデフォルト値を設定し、生成後に自動検証を行います。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit gen-invoice <invoice.schema.json path> [OPTIONS]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit gen-invoice <invoice.schema.json path> [OPTIONS]
    ```

#### オプション

| オプション | 説明 | 必須 |
| ---------- | ---- | ---- |
| -o(--output) | 出力ファイルパス。省略時はカレントディレクトリに`invoice.json`を作成 | - |
| --fill-defaults/--no-fill-defaults | デフォルト値を埋めるかどうか（デフォルト: 有効） | - |
| --required-only | 必須フィールドのみを含める | - |
| --format | 出力フォーマット（`pretty`または`compact`）。デフォルト: `pretty` | - |

#### 使用例

```bash title="基本的な使用"
python3 -m rdetoolkit gen-invoice tasksupport/invoice.schema.json
```

```bash title="出力先を指定"
python3 -m rdetoolkit gen-invoice tasksupport/invoice.schema.json -o container/data/invoice/invoice.json
```

```bash title="必須フィールドのみ、コンパクトフォーマット"
python3 -m rdetoolkit gen-invoice tasksupport/invoice.schema.json --required-only --format compact
```

#### デフォルト値の優先順位

1. スキーマの`default`フィールド
2. スキーマの`examples`配列の最初の値
3. 型ベースのデフォルト値: string→`""`、number→`0.0`、integer→`0`、boolean→`false`

!!! tip "詳細なAPIドキュメント"
    プログラムからの使用方法については、[Invoice Generator API](../rdetoolkit/cmd/gen_invoice.md)を参照してください。

### agent-guide: AIエージェントガイドの表示

AIコーディングアシスタント（Claude Code、GitHub Copilot、Cursor等）向けの組み込みガイドを表示します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit agent-guide
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit agent-guide
    ```

このコマンドはrdetoolkitの使用方法、アーキテクチャ、ベストプラクティスに関するガイドテキストを出力します。AIアシスタントのコンテキストに追加して、rdetoolkitを使用したコード生成の精度を向上させることができます。

#### Pythonからの使用

```python
import rdetoolkit

# エージェントガイドを取得
guide = rdetoolkit.agent_guide()
print(guide)
```

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
| 1 | バリデーション失敗 | データまたはスキーマのエラーが見つかった |
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

### artifact: RDE提出用アーカイブの作成

RDEに提出するためのアーカイブ（.zip）を作成します。指定したソースディレクトリを圧縮し、除外パターンに一致するファイルやディレクトリを除外します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit artifact --source-dir <ソースディレクトリ> --output-archive <出力アーカイブファイル> --exclude <除外パターン>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit artifact --source-dir <ソースディレクトリ> --output-archive <出力アーカイブファイル> --exclude <除外パターン>
    ```

#### オプション

| オプション           | 説明                                                                            | 必須 |
| -------------------- | ------------------------------------------------------------------------------- | ---- |
| -s(--source-dir)     | 圧縮・スキャン対象のソースディレクトリ                                          | ○    |
| -o(--output-archive) | 出力アーカイブファイル（例：rde_template.zip）                                  | -    |
| -e(--exclude)        | 除外するディレクトリ名。デフォルトでは 'venv' と 'site-packages' が除外されます | -    |

#### 実行レポート

アーカイブが作成されると、以下のような実行レポートが生成されます：

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
    - `--output-archive`を指定しない場合、デフォルトのファイル名でアーカイブが作成されます。
    - `--exclude`オプションは複数回指定することができます（例：`--exclude venv --exclude .git`）。

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
# → init, version, gen-config などが表示される

# オプション名の補完
python -m rdetoolkit gen-config --<Tab>
# → --template, --overwrite, --lang などが表示される

# オプション値の補完
python -m rdetoolkit gen-config --template <Tab>
# → static, interactive が表示される
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
