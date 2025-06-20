# インストール方法

## PyPIリポジトリからインストール

rdetoolkitのインストール方法は以下の通りです。

=== "Unix/macOS"

    ```shell
    python3 -m pip install rdetoolkit
    python3 -m pip install rdetoolkit==<指定バージョン>
    ```

=== "Windows"

    ```powershell
    py -m pip install rdetoolkit
    py -m pip install rdetoolkit==<指定バージョン>
    ```

### MinIO機能付きインストール

MinIOを利用する場合は、extras オプション `[minio]` を指定してインストールしてください。

=== "Unix/macOS"

```shell
python3 -m pip install "rdetoolkit[minio]"
python3 -m pip install "rdetoolkit[minio]==<指定バージョン>"
```

=== "Windows"

```powershell
py -m pip install "rdetoolkit[minio]"
py -m pip install "rdetoolkit[minio]==<指定バージョン>"
```

### Githubリポジトリからインストール

Githubリポジトリから直接インストールしたい場合や、開発版のパッケージをインストールする場合、リポジトリから直接インストールしてください。

=== "Unix/macOS"

    ```shell
    python3 -m pip install rdetoolkit@git+https://github.com/nims-dpfc/rdetoolkit.git
    ```

=== "Windows"

    ```powershell
    py -m pip install "rdetoolkit@git+https://github.com/nims-dpfc/rdetoolkit.git"
    ```

## 開発者向け: ソースからのビルドとインストール

開発者やカスタマイズが必要なユーザー向けに、ソースコードからビルドしてインストールする手順を説明します。

### 前提条件

以下のソフトウェアがインストールされている必要があります：

- **Python 3.9以上**
- **Rust toolchain** (cargo, rustc)
- **Git**

### 手順

#### 1. リポジトリのクローン

```shell
git clone https://github.com/nims-dpfc/rdetoolkit.git
cd rdetoolkit
```

#### 2. Rust環境のセットアップ

Rustがインストールされていない場合：

=== "Unix/macOS/Linux"

    ```shell
    # Rustのインストール
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    source ~/.cargo/env
    
    # maturinのインストール
    pip install maturin
    ```

=== "Windows"

    ```powershell
    # Rustのインストール（https://rustup.rs/ からダウンロード）
    # または Chocolatey を使用
    choco install rust
    
    # maturinのインストール
    pip install maturin
    ```

#### 3. 依存関係のインストール

```shell
# Python依存関係のインストール
pip install -r requirements.lock
```

#### 4. ビルドとインストール

##### 開発モード（推奨）

開発中は以下のコマンドでビルドとインストールを同時に行います：

```shell
# 開発モードでビルド・インストール
maturin develop

# または editable mode でインストール
pip install -e .
```

##### 配布用ビルド

配布用のwheelファイルを作成する場合：

```shell
# wheelファイルの作成
maturin build --release

# 生成されたwheelファイルをインストール
pip install target/wheels/rdetoolkit-*.whl
```

#### 5. インストールの確認

```shell
# インストールの確認
python -c "import rdetoolkit; print(rdetoolkit.__version__)"

# コマンドラインツールの確認
python -m rdetoolkit --help
```

### トラブルシューティング

#### Rustコンパイルエラー

```
error: Microsoft Visual C++ 14.0 is required (Windows)
```

**解決方法**: Windows の場合、Microsoft C++ Build Tools をインストールしてください。

#### maturinが見つからない

```
maturin: command not found
```

**解決方法**: 
```shell
pip install --upgrade maturin
```

#### Python.hが見つからない

```
fatal error: Python.h: No such file or directory
```

**解決方法**: 
=== "Ubuntu/Debian"
    ```shell
    sudo apt-get install python3-dev
    ```

=== "CentOS/RHEL"
    ```shell
    sudo yum install python3-devel
    ```

=== "macOS"
    ```shell
    xcode-select --install
    ```

### 依存関係

本パッケージは、以下のライブラリ群に依存しています。

- [pyproject.toml - nims-dpfc/rdetoolkit](https://github.com/nims-dpfc/rdetoolkit/blob/main/pyproject.toml)
