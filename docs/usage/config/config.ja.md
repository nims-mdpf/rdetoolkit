# 設定ファイルを作成する方法

## 目的

RDEToolKitの構造化処理動作をカスタマイズするための設定ファイル（`rdeconfig.yaml`）の作成と設定方法について説明します。基本設定から高度な設定まで、段階的に学べます。

## 前提条件

- RDEToolKitの基本的な使用方法の理解
- YAMLファイル形式の基本知識
- 構造化処理のディレクトリ構造の理解

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

入力データを`raw`ディレクトリにコピーするかを制御します：

```yaml title="save_raw設定"
system:
  save_raw: true   # 入力データをrawディレクトリにコピー（推奨）
  save_raw: false  # 入力データをコピーしない
```

!!! tip "推奨設定"
    データの追跡性を確保するため、`save_raw: true`を推奨します。

#### magic_variable設定

ファイル名の動的置換機能を制御します：

```yaml title="magic_variable設定"
system:
  magic_variable: true   # ${filename}などの置換を有効化
  magic_variable: false  # 置換機能を無効化（デフォルト）
```

使用例：
```json title="magic_variable使用例"
{
  "data_name": "${filename}",
  "output_file": "${filename}_processed.csv"
}
```

#### save_thumbnail_image設定

メイン画像からサムネイル画像の自動生成を制御します：

```yaml title="save_thumbnail_image設定"
system:
  save_thumbnail_image: true   # サムネイル自動生成（推奨）
  save_thumbnail_image: false  # サムネイル生成を無効化
```

#### extended_mode設定

高度な処理モードを指定します：

```yaml title="extended_mode設定"
system:
  extended_mode: null           # 標準モード
  extended_mode: "rdeformat"    # RDEフォーマットモード
  extended_mode: "MultiDataTile" # マルチデータタイルモード
```

### 4. 高度な設定を追加する

#### MultiDataTile設定

複数データタイルを統合管理する場合の設定：

```yaml title="MultiDataTile設定"
system:
  extended_mode: "MultiDataTile"

multidatatile:
  divided_dir_digit: 4
  divided_dir_start_number: 1
```

#### SmartTable設定

SmartTable機能を使用する場合の設定：

```yaml title="SmartTable設定"
smarttable:
  generate_template: true
  template_name: "smarttable_template.xlsx"
  auto_fill_metadata: true
```

### 5. 設定ファイルの検証

作成した設定ファイルが正しいかを確認します：

```python title="設定ファイル検証"
import yaml

def validate_config_file(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 必須項目の確認
        if 'system' not in config:
            print("❌ systemセクションが見つかりません")
            return False
        
        system = config['system']
        required_fields = ['save_raw', 'magic_variable', 'save_thumbnail_image']
        
        for field in required_fields:
            if field not in system:
                print(f"❌ 必須フィールドが不足: {field}")
                return False
        
        print("✅ 設定ファイルは有効です")
        return True
        
    except yaml.YAMLError as e:
        print(f"❌ YAML形式エラー: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ 設定ファイルが見つかりません: {config_path}")
        return False
```

## 結果の確認

設定が正しく適用されているかを確認します：

### 設定値の確認

```python title="設定値確認"
def check_applied_settings():
    from rdetoolkit.models.config import Config
    
    # 設定の読み込み
    config = Config.from_file("data/tasksupport/rdeconfig.yaml")
    
    print(f"save_raw: {config.system.save_raw}")
    print(f"magic_variable: {config.system.magic_variable}")
    print(f"save_thumbnail_image: {config.system.save_thumbnail_image}")
    print(f"extended_mode: {config.system.extended_mode}")
```

### 動作確認

```shell title="動作確認コマンド"
# 構造化処理を実行して設定が反映されるかテスト
python main.py

# ログファイルで設定値を確認
grep -i "config" data/logs/rdesys.log
```

## 設定例集

### 標準的な研究データ処理

```yaml title="標準設定例"
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true
  extended_mode: null
```

### 大量データ一括処理

```yaml title="一括処理設定例"
system:
  save_raw: true
  magic_variable: true
  save_thumbnail_image: false
  extended_mode: "MultiDataTile"

multidatatile:
  divided_dir_digit: 4
  divided_dir_start_number: 1
```

### 既存データ移行

```yaml title="移行設定例"
system:
  save_raw: false
  magic_variable: false
  save_thumbnail_image: true
  extended_mode: "rdeformat"
```

## 関連情報

設定ファイルについてさらに学ぶには、以下のドキュメントを参照してください：

- [処理モード](mode.ja.md)で各extended_modeの詳細を確認する
- [Magic Variable機能](magic_variable.ja.md)で動的置換機能を学ぶ
- [構造化処理の概念](../structured_process/structured.ja.md)で設定が影響する処理フローを理解する
