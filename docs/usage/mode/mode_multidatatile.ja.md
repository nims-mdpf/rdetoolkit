# MultiDataTileモードとは

## 目的

データを複数登録する登録モードとして、MultiDataTileモードがあります。RDE標準の送り状モードの拡張という位置付けになるので、Excelファイルなどを使用せず、RDEの送り状(Web上の登録画面)から登録できるモードになります。

複数データ登録するモードとして、ExcelInvoiceモードがありますが、こちらは、同じ送り状で一度に複数データを登録することが可能です。(例: 同じ試料情報のデータなど。)

![multidatatile_mode](../../img/multidatatile_mode.svg)

## 特徴

- 設定一つで、送り状(Web上)から一括でデータ登録が可能。
- 同一の実験条件や試料情報のデータの登録に向く。

## 使用場面

- 同一の実験条件や試料情報のデータを一括で登録したい場合

## 設定方法

設定ファイル`rdeconfig.yml`に、以下のように設定します。

```yaml
system:
  extended_mode: "MultiDataTile"
```

## ディレクトリ構造

`inputdata`ディレクトリに、Excelファイルとzipファイルを配置します。

```bash
data/
├── inputdata/
│   ├── file1.rasx
│   └── file2.rasx
├── invoice/
└── tasksupport/
    └── rdeconfig.yml
```

実行後は、以下のように、`divided`ディレクトリに分割されたデータが格納されます。

```bash
data/
├── inputdata/
│   ├── file1.rasx
│   └── file2.rasx
├── invoice/
├── tasksupport/
├── divided/
│   ├── 0001/
│   │   ├── structured/
│   │   ├── meta/
│   │   └── raw/
│   └── 0002/
│       ├── structured/
│       ├── meta/
│       └── raw/
└── logs/
```

## よくあるエラーや質問について

### 一つのタイルに複数のデータを登録したい

MultiDataTileモードを使用する場合、一つのタイルに複数のデータが登録することが難しいです。回避策として、タイルごとに登録したいzipファイルにまとめ、それを個別の構造化処理内に登録する方法があります。
