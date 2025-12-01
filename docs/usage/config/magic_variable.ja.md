# Magic Variable機能とは

## 目的

RDEToolKitのMagic Variable機能について説明します。ファイル名やタイムスタンプなどの動的な値を自動的に置換する仕組みと設定方法を理解できます。

## 課題と背景

構造化処理において、以下のような課題がありました：

- **ファイル名の手動入力**: メタデータにファイル名を手動で記入する必要があった
- **一貫性の維持**: 複数のエントリで同じファイル名を正確に記入することが困難
- **効率性の問題**: 大量のファイルを処理する際の作業時間の増大
- **動的値の管理**: タイムスタンプや計算値などの動的な値の管理が複雑

これらの課題を解決するために、Magic Variable機能が開発されました。

## Magic Variableの使い方

RDEデータ登録時に、`サポートされる変数`記載の変数を指定すると、ルールに従ってRDE構造化処理内でデータセット名が自動補完されます。

ローカルでテストする際は、invoice.jsonに事前にMagic Variableを設定してください。(後述)

![docs/img/magic_filename.svg]

## サポートされる変数

| 変数名                           | 説明                                                                                | 例                                             |
| -------------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------- |
| `${filename}`                    | 拡張子を含んだ元ファイル名                                                          | `sample.csv` → `sample.csv`                    |
| `${invoice:basic:<field>}`       | `invoice_org` の `basic` 配下の値                                                   | `${invoice:basic:experimentId}` → `EXP-42`     |
| `${invoice:custom:<field>}`      | `invoice_org` の `custom` 配下の値                                                  | `${invoice:custom:batch}` → `B-9`              |
| `${invoice:sample:names}`        | `sample.names` に含まれる空でない文字列を `_` で連結                                | `["alpha", "", "beta"]` → `alpha_beta`         |
| `${metadata:constant:<field>}`   | `metadata.json` (`paths.meta / metadata.json`) の `constant.<field>.value` の値     | `${metadata:constant:project_code}` → `PRJ01`  |

> **注意:** `metadata:variable:<field>` は実行時に値が変化するため、Magic Variableではサポートしません。

### 送り状定義の変数を指定する場合

Invoice関連の参照は常に `invoice_org` を対象にし、ユーザーが入力した値をそのまま利用します。存在しないフィールドを参照すると `StructuredError` が発生し、値が空文字のときは警告を記録した上で置換をスキップし、連続した `_` が出ないよう自動調整します。

- `basic` 配下では `experimentId` や `dateSubmitted` などを再利用できます。
- `custom` 配下では `invoice.schema.json` で定義した任意のキーが対象です。
- `sample.names` は空でない要素だけを `_` で連結します。配列が空の場合はエラーになります。

## メタデータ定数を指定する場合

`${metadata:constant:<field>}` は `RdeDatasetPaths.meta / metadata.json` に保存された `constant` の値を参照します。ファイルやキーが存在しない場合は `StructuredError` が発生し、ワークフローは中断されます。

## 設定方法

### 1. 設定ファイルでの有効化

`rdeconfig.yaml`でMagic Variable機能を有効にします：

```yaml title="rdeconfig.yaml"
system:
  magic_variable: true
```

### 2. JSONファイルでの使用

メタデータファイルや送り状で複数の変数を組み合わせます：

```json title="invoice.json"
{
  "basic": {
    "experimentId": "EXP-42",
    "dataName": "${invoice:basic:experimentId}_${metadata:constant:project_code}_${invoice:sample:names}_${filename}"
  },
  "custom": {
    "batch": "B-9"
  },
  "sample": {
    "names": ["alpha", "", "beta"]
  }
}
```

### 3. 処理結果の確認

`metadata.json` に `{"constant": {"project_code": {"value": "PRJ01"}}}` が含まれている場合、以下のように置換されます：

```json title="処理後のinvoice.json"
{
  "basic": {
    "experimentId": "EXP-42",
    "dataName": "EXP-42_PRJ01_alpha_beta_sample.csv"
  },
  "custom": {
    "batch": "B-9"
  },
  "sample": {
    "names": ["alpha", "", "beta"]
  }
}
```

存在しないフィールドを参照した場合は例外が発生し、値が空文字のときは警告が出力されて置換はスキップされます（`__` のような連続したアンダースコアは自動的に抑制されます）。

## まとめ

Magic Variable機能の主要な特徴：

- **自動化**: ファイル名やタイムスタンプの自動置換
- **一貫性**: 複数エントリでの情報の一貫性確保
- **効率性**: 手動入力作業の大幅削減
- **コンテキスト活用**: Invoiceの `basic/custom/sample.names` や `metadata.json` の値を動的に組み合わせ可能

## 次のステップ

Magic Variable機能をさらに活用するために、以下のドキュメントを参照してください：

- [設定ファイル](config.ja.md)で詳細な設定方法を学ぶ
- [構造化処理の概念](../structured_process/structured.ja.md)で処理フローを理解する
- [メタデータ定義ファイル](../metadata_definition_file.ja.md)でメタデータ設計を確認する
