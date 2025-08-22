# 開発者ガイド

## 目的

このセクションでは、RDEToolKitプロジェクトへの貢献方法と開発環境の構築について説明します。バグ修正、新機能の追加、ドキュメントの改善など、様々な形での貢献を歓迎します。

## 貢献の種類

### コード貢献

- **バグ修正**: 既存の問題の解決
- **新機能開発**: 機能追加と拡張
- **パフォーマンス改善**: 処理速度とメモリ使用量の最適化
- **テストの追加**: カバレッジの向上

### ドキュメント貢献

- **ドキュメントの改善**: 既存ドキュメントの品質向上
- **翻訳**: 多言語対応の拡充
- **チュートリアルの作成**: 学習リソースの充実

### コミュニティ貢献

- **バグ報告**: 問題の発見と報告
- **機能要望**: 新機能の提案
- **質問への回答**: コミュニティサポート

## 開発環境の構築 {#開発環境の構築}

### 前提条件

- **Python**: 3.9以上
- **Git**: バージョン管理
- **Rye**: パッケージ管理ツール

### セットアップ手順

1. **リポジトリのクローン**
   ```bash title="terminal"
   git clone https://github.com/nims-mdpf/rdetoolkit.git
   cd rdetoolkit
   ```

2. **Ryeのインストール**
   ```bash title="terminal"
   curl -sSf https://rye-up.com/get | bash
   source ~/.rye/env
   ```

3. **依存関係のインストール**
   ```bash title="terminal"
   rye sync
   ```

4. **開発環境の有効化**
   ```bash title="terminal"
   source .venv/bin/activate
   ```

5. **pre-commitの設定**
   ```bash title="terminal"
   pre-commit install
   ```

## 開発ワークフロー

### ブランチ戦略

- **main**: 安定版のメインブランチ
- **feature/**: 新機能開発用ブランチ
- **bugfix/**: バグ修正用ブランチ
- **docs/**: ドキュメント更新用ブランチ

### 開発手順

1. **Issueの作成または確認**
   - 作業内容をGitHub Issuesで明確化
   - 既存のIssueがあるか確認

2. **ブランチの作成**
   ```bash title="terminal"
   git checkout -b feature/your-feature-name
   ```

3. **開発とテスト**
   ```bash title="terminal"
   # コードの変更
   # テストの実行
   rye test

   # リントチェック
   rye lint

   # フォーマット
   rye fmt
   ```

4. **コミットとプッシュ**
   ```bash title="terminal"
   git add .
   git commit -m "feat: add new feature description"
   git push origin feature/your-feature-name
   ```

5. **プルリクエストの作成**
   - GitHub上でプルリクエストを作成
   - 詳細な説明とテスト結果を記載

## コーディング規約

### Python スタイル

- **PEP 8**: Python標準のスタイルガイドに準拠
- **型ヒント**: 全ての関数に型注釈を追加
- **docstring**: Google形式のdocstringを使用

```python title="example_function.py"
def process_data(
    input_data: List[Dict[str, Any]],
    config: Optional[Config] = None
) -> ProcessResult:
    """
    データを処理する関数

    Args:
        input_data: 処理対象のデータリスト
        config: 処理設定（オプション）

    Returns:
        処理結果を含むProcessResultオブジェクト

    Raises:
        ValueError: 入力データが無効な場合
        ProcessingError: 処理中にエラーが発生した場合

    Example:
        >>> data = [{"key": "value"}]
        >>> result = process_data(data)
        >>> print(result.status)
        'success'
    """
    if not input_data:
        raise ValueError("Input data cannot be empty")

    # 処理ロジック
    return ProcessResult(status="success")
```

### テストの書き方

```python title="test_example.py"
import pytest
from rdetoolkit.processing import process_data

class TestProcessData:
    def test_valid_input(self):
        """正常な入力データのテスト"""
        data = [{"key": "value"}]
        result = process_data(data)
        assert result.status == "success"

    def test_empty_input(self):
        """空の入力データのテスト"""
        with pytest.raises(ValueError):
            process_data([])

    def test_invalid_input(self):
        """無効な入力データのテスト"""
        with pytest.raises(TypeError):
            process_data("invalid")
```

## 品質保証

### 自動チェック

- **pre-commit**: コミット前の自動チェック
- **GitHub Actions**: CI/CDパイプライン
- **codecov**: テストカバレッジの測定

### チェック項目

- **リント**: flake8, pylint
- **フォーマット**: black, isort
- **型チェック**: mypy
- **テスト**: pytest
- **セキュリティ**: bandit

## リリースプロセス

### バージョニング

セマンティックバージョニング（SemVer）を採用：

- **MAJOR**: 破壊的変更
- **MINOR**: 後方互換性のある機能追加
- **PATCH**: 後方互換性のあるバグ修正

### リリース手順

1. **変更ログの更新**
2. **バージョン番号の更新**
3. **タグの作成**
4. **PyPIへの公開**
5. **GitHub Releaseの作成**

## コミュニティガイドライン

### コミュニケーション

- **GitHub Issues**: バグ報告と機能要望
- **GitHub Discussions**: 質問と議論
- **Pull Request**: コードレビューと議論

### 行動規範

- **尊重**: 全ての参加者を尊重する
- **建設的**: 建設的なフィードバックを提供する
- **協力的**: チームワークを重視する
- **包括的**: 多様性を歓迎する

## 次のステップ

開発に参加するには：

1. [コントリビューション](contributing.ja.md) - 詳細な貢献ガイドライン
2. [ドキュメント作成](docs.ja.md) - ドキュメント作成の方法
3. [GitHub Issues](https://github.com/nims-mdpf/rdetoolkit/issues) - 作業可能なタスクの確認

!!! tip "初回貢献者へ"
    初めて貢献する場合は、「good first issue」ラベルの付いたIssueから始めることをお勧めします。
