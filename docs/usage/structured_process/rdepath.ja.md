# ディレクトリパスを取得する方法

## 目的

RDE構造化処理でファイルの読み書きを行うためのディレクトリパス管理について説明します。`RdeInputDirPaths`と`RdeOutputResourcePath`を統合した`RdeDatasetPaths`が追加されており、新規実装ではこのクラスを利用することを推奨します。既存コードとの後方互換性のため、従来のクラスも引き続き利用できます。

## 推奨: `RdeDatasetPaths` を使う

`RdeDatasetPaths`は入力系と出力系のパスを1つのオブジェクトにまとめ、データセット関数を単一引数で扱えるようにします。設定や補助ファイルへのアクセスも同じインターフェースで利用できるため、コールバックの実装をシンプルに保てます。

### データセット関数の基本形

```python title="推奨シグネチャ"
from rdetoolkit.models.rde2types import RdeDatasetPaths


def dataset(paths: RdeDatasetPaths) -> None:
    # 入力ファイル一覧の取得
    for csv_file in paths.inputdata.glob("*.csv"):
        print(f"入力CSV: {csv_file}")

    # 生成した構造化データの保存先
    struct_dir = paths.struct
    print(f"構造化データ出力: {struct_dir}")
```

### 利用できる主なプロパティ

- `paths.inputdata`: 入力データディレクトリ。`Path.glob()`などの操作が可能です。
- `paths.invoice`: 入力側の`invoice`ディレクトリ。
- `paths.tasksupport`: `metadata-def.json`等の補助データが格納されているディレクトリ。
- `paths.struct`: 構造化データの出力先。
- `paths.meta`: メタデータの出力先。
- `paths.rawfiles`: 1データタイル単位で入力ファイル群が格納される。また各種モードを解釈した状態でパスが格納される。`divided`ディレクトリを考慮したパスなどが格納されます。
- `paths.raw` / `paths.nonshared_raw`: 生データの保存先。
- `paths.main_image`・`paths.other_image`・`paths.thumbnail`: 画像系出力先。
- `paths.logs`: ログファイルの保存先。
- `paths.metadata_def_json`: `tasksupport/metadata-def.json`へのショートカット。

### 例: 入力ファイルを読み込む

```python title="RdeDatasetPathsでの読み込み"
import pandas as pd
from rdetoolkit.models.rde2types import RdeDatasetPaths


def read_inputs(paths: RdeDatasetPaths) -> None:
    # rawfilesには構造化対象の入力ファイルがまとまっている
    for source in paths.rawfiles:
        df = pd.read_csv(source)
        print(f"{source.name} 読み込み完了: {df.shape}")
```

### 例: 出力先に保存する

```python title="RdeDatasetPathsでの保存"
import json
from rdetoolkit.models.rde2types import RdeDatasetPaths


def save_results(paths: RdeDatasetPaths, payload: dict) -> None:
    output_path = paths.struct / "results.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta_path = paths.meta / "metadata.json"
    meta_path.write_text(
        json.dumps({"count": len(payload)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

## 互換性とレガシースタイル

既存のコードでは`RdeInputDirPaths`と`RdeOutputResourcePath`を別々に受け取るケースがあります。後方互換性のため旧シグネチャはサポートされていますが、新規の構造化処理では`RdeDatasetPaths`の単一引数スタイルを採用してください。

### 旧シグネチャの使用例

```python title="旧実装の例（メンテナンス用途のみ推奨）"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    print(srcpaths.inputdata)
    print(resource_paths.struct)
```

### `RdeDatasetPaths`から旧引数を取り出す

既存のヘルパー関数やモジュールに引数を渡す場合は、`as_legacy_args()`で2つのオブジェクトに分割できます。

```python title="レガシーAPIとの橋渡し"
from rdetoolkit.models.rde2types import RdeDatasetPaths


def dataset(paths: RdeDatasetPaths) -> None:
    srcpaths, resource_paths = paths.as_legacy_args()
    legacy_dataset(srcpaths, resource_paths)
```

## 操作結果の確認

`RdeDatasetPaths`は従来通りファイル数や存在確認にも利用できます。

```python title="出力ディレクトリの確認"
from rdetoolkit.models.rde2types import RdeDatasetPaths


def verify_outputs(paths: RdeDatasetPaths) -> None:
    for name, directory in {
        "structured": paths.struct,
        "meta": paths.meta,
        "raw": paths.raw,
        "main_image": paths.main_image,
    }.items():
        if directory.exists():
            print(f"{name} ディレクトリ: {len(list(directory.iterdir()))} 件")
        else:
            print(f"⚠️ {name} ディレクトリが存在しません")
```

## 関連情報

- [構造化処理の概念](structured.ja.md)
- [ディレクトリ構造仕様](directory.ja.md)
- [エラーハンドリング](errorhandling.ja.md)
