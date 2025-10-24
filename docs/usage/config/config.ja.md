# 設定ファイルを作成する方法

## 目的

RDEToolKitの構造化処理動作をカスタマイズするための設定ファイル（`rdeconfig.yaml`）の作成と設定方法について説明します。基本設定から高度な設定まで、段階的に学べます。

## 前提条件

- RDEToolKitの基本的な使用方法の理解
- YAMLファイル形式の基本知識
- 構造化処理のディレクトリ構造の理解

## 設定ファイル要件

- ファイル名: `rdeconfig.yml`, `rdeconfig.yaml`, `pyproject.toml`が使用可能
- 配置場所:
  - YAML形式: `data/tasksupport/`ディレクトリ内
  - `pyproject.toml`はプロジェクトルート
- フォーマット: YAML形式(もしくはTOML形式)

## 手順

### 1. 設定ファイルを配置する

設定ファイルを正しい場所に配置します：

```shell title="設定ファイルの配置場所"
data/
└── tasksupport/
    └── rdeconfig.yaml  # ここに配置
```

### 2. 基本設定を作成する

最小限の設定ファイルを作成します：

```yaml title="基本的なrdeconfig.yaml"
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true
  extended_mode: null
```

### 3. 各設定項目を設定する

#### save_raw設定

- 入力データを`raw`ディレクトリにコピーするかを制御します：
- type: `bool`
- デフォルト: `false`

```yaml title="save_raw設定"
system:
  save_raw: true   # 入力データをrawディレクトリにコピー
  save_raw: false  # 入力データをコピーしない
```

!!! tip "Save Raw Data"
    save_rawの設定をtrueにした場合、下記のsave_nonshared_rawの設定はfalseにしてください。両方trueにすると、save_rawディレクトリと, nonshared_rawディレクトリにコピーされます。

#### save_nonshared_raw設定

- 入力データを`save_nonshared_raw`ディレクトリにコピーするかを制御します：
- type: `bool`
- デフォルト: `false`

```yaml title="save_raw設定"
system:
  save_nonshared_raw: true   # 入力データをsave_nonshared_rawディレクトリにコピー（推奨）
  save_nonshared_raw: false  # 入力データをコピーしない
```

!!! tip "Save Raw Data"
    save_nonshared_rawの設定をtrueにした場合、下記のsave_rawの設定はfalseにしてください。両方trueにすると、save_rawディレクトリと, nonshared_rawディレクトリにコピーされます。

#### magic_variable設定

ファイル名の動的置換機能を制御します。この機能を有効化すると、`${filename}`などのマジック変数が送り状から使用可能となり、データタイル名が登録したデータファイル名に自動で置換されます。

- type: `bool`
- デフォルト: `false`

```yaml title="magic_variable設定"
system:
  magic_variable: true   # ${filename}などの置換を有効化
  magic_variable: false  # 置換機能を無効化（デフォルト）
```

設定を有効化し、送り状から``${filename}``などのマジック変数を使用することで、データタイル名が自動で置換されます。例えば、以下のような送り状と`20250101_sample_data.dat`というデータを登録したとします。

登録時の送り状:

```json
{
  "datasetId": "e66233bf-821a-404c-a584-083ff36bb825",
  "basic": {
      "dateSubmitted": "2025-01-01",
      "dataOwnerId": "010z27x4095x7fx10x5614428108ce53e5628a0b3830987098664533",
      "dataName": "${filename}",
      "instrumentId": "409ada22-108f-42e2-8ba0-e53e5628a0b383098",
      "experimentId": null,
      "description": "",
      "dataset_title": "xrd",
      "dataOwner": "Sample,Username"
  },
  ...
}
```

構造化処理後

```json
{
  "datasetId": "e66233bf-821a-404c-a584-083ff36bb825",
  "basic": {
      "dateSubmitted": "2025-01-01",
      "dataOwnerId": "010z27x4095x7fx10x5614428108ce53e5628a0b3830987098664533",
      "dataName": "20250101_sample_data.dat",
      "instrumentId": "409ada22-108f-42e2-8ba0-e53e5628a0b383098",
      "experimentId": null,
      "description": "",
      "dataset_title": "xrd",
      "dataOwner": "Sample,Username"
  },
  ...
}
```

#### save_thumbnail_image設定

- メイン画像(main_imageディレクトリ)からサムネイル画像の自動生成を制御します
- type: `bool`
- デフォルト: `false`

```yaml title="save_thumbnail_image設定"
system:
  save_thumbnail_image: true   # サムネイル自動生成（推奨）
  save_thumbnail_image: false  # サムネイル生成を無効化
```

#### extended_mode設定

- データ登録モードの拡張を指定します。
- type: `str` | `null`
- デフォルト: `null`
- 選択可能なモード:
  - `null`: 標準モード
  - `rdeformat`: RDEフォーマットモード
  - `MultiDataTile`: マルチデータタイルモード

```yaml title="extended_mode設定"
system:
  extended_mode: null           # 標準モード
  extended_mode: "rdeformat"    # RDEフォーマットモード
  extended_mode: "MultiDataTile" # マルチデータタイルモード
```

モードの詳細については、[データ登録モード](../mode/mode.md)を参照してください。

### 4. 登録モード固有の設定を追加する

#### MultiDataTileでエラーを無視する

> MultiDataTileが有効の場合、この設定は機能します。

- マルチデータタイルモードで、エラーが発生しても処理を継続します。エラーが発生したデータタイルは登録されません。
- type: `bool`
- デフォルト: `false`

```yaml
multidatatile:
  ignore_errors: true # もしくはfalse
```

#### SmartTable設定

> SmartTableが有効の場合、この設定は機能します。

- この設定を有効化すると、データ投入したテーブルデータファイルをデータタイルとして保存します。
- type: `bool`
- デフォルト: `false`

```yaml title="SmartTable設定"
smarttable:
  save_table_file: true
```

### 5. ログやスタックトレースに関する設定を追加する

#### Traceback設定

- LLM/AIフレンドリーなスタックトレース機能の設定
- type: `bool`
- デフォルト: `false`

```yaml title="Traceback設定"
traceback:
  enabled: true                # トレースバック機能の有効/無効
```

**各設定項目の詳細:**

上記の設定で、`enabled`を`true`にすると、以下の詳細設定が可能になります：

- `format`: 出力形式を指定します
  - type: `str`
  - デフォルト: `"duplex"`
  - 選択可能な値: `"compact"`, `"python"`, `"duplex"`
  - `compact`: LLM向けの機械可読形式
  - `python`: 従来のPython標準のスタックトレース形式
  - `duplex`: 両方の形式を同時出力
- `include_context`: ソースコード行の表示を制御します
  - type: `bool`
  - デフォルト: `true`
- `include_locals`: ローカル変数の表示を制御します（セキュリティリスク）
  - type: `bool`
  - デフォルト: `false`
- `include_env`: 環境情報の表示を制御します
  - type: `bool`
  - デフォルト: `true`
- `max_locals_size`: 変数出力のサイズ制限を指定します
  - type: `int`
  - デフォルト: `512`
- `sensitive_patterns`: カスタム機密パターンを指定します
  - type: `list[str]`
  - デフォルト: `[]` (空のリスト)

```yaml title="Traceback設定"
traceback:
  enabled: true
  format: "duplex"             # 出力形式：compact, python, duplex
  include_context: true        # ソースコード行の表示
  include_locals: false        # ローカル変数の表示（セキュリティリスク）
  include_env: true            # 環境情報の表示
  max_locals_size: 512         # 変数出力のサイズ制限
  sensitive_patterns:          # カスタム機密パターン
    - "database_url"
    - "private_key"
    - "connection_string"
```

## 設定例集

以下の`rdeconfig.yml`の設定例を参考に、適宜カスタマイズしてください。

### 標準的な設定(送り状登録モード)

```yaml
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true
```

### 登録データ(生データ)を非公開ディレクトリに登録する

```yaml
system:
  save_nonshared_raw: true
  magic_variable: false
  save_thumbnail_image: true
```

### 複数データ登録モードの設定(MultiDataTile)

```yaml
system:
  save_raw: true
  magic_variable: true
  save_thumbnail_image: true
  extended_mode: "MultiDataTile"
```

### システム間の連系(RDEFormatモード)

```yaml
system:
  extended_mode: "rdeformat"
```

### AIエージェント連携

```yaml title="AIエージェント設定例"
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true

traceback:
  enabled: true
  format: "compact"            # 機械可読のみ
  include_context: true        # AI解析用ソースコード
  include_locals: false        # セキュリティ重視
  include_env: false           # 最小限の情報
  max_locals_size: 0           # 本番環境では変数なし
  sensitive_patterns:
    - "database_url"
    - "private_key"
    - "connection_string"
    - "encryption_key"
```

## 関連情報

設定ファイルについてさらに学ぶには、以下のドキュメントを参照してください：

- [処理モード](../mode/mode.ja.md)で各extended_modeの詳細を確認する
- [Magic Variable機能](magic_variable.ja.md)で動的置換機能を学ぶ
- [構造化処理の概念](../structured_process/structured.ja.md)で設定が影響する処理フローを理解する
- [LLM/AI向けトレースバック設定](../structured_process/traceback.ja.md)でスタックトレース機能を学ぶ
