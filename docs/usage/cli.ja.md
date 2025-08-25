# コマンドライン機能について

## 概要

RDEToolKitは、RDE構造化処理の開発と実行を支援する包括的なコマンドラインインターフェースを提供します。プロジェクトの初期化から、Excelインボイスの生成、アーカイブの作成まで、開発ワークフロー全体をサポートします。

## 前提条件

- Python 3.9以上
- rdetoolkitパッケージのインストール

## 利用可能なコマンド

### init: スタートアッププロジェクトの作成

RDE構造化処理のスタートアッププロジェクトを作成します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit init
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit init
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

## 次のステップ

- [構造化処理の概念](../user-guide/structured-processing.ja.md)を理解する
- [設定ファイル](../user-guide/config.ja.md)の作成方法を学ぶ
- [APIリファレンス](../api/index.ja.md)で詳細な機能を確認する
