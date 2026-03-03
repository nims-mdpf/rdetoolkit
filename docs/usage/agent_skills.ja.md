# AIコーディングアシスタント向け Agent Skills

## Agent Skillsとは

rdetoolkitのソースリポジトリには、Claude CodeなどのAIコーディングアシスタントが自動認識する開発ガイド（`.agents/SKILL.md`）が含まれています。

このファイルがリポジトリ内にあると、AIアシスタントはrdetoolkitのAPI規約やプロジェクト構成を把握した状態でコード生成を行います。たとえばJSONファイルの読み書きに標準の`json.load()`ではなく`rdetoolkit.fileops.read_from_json_file()`を使うべき、といった判断をアシスタント側が自動的に行えるようになります。

## Agent Guide APIとの違い

rdetoolkitには2つのAIアシスタント向けガイドがあります。目的が異なるので、状況に応じて使い分けてください。

### Agent Guide（`_agent/`ディレクトリ）

パッケージに同梱されるガイドです。pip installした環境でAPIやCLIからアクセスできます。

```python
import rdetoolkit

guide = rdetoolkit.agent_guide()
```

```bash
rdetoolkit agent-guide
```

汎用的なガイドで、rdetoolkitをインストールした任意の環境で利用できます。自分のプロジェクトにrdetoolkitを導入しているが、ソースリポジトリをcloneしていないケースに向いています。

### Agent Skills（`.agents/`ディレクトリ）

ソースリポジトリ内に配置されたガイドです。Claude Codeがプロジェクトを開くと自動的に読み込まれ、開発セッション中のcontextual guidanceとして機能します。

Agent Guideよりも踏み込んだ内容を含んでいます。処理モードの選択フローチャート、CLI操作の正しい順序、設定ファイルの仕様、よくあるミスの一覧と修正方法など、開発作業中にそのまま参照できる情報が揃っています。

## セットアップ

### 自分のrdetoolkitプロジェクトで使う

rdetoolkitのソースリポジトリをcloneしている場合、Agent Skillsはそのまま使えます。追加の設定は不要です。

```bash
git clone https://github.com/nims-mdpf/rdetoolkit.git
cd rdetoolkit
# Claude Codeを起動すれば .agents/SKILL.md が自動認識される
```

### 自分のプロジェクトに導入する

rdetoolkitを使った構造化処理プロジェクトを独立リポジトリで開発している場合は、以下の手順で配置してください。

#### 1. 正典ソースをコピーする

`.agents/skills/rdetoolkit-skill/` に実体を配置します。

```bash
# rdetoolkitリポジトリからスキルファイルをコピー
mkdir -p ./your-project/.agents/skills/rdetoolkit-skill
cp -r /path/to/rdetoolkit/src/rdetoolkit/.agents/* ./your-project/.agents/skills/rdetoolkit-skill/
```

#### 2. 使用するAIエージェント用にシンボリックリンクを作成する

各AIコーディングアシスタントはそれぞれ専用のディレクトリからスキルファイルを読み込みます。使用するエージェントに合わせてシンボリックリンク（またはコピー）を作成してください。

```bash
# Claude Code 用
mkdir -p .claude/skills
ln -s ../../.agents/skills/rdetoolkit-skill .claude/skills/rdetoolkit-skill

# GitHub Copilot 用
mkdir -p .github/skills
ln -s ../../.agents/skills/rdetoolkit-skill .github/skills/rdetoolkit-skill

# Gemini CLI 用
mkdir -p .gemini/skills
ln -s ../../.agents/skills/rdetoolkit-skill .gemini/skills/rdetoolkit-skill

# OpenCode 用
mkdir -p .opencode/skills
ln -s ../../.agents/skills/rdetoolkit-skill .opencode/skills/rdetoolkit-skill

# Devin 用
mkdir -p .devin/skills
ln -s ../../.agents/skills/rdetoolkit-skill .devin/skills/rdetoolkit-skill
```

すべてのエージェントに対応する必要はありません。使用するツールに対応するディレクトリだけ作成すれば十分です。

## Agent Skillsの構成

自分のプロジェクトに導入した場合のディレクトリ構成は以下のようになります。

```
your-project/
├── .agents/
│   └── skills/
│       └── rdetoolkit-skill/           # ← 実体（正典ソース）
│           ├── SKILL.md                #    エントリポイント
│           └── references/
│               ├── building-structured-processing.md
│               ├── preferred-apis.md
│               ├── cli-workflow.md
│               ├── config.md
│               └── modes.md
├── .claude/
│   └── skills/
│       └── rdetoolkit-skill/           # Claude Code 用（シンボリックリンク）
├── .github/
│   └── skills/
│       └── rdetoolkit-skill/           # GitHub Copilot 用（シンボリックリンク）
├── .gemini/
│   └── skills/
│       └── rdetoolkit-skill/           # Gemini CLI 用（シンボリックリンク）
├── .opencode/
│   └── skills/
│       └── rdetoolkit-skill/           # OpenCode 用（シンボリックリンク）
└── .devin/
    └── skills/
        └── rdetoolkit-skill/           # Devin 用（シンボリックリンク）
```

`.agents/skills/rdetoolkit-skill/` が唯一の実体で、各エージェント用ディレクトリにはシンボリックリンクを配置します。スキルファイルの更新は正典ソースだけで済み、すべてのエージェントに自動で反映されます。

### SKILL.md

全体のエントリポイントです。YAML frontmatterにアクティベーショントリガーが定義されており、rdetoolkitのimport文やRDE関連のキーワードに反応してスキルが有効化されます。

以下の内容が含まれます。

- プロジェクト初期化からdataset関数の実装までのクイックスタート
- `rdetoolkit.fileops`による文字コード安全なファイルI/O
- `Meta`クラスによるmetadata.json書き出し
- Result型によるエラーハンドリングパターン
- 処理モードの選択テーブルとフローチャート
- CLIテンプレート編集・バリデーションの正しい実行順序
- 構造化処理を自律構築する際の手順ガイド
- よくある間違いと修正方法

### references/building-structured-processing.md

構造化処理プログラムをゼロから構築するための実装パターンです。dataset関数の標準構成、metadata-def.jsonの書式、Metaクラスの使い方、Result型によるエラーハンドリング、ディレクトリ仕様、提出チェックリストを含みます。

### references/preferred-apis.md

`rdetoolkit.fileops`と`rdetoolkit.csv2graph`のAPI詳細です。なぜ標準Pythonのファイル操作を使ってはいけないのか、Shift_JISやEUC-JPなどのレガシー日本語エンコーディングにどう対処するかを、コード例とアンチパターンで示しています。

### references/modes.md

5つの処理モード（Invoice、ExcelInvoice、SmartTableInvoice、MultiDataTile、RDEFormat）それぞれの設定例、用途、ディレクトリ構成、比較表を含む詳細リファレンスです。

### references/cli-workflow.md

CLIコマンドの完全リファレンスです。テンプレートファイルの編集順序、バリデーションの実行順序、CI/CD統合の例、バリデーションエラーのトラブルシューティング表を含みます。

### references/config.md

`rdeconfig.yaml`と`pyproject.toml`両形式の設定ファイル仕様です。モード別の設定例、フィールド一覧、マジック変数、よくある設定ミスをまとめています。

## AIアシスタントが自動で守るルール

Agent Skillsが有効な状態では、AIアシスタントは以下のルールを自動的に適用します。

- JSONファイルの読み書きに`rdetoolkit.fileops`を使う（`json.load()`は使わない）
- metadata.jsonの書き出しに`Meta`クラスを使う（手動でJSONを書かない）
- ヘルパー関数でResult型によるエラーハンドリングを行う
- パスのハードコーディングをせず`RdeDatasetPaths`の属性を使う
- テンプレート編集はschema → metadata-def → invoiceの順で行う
- バリデーションはschema → invoice → metadata-defの順で実行する

これらのルールはSKILL.mdの「Critical Rules」セクションで定義されています。プロジェクト固有のルールを追加したい場合は、SKILL.mdを直接編集するか、プロジェクトルートの`CLAUDE.md`に記述してください。
