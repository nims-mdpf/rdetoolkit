# 設定ファイルを使用する方法

## 目的

このガイドでは、RDEToolKitの動作を制御する設定ファイルの作成と使用方法を説明します。設定ファイルを適切に構成することで、処理モードの選択、ファイル保存の制御、カスタム設定の定義が可能になります。

## 前提条件

設定ファイルを使用する前に、以下を確認してください：

- RDEToolKitがインストール済みであること
- プロジェクトディレクトリが作成済みであること
- 基本的なYAMLまたはTOML形式の知識

## 手順

### 1. 設定ファイルを作成する

RDEToolKitは、以下の場所とファイル名で設定ファイルを自動検索します：

#### サポートされるファイル名と場所

| ファイル名 | 配置場所 | 形式 |
|------------|----------|------|
| `rdeconfig.yaml` | `tasksupport/` または プロジェクト直下 | YAML |
| `rdeconfig.yml` | `tasksupport/` または プロジェクト直下 | YAML |
| `pyproject.toml` | プロジェクト直下 | TOML |

!!! tip "推奨配置"
    プロジェクト固有の設定は `tasksupport/rdeconfig.yaml` に、開発環境全体の設定は `pyproject.toml` に配置することを推奨します。

### 2. 基本設定を定義する

#### 処理モードの設定

=== "YAML形式"
    ```yaml title="tasksupport/rdeconfig.yaml"
    system:
      # 拡張モードの指定
      extended_mode: 'MultiDataTile'  # または 'rdeformat'
      
      # ファイル保存設定
      save_raw: true
      save_nonshared_raw: true
      
      # 機能の有効/無効
      magic_variable: true
      save_thumbnail_image: true
    ```

=== "TOML形式"
    ```toml title="pyproject.toml"
    [tool.rdetoolkit.system]
    extended_mode = 'MultiDataTile'
    save_raw = true
    save_nonshared_raw = true
    magic_variable = true
    save_thumbnail_image = true
    ```

#### 設定項目の詳細

| 設定項目 | 型 | デフォルト値 | 説明 |
|----------|----|-----------|----|
| `extended_mode` | string | なし | 拡張モード（'MultiDataTile' または 'rdeformat'） |
| `save_raw` | boolean | false | `raw`ディレクトリへの入力ファイル保存 |
| `save_nonshared_raw` | boolean | true | `nonshared_raw`ディレクトリへの入力ファイル保存 |
| `magic_variable` | boolean | false | Magic Variable機能の有効化 |
| `save_thumbnail_image` | boolean | false | サムネイル画像の自動生成 |

### 3. 処理モード別の設定

#### invoiceモード（デフォルト）

```yaml title="tasksupport/rdeconfig.yaml"
system:
  magic_variable: true
  save_thumbnail_image: true
```

#### マルチデータタイルモード

```yaml title="tasksupport/rdeconfig.yaml"
system:
  extended_mode: 'MultiDataTile'
  
multidata_tile:
  ignore_errors: true  # エラー時の処理継続
```

#### RDEフォーマットモード

```yaml title="tasksupport/rdeconfig.yaml"
system:
  extended_mode: 'rdeformat'
  save_raw: false
  save_nonshared_raw: false
```

### 4. カスタム設定を追加する

独自の設定値を定義して、構造化処理内で参照できます：

=== "YAML形式"
    ```yaml title="tasksupport/rdeconfig.yaml"
    custom:
      # 画像処理設定
      thumbnail_image_name: "inputdata/sample_image.png"
      image_quality: 85
      max_image_size: 1920
      
      # データ処理設定
      analysis_parameters:
        threshold: 0.5
        iterations: 100
      
      # 出力設定
      output_format: "csv"
      include_metadata: true
    ```

=== "TOML形式"
    ```toml title="pyproject.toml"
    [tool.rdetoolkit.custom]
    thumbnail_image_name = "inputdata/sample_image.png"
    image_quality = 85
    max_image_size = 1920
    output_format = "csv"
    include_metadata = true
    
    [tool.rdetoolkit.custom.analysis_parameters]
    threshold = 0.5
    iterations = 100
    ```

### 5. 構造化処理内で設定を参照する

作成した設定値を構造化処理関数内で使用する方法：

```python title="modules/process.py"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # システム設定の参照
    extended_mode = srcpaths.config.system.extended_mode
    save_raw = srcpaths.config.system.save_raw
    magic_variable = srcpaths.config.system.magic_variable
    
    print(f"処理モード: {extended_mode}")
    print(f"Raw保存: {save_raw}")
    print(f"Magic Variable: {magic_variable}")
    
    # カスタム設定の参照
    if hasattr(srcpaths.config, 'custom'):
        custom_config = srcpaths.config.custom
        
        # 画像設定の取得
        thumbnail_name = custom_config.get('thumbnail_image_name')
        image_quality = custom_config.get('image_quality', 75)
        
        # 解析パラメータの取得
        analysis_params = custom_config.get('analysis_parameters', {})
        threshold = analysis_params.get('threshold', 0.5)
        
        print(f"サムネイル画像: {thumbnail_name}")
        print(f"画像品質: {image_quality}")
        print(f"閾値: {threshold}")
```

## 結果の確認

### 設定ファイルの読み込み確認

設定が正しく読み込まれているかを確認する方法：

```python title="test_config.py"
from rdetoolkit.config import parse_config_file

# 設定ファイルの読み込みテスト
config = parse_config_file()

print("=== 設定確認 ===")
print(f"拡張モード: {config.system.extended_mode}")
print(f"Raw保存: {config.system.save_raw}")
print(f"Magic Variable: {config.system.magic_variable}")

if hasattr(config, 'custom'):
    print(f"カスタム設定: {config.custom}")
```

### 設定の優先順位

複数の設定ファイルが存在する場合の優先順位：

1. `tasksupport/rdeconfig.yaml`
2. `tasksupport/rdeconfig.yml`
3. `./rdeconfig.yaml`
4. `./rdeconfig.yml`
5. `./pyproject.toml`

!!! warning "設定の競合"
    同じ設定項目が複数のファイルに定義されている場合、優先順位の高いファイルの設定が使用されます。

## トラブルシューティング

### よくある問題と解決方法

#### YAML構文エラー

```
ERROR: YAML parsing failed
```

**解決方法**: YAML構文を確認する
```yaml
# 正しい例
system:
  extended_mode: 'MultiDataTile'
  save_raw: true

# 間違った例（インデントエラー）
system:
extended_mode: 'MultiDataTile'
save_raw: true
```

#### 設定値が反映されない

**確認事項**:
1. ファイル名のスペルミス
2. ファイルの配置場所
3. YAML/TOMLの構文エラー
4. 設定項目名の間違い

#### カスタム設定にアクセスできない

```python title="safe_config_access.py"
def safe_get_custom_config(config, key, default=None):
    """安全にカスタム設定を取得する"""
    if hasattr(config, 'custom') and key in config.custom:
        return config.custom[key]
    return default

# 使用例
thumbnail_name = safe_get_custom_config(
    srcpaths.config, 
    'thumbnail_image_name', 
    'default_thumbnail.png'
)
```

## 関連情報

設定ファイルの詳細な仕様については：

- [Magic Variables](#magic-variable機能) - 動的メタデータ置換機能の詳細
- [API リファレンス](../api/index.ja.md) - 設定関連のAPI仕様
