# Changelog

## バージョン一覧

| バージョン | リリース日 | 主な変更点 | 詳細セクション |
| ---------- | ---------- | ---------- | -------------- |
| v1.6.0     | 2026-01-30 | **破壊的変更**: Python 3.9サポート終了（最小バージョン3.10+） / `pytz`依存削除 | [v1.6.0](#v160-2026-01-30) |
| v1.5.2     | 2026-01-27 | CLI validate終了コード標準化 / metadata-def検証修正 / 設定エラーメッセージ改善 / Python 3.9非推奨警告 / PBTインフラ導入 | [v1.5.2](#v152-2026-01-27) |
| v1.5.1     | 2026-01-21 | SmartTable行データ直接アクセス / variable配列のfeature説明欄転記 | [v1.5.1](#v151-2026-01-21) |
| v1.5.0     | 2026-01-09 | Result型 / Typer CLI+validate / タイムスタンプログ / 遅延import / Python 3.14対応 | [v1.5.0](#v150-2026-01-09) |
| v1.4.3     | 2025-12-25 | SmartTable行データの整合性修復 / csv2graph HTML出力先と凡例・対数軸調整 | [v1.4.3](#v143-2025-12-25) |
| v1.4.2     | 2025-12-18 | Invoice overwrite検証 / Excelインボイス統合 / csv2graph単一系列自動判定 / MultiDataTile空入力実行 | [v1.4.2](#v142-2025-12-18) |
| v1.4.1     | 2025-11-05 | SmartTable行CSVアクセサ / 旧`rawfiles`フォールバック警告 | [v1.4.1](#v141-2025-11-05) |
| v1.4.0     | 2025-10-24 | SmartTableの`metadata.json`自動生成 / LLM向けスタックトレース / CSV可視化ユーティリティ / `gen-config` | [v1.4.0](#v140-2025-10-24) |
| v1.3.4     | 2025-08-21 | SmartTable検証の安定化 | [v1.3.4](#v134-2025-08-21) |
| v1.3.3     | 2025-07-29 | `ValidationError`修正 / 再構造化用`sampleWhenRestructured`追加 | [v1.3.3](#v133-2025-07-29) |
| v1.3.2     | 2025-07-22 | SmartTableの必須項目検証の強化 | [v1.3.2](#v132-2025-07-22) |
| v1.3.1     | 2025-07-14 | Excelインボイス空シート生成の修正 / `extended_mode`厳密化 | [v1.3.1](#v131-2025-07-14) |
| v1.2.0     | 2025-04-14 | MinIO対応 / アーカイブ生成 / レポート生成 | [v1.2.0](#v120-2025-04-14) |

# リリース詳細

## v1.6.0 (2026-01-30)

!!! warning "破壊的変更"
    このリリースではPython 3.9のサポートが終了しました。最小Pythonバージョンは **3.10以上** です。

!!! info "参照"
    - 主な課題: [#351](https://github.com/nims-mdpf/rdetoolkit/issues/351)

### 破壊的変更: Python 3.9サポート終了

#### 概要
rdetoolkit v1.6.0からPython 3.9のサポートが削除されました。サポートされる最小Pythonバージョンは **3.10** です。

#### 理由
- **サポート終了**: Python 3.9は **2025年10月31日** にEnd of Lifeを迎えました
- **セキュリティ**: サポート継続はメンテナンスとセキュリティのリスクを増大させます
- **モダン化**: Python 3.10以降では、改善された型ヒント機能、より良いパフォーマンス、言語拡張が提供されます

#### 影響
- **Python 3.9ユーザー**: `pip install rdetoolkit`は自動的に最後の互換バージョン（**v1.5.2**）に解決されます
- **CI/CDパイプライン**: GitHub ActionsとtoxはPython 3.9でのテストを行わなくなりました
- **PyPIメタデータ**: パッケージメタデータからPython 3.9分類子が削除されました

#### 移行オプション

**オプション1: Pythonのアップグレード（推奨）**
```bash
# Python 3.10以上をインストール
# その後、rdetoolkitを再インストール
pip install --upgrade rdetoolkit
```

サポート対象バージョン: Python 3.10, 3.11, 3.12, 3.13, 3.14

**オプション2: 最後の互換バージョンに固定**
```bash
# Python 3.9でrdetoolkit v1.5.2を使用
pip install "rdetoolkit<1.6.0"
```

!!! warning
    v1.5.2に固定すると、v1.6.0以降の新機能、バグ修正、セキュリティ更新を受け取れません。

Pythonバージョンサポートのライフサイクルに関する詳細は、以下を参照してください: [https://endoflife.date/python](https://endoflife.date/python)

---

### 技術的な変更

#### パッケージメタデータ
- `pyproject.toml`の`requires-python`を`>=3.10`に更新
- `Programming Language :: Python :: 3.9`分類子を削除
- ruff設定をPython 3.10ターゲットに更新（`target-version = "py310"`）

#### CI/CDパイプライン
- GitHub Actionsワークフロー（`pypi-release.yml`、`docs-ci.yml`）からPython 3.9を削除
- tox設定をPython 3.10-3.14環境のみをテストするように更新
- `tox.ini`からすべての`py39-*`テスト環境セクションを削除

#### コードクリーンアップ
- Python 3.9互換性コードとバージョン分岐を削除:
  - `__init__.py`、`result.py`、`command.py`の`sys.version_info`チェック
  - バージョン固有のdataclassパラメータ処理（`_DATACLASS_KWARGS`）
  - 条件付き`slots=True`ロジック（現在は常に有効）
- Python 3.10以降の組み込み型ヒントを使用するように最適化:
  - `typing`モジュールから`Never`、`ParamSpec`、`TypeAlias`（`typing_extensions`ではなく）
  - ネイティブユニオン構文（`X | Y`）を使用した型注釈の簡素化

#### ドキュメント
- インストールドキュメント（英語版・日本語版）をPython 3.10以上の要件を反映するように更新
- 使用ドキュメント（CLI、クイックスタート、検証、オブジェクトストレージ）をPython 3.10以上を指定するように更新
- 開発ドキュメントからPython 3.9への言及を削除
- README.mdの非推奨通知をv1.6.0での削除を反映するように調整

#### 依存関係
- Python 3.10以上の制約でロックファイル（`uv.lock`、`requirements.lock`、`requirements-dev.lock`）を再生成
- Python 3.9固有のパッケージwheelとマーカーを2,986行削除
- `pytz`および`types-pytz`依存を削除し、全てのタイムゾーン処理を`datetime.timezone.utc`に移行 ([#375](https://github.com/nims-mdpf/rdetoolkit/issues/375))

---

### テスト
Python 3.10-3.14でのすべてのコアテストが正常に通過:
- **ユニットテスト**: 1,603通過
- **品質チェック**: ruff、mypy、pytestすべて通過
- **統合テスト**: すべてのワークフローで検証済み

---

## v1.5.2 (2026-01-27)

!!! info "参照"
    - 主な課題: [#358](https://github.com/nims-mdpf/rdetoolkit/issues/358), [#359](https://github.com/nims-mdpf/rdetoolkit/issues/359), [#360](https://github.com/nims-mdpf/rdetoolkit/issues/360), [#361](https://github.com/nims-mdpf/rdetoolkit/issues/361), [#362](https://github.com/nims-mdpf/rdetoolkit/issues/362), [#370](https://github.com/nims-mdpf/rdetoolkit/issues/370), [#372](https://github.com/nims-mdpf/rdetoolkit/issues/372), [#373](https://github.com/nims-mdpf/rdetoolkit/issues/373), [#381](https://github.com/nims-mdpf/rdetoolkit/issues/381), [#382](https://github.com/nims-mdpf/rdetoolkit/issues/382)

#### ハイライト
- CI/CDパイプライン統合のためのCLI `validate`コマンド終了コード（0/1/2）の標準化
- `metadata-def.json`検証で正しいPydanticモデル（`MetadataDefinitionValidator`）を使用するよう修正
- 設定エラーメッセージの改善（ファイルパス、行/列情報、ドキュメントリンクを含む詳細なコンテキスト）
- v2.0での削除タイムラインを明記したPython 3.9非推奨警告の追加
- 5モジュールにわたる75テストを含むHypothesis Property-Based Testing（PBT）インフラの導入

---

### CLI Validate終了コード標準化 (Issue #362, #381)

#### 機能強化
- **終了コード標準化**: CI/CD統合のための一貫した終了コードを実装：
  - 終了コード 0: すべての検証に成功
  - 終了コード 1: 検証失敗（データ/スキーマの問題）
  - 終了コード 2: 使用/設定エラー（無効な引数、ファイル未検出など）
- **バグ修正**: `typer.Exit`が`except Exception`ハンドラで誤ってキャッチされ、「Internal error during validation:」という誤ったメッセージが表示される問題を修正
- **CLIヘルプ更新**: すべてのvalidateサブコマンドのdocstringに終了コードドキュメントを追加
- **ユーザードキュメント**: GitHub Actions、GitLab CI、シェルスクリプト向けのCI/CD統合例を追加

#### 使用例

```bash
# CI/CDパイプライン例
rdetoolkit validate --all ./data

if [ $? -eq 0 ]; then
    echo "検証成功"
elif [ $? -eq 1 ]; then
    echo "検証失敗 - 出力を確認してください"
    exit 1
elif [ $? -eq 2 ]; then
    echo "コマンドエラー - 引数を確認してください"
    exit 2
fi
```

---

### メタデータ定義検証の修正 (Issue #382)

#### 機能強化
- **新Pydanticモデル**: `metadata-def.json`スキーマ検証用の`MetadataDefEntry`と`MetadataDefinition`モデルを追加
  - 必須フィールド: `name.ja`, `name.en`, `schema.type`
  - オプションフィールド: `unit`, `description`, `uri`, `mode`, `order`, `originalName`
  - `extra="allow"`で未定義フィールド（例: `variable`）を無視
- **新バリデータ**: メタデータ定義ファイル検証用の`MetadataDefinitionValidator`クラスを追加
- **CLI修正**: `MetadataDefCommand`が誤った`MetadataValidator`ではなく`MetadataDefinitionValidator`を使用するよう更新

---

### 設定エラーメッセージの改善 (Issue #361)

#### 機能強化
- **ConfigError例外**: 包括的なエラー情報を含む新しいカスタム例外クラス：
  - 読み込みに失敗したファイルパス
  - パースエラー時の行/列情報（利用可能な場合）
  - スキーマエラー時のフィールド名と検証理由
  - 解決ガイダンスのためのドキュメントリンク
- **ファイル未検出**: `gen-config`コマンドのガイダンスを含む明確なエラーメッセージ
- **パースエラー**: YAML/TOML構文エラーに行/列情報を含む
- **検証エラー**: Pydantic検証エラーで特定のフィールド名と有効な値を表示

#### エラーメッセージ例

```python
# ファイル未検出
ConfigError: 設定ファイルが見つかりません: '/path/to/rdeconfig.yaml'
設定ファイルを作成するか、'rdetoolkit gen-config'で生成してください。
参照: https://nims-mdpf.github.io/rdetoolkit/usage/config/config/

# 行情報付きパースエラー
ConfigError: '/path/to/rdeconfig.yaml'のパースに失敗しました: 15行目でYAML構文エラー

# スキーマ検証エラー
ConfigError: '/path/to/rdeconfig.yaml'の設定が無効です:
'extended_mode'は['MultiDataTile', 'RDEFormat']のいずれかである必要があります。
```

---

### Python 3.9非推奨警告 (Issue #360)

#### 機能強化
- **DeprecationWarning**: Python 3.9環境でrdetoolkitをインポートした際に警告を表示
- **明確なタイムライン**: 警告メッセージでv2.0での削除を明記
- **セッション安全**: ノイズを避けるためセッションごとに1回のみ警告を表示
- **ドキュメント**: README、CHANGELOG、インストールドキュメント（英語/日本語）に非推奨通知を追加

#### 警告メッセージ

```
DeprecationWarning: Python 3.9のサポートは非推奨であり、rdetoolkit v2.0で削除されます。
Python 3.10以降にアップグレードしてください。
```

---

### Property-Based Testingインフラ導入 (Issue #372)

#### 機能強化
- **Hypothesisライブラリ**: 開発依存に`hypothesis>=6.102.0`を追加
- **テストディレクトリ**: 共有ストラテジーとプロファイル設定を含む`tests/property/`を作成
- **75のPBTテスト**（5モジュール）：
  - `graph.normalizers`（14テスト）: 列の正規化と検証
  - `graph.textutils`（20テスト）: ファイル名サニタイズ、テキスト変換
  - `graph.io.path_validator`（13テスト）: パス安全性検証
  - `rde2util.castval`（15テスト）: 型キャストとエラー処理
  - `validation`（10テスト）: インボイス検証の不変条件
- **CI統合**: 最適化されたCI実行のための`HYPOTHESIS_PROFILE: ci`環境変数を追加
- **Tox統合**: すべてのtox環境に`passenv = HYPOTHESIS_PROFILE`を追加

#### PBTテストの実行

```bash
# すべてのテストを実行（例ベース + プロパティベース）
tox -e py312-module

# プロパティベーステストのみ実行
pytest tests/property/ -v -m property

# CIプロファイルで実行（高速、例数削減）
HYPOTHESIS_PROFILE=ci pytest tests/property/ -v -m property
```

---

### ワークフロードキュメントの整合性修正 (Issue #370)

#### 機能強化
- **Docstring更新**: `workflows.run`のNoteセクションを実際の実装に合わせて更新
- **モード選択**: 実際のモード優先順位と許可される`extended_mode`値をドキュメント化
- **新テスト**: 優先順位と失敗処理をカバーする`_process_mode`のEP/BVテーブルとユニットテストを追加

---

### ドキュメント修正 (Issue #358, #359)

#### 修正
- **バッジURL**: READMEのバッジ（リリース、ライセンス、イシュートラッキング、ワークフロー）を`nims-dpfc`から`nims-mdpf`組織に更新
- **タイポ修正**: READMEと日本語ドキュメントの`display_messsage`を`display_message`に修正

---

### 依存関係の修正 (Issue #373)

#### 修正
- **pytz依存関係**: CI失敗を修正するためランタイム依存に`pytz>=2024.1`を追加
  - 根本原因: pandas 2.2がpytz依存を削除したが、`archive.py`とテストは依然としてpytzを直接インポート
  - 解決策: `pyproject.toml`に明示的なpytz依存を追加し、ロックファイルを再生成

---

### 移行 / 互換性

#### CLI Validate終了コード
- **終了コードの変更**: 内部エラーは一貫性のため終了コード2を返すようになりました（以前は3）
- **CIスクリプト**: 終了コード3をチェックしているスクリプトは終了コード2をチェックするよう更新が必要

#### メタデータ定義検証
- **後方互換**: 既存の有効な`metadata-def.json`ファイルは正しく検証されるようになります
- **エラーメッセージ**: 無効なメタデータ定義に対してより正確なエラーメッセージを表示

#### Python 3.9
- **非推奨のみ**: Python 3.9は引き続き動作しますが、非推奨警告が表示されます
- **必要なアクション**: rdetoolkit v2.0までにPython 3.10+へのアップグレードを計画してください

#### 設定エラー
- **後方互換**: ConfigErrorは新しい例外タイプですが、既存のエラー処理は引き続き動作します
- **デバッグ強化**: 設定に関する問題に対してより有益なエラーメッセージを提供

---

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.5.1 (2026-01-21)

!!! info "参照"
    - 主な課題: [#207](https://github.com/nims-mdpf/rdetoolkit/issues/207), [#210](https://github.com/nims-mdpf/rdetoolkit/issues/210)

#### ハイライト
- SmartTableモードで行データに直接アクセスできる`smarttable_row_data`プロパティを`RdeDatasetPaths`に追加。ユーザーがCSVファイルを手動で読み込み・解析する必要がなくなりました
- `metadata.json`の`variable`配列内にある`_feature`フラグ付き項目を配列形式（`[A,B,C]`）で説明欄に転記する機能を追加
- 説明欄への自動転記を制御する`feature_description`設定フラグを追加

---

### SmartTable行データ直接アクセス (Issue #207)

#### 機能強化
- **新属性**: `RdeOutputResourcePath`データクラスに`smarttable_row_data: dict[str, Any] | None`を追加
- **新プロパティ**: ユーザーコールバックからアクセスできる`smarttable_row_data`プロパティを`RdeDatasetPaths`に追加
- **プロセッサ更新**: `SmartTableInvoiceInitializer`でCSVを解析し、行データをcontextに保存するよう変更
- **型スタブ**: IDE自動補完のための`.pyi`ファイルを更新
- **包括的テスト**: 新旧シグネチャをカバーするユニットテストと統合テストを追加

#### 使用例

**Before（既存の方法も引き続き動作）:**
```python
def custom_dataset(paths: RdeDatasetPaths):
    csv_path = paths.smarttable_rowfile
    if csv_path:
        df = pd.read_csv(csv_path)
        sample_name = df.iloc[0]["sample/name"]
```

**After（新しい改善されたAPI）:**
```python
def custom_dataset(paths: RdeDatasetPaths):
    row_data = paths.smarttable_row_data  # dict[str, Any] | None
    if row_data:
        sample_name = row_data.get("sample/name")
```

---

### variable配列のfeature説明欄転記対応 (Issue #210)

#### 機能強化
- **新ヘルパー関数**: `__collect_values_from_variable`で`variable`配列から指定キーの全値を収集
- **新ヘルパー関数**: `__format_description_entry`でフォーマット処理を共通化（DRY原則）
- **関数拡張**: `update_description_with_features`がvariable配列の検索に対応
  - `constant`の値が`variable`より優先（後方互換）
  - 複数値: `[A,B,C]`形式、単一値: 従来形式
- **新設定フラグ**: `SystemSettings`に`feature_description`ブール値を追加
  - デフォルト: `True`（後方互換）
  - 説明欄への自動転記を制御
  - `rdeconfig.yaml`または`pyproject.toml`で設定可能

#### 設定例

**rdeconfig.yaml:**
```yaml
system:
  feature_description: false  # 自動転記を無効化
```

**pyproject.toml:**
```toml
[tool.rdetoolkit.system]
feature_description = false
```

---

### 移行 / 互換性

#### SmartTable行データアクセス
- **後方互換**: 既存の`smarttable_rowfile`パスアクセスは引き続き動作
- **段階的移行**: 旧方式（ファイルパス）と新方式（dict）の両方が共存可能
- **非SmartTableモード**: SmartTableモード以外では`smarttable_row_data`は`None`を返す

#### variable配列のfeature対応
- **後方互換**: 既存のconstantのみのfeature動作は変更なし
- **優先規則**: `constant`の値は常に`variable`より優先
- **設定デフォルト**: `feature_description`は`True`がデフォルトで、既存の動作を維持
- **オプトアウト可能**: `feature_description: false`で自動転記を無効化

---

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.5.0 (2026-01-09)

!!! info "参照"
    - 主な課題: [#3](https://github.com/nims-mdpf/rdetoolkit/issues/3), [#247](https://github.com/nims-mdpf/rdetoolkit/issues/247), [#249](https://github.com/nims-mdpf/rdetoolkit/issues/249), [#262](https://github.com/nims-mdpf/rdetoolkit/issues/262), [#301](https://github.com/nims-mdpf/rdetoolkit/issues/301), [#323](https://github.com/nims-mdpf/rdetoolkit/issues/323), [#324](https://github.com/nims-mdpf/rdetoolkit/issues/324), [#325](https://github.com/nims-mdpf/rdetoolkit/issues/325), [#326](https://github.com/nims-mdpf/rdetoolkit/issues/326), [#327](https://github.com/nims-mdpf/rdetoolkit/issues/327), [#328](https://github.com/nims-mdpf/rdetoolkit/issues/328), [#329](https://github.com/nims-mdpf/rdetoolkit/issues/329), [#330](https://github.com/nims-mdpf/rdetoolkit/issues/330), [#333](https://github.com/nims-mdpf/rdetoolkit/issues/333), [#334](https://github.com/nims-mdpf/rdetoolkit/issues/334), [#335](https://github.com/nims-mdpf/rdetoolkit/issues/335), [#336](https://github.com/nims-mdpf/rdetoolkit/issues/336), [#337](https://github.com/nims-mdpf/rdetoolkit/issues/337), [#338](https://github.com/nims-mdpf/rdetoolkit/issues/338), [#341](https://github.com/nims-mdpf/rdetoolkit/issues/341)

#### ハイライト
- 例外を使用しない明示的で型安全なエラーハンドリングのためのResult型パターン(`Result[T, E]`)を導入
- システムログファイル名が静的な`rdesys.log`からタイムスタンプ付き(`rdesys_YYYYMMDD_HHMMSS.log`)に変更され、実行ごとのログ管理が可能になり、並行実行や連続実行時のログ衝突を防止
- CLIをTyperに刷新し、`validate`サブコマンド、`rdetoolkit run`、`init`のテンプレートパス指定を追加しつつ`python -m rdetoolkit`互換を維持
- コア/ワークフロー/CLI/グラフの遅延import化で起動負荷を軽減し、重い依存を必要時にのみロード
- `structured`への`invoice.json`保存（任意）とMagic Variable拡張、Python 3.14公式対応を追加

---

### Result型パターン (Issue #334)

#### 機能強化
- **新しいResultモジュール** (`rdetoolkit.result`):
  - `Success[T]`: 値を持つ成功結果のためのイミュータブルなfrozen dataclass
  - `Failure[E]`: エラーを持つ失敗結果のためのイミュータブルなfrozen dataclass
  - `Result[T, E]`: `Success[T] | Failure[E]`の型エイリアス
  - `try_result`デコレータ: 例外ベースの関数をResult返却関数に変換
  - `TypeVar`と`ParamSpec`による完全なジェネリック型サポートで型安全性を実現
  - 関数型メソッド: `is_success()`, `map()`, `unwrap()`
- **Resultベースのワークフロー関数**:
  - `check_files_result()`: 明示的なResult型によるファイル分類
  - `Result[tuple[RawFiles, Path | None, Path | None], StructuredError]`を返却
- **Resultベースのモード処理関数**:
  - `invoice_mode_process_result()`: Result型によるインボイス処理
  - `Result[WorkflowExecutionStatus, Exception]`を返却
- **型スタブ**: IDE自動補完と型チェックのための完全な`.pyi`ファイル
- **ドキュメント**: 英語と日本語の包括的なAPIドキュメント(`docs/api/result.en.md`, `docs/api/result.ja.md`)
- **公開API**: `rdetoolkit.__init__.py`からResult型をエクスポートし、簡単にインポート可能
- **100%テストカバレッジ**: Resultモジュールの包括的な40ユニットテスト

#### 使用例

**Resultベースのエラーハンドリング:**
```python
from rdetoolkit.workflows import check_files_result

result = check_files_result(srcpaths, mode="invoice")
if result.is_success():
    raw_files, excel_path, smarttable_path = result.unwrap()
    # ファイル処理
else:
    error = result.error
    print(f"Error {error.ecode}: {error.emsg}")
```

**従来の例外ベース (引き続き動作):**
```python
from rdetoolkit.workflows import check_files

try:
    raw_files, excel_path, smarttable_path = check_files(srcpaths, mode="invoice")
except StructuredError as e:
    print(f"Error {e.ecode}: {e.emsg}")
```

---

### タイムスタンプ付きログファイル名 (Issue #341)

#### 機能強化
- ファイルシステムセーフなタイムスタンプ文字列を生成する`generate_log_timestamp()`ユーティリティ関数を追加
- 各ワークフロー実行でユニークなタイムスタンプ付きログファイルを生成するように`workflows.run()`を変更
- P2バグを修正: 同一プロセス内で`run()`を複数回呼び出した際のハンドラ蓄積問題
  - 根本原因: Loggerシングルトンが異なるファイル名の古いLazyFileHandlerを保持
  - 解決策: 新しいハンドラを追加する前に既存のLazyFileHandlerをクリア
  - 影響: 1実行=1ログファイルを保証し、ログのクロスコンタミネーションを防止
- 保守性向上のためカスタム`LazyFileHandler`を標準の`logging.FileHandler(delay=True)`に置き換え
- 新しいタイムスタンプ付きログファイル名パターンを参照するようにすべてのドキュメントを更新

#### 利点
- **実行ごとの分離**: 各ワークフロー実行が個別のログファイルを作成し、ログの混在を防止
- **並行実行**: 複数のワークフローを同時実行してもログが衝突しない
- **比較が容易**: 手動で分離することなく、異なる実行のログを比較可能
- **監査の簡素化**: デバッグやコンプライアンスのために実行ごとのログを収集・アーカイブ
- **保守性の向上**: 標準ライブラリのFileHandlerは十分にテストされ、広く理解されている

---

### CLI刷新とバリデーション (Issue #247, #262, #337, #338)

#### 機能強化
- CLIをTyperへ移行し遅延import化。`python -m rdetoolkit`の起動とコマンド名（`init`/`version`/`gen-config`/`make-excelinvoice`/`artifact`/`csv2graph`）を維持
- `rdetoolkit run <module_or_file::attr>`を追加し、動的関数ロード、クラス/呼び出し可能オブジェクトの除外、2引数受け取り可否の検証を実装
- `rdetoolkit validate`コマンド（`invoice-schema`/`invoice`/`metadata-def`/`metadata`/`all`）を追加し、`--format text|json`、`--quiet`、`--strict/--no-strict`、終了コード（0/1/2/3）を提供
- `init`テンプレートパスオプション（`--entry-point`/`--modules`/`--tasksupport`/`--inputdata`/`--other`）を追加し、`pyproject.toml`/`rdeconfig.yaml`に保存

#### Initテンプレートパスオプション詳細 (Issue #262)

`rdetoolkit init`コマンドにテンプレートパスオプションを追加し、カスタムテンプレートからプロジェクトを初期化できるようになりました。

**想定用途**:

- よく使う機能をまとめたファイル群を`modules/`フォルダに配置した状態で初期化
- `main.py`を好みの形式でカスタマイズ
- いつも使う設定ファイルをテンプレートとして初期化
- 独自のオブジェクト指向スクリプトのひな形を指定

**追加されたオプション**:

- `--entry-point`: container/ディレクトリにエントリーポイント（.pyファイル）を配置
- `--modules`: container/modules/ディレクトリにモジュールを配置（フォルダ指定でサブディレクトリ含む）
- `--tasksupport`: tasksupport/ディレクトリに設定ファイルを配置（フォルダ指定でサブディレクトリ含む）
- `--inputdata`: container/data/inputdata/ディレクトリに入力データを配置（フォルダ指定でサブディレクトリ含む）
- `--other`: container/ディレクトリにその他のファイルを配置（フォルダ指定でサブディレクトリ含む）

**設定の永続化**:

- CLI指定されたパスは`pyproject.toml`または`rdeconfig.yaml(yml)`に自動保存
- 設定ファイルが存在しない場合は`pyproject.toml`を自動生成
- 既存の設定がある場合は上書き

**安全対策**:

- 自己コピー（同一パス）の検知とスキップ
- 不正パスや空文字のバリデーションとエラー報告

**設定ファイル例** (`pyproject.toml`):
```toml
[tool.rdetoolkit.init]
entry_point = "path/to/your/template/main.py"
modules = "path/to/your/template/modules/"
tasksupport = "path/to/your/template/config/"
inputdata = "path/to/your/template/inputdata/"
other = [
    "path/to/your/template/file1.txt",
    "path/to/your/template/dir2/"
]
```

**設定ファイル例** (`rdeconfig.yaml`):
```yaml
init:
  entry_point: "path/to/your/template/main.py"
  modules: "path/to/your/template/modules/"
  tasksupport: "path/to/your/template/config/"
  inputdata: "path/to/your/template/inputdata/"
  other:
    - "path/to/your/template/file1.txt"
    - "path/to/your/template/dir2/"
```

---

### 起動パフォーマンス改善 (Issue #323-330)

#### 機能強化
- `rdetoolkit`および`rdetoolkit.graph`で遅延エクスポートを導入し、未使用時の重いサブモジュール読み込みを回避
- インボイス/検証/エンコード、コアユーティリティ、ワークフロー、CLI、グラフレンダラーの重い依存を必要時のみロード
- 遅延importを行う対象ファイルで`PLC0415`を許可するRuffのper-file ignoreを追加

---

### 型安全性とリファクタ (Issue #333, #335, #336)

#### 機能強化
- `models.rde2types`の型エイリアスをNewType定義と検証付きパス型に刷新し、`FileGroup`/`ProcessedFileGroup`を追加
- 読み取り専用の入力を`Mapping`、変更を伴う入力を`MutableMapping`へ拡張し、`Validator.validate()`は`Mapping`を受け取り`dict`へ正規化
- `rde2util.castval`、インボイスシート処理、アーカイブ形式判定のif/elif連鎖をディスパッチテーブルへ置換し、互換性テストで挙動を維持

---

### ワークフロー/設定の拡張 (Issue #3, #301)

#### 機能強化
- `system.save_invoice_to_structured`（デフォルト`false`）と`StructuredInvoiceSaver`を追加し、サムネイル生成後に`structured`へ`invoice.json`を任意でコピー
- Magic Variableパターンを拡張：`${invoice:basic:*}`、`${invoice:custom:*}`、`${invoice:sample:names:*}`、`${metadata:constant:*}`。欠損時の警告と厳密な検証を追加

---

### ツール/プラットフォーム対応 (Issue #249)

#### 機能強化
- Python 3.14を公式サポートし、classifier/`tox`/CIのビルド・テストマトリクスを更新

---

### 移行 / 互換性

#### Result型パターン
- **後方互換性**: すべての元の例外ベース関数は変更なし
- **段階的な移行**: 両方のパターン(例外ベースとResultベース)が共存可能
- **委譲パターン**: 元の関数は内部的に`*_result()`バージョンに委譲
- **型安全性**: `isinstance(result, Failure)`を使用した型安全なエラーチェック
- **エラー情報の保持**: すべてのエラー情報(StructuredError属性、Exception詳細)がFailureに保持

#### タイムスタンプ付きログファイル名
- **ログファイル名の変更**: システムログは`data/logs/rdesys.log`ではなく`data/logs/rdesys_YYYYMMDD_HHMMSS.log`に書き込まれます
- **ログの検索**: ワイルドカードパターンを使用してログを検索：`ls -t data/logs/rdesys_*.log | head -1`で最新のログを確認
- **スクリプトとツール**: `rdesys.log`を直接参照するスクリプトや監視ツールを、`rdesys_*.log`のパターンマッチングを使用するように更新してください
- **ログ収集**: 自動ログ収集システムは、単一の静的ファイルではなく、複数のタイムスタンプ付きファイルを処理するように更新が必要です
- **古いログファイル**: 以前のバージョンからの既存の`rdesys.log`ファイルはそのまま残り、自動的には削除されません
- **設定不要**: 新しい動作は自動的に適用され、設定変更は必要ありません

#### CLI（Typer移行と新コマンド）
- **起動互換**: `python -m rdetoolkit ...`の呼び出しは継続し、コマンド名/主要オプションも維持
- **依存関係**: Click依存は削除。`rdetoolkit.cli`のClick依存オブジェクトを直接利用していた場合は見直しが必要
- **validateコマンド**: `rdetoolkit validate`は終了コード0/1/2/3を返し、CI自動化に利用可能

#### initテンプレートパス
- **設定への保存**: 指定したテンプレートパスは`pyproject.toml`/`rdeconfig.yaml`に保存され、既存設定はそのまま利用可能

#### invoice.jsonのstructured保存
- **オプション制**: `system.save_invoice_to_structured`は`false`が既定。`true`にすると`structured/invoice.json`が生成されます

#### Magic Variables
- **拡張パターン**: `${invoice:basic:*}`、`${invoice:custom:*}`、`${invoice:sample:names:*}`、`${metadata:constant:*}`を追加
- **エラー/警告**: 必須フィールド欠損はエラー、空要素は警告付きでスキップされ`__`連結を防止

#### Mapping型ヒント
- **型のみ変更**: `Mapping`/`MutableMapping`の採用で入力型が拡張されるが、実行時の挙動は維持
- **validate入力**: `Validator.validate(obj=...)`は`Mapping`を`dict`へコピーして正規化

#### Python 3.14対応
- **互換性**: Python 3.14を公式サポートし、CI/配布設定を更新

---

#### 既知の問題
- `invoice_mode_process`のみがResultベースバージョンを持ちます。他のモードプロセッサは将来のリリースで移行される予定です

---

## v1.4.3 (2025-12-25)

!!! info "参照資料"
    - 対応Issue: [#292](https://github.com/nims-mdpf/rdetoolkit/issues/292), [#310](https://github.com/nims-mdpf/rdetoolkit/issues/310), [#311](https://github.com/nims-mdpf/rdetoolkit/issues/311), [#302](https://github.com/nims-mdpf/rdetoolkit/issues/302), [#304](https://github.com/nims-mdpf/rdetoolkit/issues/304)

#### ハイライト
- SmartTable 分割処理で `sample.ownerId` と boolean 列が失われず、空欄が前行から継承されないよう修正し、行単位のデータ整合性を回復。
- csv2graph の HTML 出力を CSV 保存先（structured）にデフォルト固定し、`html_output_dir` で任意ディレクトリへ振り分け可能に。Plotly/Matplotlib の凡例表示とログ目盛を統一し再現性を向上。

#### 追加機能 / 改善
- SmartTableInvoiceInitializer で元 invoice を一度だけ読み込み、各行処理に deepcopy を渡すことで分割後も `sample.ownerId` を保持。
- SmartTable 行の空欄セルを検出して既存値をクリアし、basic/custom/sample いずれも前行値を引き継がないようマッピングを整理。
- SmartTable boolean 変換で `"TRUE"` / `"FALSE"`（大文字小文字無視）をスキーマの boolean 型に従って確定し、Excel 由来の文字列を正しく反映。
- csv2graph に `html_output_dir` / `--html-output-dir` を追加し、HTML を CSV と同じディレクトリへ保存するデフォルトを導入。ドキュメントとサンプル（英/日）も更新。
- グラフレンダラーで Plotly 凡例をシリーズ名のみに統一し、ログ軸を 10 の累乗目盛・10^n 表記に固定（Plotly/Matplotlib 両方）。
- EP/BV 表付きの回帰テストを SmartTable・csv2graph・レンダラーに追加し、ownerId 継承、空欄クリア、boolean 変換、HTML 出力先、凡例/ログ目盛を網羅。

#### 不具合修正
- SmartTable 分割時に 2 行目以降の `sample.ownerId` が消失する問題を解消。
- SmartTable の空欄セルが前行の basic/description や sample/composition などを引き継いでしまう問題を解消。
- `"FALSE"` が真と解釈される boolean 変換の不具合を修正し、スキーマ型に基づいたキャストを強制。
- csv2graph で `output_dir=other_image` を指定した際に HTML が構造化ディレクトリ外へ出力される問題を修正し、デフォルトで CSV 直下（structured）へ保存。
- Plotly 凡例にヘッダー全体（例: `total:intensity`）が表示される挙動と、ログ軸の 2・5 の補助目盛/非指数表記を修正。

#### 移行ガイド / 互換性
- csv2graph の HTML 出力は既定で CSV 配下（通常は `data/structured`）に保存されます。別ディレクトリに出力したい場合は `html_output_dir`（API）または `--html-output-dir`（CLI）を指定してください。
- SmartTable で空欄セルが自動的に既存値を再利用する挙動は廃止されました。必要な値は各行に明示的に入力してください。
- `"TRUE"` / `"FALSE"` の文字列は boolean 型に強制キャストされます。旧挙動（非空文字列は常に真）に依存したワークフローがある場合は見直しを推奨します。
- その他の後方互換性への影響はありません。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.4.2 (2025-12-18)

!!! info "参照資料"
    - 対応Issue: [#30](https://github.com/nims-mdpf/rdetoolkit/issues/30), [#36](https://github.com/nims-mdpf/rdetoolkit/issues/36), [#246](https://github.com/nims-mdpf/rdetoolkit/issues/246), [#293](https://github.com/nims-mdpf/rdetoolkit/issues/293)

#### ハイライト
- `InvoiceFile.overwrite()` が辞書入力を受け付け、`InvoiceValidator` での検証と `invoice_path` へのフォールバック保存に対応。
- Excel インボイスの読み込みを `ExcelInvoiceFile` に集約し、`read_excelinvoice()` は v1.5.0 で削除予定の警告付き互換ラッパーへ移行。
- csv2graph が単一系列を自動検出し、CLI フラグの明示がない限り個別プロット生成を抑止して CLI / API のデフォルト動作を統一。
- MultiDataTile パイプラインが Excel のみ / 空ディレクトリでも実行され、必ずデータセット検証が発火。

#### 追加機能 / 改善
- `InvoiceFile.overwrite()` のシグネチャをマッピング受け取りに拡張し、`InvoiceValidator` によるスキーマ検証とインスタンス `invoice_path` へのデフォルト書き込みを追加。docstring と `docs/rdetoolkit/invoicefile.md` も更新。
- `read_excelinvoice()` を警告付きラッパーとして `ExcelInvoiceFile.read()` に委譲し、`src/rdetoolkit/impl/input_controller.py` がクラス API を直接利用するよう変更。`df_general` / `df_specific` が `None` を取り得ることをドキュメントと型定義で明確化。
- `Csv2GraphCommand` の `no_individual` を `bool | None` 型に改め、CLI では `ctx.get_parameter_source()` を用いて明示指定を検出。`docs/rdetoolkit/csv2graph.md` に新しい自動判定の仕様を追記。
- `assert_optional_frame_equal` を追加し、csv2graph CLI/API・MultiFileChecker（Excelのみ/空/単体/複数ファイル）を網羅する新規テストで退行を防止。

#### 不具合修正
- 単一系列の自動検出により空の個別グラフ生成を回避し、CLI と Python API の出力整合性を確保。
- `_process_invoice_sheet()` / `_process_general_term_sheet()` / `_process_specific_term_sheet()` が一貫して `pd.DataFrame` を返すように修正し、フレーム操作の前提崩壊を防止。
- 入力ファイルが存在しない場合に `MultiFileChecker.parse()` が `[()]` を返すよう変更し、MultiDataTile でも空ディレクトリ時に検証が必ず実行されるよう統一。

#### 移行ガイド / 互換性
- `InvoiceFile.overwrite()` には辞書を直接渡せるようになった。出力先を省略した場合はインスタンスの `invoice_path` に書き込まれ、不正なスキーマは検証エラーとして通知される。
- `read_excelinvoice()` は非推奨となり v1.5.0 で削除予定のため、`ExcelInvoiceFile().read()` への移行を推奨。
- `csv2graph` は `--no-individual` を指定しない単一系列入力でオーバーレイのみを生成する。旧挙動を維持するには `--no-individual=false` を指定し、常に抑止したい場合は `--no-individual` を付与する。
- MultiDataTile では空ディレクトリでも処理と検証が走るため、これまで静かにスキップされていたケースでも不足ファイルのエラーが表に出る。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.4.1 (2025-11-05)

!!! info "参照資料"
    - 対応Issue: [#204](https://github.com/nims-mdpf/rdetoolkit/issues/204), [#272](https://github.com/nims-mdpf/rdetoolkit/issues/272), [#273](https://github.com/nims-mdpf/rdetoolkit/issues/273), [#278](https://github.com/nims-mdpf/rdetoolkit/issues/278)

#### ハイライト
- SmartTable 行CSVへの専用アクセサを追加し、`rawfiles[0]` 依存の既存コールバックとの互換性を維持。
- MultiDataTile ワークフローが必ずステータスを返し、失敗モード名付きで `StructuredError` を通知するよう改善。
- CSV パーサーがメタデータ行と空データに対応し、`ParserError` / `EmptyDataError` を防止。
- グラフ可視化ヘルパー（`csv2graph`, `plot_from_dataframe`）を `rdetoolkit.graph` 直下からインポート可能に。

#### 追加機能 / 改善
- `RdeOutputResourcePath` に `smarttable_rowfile` を追加し、`ProcessingContext.smarttable_rowfile` と `RdeDatasetPaths` から参照可能に。
- SmartTable 系処理で行CSVを自動設定し、フォールバックで `rawfiles[0]` を参照した場合は移行を促す `FutureWarning` を発行。
- SmartTable の開発者向けドキュメントを更新し、行CSVの取得方法を新アクセサ基準に整理。
- `rdetoolkit.graph` パッケージで `csv2graph` / `plot_from_dataframe` を再エクスポートし、ドキュメントとサンプルのインポート例を統一。

#### 不具合修正
- MultiDataTile モードが `WorkflowExecutionStatus` を必ず返し、応答がない場合は失敗したモード名付きで `StructuredError` を送出するよう修正。
- `CSVParser._parse_meta_block()` / `_parse_no_header()` で `#` 始まりのメタデータ行を無視し、データが空のときは空の `DataFrame` を返すことで `ParserError` / `EmptyDataError` を解消。

#### 移行ガイド / 互換性
- `resource_paths.rawfiles[0]` を利用するコードは動作を継続するが、`smarttable_rowfile` へ移行しないと警告が表示される。
- `rawfiles` タプル自体は引き続きユーザー投入ファイルの一覧として利用される。先頭要素が常に SmartTable 行CSVであるという前提のみ段階的に解消する方針。
- CSV 取り込み側での追加対応は不要。今回の改修は後方互換。
- 推奨インポートは `from rdetoolkit.graph import csv2graph, plot_from_dataframe`。従来の `rdetoolkit.graph.api` パスは当面利用可能。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.4.0 (2025-10-24)

!!! info "参照資料"
    - 主なIssues: [#144](https://github.com/nims-mdpf/rdetoolkit/issues/144), [#188](https://github.com/nims-mdpf/rdetoolkit/issues/188), [#197](https://github.com/nims-mdpf/rdetoolkit/issues/197), [#205](https://github.com/nims-mdpf/rdetoolkit/issues/205), [#236](https://github.com/nims-mdpf/rdetoolkit/issues/236)

#### ハイライト
- SmartTableInvoice で `meta/` 列を `metadata.json` に自動書き込み
- LLM/AI 向けコンパクト・スタックトレース（デュプレックス出力）
- CSV 可視化ユーティリティ `csv2graph`
- 設定ファイル雛形生成コマンド `gen-config`

#### 追加機能 / 改善
- `csv2graph` API を追加。複数CSVフォーマット、方向フィルタ、Plotly HTML 出力、220件超のテストを整備。
- `gen-config` CLI を追加。テンプレート生成、日英対応対話モード、`--overwrite` オプションをサポート。
- SmartTableInvoice で `meta/` プレフィックス列を型変換付きで `metadata.json` の `constant` セクションへ反映。既存値は温存し、`metadata-def.json` がない場合はスキップ。
- 例外処理で `compact` / `python` / `duplex` を選択可能なスタックトレース出力を導入し、センシティブ情報の自動マスキングを実装。
- RDE データセットコールバックを `RdeDatasetPaths` 単一引数に集約し、旧シグネチャには非推奨警告を追加。

#### 不具合修正
- MultiDataTile モードで `ignore_errors=True` 時に `StructuredError` が停止しないバグを修正。
- SmartTable 周辺のエラーハンドリングと型注釈を整理し、処理失敗時の挙動を安定化。

#### 移行ガイド / 互換性
- 旧来の 2 引数コールバックは当面動作するが、`RdeDatasetPaths` 単一引数への移行を推奨。
- SmartTable の `meta/` 列自動書き込みを利用する場合は、各プロジェクトに `metadata-def.json` を配置する。
- スタックトレース形式の切り替えは任意。既存設定に影響はない。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.4 (2025-08-21)

!!! info "参照資料"
    - 主なIssue: [#217](https://github.com/nims-mdpf/rdetoolkit/issues/217)（SmartTable/Invoice 検証の安定化）

#### ハイライト
- SmartTable/Invoice の検証フローを安定化

#### 追加機能 / 改善
- バリデーションと初期化フローを整理し、不要なフィールド混入と例外の出力形式を改善。

#### 不具合修正
- SmartTableInvoice の検証で発生し得た例外伝播と型注釈の不整合を解消。

#### 移行ガイド / 互換性
- 互換性を損なう変更はありません。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.3 (2025-07-29)

!!! info "参照資料"
    - 主なIssue: [#201](https://github.com/nims-mdpf/rdetoolkit/issues/201)

#### ハイライト
- `ValidationError` 構築不備を修正し、Invoice パイプラインを安定化
- コピー再構造化向け `sampleWhenRestructured` スキーマパターンを追加

#### 追加機能 / 改善
- スキーマに `sampleWhenRestructured` を追加し、再構造化ワークフローで `sampleId` のみが必須となるシナリオを正式サポート。
- すべてのサンプル検証パターンに包括的なテストを追加し、後方互換性を担保。

#### 不具合修正
- `_validate_required_fields_only` に起因する `ValidationError.__new__()` 例外を `SchemaValidationError` へ置き換えて解消。
- `InvoiceSchemaJson` と `Properties` 生成時にオプションフィールドを明示し、mypy 型チェックエラーを修正。

#### 移行ガイド / 互換性
- 追加の設定変更は不要。既存の `invoice.json` も後方互換性が保たれる。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.2 (2025-07-22)

!!! info "参照資料"
    - 主なIssue: [#193](https://github.com/nims-mdpf/rdetoolkit/issues/193)

#### ハイライト
- SmartTableInvoice の必須項目検証を強化

#### 追加機能 / 改善
- `invoice.json` 検証で必須項目のみを許容する仕組みを導入し、不要なフィールド混入を防止。
- 早期終了（EarlyExit）時にもバリデーションが確実に実行されるよう統合。

#### 不具合修正
- 検証過程での例外伝播と型注釈の不具合を整理し、安定性を向上。

#### 移行ガイド / 互換性
- 後方互換。`invoice.json` に不要フィールドを付与している場合は除去を推奨。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.1 (2025-07-14)

!!! info "参照資料"
    - 主なIssues: [#144](https://github.com/nims-mdpf/rdetoolkit/issues/144), [#161](https://github.com/nims-mdpf/rdetoolkit/issues/161), [#163](https://github.com/nims-mdpf/rdetoolkit/issues/163), [#168](https://github.com/nims-mdpf/rdetoolkit/issues/168), [#169](https://github.com/nims-mdpf/rdetoolkit/issues/169), [#173](https://github.com/nims-mdpf/rdetoolkit/issues/173), [#174](https://github.com/nims-mdpf/rdetoolkit/issues/174), [#177](https://github.com/nims-mdpf/rdetoolkit/issues/177), [#185](https://github.com/nims-mdpf/rdetoolkit/issues/185)

#### ハイライト
- Excel インボイス空シート生成の不具合を修正
- `extended_mode` の厳密バリデーションを導入

#### 追加機能 / 改善
- `invoice_schema.py` に `serialization_alias` を追加し、`invoice.schema.json` の `$schema` / `$id` を正しく出力。
- `models/config.py` の `extended_mode` で許可値を限定し、検証を強化。
- `save_raw` / `save_nonshared_raw` の挙動を再設計し、テストを拡充。
- SmartTable モードに `save_table_file` オプションと `SkipRemainingProcessorsError` を追加し、処理制御を柔軟化。
- `models/rde2types.py` の型注釈を拡張し、DataFrame 警告を抑制。
- Rust 側の文字列整形・`build.rs`・CI ワークフローを整理し、品質と速度を向上。

#### 不具合修正
- Raw ディレクトリ存在チェックを追加し、コピー時の例外を防止。
- Excel テンプレート生成で `generalTerm` / `specificTerm` シート欠落を修正し、変数名の誤りを解消。
- `FixedHeaders` クラスで `orient` を明示し、将来の警告を抑制。

#### 移行ガイド / 互換性
- `extended_mode` に非許可値が設定されている場合はエラーとなるため、設定ファイルの見直しが必要。
- SmartTable モードで `save_table_file` のデフォルト挙動が変わる可能性があるため、必要に応じて設定を追加。
- `tqdm` 依存を削除したため、外部スクリプトで利用している場合は対応を検討。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.2.0 (2025-04-14)

!!! info "参照資料"
    - 主なIssue: [#157](https://github.com/nims-mdpf/rdetoolkit/issues/157)

#### ハイライト
- MinIO ストレージ対応
- 成果物アーカイブ生成とレポート生成ワークフローを追加

#### 追加機能 / 改善
- `MinIOStorage` クラスを実装し、オブジェクトストレージ連携を公式サポート。
- 成果物の圧縮（ZIP / tar.gz）およびレポート生成コマンドを追加。
- オブジェクトストレージ利用手順やレポート API を含むドキュメントを拡充。

#### 不具合修正
- 依存パッケージの更新と CI 設定の近代化を実施。

#### 移行ガイド / 互換性
- 後方互換。MinIO を利用する場合はオプション依存をインストールすること。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。
