# サポートするディレクトリ構造

## 目的

RDE構造化処理でサポートされるディレクトリ構造の詳細仕様について説明します。入力・出力ディレクトリの役割と命名規則、dividedディレクトリの使用方法を理解できます。

## ディレクトリ構造仕様

### 入力ディレクトリ

構造化処理実行時に必要な入力ディレクトリ群です。ローカル実行時は事前に作成が必要です：

| ディレクトリ名 | 種別         | 用途                                                             |
| -------------- | ------------ | ---------------------------------------------------------------- |
| inputdata      | 入力データ   | 入力データファイルを格納                                         |
| invoice        | 送り状データ | 送り状(invoice.json)が格納されます。                             |
| tasksupport    | 画像ファイル | 事前にテンプレート作成時に登録した構造化処理補助ファイル群を格納 |

### 構造化処理実行前のディレクトリ例

ローカルで構造化処理を実行する場合、以下のように事前にディレクトリを作成します：

```shell
.
├── modules
│   └── custom_modules.py
├── data
│   ├── inputdata
│   │   └── sample_data.ras
│   ├── invoice
│   │   └── invoice.json
│   └── tasksupport
│       ├── invoice.schema.json
│       └── metadata-def.json
├── main.py # 起動処理を定義(entry point)
└── requirements.txt
```

### 出力ディレクトリ

出力ディレクトリは、構造化処理を実行した結果を格納するディレクトリ群です。rdetoolkitでは、構造化処理実行すると、下記ディレクトリが自動で作成されます：

| ディレクトリ名 | 種別                       | 用途                                                                                                           |
| -------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------- |
| meta           | 主要パラメータ情報ファイル | 主要パラメータ情報ファイル(`metadata.json`)を格納                                                              |
| main_image     | 画像ファイル               | RDEデータセット詳細画像として表示されるサムネイルファイル                                                      |
| other_image    | 画像ファイル               | RDEデータセットファイル一覧にのみ表示される                                                                    |
| thumbnail      | 画像ファイル               | RDEデータセット一覧に表示される画像ファイル                                                                    |
| attachment     | -                          | 添付ファイル(※)                                                                                                |
| nonshared_raw  | -                          | 共有不可能なファイル群を配置                                                                                   |
| raw            | rawデータファイル          | 共有可能なrawファイル群を配置。入力データを配置する。                                                          |
| structured     | 構造化ファイル             | 構造化処理により生成されたファイルを配置。入力データを配置する。                                               |
| logs           | -                          | データセットに登録・反映されませんが、ログを蓄積するためのディレクトリが作成されます。                         |
| temp           | -                          | データセットに登録・反映されませんが、一時的ディレクトリとして、tempディレクトリが作成されるケースがあります。 |

!!! warning
    attachmentは、rdetoolkitでは自動で生成されません。

### ローカルで構造化処理実行後のディレクトリ例

```shell
├── modules
│   └── custom_modules.py
├── data
│   ├── inputdata
│   │   └── excelinvoice.zip
│   ├── invoice
│   │   └── invoice.json
│   ├── logs
│   │   └── rdesys.log
│   ├── main_image
│   │   └── iamge0.png
│   ├── meta
│   │   └── metadata.json
│   ├── nonshared_raw
│   ├── other_image
│   │   ├── sub_image1.png
│   │   └── sub_image2.png
│   ├── raw
│   │   ├── DMF-pos-1.xyz
│   │   ├── li-mole.inp
│   │   └── opt.xyz
│   ├── structured
│   │   └── sample.csv
│   ├── tasksupport
│   │   ├── invoice.schema.json
│   │   └── metadata-def.json
│   ├── temp
│   │   └── invoice_org.json
│   └── thumbnail
│       └── image.png
├── main.py
└── requirements.txt
```

## dividedディレクトリ

### 概要

RDE構造化処理では、[ExcelInvoice](../config/mode.ja.md)や、[マルチデータタイルモード](../config/mode.ja.md)という、一度に複数のデータを登録するモードが存在します。このモードを使用する場合、`divided`というディレクトリを作成しなければなりません。

!!! note
    [ExcelInvoice](../config/mode.ja.md)や、[マルチデータタイルモード](../config/mode.ja.md)を設定ファイルに記述し、指定した入力規則で構造化処理を実行した場合、自動的にdividedディレクトリが作成されます。

### dividedディレクトリの命名規則

- 命名規則: `data/divided/00xx`
- `00xx`: 4桁でゼロ埋め(例：0001/, 0029/など)
- `data/divided/00xx`配下に、`structured`や`meta`などのRDE構造化処理がサポートするディレクトリを配置
- この時、`inputdata`, `invoice`, `tasksupport`は作成しなくて良い

### dividedディレクトリ構造例

```bash
├── divided/
│   ├── 0001/  # 例: 0001/, 0002/ など
│   │   ├── structured/
│   │   ├── meta/
│   │   ├── thumbnail/
│   │   ├── main_image/
│   │   ├── other_image/
│   │   ├── nonshared_raw/
│   │   └── raw/
│   ├── 0002/
│   │   ├── structured/
│   │   ├── meta/
│   │   ├── thumbnail/
│   │   ├── main_image/
│   │   ├── other_image/
│   │   ├── nonshared_raw/
│   │   └── raw/
├── inputdata/
├── invoice/
├── tasksupport/
├── structured/
├── meta/
├── thumbnail/
├── main_image/
├── other_image/
├── nonshared_raw/
└── raw/
```

## DirectoryOpsによるディレクトリ作成

### 概要

上記で示した通り、RDE構造化処理でサポートするディレクトリは、`divided/00xx`のようにディレクトリなど、命名規則にしたがって生成しなければならないケースが存在します。`rdetoolkit.core.DirectoryOps`使用すると、簡単にRDE構造化処理をサポートするディレクトリを作成することができます。

### 使用例

```python title="DirectoryOpsの使用方法"
from rdetoolkit.core import DirectoryOps

# 1. インスタンス生成: dataディレクトリを作成
dir_ops = DirectoryOps("data")

# 2. structuredディレクトリを作成
p = dir_ops.structured.path
print(p)  # data/structured

# 3. index付きのディレクトリを作成
p = dir_ops.structured(2).path
print(p)  # data/divided/0002/structured

# 4. dataディレクトリ以下にファイル一覧を一度に作成しパスを取得する
p = dir_ops.all()
print(p)  # ['data/invoice', 'data/invoice_patch', 'data/attachment', ...]

# 5. dataディレクトリ以下に、index付きのファイル一覧を一度に作成しパスを取得する
p = dir_ops.all(1)
print(p)  # ['data/invoice', ..., 'data/divided/0001/structured', ...]

# 6. 指定ディレクトリ以下のファイル一覧を取得する
p = dir_ops.structured.list()
print(p)  # ['data/structured/structured_item_1.csv', ...]

# 7. 指定ディレクトリ以下のファイル一覧を取得する(divided)
p = dir_ops.structured(2).list()
print(p)  # ['data/divided/0002/structured/structured_item_1.csv', ...]
```

## 関連情報

ディレクトリ構造についてさらに学ぶには、以下のドキュメントを参照してください：

- [構造化処理の概念](structured.ja.md)でディレクトリが使用される処理フローを理解する
- [ディレクトリパス取得](rdepath.ja.md)でパス操作方法を確認する
- [処理モード](../config/mode.ja.md)でdividedディレクトリを使用するモードを学ぶ
