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

## 主要コンセプト

### Magic Variableの仕組み

```mermaid
flowchart LR
    A[JSONファイル] --> B[${filename}]
    C[実際のファイル名] --> D[sample.csv]
    B --> E[置換処理]
    D --> E
    E --> F[sample.csv]
```

### サポートされる変数

| 変数名        | 説明                     | 例                      |
| ------------- | ------------------------ | ----------------------- |
| `${filename}` | 拡張子を除いたファイル名 | `sample.csv` → `sample` |

## 設定方法

### 1. 設定ファイルでの有効化

`rdeconfig.yaml`でMagic Variable機能を有効にします：

```yaml title="rdeconfig.yaml"
system:
  magic_variable: true
```

### 2. JSONファイルでの使用

メタデータファイルやその他のJSONファイルで変数を使用します：

```json title="metadata.json"
{
  "data_name": "${filename}",
}
```

### 3. 処理結果の確認

Magic Variable機能が有効な場合、以下のように置換されます：

```json title="処理後のmetadata.json"
{
  "data_name": "sample.csv",
}
```

## まとめ

Magic Variable機能の主要な特徴：

- **自動化**: ファイル名やタイムスタンプの自動置換
- **一貫性**: 複数エントリでの情報の一貫性確保
- **効率性**: 手動入力作業の大幅削減
- **動的値**: タイムスタンプや日付の動的生成

## 次のステップ

Magic Variable機能をさらに活用するために、以下のドキュメントを参照してください：

- [設定ファイル](config.ja.md)で詳細な設定方法を学ぶ
- [構造化処理の概念](../structured_process/structured.ja.md)で処理フローを理解する
- [メタデータ定義ファイル](../metadata_definition_file.ja.md)でメタデータ設計を確認する
