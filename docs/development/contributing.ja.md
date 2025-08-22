# コントリビューション方法

## 目的

このガイドでは、RDEToolKitプロジェクトに効果的に貢献するための具体的な手順と方法を説明します。初回貢献者から経験豊富な開発者まで、全ての方が円滑に貢献できるよう詳細な情報を提供します。

## 前提条件

貢献を開始する前に、以下を確認してください：

- **GitHub アカウント**: プルリクエストの作成に必要
- **Git の基本知識**: ブランチ操作、コミット、プッシュ
- **Python 開発経験**: 基本的なPython知識
- **開発環境**: [開発環境の構築](index.ja.md#開発環境の構築)が完了済み

## 手順

### 1. 貢献する内容を決定する

#### Issue の確認

既存のIssueから作業を選択するか、新しいIssueを作成します：

```bash title="terminal"
# リポジトリの最新状態を取得
git fetch origin
git checkout main
git pull origin main
```

#### 貢献の種類

| 種類 | 説明 | ラベル |
|------|------|--------|
| バグ修正 | 既存機能の問題解決 | `bug` |
| 新機能 | 機能追加や拡張 | `enhancement` |
| ドキュメント | ドキュメントの改善 | `documentation` |
| テスト | テストの追加や改善 | `testing` |

!!! tip "初回貢献者向け"
    `good first issue` ラベルの付いたIssueから始めることをお勧めします。

### 2. 開発ブランチを作成する

#### ブランチ命名規則

```bash title="terminal"
# 機能追加の場合
git checkout -b feature/issue-123-add-new-validator

# バグ修正の場合
git checkout -b bugfix/issue-456-fix-config-parsing

# ドキュメント更新の場合
git checkout -b docs/issue-789-update-api-reference
```

#### ブランチ名の構成要素

- **プレフィックス**: `feature/`, `bugfix/`, `docs/`
- **Issue番号**: `issue-123`
- **簡潔な説明**: `add-new-validator`

### 3. 開発を実行する

#### コード変更

```python title="example_contribution.py"
from typing import List, Optional
from rdetoolkit.models.rde2types import RdeInputDirPaths

def validate_input_files(srcpaths: RdeInputDirPaths) -> List[str]:
    """
    入力ファイルの妥当性を検証する
    
    Args:
        srcpaths: 入力ファイルのパス情報
    
    Returns:
        検証エラーのリスト（空の場合は妥当）
    
    Example:
        >>> errors = validate_input_files(srcpaths)
        >>> if not errors:
        ...     print("All files are valid")
    """
    errors = []
    
    # 入力ディレクトリの存在確認
    if not srcpaths.inputdata.exists():
        errors.append("Input data directory does not exist")
    
    # ファイル数の確認
    if srcpaths.inputdata.exists():
        files = list(srcpaths.inputdata.glob("*"))
        if len(files) == 0:
            errors.append("No input files found")
    
    return errors
```

#### テストの追加

```python title="test_contribution.py"
import pytest
from pathlib import Path
from rdetoolkit.validation import validate_input_files
from rdetoolkit.models.rde2types import RdeInputDirPaths

class TestValidateInputFiles:
    def test_valid_directory_with_files(self, tmp_path):
        """ファイルが存在する有効なディレクトリのテスト"""
        # テストデータの準備
        input_dir = tmp_path / "inputdata"
        input_dir.mkdir()
        (input_dir / "test_file.txt").write_text("test content")
        
        srcpaths = RdeInputDirPaths(inputdata=input_dir)
        
        # テスト実行
        errors = validate_input_files(srcpaths)
        
        # 検証
        assert errors == []
    
    def test_missing_directory(self, tmp_path):
        """存在しないディレクトリのテスト"""
        input_dir = tmp_path / "nonexistent"
        srcpaths = RdeInputDirPaths(inputdata=input_dir)
        
        errors = validate_input_files(srcpaths)
        
        assert "Input data directory does not exist" in errors
    
    def test_empty_directory(self, tmp_path):
        """空のディレクトリのテスト"""
        input_dir = tmp_path / "inputdata"
        input_dir.mkdir()
        
        srcpaths = RdeInputDirPaths(inputdata=input_dir)
        
        errors = validate_input_files(srcpaths)
        
        assert "No input files found" in errors
```

### 4. 品質チェックを実行する

#### 自動チェックの実行

```bash title="terminal"
# 全てのチェックを実行
rye test
rye lint
rye fmt

# 個別チェック
pytest tests/test_contribution.py -v
mypy src/rdetoolkit/validation.py
black src/rdetoolkit/validation.py
```

#### pre-commit の実行

```bash title="terminal"
# pre-commitフックの手動実行
pre-commit run --all-files

# 特定のフックのみ実行
pre-commit run black --all-files
pre-commit run mypy --all-files
```

### 5. コミットとプッシュを行う

#### コミットメッセージの規則

```bash title="terminal"
# 機能追加
git commit -m "feat: add input file validation function

- Add validate_input_files function to check directory existence
- Add comprehensive test cases for validation scenarios
- Update documentation with usage examples

Closes #123"

# バグ修正
git commit -m "fix: resolve config parsing error for YAML files

- Fix YAML parsing issue when file contains special characters
- Add error handling for malformed YAML files
- Update tests to cover edge cases

Fixes #456"
```

#### コミットメッセージの構成

- **タイプ**: `feat`, `fix`, `docs`, `test`, `refactor`
- **説明**: 変更内容の簡潔な説明
- **詳細**: 必要に応じて詳細な説明
- **Issue参照**: `Closes #123`, `Fixes #456`

### 6. プルリクエストを作成する

#### プルリクエストのテンプレート

```markdown title="pull_request_template.md"
## 概要
この変更の目的と内容を簡潔に説明してください。

## 変更内容
- [ ] 新機能の追加
- [ ] バグの修正
- [ ] ドキュメントの更新
- [ ] テストの追加
- [ ] リファクタリング

## テスト
- [ ] 既存のテストが全て通過する
- [ ] 新しいテストを追加した
- [ ] 手動テストを実行した

## チェックリスト
- [ ] コードがプロジェクトのスタイルガイドに準拠している
- [ ] 自己レビューを実行した
- [ ] 必要に応じてドキュメントを更新した
- [ ] 変更がbreaking changeを含まない

## 関連Issue
Closes #123
```

#### レビュープロセス

1. **自動チェック**: CI/CDパイプラインの通過
2. **コードレビュー**: メンテナーによるレビュー
3. **修正対応**: フィードバックに基づく修正
4. **マージ**: 承認後のマージ

## 結果の確認

### CI/CD の確認

```bash title="terminal"
# GitHub Actions の状況確認
gh pr checks

# 特定のチェックの詳細確認
gh run view --log
```

### レビューフィードバックへの対応

```bash title="terminal"
# フィードバックに基づく修正
git add .
git commit -m "fix: address review feedback

- Update function documentation
- Add missing type hints
- Fix test assertion logic"

git push origin feature/issue-123-add-new-validator
```

## トラブルシューティング

### よくある問題と解決方法

#### テストの失敗

```bash title="terminal"
# 詳細なテスト結果の確認
pytest -v --tb=long

# 特定のテストのみ実行
pytest tests/test_contribution.py::TestValidateInputFiles::test_valid_directory_with_files -v
```

#### リントエラー

```bash title="terminal"
# 自動修正可能なエラーの修正
black src/
isort src/

# 手動修正が必要なエラーの確認
flake8 src/
pylint src/
```

#### マージコンフリクト

```bash title="terminal"
# 最新のmainブランチを取得
git fetch origin
git checkout main
git pull origin main

# フィーチャーブランチにマージ
git checkout feature/issue-123-add-new-validator
git merge main

# コンフリクトを解決後
git add .
git commit -m "resolve merge conflicts with main"
git push origin feature/issue-123-add-new-validator
```

## 関連情報

貢献に関する詳細情報：

- [開発者ガイド](index.ja.md) - 開発環境の構築
- [ドキュメント作成](docs.ja.md) - ドキュメント貢献の方法
- [GitHub Issues](https://github.com/nims-mdpf/rdetoolkit/issues) - 作業可能なタスク

!!! note "コミュニティサポート"
    質問や困ったことがあれば、[GitHub Discussions](https://github.com/nims-mdpf/rdetoolkit/discussions)で気軽に相談してください。
