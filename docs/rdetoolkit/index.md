# RDE Toolkit API Documentation

## Core Modules

- [config](./config): 設定ファイルの読み込みと管理を行うモジュール
- [core](./core): コア機能を提供するモジュール
- [errors](./errors): エラーハンドリングを行うモジュール
- [exceptions](./exceptions): 例外処理を行うモジュール
- [fileops](./fileops): RDE関連のファイル操作を提供するモジュール
- [img2thumb](./img2thumb): 画像をサムネイルに変換するモジュール
- [invoicefile](./invoicefile): 送り状ファイルの処理を行うモジュール
- [modeproc](./modeproc): モード処理を行うモジュール
- [rde2util](./rde2util): RDE関連のユーティリティ関数を提供するモジュール
- [rdelogger](./rdelogger): ロギング機能を提供するモジュール
- [validation](./validation): データの検証を行うモジュール
- [workflows](./workflows): ワークフローの定義と管理を行うモジュール

## Models

- [config](./models/config): 設定ファイルの読み込みと管理を行うモジュール
- [invoice](./models/invoice): 送り状やExcelinvoiceの情報を定義するモジュール
- [invoice_schema](./models/invoice_schema): 送り状のスキーマを定義するモジュール
- [metadata](./models/metadata): メタデータの管理を行うモジュール
- [rde2types](./models/rde2types): RDE関連の型定義を提供するモジュール
- [report](./models/report): レポート関連のデータモデルを定義するモジュール
- [result](./models/result): 処理結果を管理するモジュール

## Implementation

- [compressed_controller](./impl/compressed_controller): 圧縮ファイルの管理を行うモジュール
- [input_controller](./impl/input_controller): 入力モードの管理を行うモジュール

## Interface

- [filechecker](./interface/filechecker): ファイルチェック機能のインターフェース

## Commands

- [archive](./cmd/archive): アーカイブ関連のコマンド
- [command](./cmd/command): コマンド処理の基本機能
- [gen_excelinvoice](./cmd/gen_excelinvoice): Excel送り状生成コマンド

## Processing

- [processing](./processing/): データ処理パイプライン
  - [context](./processing/context): 処理コンテキストの管理
  - [factories](./processing/factories): プロセッサファクトリ
  - [pipeline](./processing/pipeline): 処理パイプライン
  - [processors](./processing/processors/): 各種プロセッサ
    - [datasets](./processing/processors/datasets): データセット処理
    - [descriptions](./processing/processors/descriptions): 説明文処理
    - [files](./processing/processors/files): ファイル処理
    - [invoice](./processing/processors/invoice): 送り状処理
    - [thumbnails](./processing/processors/thumbnails): サムネイル処理
    - [validation](./processing/processors/validation): 検証処理
    - [variables](./processing/processors/variables): 変数処理

## Storage

- [minio](./storage/minio): MinIO ストレージ連携機能

## Artifacts

- [report](./artifact/report): レポート生成機能
