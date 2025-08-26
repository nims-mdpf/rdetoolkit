# RDEFormatモードとは

## 目的

RDEFormatモードは、RDEと別システムを連携するために、RDE形式データをRDEに登録するためのモードです。あるシステムからRDE形式データを出力すると、RDEFormatモードを使用して、出力されたデータを、そのままRDEに登録することができます。

![rdeformat](../../img/rdeformat.svg)

## 特徴

- 指定のRDE登録データ形式(.zip)をそのまま登録可能。

## 使用場面

- RDE形式データを他のシステムからRDEに登録したい場合
- モック的にデータセットを開設し、データを登録したい場合

## 設定方法

設定ファイル`rdeconfig.yml`に、以下のように設定します。

```yaml
system:
  extended_mode: "rdeformat"
```

## 展開されるフォルダ

zipに含めて展開される対象のフォルダは、以下のとおりです。

- raw
- main_image
- other_image
- meta
- structured
- nonshared_raw

## 入力ファイル

RDE構造化処理でサポートされているディレクトリ構造をzip形式で圧縮します。

```bash
input.zip
├── main_image
│   └── sample1.png
├── meta
│   └── metadata.json
├── nonshared_raw
├── other_image
│   └── other_sampling.png
├── raw
│   └── sample1.raw
└── structured
    └── sample1.csv
```

## ディレクトリ構造

`inputdata`ディレクトリに、Excelファイルとzipファイルを配置します。

```bash
data/
├── inputdata/
│   ├── input.zip
├── invoice/
└── tasksupport/
    └── rdeconfig.yml
```

実行後は、以下のように、input.zipの内容がそのまま登録されます。`divided`ディレクトリで分割されたデータも対応しています。

```bash
data/
├── inputdata/
│   ├── file1.rasx
│   └── file2.rasx
├── invoice/
├── tasksupport/
├── main_image
│   └── sample1.png
├── meta
│   └── metadata.json
├── nonshared_raw
├── other_image
│   └── other_sampling.png
├── raw
│   └── sample1.raw
└── structured
    └── sample1.csv
```

## よくあるエラーや質問について

### RDEFormatモードをつかって構造化処理を実装できますか

RDEFormatモードは、RDE形式データをそのまま登録するためのモードですが、構造化処理を実装することも可能です。Invoiceモードなどと同様に、構造化処理を定義していただければ、登録時に、事前に定義した処理を実行することができます。

### RDEFormatモードでinvoice.jsonを含めて上書きできますか

RDEFormatモードでは、invoice.jsonを含めて上書きすることはできません。RDEFormatモードでは、RDE形式データをそのまま登録するため、invoice.jsonは登録時に自動生成されます。

展開される対象のフォルダは、以下のとおりです。

- raw
- main_image
- other_image
- meta
- structured
- nonshared_raw
