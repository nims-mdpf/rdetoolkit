# RDEToolKitをインストールする方法

## 目的

このガイドでは、RDEToolKitをPython環境にインストールする手順を説明します。開発環境とプロダクション環境の両方に対応した複数のインストール方法を提供します。

## 前提条件

RDEToolKitをインストールする前に、以下の要件を満たしていることを確認してください：

- **Python**: バージョン 3.9 以上 (Python 3.10以降を推奨)
- **pip**: 最新版を推奨
- **インターネット接続**: PyPIからのパッケージダウンロードに必要

!!! warning "Python 3.9非推奨のお知らせ"
    **重要**: Python 3.9のサポートは非推奨となり、rdetoolkit v2.0 (2025年Q4以降を予定) で削除されます。Python 3.9はrdetoolkit 1.x系では引き続き動作しますが、インポート時に`DeprecationWarning`が表示されます。

    **推奨アクション**: 将来のrdetoolkitリリースとの互換性を確保するため、Python 3.10以降へのアップグレードを計画してください。

    **サポート状況**:

    - Python 3.9: 非推奨 (警告が表示されます)
    - Python 3.10以降: 完全サポート

!!! tip "Python環境の確認"
    現在のPython環境を確認するには、以下のコマンドを実行してください：
    ```bash
    python --version
    pip --version
    ```

## 手順

### 1. 標準インストール

最も一般的なインストール方法です。PyPIからの安定版をインストールします。

=== "Unix/macOS"
    ```bash title="terminal"
    pip install rdetoolkit
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install rdetoolkit
    ```

### 2. MinIOサポート付きインストール

オブジェクトストレージ（MinIO）機能を使用する場合は、追加の依存関係をインストールします。

=== "Unix/macOS"
    ```bash title="terminal"
    pip install 'rdetoolkit[minio]'
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install 'rdetoolkit[minio]'
    ```

### 3. Plotlyサポート付きインストール

Plotlyは、Pythonなどでインタラクティブなグラフやダッシュボード（Webブラウザ上で動的操作可能）を生成する可視化ライブラリ。RDEToolKitでPlotly機能を使用する場合は、追加の依存関係をインストールします。

=== "Unix/macOS"
    ```bash title="terminal"
    pip install 'rdetoolkit[plotly]'
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install 'rdetoolkit[plotly]'
    ```

### 4. 開発版インストール

最新の開発版を使用する場合は、GitHubリポジトリから直接インストールします。

=== "Unix/macOS"
    ```bash title="terminal"
    pip install git+https://github.com/nims-mdpf/rdetoolkit.git
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install git+https://github.com/nims-mdpf/rdetoolkit.git
    ```

!!! warning "開発版の注意事項"
    開発版は不安定な場合があります。プロダクション環境では安定版の使用を推奨します。

### 5. 仮想環境でのインストール

プロジェクトごとに独立した環境を作成する場合の手順です。

=== "venv使用"
    ```bash title="terminal"
    # 仮想環境を作成
    python -m venv rde_env

    # 仮想環境を有効化
    source rde_env/bin/activate  # Unix/macOS
    # rde_env\Scripts\activate  # Windows

    # RDEToolKitをインストール
    pip install rdetoolkit
    ```

=== "conda使用"
    ```bash title="terminal"
    # 新しい環境を作成
    conda create -n rde_env python=3.9

    # 環境を有効化
    conda activate rde_env

    # RDEToolKitをインストール
    pip install rdetoolkit
    ```

## 結果の確認

インストールが正常に完了したかを確認します。

### インストール確認

```python title="python_console"
import rdetoolkit
print(rdetoolkit.__version__)
```

期待される出力例：
```
1.2.3
```

### 基本機能テスト

```python title="test_installation.py"
from rdetoolkit import workflows
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

# 基本的なインポートが成功することを確認
print("RDEToolKit installation successful!")
```

## トラブルシューティング

#### 依存関係の競合

```bash
ERROR: pip's dependency resolver does not currently take into account all the packages
```

**解決方法**: 仮想環境を使用する
```bash title="terminal"
python -m venv clean_env
source clean_env/bin/activate
pip install rdetoolkit
```

## 関連情報

インストール完了後の次のステップ：

- [クイックスタート](quick-start.ja.md) - 最初の構造化処理を実行
- [設定ファイル](user-guide/config.ja.md) - 動作設定のカスタマイズ
- [API リファレンス](api/index.ja.md) - 詳細な機能説明
