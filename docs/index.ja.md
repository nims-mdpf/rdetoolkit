# RDEToolKit

![GitHub Release](https://img.shields.io/github/v/release/nims-mdpf/rdetoolkit)
[![python.org](https://img.shields.io/badge/Python-3.9%7C3.10%7C3.11-%233776AB?logo=python)](https://www.python.org/downloads/release/python-3917/)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](https://github.com/nims-mdpf/rdetoolkit/blob/main/LICENSE)
[![Issue](https://img.shields.io/badge/issue_tracking-github-orange)](https://github.com/nims-mdpf/rdetoolkit/issues)
![workflow](https://github.com/nims-mdpf/rdetoolkit/actions/workflows/main.yml/badge.svg)
![coverage](img/coverage.svg)

RDEToolKitは、RDE構造化プログラムのワークフローを作成するための基本的なPythonパッケージです。RDEToolKitの各種モジュールを使うことで、RDEへの研究・実験データの登録処理を簡単に構築できます。主に、RDEToolKitは、ユーザーが定義した構造化処理の前処理・後処理をサポートします。また、ユーザーが研究や実験データに対して使用されているPythonモジュールと組み合わせることで、データの登録から加工、グラフ化などより多様な処理を実現可能です。これにより、データのクレンジング、変換、集計、可視化など、データサイエンスのワークフロー全体を効率的に管理できます。

<br>

![overview_workflow](img/overview_workflow.svg)

## 課題と背景

研究データの管理と共有において、以下の課題が存在していました：

- **データ形式の統一**: 研究者ごとに異なるデータ形式やファイル構造
- **メタデータの標準化**: 一貫性のないメタデータ記述
- **処理の自動化**: 手動でのデータ変換や整理作業の負担
- **再現性の確保**: 処理手順の文書化と標準化の困難

## 主要コンセプト

### 構造化処理ワークフロー

RDEToolKitは、研究データを標準化されたRDE形式に変換する「構造化処理」を3つのフェーズで実行します：

```mermaid
graph LR
    起動処理 --> カスタム構造化処理
    カスタム構造化処理 --> 終了処理
```

- **起動処理**: ディレクトリ作成、ファイル読み込み、モード判定
- **カスタム構造化処理**: ユーザー定義のデータ変換・解析処理
- **終了処理**: バリデーション、サムネイル生成、メタデータ記述

### 4つの処理モード

RDEToolKitは、データの種類と用途に応じて4つの処理モードを提供します：

| モード | 用途 | 特徴 |
|--------|------|------|
| invoiceモード | 単一データファイル | デフォルトモード、基本的な構造化処理 |
| ExcelInvoiceモード | Excel形式の送り状 | Excel送り状ファイルの自動処理 |
| マルチデータタイル | 複数データファイル | 一括処理、エラー処理スキップ機能 |
| RDEフォーマットモード | RDE標準形式 | 既存RDEデータの再処理 |

### 設定ファイル

設定ファイル（`rdeconfig.yaml`または`pyproject.toml`）により、処理の挙動を柔軟に変更できます：

```yaml
system:
  extended_mode: 'MultiDataTile'
  save_raw: true
  magic_variable: true
  save_thumbnail_image: true
```

## インストール

RDEToolKitはPythonパッケージとして提供されており、以下のコマンドでインストールできます。

```bash
pip install rdetoolkit
```

## Code Sample

|       Sample1: ユーザー定義構造化処理あり       |            Sample2: ユーザー定義構造化処理なし            |
| :---------------------------------------------: | :-------------------------------------------------------: |
| ![quick-sample-code](img/quick-sample-code.svg) | ![quick-sample-code-none](img/quick-sample-code-none.svg) |

## 主要機能

### 自動化機能

- **ディレクトリ構造の自動生成**: RDE標準に準拠したフォルダ構成
- **ファイル形式の自動判定**: 入力データに基づく処理モードの選択
- **メタデータの自動抽出**: ファイル情報からのメタデータ生成
- **サムネイル画像の自動作成**: Main画像からの代表画像生成

### 検証機能

- **スキーマバリデーション**: JSON Schemaによるデータ構造検証
- **ファイル整合性チェック**: 必須ファイルの存在確認
- **メタデータ検証**: metadata-def.jsonとの整合性確認

### 拡張性

- **カスタム処理の組み込み**: ユーザー定義関数の統合
- **プラグイン機能**: 独自の処理ロジックの追加
- **設定の柔軟性**: YAML/TOML形式での詳細設定

## まとめ

RDEToolKitの主要な価値：

- **効率性**: 手動作業の自動化により処理時間を大幅短縮
- **標準化**: RDE形式への統一的な変換処理
- **柔軟性**: 多様な研究データ形式への対応
- **信頼性**: バリデーション機能による品質保証
- **拡張性**: カスタム処理の容易な組み込み

## 次のステップ

RDEToolKitを使い始めるには：

1. [インストール方法](installation.ja.md) - 環境構築の手順
2. [クイックスタート](quick-start.ja.md) - 最初の構造化処理を体験
3. [ユーザーガイド](user-guide/index.ja.md) - 詳細な使用方法
