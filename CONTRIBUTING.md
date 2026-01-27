# Contributing to RDEToolKit

## コントリビュートの準備

RDEToolKitへのコントリビュートをしていただくには、以下の手順が必要です。

### リポジトリのクローンをローカルに作成する

```shell
cd <任意のディレクトリ>

# SSH
git clone git@github.com:nims-dpfc/rdetoolkit.git
# HTTPS
git clone https://github.com/nims-dpfc/rdetoolkit.git

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

RDEToolKitでは、以下の2点のコントリビュートを期待しています。

- ドキュメントのコントリビュート
- コードベースのコントリビュート

## ドキュメントのコントリビュート

RDEToolKitのモジュールドキュメントは、ユーザーがRDE構造化処理を正しく実行するために必要なリソースになります。利用者の皆様からのドキュメント改善にご協力ください。
必ずしも、RDEToolKitへの深い理解がある必要はありません。ドキュメントの内容が不足している、理解しにくいという箇所は、積極的にIssueでの報告をお待ちしています。

具体的な手順については、次のセクションから説明いたします。

### RDEToolKitのドキュメント

rdetoolkitのドキュメントは、本リポジトリの`docs`フォルダに格納しています。ドキュメントは、[MkDocs](https://www.mkdocs.org/)を使用してドキュメントを構築しています。
主に、Markdown形式で記述されています。

ドキュメント更新に関して知っておくべき重要事項について:

- rdetoolkitのドキュメントは、コード自体のdocstringと、その他のドキュメントの2つに大別されます。
- docstringは、各種モジュールの利用法が記載され、GitHub Actionsで、自動ビルドされドキュメントが更新されます。
- docstringは、**Google Style**で記述してください。
  - 参考: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)

### ドキュメントの改善点をリクエストする

以下のURLより、RDEToolKitのリポジトリにアクセスし、issueを発行してください。
この時、ラベルは`Type:documentation`というラベルを付与してください。

> [RDEToolKit - github.com](https://github.com/nims-dpfc/rdetoolkit/issues)

### ローカル環境で変更する

変更方法は、ローカルリポジトリからブランチを変更して、変更をPushしてください。ブランチ名の先頭に`docs-***`という接頭辞をつけてください。

```shell
git checkout -b docs-***
# 実行例
git checkout -b docs-install-manual
```

ドキュメントを変更し、リモートリポジトリにPushします。

```shell
git add <変更したドキュメント>
git commit -m "コミットメッセージ"
git push origin <対象のブランチ名>
```

### ドキュメントをWeb上で確認する

Github Pagesに掲載しています。

<https://nims-dpfc.github.io/rdetoolkit/>

### ドキュメントをmainブランチにマージする

ドキュメントを追加しプルリクエストを作成します。管理者が確認し、問題がなければマージします。

## 機能バグレポートと機能拡張のリクエスト

このツールで、新機能・変更・不具合等が発生した場合、以下の手順で変更をしてください。

- 上記リポジトリのissueで、Issueを作成し新機能、問題や不具合を報告する
- 変更を実際に加える場合、ローカルで新規にブランチを作成し、変更を加える。
- CIテストを実行し、プルリクエストを出す
- CIテストが全てパス、レビューが完了したら、マージする
- Releaseページを作成する

この手順書を参考にして、RDEToolKitの開発・変更を行ってください。共同開発を円滑に進めるためのガイドラインとして利用してください。

### Issueを作成する

問題や不具合が発生した場合、以下のisuueへの書き込みをお願いします。

> <https://github.com/nims-dpfc/rdetoolkit/issues>

### ブランチの作成

新しい機能や修正を行う際は、新しいブランチを作成してください。

- ブランチ名の接頭辞は、`develop/v<x.y.z>`というブランチから、末尾に任意の文字列を追加して作成してください。

```shell
git checkout -b develop/v<x.y.z>/<任意の機能名など> origin/develop/v<x.y.z>
```

**接頭辞の例**

| **接頭辞**    | **意味**                                   | **例**                           |
| ------------- | ------------------------------------------ | -------------------------------- |
| `feature/`    | 新機能の開発                               | `feature/user-authentication`    |
| `bugfix/`     | バグ修正                                   | `bugfix/login-error`             |
| `fix/`        | バグ修正（`bugfix/`と同様）                | `fix/login-error`                |
| `hotfix/`     | 緊急の修正が必要な場合                     | `hotfix/critical-security-issue` |
| `release/`    | リリース準備やバージョン管理               | `release/v1.2.0`                 |
| `chore/`      | コードのリファクタリングやメンテナンス作業 | `chore/update-dependencies`      |
| `experiment/` | 試験的な機能やアイデアの検証               | `experiment/new-ui-concept`      |
| `docs/`       | ドキュメントの更新                         | `docs/update-readme`             |
| `test/`       | テスト関連の変更                           | `test/add-unit-tests`            |
| `refactor/`   | コードのリファクタリング                   | `refactor/cleanup-auth-module`   |
| `ci/`         | 継続的インテグレーション設定の変更         | `ci/update-github-actions`       |
| `style/`      | コードのスタイルやフォーマットの変更       | `style/format-codebase`          |
| `perf/`       | パフォーマンス改善                         | `perf/optimize-db-queries`       |
| `design/`     | デザイン関連の変更                         | `design/update-mockups`          |
| `security/`   | セキュリティ関連の修正や強化               | `security/enhance-encryption`    |

### 新機能・修正を加える

#### 必要なツール

- `Python` (推奨バージョン: 3.9以上)
- [rye](https://rye-up.com/) or [Poetry](https://python-poetry.org/docs/)(プロジェクト管理ツール)
- `git` (バージョン管理)

#### RDEToolKitでのフォーマッター・リンターについて

RDEToolKitでは、`Ruff`と`mypy`を使用してフォーマット、リンターを動作させてコード品質を一定に保つことを目標としています。`Ruff`は、isort, black, flake8の機能に変わるツールです。Rustで開発されているため、isort, black, flake8で動作させるより段違いに高速です。また、`mypy`は、静的型チェックツールです。RDEToolKitは型の詳細な定義を強制することで、コードの可読性と保守性の向上を目的としています。

> - Ruff: <https://docs.astral.sh/ruff/>
> - mypy: <https://mypy.readthedocs.io/en/stable/>

### テストの実行

変更を行った後は、テストを実行して正常に動作することを確認してください。

```shell
tox
```

#### テストの種類

RDEToolKitは2種類のテストアプローチを使用しています:

1. **Example-Based Testing**: 特定の入力/出力例を使用した従来のテスト
   - 場所: `tests/` ディレクトリ
   - 同値分割および境界値分析に従う
   - 100%のブランチカバレッジを提供

2. **Property-Based Testing (PBT)**: 自動生成された入力を使用したテスト
   - 場所: `tests/property/` ディレクトリ
   - Hypothesisライブラリを使用してエッジケースを発見
   - 常に成り立つべき不変条件や性質をテスト
   - `@pytest.mark.property` でマーク

#### テスト実行コマンド

```bash
# 全テストを実行 (example-based + property-based)
tox -e py312-module

# Property-basedテストのみ実行
pytest tests/property/ -v -m property

# CIプロファイルで実行 (高速、少ない例)
HYPOTHESIS_PROFILE=ci pytest tests/property/ -v -m property
```

#### Property-Based Testingについて

Property-Based Testingの詳細は `CLAUDE.md` のPBTセクションを参照してください。

### コミットとプッシュ

変更をコミットし、リモートリポジトリにプッシュします。

```shell
git add .
git commit -m "#[issue番号] [変更内容の簡単な説明]"
git push origin develop-v<x.y.z>/<任意の名称>
```

もし、pre-commitのチェックでコミットできない場合、全てのエラーを解消した上でコミットをお願いします。

### 変更リクエスト (Merge Request)

:warning: **この時、`main`ブランチにプルリクエストを発行してないでください。**

変更が完了したら、GitHub等のプラットフォームを使用して変更リクエスト (PR) を作成します。
この時、レビューを受け、必ずCIテストが全てパスすることを確認してください。

もし、CI上のテストがパスしない場合、全てのエラーを解消した上で、レビューの依頼を発行してください。

### マージ

レビューが完了し、問題がないと判断されたら、対象ブランチにマージします。

また、全ての開発がfixしたら、mainブランチにマージしてください。mainブランチにマージ後、デプロイが正しく実行できたら、tagの作成とReleaseページを作成してください。

> Releaseページ: <https://github.com/nims-dpfc/rdetoolkit/releases>

## 関連ページ

- [トップページに戻る](home)
