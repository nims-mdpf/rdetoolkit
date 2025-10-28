# ユーザーガイド

## 目的

このセクションでは、RDEToolKitの詳細な使用方法と高度な機能について説明します。基本的なインストールと初回実行を完了した後に、より効果的にRDEToolKitを活用するための情報を提供します。

## 主要トピック

### 基本概念

- [構造化処理とは](structured-processing.ja.md) - RDEToolKitの中核となる概念と処理フロー
- [処理モード](config.ja.md#処理モード) - 4つの処理モードの特徴と使い分け
- [ディレクトリ構造](structured-processing.ja.md#ディレクトリ構造) - RDEプロジェクトの標準的なファイル構成
- [構造化処理開発ガイド（概要）](../usage/structured_process/development_guide.ja.md#rde構造化処理の開発プロセス) - 実践的な開発プロセスと学習の流れ

### 設定とカスタマイズ

- [設定ファイル](config.ja.md) - rdeconfig.yamlとpyproject.tomlによる動作制御
- [Magic Variable](config.ja.md#magic-variable機能) - 動的なメタデータ置換機能
- [gen-config CLI](../usage/cli.ja.md#gen-config-rdeconfigyamlテンプレートの生成) - 用途別テンプレートや対話形式でrdeconfig.yamlを生成

### テンプレートファイル

- [テンプレートファイルガイド](../usage/metadata_definition_file.ja.md) - `invoice.schema.json` / `invoice.json` / `metadata-def.json` / `metadata.json` の役割と構造
- [init CLI](../usage/cli.ja.md#init-スタートアッププロジェクトの作成) - 主要テンプレートとディレクトリ骨格を自動生成
- リポジトリ内のサンプル: `templates/tasksupport/invoice.schema.json`, `templates/tasksupport/metadata-def.json`

### 実践的な使用方法

- [CLIツール](../usage/cli.ja.md) - コマンドライン操作の詳細
- [構造化処理開発ガイド（実装編）](../usage/structured_process/development_guide.ja.md) - 実データを用いた開発ハンズオン
- [バリデーション](../usage/validation.ja.md) - データ品質の検証方法

### 高度な機能

- [Docker使用方法](../usage/docker.ja.md) - Dockerを使用した環境構築と実行

## 使用方法の流れ

1. **概念理解**: [構造化処理とは](structured-processing.ja.md)と[構造化処理開発ガイド](../usage/structured_process/development_guide.ja.md)で全体像を把握
2. **テンプレート準備**: [init CLI](../usage/cli.ja.md#init-スタートアッププロジェクトの作成)や[gen-config CLI](../usage/cli.ja.md#gen-config-rdeconfigyamlテンプレートの生成)で初期ファイルを生成
3. **環境設定**: [設定ファイル](config.ja.md)や[テンプレートファイルガイド](../usage/metadata_definition_file.ja.md)を基にrdeconfig.yamlやinvoice/metadata定義を調整
4. **実践応用**: [CLIツール](../usage/cli.ja.md)や[バリデーション](../usage/validation.ja.md)でワークフローを運用し、必要に応じて高度な機能へ拡張

## サポートリソース

### ドキュメント

- [API リファレンス](../api/index.ja.md) - 全機能の技術仕様
- [開発者ガイド](../development/index.ja.md) - コントリビューション方法
- [構造化処理開発ガイド](../usage/structured_process/development_guide.ja.md) - テンプレート作成から検証までの実践手順

### コミュニティ

- [GitHub Issues](https://github.com/nims-mdpf/rdetoolkit/issues) - バグ報告と機能要望
- [GitHub Discussions](https://github.com/nims-mdpf/rdetoolkit/discussions) - 質問と情報交換

!!! tip "学習の進め方"
    RDEToolKitを効果的に学習するには、まず[構造化処理とは](structured-processing.ja.md)で基本概念を理解し、その後に具体的な用途に応じたトピックを参照することをお勧めします。

## 次のステップ

- 初めての方: [構造化処理とは](structured-processing.ja.md)から開始
- 設定を変更したい方: [設定ファイル](config.ja.md)を参照
- 高度な機能を使いたい方: [Docker使用方法](../usage/docker.ja.md)を確認
