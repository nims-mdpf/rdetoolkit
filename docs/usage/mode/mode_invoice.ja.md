# Invoiceモードとは

## 目的

RDEデータ登録における、最も基本的な処理モードです。RDEの送り状(Web上の登録画面)を利用して、データを1つずつ登録するモードのことを指します。

![invoice_mode](../../img/invoice_mode.svg)

### 特徴

- 1つの実験結果を1つのデータセットとして登録
- シンプルな設定と操作
- 初心者に最適

## 使用場面

- 単発の実験データ登録

## 設定例

Invoiceモードを使用する場合、設定ファイルの変更等は不要です。

## ディレクトリ構造

構造化処理実行前後のディレクトリ構造は、以下のとおりです。

```bash
data
├── inputdata
│   └── 20250101_myexp.dat
├── invoice
│   └── invoice.json
└── tasksupport
    ├── invoice.schema.json
    ├── metadata-def.json
    └── rdeconfig.yml
```

実行後のディレクトリは以下の通りです。

> ファイル等は出力例です。構造化処理の定義によって変化します。

```bash
data
├── attachment
├── inputdata
│   └── 20250101_myexp.dat
├── invoice
│   └── invoice.json
├── invoice_patch
├── logs
│   └── rdesys.log
├── main_image
│   └── 20250101.png
├── meta
├── nonshared_raw
├── other_image
│   └── 20250101_log_scale.png
├── raw
│   └── 20250101_myexp.dat
├── structured
│   └── 20250101_myexp.csv
├── tasksupport
│   ├── default_value.csv
│   ├── invoice.schema.json
│   ├── metadata-def.json
│   └── rdeconfig.yml
├── temp
└── thumbnail
```
