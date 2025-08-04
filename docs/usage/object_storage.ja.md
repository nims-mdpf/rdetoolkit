# オブジェクトストレージ（MinIO）の利用方法

## 概要

MinIOStorageは、オブジェクトストレージサービスであるMinIOとの連携を簡単に行うためのPythonインターフェースです。ファイルのアップロード、ダウンロード、メタデータの取得など、MinIOの主要な機能を簡単に利用することができます。

## 前提条件

- Python 3.9以上
- MinIOサーバーへのアクセス（エンドポイントURL、アクセスキー、シークレットキー）

## インストール方法

rdetoolkitパッケージの一部として提供されているため、以下のコマンドでインストールできます：

```bash
pip install rdetoolkit[minio]
```

## 基本的な使い方

### MinIOStorageのインスタンス化

```python
from rdetoolkit.storage.minio import MinIOStorage

# 直接認証情報を指定する方法
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key",
    secure=True  # HTTPSを使用する場合はTrue
)

# 環境変数から認証情報を取得する方法
import os
os.environ["MINIO_ACCESS_KEY"] = "your-access-key"
os.environ["MINIO_SECRET_KEY"] = "your-secret-key"

storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    # access_keyとsecret_keyを省略すると環境変数から読み込む
)
```

### バケット操作

#### バケットの作成

```python
storage.make_bucket("my-bucket", location="us-east-1")
```

#### バケット一覧の取得

```python
buckets = storage.list_buckets()
for bucket in buckets:
    print(f"バケット名: {bucket['name']}, 作成日: {bucket['creation_date']}")
```

#### バケットの存在確認

```python
if storage.bucket_exists("my-bucket"):
    print("バケットが存在します")
else:
    print("バケットが存在しません")
```

#### バケットの削除

```python
storage.remove_bucket("my-bucket")  # バケットが空である必要があります
```

### オブジェクト操作

#### オブジェクトのアップロード（メモリ上のデータから）

```python
# 文字列からアップロード
data = "Hello, MinIO!"
storage.put_object(
    bucket_name="my-bucket",
    object_name="hello.txt",
    data=data,
    length=len(data),
    content_type="text/plain"
)

# バイナリデータからアップロード
binary_data = b"\x00\x01\x02\x03"
storage.put_object(
    bucket_name="my-bucket",
    object_name="binary-file",
    data=binary_data,
    length=len(binary_data),
    content_type="application/octet-stream"
)
```

#### ファイルからのアップロード

```python
storage.fput_object(
    bucket_name="my-bucket",
    object_name="document.pdf",
    file_path="/path/to/local/document.pdf",
    content_type="application/pdf"
)
```

#### メタデータ付きでアップロード

```python
metadata = {
    "Author": "山田太郎",
    "Version": "1.0",
    "Department": "開発部"
}

storage.fput_object(
    bucket_name="my-bucket",
    object_name="document.pdf",
    file_path="/path/to/local/document.pdf",
    content_type="application/pdf",
    metadata=metadata
)
```

#### オブジェクトのダウンロード（メモリ上に）

```python
response = storage.get_object(
    bucket_name="my-bucket",
    object_name="hello.txt"
)

# レスポンスデータを読み込む
data = response.read()
print(data.decode('utf-8'))  # "Hello, MinIO!"

# 使い終わったらリソースを解放
response.close()
```

#### オブジェクトをファイルにダウンロード

```python
storage.fget_object(
    bucket_name="my-bucket",
    object_name="document.pdf",
    file_path="/path/to/save/document.pdf"
)
```

#### オブジェクトのメタデータ取得

```python
object_info = storage.stat_object(
    bucket_name="my-bucket",
    object_name="document.pdf"
)

print(f"サイズ: {object_info.size} bytes")
print(f"最終更新日: {object_info.last_modified}")
print(f"ETag: {object_info.etag}")
print(f"コンテンツタイプ: {object_info.content_type}")
print(f"メタデータ: {object_info.metadata}")
```

#### オブジェクトの削除

```python
storage.remove_object(
    bucket_name="my-bucket",
    object_name="document.pdf"
)
```

### 署名付きURL（presigned URL）の生成

#### オブジェクト取得用の署名付きURL

```python
from datetime import timedelta

# 1時間有効な署名付きURLを生成
url = storage.presigned_get_object(
    bucket_name="my-bucket",
    object_name="private-document.pdf",
    expires=timedelta(hours=1)
)

print(f"次のURLからダウンロードできます: {url}")
# このURLは認証なしで1時間だけアクセス可能
```

#### オブジェクトアップロード用の署名付きURL

```python
# 1日有効な署名付きURLを生成
url = storage.presigned_put_object(
    bucket_name="my-bucket",
    object_name="upload-here.zip",
    expires=timedelta(days=1)
)

print(f"次のURLにアップロード可能です: {url}")
# このURLに対してPUTリクエストを送ることでアップロード可能
```

### セキュアなオブジェクト取得

通常の`get_object`よりもセキュアな方法でオブジェクトを取得します：

```python
response = storage.secure_get_object(
    bucket_name="my-bucket",
    object_name="sensitive-document.pdf",
    expires=timedelta(minutes=5)  # 非常に短い有効期限を設定
)

# データを読み込む
data = response.read()

# 使い終わったらリソースを解放
response.close()
```

## プロキシ環境での利用

プロキシ環境下でMinIOStorageを利用する場合、以下のように環境変数を設定するか、明示的にHTTPクライアントを指定することができます。

### 環境変数でプロキシを設定

```python
import os

# 環境変数でプロキシを設定
os.environ["HTTP_PROXY"] = "http://proxy.example.com:8080"
os.environ["HTTPS_PROXY"] = "http://proxy.example.com:8080"

# 通常通りインスタンス化
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key"
)
```

### カスタムHTTPクライアントの設定

```python
from rdetoolkit.storage.minio import MinIOStorage

# カスタムプロキシクライアントを作成
proxy_client = MinIOStorage.create_proxy_client(
    proxy_url="http://proxy.example.com:8080"
)

# プロキシクライアントを使用してインスタンス化
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key",
    http_client=proxy_client
)
```

## トラブルシューティング

### 一般的なエラー

1. **認証エラー**
   - アクセスキーとシークレットキーが正しいか確認してください
   - 環境変数が正しく設定されているか確認してください

2. **接続エラー**
   - エンドポイントが正しいか確認してください
   - MinIOサーバーが稼働しているか確認してください
   - ネットワーク接続を確認してください
   - プロキシ設定が必要な場合は正しく設定されているか確認してください

3. **権限エラー**
   - バケットやオブジェクトへの操作権限があるか確認してください

4. **バケットが見つからないエラー**
   - バケット名のスペルを確認してください
   - バケットが存在するか`bucket_exists()`で確認してください

### ログの確認

問題解決のために、より詳細なログを有効にすることができます：

```python
import logging

# MinIOのログを有効にする
logging.basicConfig(level=logging.DEBUG)
```

## 実践例

### 基本的なファイル管理システム

```python
from rdetoolkit.storage.minio import MinIOStorage
from datetime import timedelta
import os

# MinIOStorageの初期化
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key"
)

# 作業用バケットの作成
bucket_name = "my-documents"
if not storage.bucket_exists(bucket_name):
    storage.make_bucket(bucket_name)
    print(f"バケット '{bucket_name}' を作成しました")

# ファイルのアップロード
local_file = "/path/to/important-doc.pdf"
object_name = os.path.basename(local_file)

storage.fput_object(
    bucket_name=bucket_name,
    object_name=object_name,
    file_path=local_file,
    content_type="application/pdf",
    metadata={"CreatedBy": "User123"}
)
print(f"ファイル '{object_name}' をアップロードしました")

# 一時的な共有リンクの作成
share_url = storage.presigned_get_object(
    bucket_name=bucket_name,
    object_name=object_name,
    expires=timedelta(hours=24)
)
print(f"24時間有効な共有リンク: {share_url}")

# ファイルのダウンロード
download_path = f"/path/to/downloads/{object_name}"
storage.fget_object(
    bucket_name=bucket_name,
    object_name=object_name,
    file_path=download_path
)
print(f"ファイルを '{download_path}' にダウンロードしました")
```

## まとめ

MinIOStorageクラスを使用すると、MinIOサーバーとの連携が非常に簡単になります。主な機能は以下の通りです：

- バケットの作成、一覧取得、削除
- オブジェクト（ファイル）のアップロードとダウンロード
- メタデータの管理
- 署名付きURL（期限付きアクセスリンク）の生成
- プロキシ環境への対応

## 次のステップ

- [APIリファレンス](../rdetoolkit/storage/minio.md)で詳細な機能を確認する
- [MinIO Python SDKの公式ドキュメント](https://min.io/docs/minio/linux/developers/python/API.html)を参照する
- [構造化処理](../user-guide/structured-processing.ja.md)でのオブジェクトストレージ活用方法を学ぶ
