# DockerでRDEToolKitを使用する方法

## 概要

RDEToolKitを使った構造化処理をDocker上で動作させる方法について説明します。Dockerを使用することで、環境の一貫性を保ち、デプロイメントを簡素化できます。

## 前提条件

- Docker Desktop または Docker Engine がインストールされていること
- 基本的なDockerコマンドの知識
- RDEToolKitプロジェクトの基本構造の理解

## ディレクトリ構造

構造化処理プロジェクトの推奨ディレクトリ構造：

```shell
(構造化プロジェクトディレクトリ)
├── container
│   ├── data/
│   ├── modules/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── inputdata
│   ├── input1
│   └── input2
├── README.md
└── template
    ├── batch.yaml
    ├── catalog.schema.json
    ├── invoice.schema.json
    ├── jobs.template.yaml
    ├── metadata-def.json
    └── tasksupport
```

## Dockerfileの作成

`container/Dockerfile`を作成します。以下は基本的なDockerfileの例です：

```dockerfile title="container/Dockerfile"
FROM python:3.11.9

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY main.py /app
COPY modules/ /app/modules/
```

!!! tip "カスタマイズ"
    使用するDockerイメージや各種実行文は、各プロジェクトの要件に応じて自由に変更してください。

!!! note "参考資料"
    [Docker Hub Container Image Library](https://hub.docker.com/)でベースイメージを探すことができます。

## イメージのビルド

### 基本的なビルド

`Dockerfile`が配置されているディレクトリに移動して、docker buildコマンドを実行します：

```bash title="イメージビルド"
# 基本コマンド
docker build -t イメージ名:タグ パス

# 実行例
docker build -t sample_tif:v1 .
```

### オプション説明

- `-t`オプション: イメージ名とタグを指定します。イメージ名は任意ですが、一意であることが望ましいです。
- パス: `Dockerfile`が存在するディレクトリのパスを指定します。カレントディレクトリの場合は`.`を指定します。

### プロキシ環境での対応

プロキシ環境下でビルドする場合は、以下のオプションを追加してください：

```bash title="プロキシ環境でのビルド"
docker build -t sample_tif:v1 \
  --build-arg http_proxy=http://proxy.example.com:8080 \
  --build-arg https_proxy=http://proxy.example.com:8080 \
  .
```

## pipコマンドエラーの対処法

pipコマンドでSSL証明書エラーが発生する場合の対処法：

### pip.confファイルの作成

Dockerfileと同じ階層に`pip.conf`ファイルを作成します：

```ini title="pip.conf"
[install]
trusted-host =
    pypi.python.org
    files.pythonhosted.org
    pypi.org
```

### Dockerfileの修正

pip.confを使用するようにDockerfileを修正します：

```dockerfile title="修正後のDockerfile"
FROM python:3.11

WORKDIR /app

COPY requirements.txt .
COPY pip.conf /etc/pip.conf

RUN pip install -r requirements.txt

COPY main.py /app
COPY modules/ /app/modules/
```

## Dockerコンテナの実行

### 基本的な実行方法

ビルドしたイメージを実行するには、`docker run`コマンドを使用します：

```bash title="コンテナ実行"
# 基本コマンド
docker run [オプション] イメージ名 [コマンド]

# 実行例
docker run -it -v ${HOME}/sample_tif/container/data:/app2/data --name "sample_tifv1" sample_tif:v1 "/bin/bash"
```

### オプション詳細

| オプション | 説明 |
|-----------|------|
| `-it` | 対話的なモードでコンテナを実行。ターミナルやコマンドラインインタフェースを利用可能 |
| `-v ホストパス:コンテナパス` | ホストとコンテナ間でディレクトリをマウント |
| `--name "コンテナ名"` | コンテナに名前を付ける |
| `イメージ名:タグ` | 実行するDockerイメージの名前とバージョン |
| `"/bin/bash"` | コンテナ内で実行するコマンド |

### データボリュームのマウント

構造化処理をテストするため、入力ファイルのディレクトリをマウントします：

```bash title="データマウント例"
docker run -it \
  -v ${HOME}/sample_tif/container/data:/app2/data \
  -v ${HOME}/sample_tif/inputdata:/app2/inputdata \
  --name "sample_tifv1" \
  sample_tif:v1 \
  "/bin/bash"
```

## コンテナ内でのプログラム実行

コンテナが起動したら、開発したプログラムを実行します：

```bash title="プログラム実行"
# 作業ディレクトリに移動
cd /app2

# 構造化処理プログラムを実行
python3 /app/main.py
```

!!! tip "ターミナルの変化"
    実行すると、ターミナルが`root@(コンテナID):`のように変化します。

## コンテナの管理

### コンテナの終了

```bash title="コンテナ終了"
exit
```

### コンテナの再起動

```bash title="停止したコンテナの再起動"
docker start sample_tifv1
docker exec -it sample_tifv1 /bin/bash
```

### コンテナの削除

```bash title="コンテナ削除"
docker rm sample_tifv1
```

## ベストプラクティス

### マルチステージビルド

本番環境では、マルチステージビルドを使用してイメージサイズを最適化できます：

```dockerfile title="マルチステージDockerfile"
# ビルドステージ
FROM python:3.11 as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# 実行ステージ
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY main.py /app
COPY modules/ /app/modules/
ENV PATH=/root/.local/bin:$PATH
```

### .dockerignoreファイル

不要なファイルをビルドコンテキストから除外します：

```text title=".dockerignore"
.git
.gitignore
README.md
Dockerfile
.dockerignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.venv
```

## トラブルシューティング

### よくある問題と解決方法

1. **ポート競合エラー**
   - 既に使用されているポートを避ける
   - `docker ps`で実行中のコンテナを確認

2. **ボリュームマウントエラー**
   - パスが正しいか確認
   - 権限設定を確認

3. **メモリ不足エラー**
   - Dockerのメモリ制限を確認
   - 不要なコンテナを停止

## 次のステップ

- [構造化処理の概念](../user-guide/structured-processing.ja.md)を理解する
- [設定ファイル](../user-guide/config.ja.md)でDocker環境用の設定を学ぶ
- [コマンドライン機能](cli.ja.md)でartifactコマンドを使ったアーカイブ作成を確認する
