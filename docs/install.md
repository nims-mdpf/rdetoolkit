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

### 依存関係

本パッケージは、以下のライブラリ群に依存しています。

- [pyproject.toml - nims-dpfc/rdetoolkit](https://github.com/nims-dpfc/rdetoolkit/blob/main/pyproject.toml)
