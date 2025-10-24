# API リファレンス

## 目的

このセクションでは、RDEToolKitの全機能に関する技術仕様を提供します。各モジュールの詳細な機能、パラメータ、返り値、使用例を含む包括的なリファレンスです。

## API ドキュメントの構成

RDEToolKitのAPIドキュメントは、ハイブリッド方式で構成されています：

- **自動生成部分**: ソースコード内のdocstringから生成される詳細な技術仕様
- **手動作成部分**: 実践的な使用例とモジュール間の連携方法

## 主要モジュール

### ワークフロー管理

- [workflows](../rdetoolkit/workflows.md) - 構造化処理の実行とワークフロー管理
- [modeproc](../rdetoolkit/modeproc.md) - モード処理

### 設定とファイル操作

- [config](../rdetoolkit/config.md) - 設定ファイルの読み込みと管理
- [fileops](../rdetoolkit/fileops.md) - RDE関連のファイル操作

### データ処理

- [invoicefile](../rdetoolkit/invoicefile.md) - 送り状ファイルの処理
- [validation](../rdetoolkit/validation.md) - データの検証
- [rde2util](../rdetoolkit/rde2util.md) - RDE関連のユーティリティ関数

### 代表画像操作

- [img2thumb](../rdetoolkit/img2thumb.md) - 画像をサムネイルに変換

### エラー処理とログ

- [rdelogger](../rdetoolkit/rdelogger.md) - ロギング機能
- [errors](../rdetoolkit/errors.md) - エラーハンドリング
- [exceptions](../rdetoolkit/exceptions.md) - 例外処理

## データモデル

### 設定モデル

- [models.config](../rdetoolkit/models/config.md) - 設定データの構造定義

### RDE関連モデル

- [models.rde2types](../rdetoolkit/models/rde2types.md) - RDE関連の型定義
- [models.invoice](../rdetoolkit/models/invoice_schema.md) - 送り状データの構造
- [models.metadata](../rdetoolkit/models/metadata.md) - メタデータの管理

### 処理結果モデル

- 処理結果の管理機能は各モジュールに統合されています

## 実装モジュール

### コントローラー

- [impl.input_controller](../rdetoolkit/impl/input_controller.md) - 入力モードの管理
- [impl.compressed_controller](../rdetoolkit/impl/compressed_controller.md) - 圧縮ファイルの管理

### インターフェース

- [interface.filechecker](../rdetoolkit/interface/filechecker.md) - ファイル検証インターフェース

### コマンドライン

- [CLIコマンド](../usage/cli.ja.md) - コマンドライン機能の使用方法

## 使用パターン

### 基本的な使用方法

```python title="basic_usage.py"
import rdetoolkit
from rdetoolkit.models.rde2types import RdeDatasetPaths


def my_dataset_function(paths: RdeDatasetPaths) -> None:
    # カスタム処理をここに実装
    pass


# 構造化処理の実行
result = rdetoolkit.workflows.run(custom_dataset_function=my_dataset_function)
```

> 互換性のため、`RdeInputDirPaths` と `RdeOutputResourcePath` の 2 引数スタイルも引き続き利用できます。
> `paths.invoice` / `paths.invoice_org` / `paths.metadata_def_json` といった
> プロパティで主要なパスを直接取得できます。

### 設定ファイルの使用

```python title="config_usage.py"
from rdetoolkit.config import parse_config_file

# 設定ファイルの読み込み
config = parse_config_file()

# 設定値の参照
extended_mode = config.system.extended_mode
save_raw = config.system.save_raw
```

### エラーハンドリング

```python title="error_handling.py"
from rdetoolkit.exceptions import RdeToolkitError
from rdetoolkit import workflows

try:
    result = workflows.run(custom_dataset_function=my_function)
except RdeToolkitError as e:
    print(f"RDEToolKit エラー: {e}")
    print(f"エラーコード: {e.error_code}")
```

## API バージョン情報

| バージョン | 互換性 | 主な変更点 |
|------------|--------|------------|
| 1.0.x | 安定版 | 初期リリース |
| 1.1.x | 後方互換 | 新機能追加 |
| 1.2.x | 後方互換 | パフォーマンス改善 |

!!! note "API の安定性"
    メジャーバージョン内では後方互換性を維持します。破壊的変更はメジャーバージョンアップ時にのみ行われます。

## 開発者向け情報

### 型ヒント

RDEToolKitは完全な型ヒントをサポートしています：

```python title="type_hints.py"
from typing import Optional
from rdetoolkit.models.rde2types import RdeDatasetPaths


def process_data(paths: RdeDatasetPaths, options: Optional[dict] = None) -> bool:
    # 型安全な実装
    return True
```


## 次のステップ

- 特定のモジュールの詳細: 上記のモジュールリンクを参照
- 実践的な使用例: [ユーザーガイド](../user-guide/index.ja.md)
- 開発への参加: [開発者ガイド](../development/index.ja.md)
