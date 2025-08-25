# Contributing to RDEToolKit

## コントリビュートの準備

RDEToolKitへのコントリビュートをしていただくには、以下の手順が必要です。

### リポジトリのクローンをローカルに作成する

```shell
cd <任意のディレクトリ>

# SSH
git clone git@github.com:nims-mdpf/rdetoolkit.git
# HTTPS
git clone https://github.com/nims-mdpf/rdetoolkit.git

# ローカルリポジトリに移動
cd rdetoolkit
```

### パッケージ管理ツールのインストール

rdetoolkitでは、`rye`を利用しています。ryeは、Flaskの作者が作成した、Pythonのパッケージ関係管理ツールです。内部実装はRustのため、非常に高速です。poetryを選択せずryeを採用した理由は、動作速度の観点と、`pyenv`を別途利用する必要があるためです。ryeは、`pyenv+poetry`のように、インタプリタの管理とパッケージの管理が統合されているため、メンテナンスの観点からもryeの方が優れているため、こちらを採用しています。

ryeは以下の公式ドキュメントを参考にインストールしてください。

> [Installation - Rye](https://rye-up.com/guide/installation/)

### 開発環境のセットアップ

ryeをインストール後、以下の手順で開発環境をセットアップしてください。`rye sync`で仮想環境が作成され、必要なパッケージが仮想環境にインストールされます。

```shell
cd <rdetoolkitのローカルリポジトリ>
rye sync
```

仮想環境を起動します。

```shell
source .venv/bin/activate
```

また、RDEToolKitではコード品質の観点から、`pre-commit`を採用しています。pre-commitのセットアップを実行するため、以下の処理を実行してください。

```shell
pre-commit install
```

もし、Visaul Stdio Codeを利用する際は、拡張機能`pre-commit`を追加してください。

## Contributing

RDEToolKitでは、以下の2点のコントリビュートを期待しています。下記のドキュメントを参考に、変更・バグレポート・機能修正を実施してください。

- [ドキュメントのコントリビュート](documents_contributing.md)
- [コードベースのコントリビュート](sourcecode_contributing.md)
