![GitHub Release](https://img.shields.io/github/v/release/nims-mdpf/rdetoolkit)
[![python.org](https://img.shields.io/badge/Python-3.9%7C3.10%7C3.11-%233776AB?logo=python)](https://www.python.org/downloads/release/python-3917/)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](https://github.com/nims-mdpf/rdetoolkit/blob/main/LICENSE)
[![Issue](https://img.shields.io/badge/issue_tracking-github-orange)](https://github.com/nims-mdpf/rdetoolkit/issues)
![workflow](https://github.com/nims-mdpf/rdetoolkit/actions/workflows/main.yml/badge.svg)
![coverage](docs/img/coverage.svg)

# RDEToolKit

RDEToolKitは、RDE構造化プログラムのワークフローを作成するための基本的なPythonパッケージです。
RDEToolKitの各種モジュールを使うことで、RDEへの研究・実験データの登録処理を簡単に構築できます。
また、ユーザーが研究や実験データに対して使用されているPythonモジュールと組み合わせることで、データの登録から加工、グラフ化などより多様な処理を実現できます。

## Documents

See [documentation](https://nims-mdpf.github.io/rdetoolkit/) for more details.

## Contributing

変更を加える場合、以下のドキュメントを一読お願いします。

- [CONTRIBUTING.md](https://github.com/nims-mdpf/rdetoolkit/blob/main/CONTRIBUTING.md)

## Install

インストールは、下記コマンドを実行してください。

```shell
pip install rdetoolkit
```

## Usage

RDE構造化プログラム構築の一例です。

### プロジェクトを作成する

まず、RDE構造化プログラムに必要なファイルを準備します。以下のコマンドをターミナルやシェル上で実行してください。

```python
python3 -m rdetoolkit init
```

コマンドが正しく動作すると、下記で示したファイル・ディレクトリが生成されます。

この例では、`container`というディレクトリを作成して、開発を進めます。

- **requirements.txt**
  - 構造化プログラム構築で使用したいPythonパッケージを追加してください。必要に応じて`pip install`を実行してください。
- **modules**
  - 構造化処理で使用したいプログラムを格納してください。別セクションで説明します。
- **main.py**
  - 構造化プログラムの起動処理を定義
- **data/inputdata**
  - 構造化処理対象データファイルを配置してください。
- **data/invoice**
  - ローカル実行させるためには空ファイルでも必要になります。
- **data/tasksupport**
  - 構造化処理の補助するファイル群を配置してください。

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

### 構造化処理の実装

入力データに対してデータ加工・グラフ化・機械学習用のcsvファイルの作成など処理を実行し、RDEへデータを登録できます。下記の書式に従っていただければ、独自の処理をRDEの構造化処理のフローに組み込み込むことが可能です。

`dataset()` の推奨シグネチャは、入力と出力のパスをまとめた
`RdeDatasetPaths` を 1 つ受け取ります。既存の 2 引数スタイル
（`RdeInputDirPaths`, `RdeOutputResourcePath`）も後方互換のため引き続き利用できます。

```python
from rdetoolkit.models.rde2types import RdeDatasetPaths

def dataset(paths: RdeDatasetPaths) -> None:
    ...
```

今回の例では、`modules` 以下に `display_messsage()` というダミー処理を定義し、独自の構造化処理を実装します。`modules/modules.py` というファイルを作成します。

```python
# modules/modules.py
from rdetoolkit.models.rde2types import RdeDatasetPaths


def display_messsage(path):
    print(f"Test Message!: {path}")


def dataset(paths: RdeDatasetPaths) -> None:
    display_messsage(paths.inputdata)
    display_messsage(paths.struct)
```

### 起動処理について

続いて、`rdetoolkit.workflow.run()`を使って、起動処理を定義します。起動処理で主に実行処理は、

- 入力ファイルのチェック
- 入力ファイルとRDE構造化で規定する各種ディレクトリパスを取得する
- ユーザーごとで定義した具体的な構造化処理を実行

```python
import rdetoolkit
from modules.modules import dataset  #独自で定義した構造化処理関数

#独自で定義した構造化処理関数を引数として渡す
rdetoolkit.workflows.run(custom_dataset_function=dataset)
```

もし、独自の構造化処理を渡さない場合、以下のように定義してください。

```python
import rdetoolkit

rdetoolkit.workflows.run()
```

### ローカル環境で動作させる場合

各自のローカル環境で、デバッグやテスト的にRDEの構造化処理を実行したい場合、`data`ディレクトリに必要な入力データを追加することで、ローカル環境でも実行可能です。ディレクトリ構造は、以下のように、main.pyと同じ階層にdataディレクトリを配置していただければ動作します。

```shell
container/
├── main.py
├── requirements.txt
├── modules/
│   └── modules.py
└── data/
    ├── inputdata/
    │   └── <処理したい実験データ>
    ├── invoice/
    │   └── invoice.json
    └── tasksupport/
        ├── metadata-def.json
        └── invoice.schema.json
```
