# コマンドライン機能について

## init: スタートアッププロジェクトの作成

以下のコマンドで、RDE構造化処理のスタートアッププロジェクトを作成することができます。

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

- requirements.txt
    - 構造化プログラム構築で使用したいPythonパッケージを追加してください。必要に応じて`pip install`を実行してください。
- modules
    - 構造化処理で使用したいプログラムを格納してください。別セクションで説明します。
- main.py
    - 構造化プログラムの起動処理を定義
- data/inputdata
    - 構造化処理対象データファイルを配置してください。
- data/invoice
    - ローカル実行させるためには空ファイルでも必要になります。
- data/tasksupport
    - 構造化処理の補助するファイル群を配置してください。

!!! Tip
    すでに存在するファイルは上書きや生成がスキップされます。

## ExcelInvoiceの生成機能について

`make_excelinvoice`で、`invoic.schema.json`からExcelinvoiceを生成可能です。利用可能なオプションは以下の通りです。

| オプション   | 説明                                                                                     | 必須 |
| ------------ | ---------------------------------------------------------------------------------------- | ---- |
| -o(--output) | 出力ファイルパス。ファイルパスの末尾は`_excel_invoice.xlsx`を付与すること。              | o    |
| -m           | モードの選択。登録モードの選択。ファイルモード`file`かフォルダモード`folder`を選択可能。 | -    |

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit make_excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit make_excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

!!! Tip
    `-o`を指定しない場合は、`template_excel_invoice.xlsx`というファイル名で、実行ディレクトリ配下に作成されます。

## version: バージョン確認

以下のコマンドで、rdetoolkitのバージョンを確認することができます。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit version
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit version
    ```

## artifact: RDE提出用アーカイブの作成

`artifact`コマンドを使用して、RDEに提出するためのアーカイブ（.zip）を作成することができます。指定したソースディレクトリを圧縮し、除外パターンに一致するファイルやディレクトリを除外します。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit artifact --source-dir <ソースディレクトリ> --output-archive <出力アーカイブファイル> --exclude <除外パターン>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit artifact --source-dir <ソースディレクトリ> --output-archive <出力アーカイブファイル> --exclude <除外パターン>
    ```

利用可能なオプションは以下の通りです。

| オプション           | 説明                                                                            | 必須 |
| -------------------- | ------------------------------------------------------------------------------- | ---- |
| -s(--source-dir)     | 圧縮・スキャン対象のソースディレクトリ                                          | o    |
| -o(--output-archive) | 出力アーカイブファイル（例：rde_template.zip）                                  | -    |
| -e(--exclude)        | 除外するディレクトリ名。デフォルトでは 'venv' と 'site-packages' が除外されます | -    |

アーカイブが作成されると、以下のような実行レポートが生成されます：

- Dockerfileやrequirements.txtの存在確認
- 含まれるディレクトリとファイルのリスト
- コードスキャン結果（セキュリティリスクの検出）
- 外部通信チェック結果

以下は実行レポートのサンプルです：

---

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
```

!!! Tip
    `--output-archive`を指定しない場合、デフォルトのファイル名でアーカイブが作成されます。
    `--exclude`オプションは複数回指定することができます（例：`--exclude venv --exclude .git`）。
