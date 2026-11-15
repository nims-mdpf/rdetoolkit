# v2構造化処理の作成者向け Agent Skills

正典はリポジトリ直下の5つの `.agents/skills/rdetoolkit-*` です。
利用者の構造化処理を支援するSkillsであり、リポジトリ開発者向けの
`AGENTS.md` / `CLAUDE.md` とは別のものです。実行用wheelとsdistには、
Skillsや廃止した組み込みガイドを含めません。

| Skill | 利用場面 |
| --- | --- |
| `rdetoolkit-flow-authoring` | eager実行のv2 flow、引数を明示するnodeの新規作成 |
| `rdetoolkit-metadata` | 実際のスキーマに沿ったメタデータの構築・保存 |
| `rdetoolkit-debugging` | 失敗の確認、入力・コードの修正、再実行 |
| `rdetoolkit-testing` | 独立したfixtureと実際の出力による検証 |
| `rdetoolkit-v1-migration` | 既存v1 callbackの移行と成果物の比較 |

## 一度ダウンロードすればオフラインで導入可能

インストール済みパッケージと**完全に同じバージョン**を使います。
`a` / `b` / `rc` 接尾辞も一致させます。不一致はインストーラが拒否します。
`python -c "from importlib.metadata import version; print(version('rdetoolkit'))"`
で確認できます。リリース処理は、そのバージョンのGitHub Releaseに
`rdetoolkit-skills-<version>.zip` と `.zip.sha256` を添付します。
この処理を追加した後にビルドしたリリースから提供され、`v2.0.0rc1` にはありません。
開発checkoutでは `python scripts/skills_pack.py build --output skill-dist` で
同じassetを作れます。利用者はソースをcloneする必要がありません。

```sh
VERSION=$(python -c "from importlib.metadata import version; print(version('rdetoolkit'))")
gh release download "v$VERSION" --repo nims-mdpf/rdetoolkit --pattern "rdetoolkit-skills-$VERSION.zip*"
python -m zipfile -e "rdetoolkit-skills-$VERSION.zip" skills-pack
python skills-pack/install_skills.py install --pack "rdetoolkit-skills-$VERSION.zip" --project ./your-project --agent codex
python skills-pack/install_skills.py install --pack "rdetoolkit-skills-$VERSION.zip" --project ./your-project --agent claude
```

Python **3.10以降**を使い、rdetoolkitが入った環境で実行します。
実行時コードをimportせず、インストール済みメタデータからバージョンを読みます。
別途バージョン確認済みなら `--version <version>` も指定できます。
ZIPには単独で動くインストーラと、全payloadのSHA-256を記録した
schema_version付きmanifestが含まれます。書き込み前にハッシュとパスを検証します。
チェックサムは破損を検出するもので、発行者の真正性の証明ではありません。
両ファイルを信頼できるReleaseから取得し、Unixの `sha256sum` または
PowerShellの `Get-FileHash` でZIPと `.sha256` の値を照合してください。

ダウンロード後の展開・導入・実行に**ネットワークは不要**です。
通常のrdetoolkit実行がリモートの指示を自動取得することはありません。
ZIPを保存すればオフラインで再導入できます。コピーはPythonで行い、
Windowsでもシンボリックリンクなしで使えます。

```powershell
$VERSION = py -c "from importlib.metadata import version; print(version('rdetoolkit'))"
py -m zipfile -e "rdetoolkit-skills-$VERSION.zip" skills-pack
py skills-pack/install_skills.py install --pack "rdetoolkit-skills-$VERSION.zip" --project .\your-project --agent claude
```

## エージェントによる認識と検証範囲

| エージェント | プロジェクト内の配置先 | 検証状況 |
| --- | --- | --- |
| Codex | `.agents/skills/<name>/SKILL.md` | コピー導入と実際の `skills/list` 認識を[検証記録](../development/agent-skills-verification.md)に記載 |
| Claude Code | `.claude/skills/<name>/SKILL.md` | コピー導入と実クライアントSDKの初期化で5つのプロジェクトSkillを認識。[検証記録](../development/agent-skills-verification.md)参照 |

導入後は `your-project` でエージェントを起動し直してください。
CodexのSkills選択画面、Claude Codeのスラッシュコマンド
（例：`/rdetoolkit-flow-authoring`）に5つの名前が出ることを
確認してから利用します。YAMLの `name` / `description` が個別の適用条件です。
導入するだけで研究データや診断内容をクラウドモデルへ送る必要はありません。
[Codex公式](https://developers.openai.com/codex/skills/)と
[Claude Code公式](https://code.claude.com/docs/en/skills)も参照してください。
Claudeが `.agents/SKILL.md` を自動認識するとはしていません。

その他のエージェント（Copilot、Cursor、Gemini、OpenCode、Devin）は
**best effort / 未検証**です。それぞれの最新の仕様に合わせて個別のSkill
ディレクトリをコピーしてください。同じ配置やsymlinkが認識されるとは限りません。
インストーラはsymlink導入に対応せず、移植可能なコピーを標準としています。

## 更新・競合・アンインストール

既存Skillや導入記録を上書きしません。対象の5つの名前のどれかがあれば、
コピー開始前に失敗します。利用者のファイルは先にバックアップ・改名してください。
更新時は旧ZIPを保存し、ローカル編集を退避して、旧版を削除してから、
更新した実行パッケージと完全に一致する新版を導入します。

```sh
python skills-pack/install_skills.py uninstall --project ./your-project --agent codex
```

Claude Codeは `--agent claude` とします。削除前に記録と全ファイルを照合します。
変更・追加・欠落・symlinkがあると、Skillを削除せず停止します。
編集を退避し、旧packの状態に戻してから再実行してください。他のSkillsは残ります。
展開先 `skills-pack` とZIPは、オフライン再導入が不要になってから削除します。

## インストール済みAPIの確認

Skillsは、APIを推測する前にインストール済みCLIで確認するようエージェントに指示します。
各一覧は `--json` に対応し、`--module package.module` を付けるとプロジェクト独自の
宣言を先に登録します。

```sh
python -m rdetoolkit nodes list --json
python -m rdetoolkit nodes show rdetoolkit.nodes.meta.build_meta --json
python -m rdetoolkit flows list --json
python -m rdetoolkit skeletons list --json
```

## 旧Agent Guide

パッケージ同梱のガイド（`rdetoolkit.get_agent_guide()`、`agent-guide` コマンド、
パッケージ内の `.agents/` ディレクトリ）はv2 GA前に削除しました。
パッケージ内に代替APIはありません。このSkills packと上記のコマンドを使ってください。
[v1からv2への移行ガイド](../migration_v1_to_v2.md)の「削除されたもの(2.0.0rc1 以降、GA 前)」を参照してください。
