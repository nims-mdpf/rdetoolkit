# Result型 - 型安全なエラーハンドリング

## 目的

`result` モジュールは、Result型パターンを通じて例外ベースのエラーハンドリングに対する型安全な代替手段を提供します。コンパイル時の型チェックによる明示的なエラーハンドリングを可能にし、関数シグネチャでエラーパスを可視化します。

## 概要

Result型パターンは、成功した値を `Success[T]` に、エラーを `Failure[E]` にラップすることで、関数が戻り値の型で成功と失敗の両方のケースを明示的に宣言できるようにします。

### 主な利点

- **明示的なエラーハンドリング**: 関数シグネチャが潜在的な失敗を明確に示す
- **型安全性**: mypy/pyrightによる完全な型推論とチェック
- **関数合成**: `map()` メソッドによる操作のチェーン化
- **不変性**: frozen dataclassにより意図しない変更を防止
- **メモリ効率**: slotsによるメモリオーバーヘッドの削減

## コア型

### Success[T]

型 `T` の値を含む成功結果を表します。

```python
from rdetoolkit.result import Success

# 成功結果を作成
result = Success(42)
print(result.value)  # 42
print(result.is_success())  # True
```

**属性:**

- `value: T` - ラップされた成功値

**メソッド:**

- `is_success() -> bool` - Successの場合、常に `True` を返す
- `map(f: Callable[[T], U]) -> Success[U]` - 値を変換
- `unwrap() -> T` - 値を取り出す

### Failure[E]

型 `E` のエラーを含む失敗結果を表します。

```python
from rdetoolkit.result import Failure

# 失敗結果を作成
result = Failure(ValueError("Invalid input"))
print(result.error)  # ValueError("Invalid input")
print(result.is_success())  # False
```

**属性:**

- `error: E` - ラップされたエラー値

**メソッド:**

- `is_success() -> bool` - Failureの場合、常に `False` を返す
- `map(f: Callable) -> Failure[E]` - selfを変更せずに返す（短絡評価）
- `unwrap() -> Never` - ラップされたエラーを送出（Exception以外の場合は型情報付きのValueError）

### Result型エイリアス

```python
Result[T, E] = Success[T] | Failure[E]
```

成功または失敗を表すユニオン型。

### try_result デコレーター

`try_result` デコレーターは、例外ベースの関数を自動的にResult型を返す関数に変換します。

```python
from rdetoolkit.result import try_result

@try_result
def divide(a: int, b: int) -> float:
    """ZeroDivisionErrorを送出する可能性のある除算。"""
    return a / b

# Result[float, Exception] を返す
result = divide(10, 2)
print(result.unwrap())  # 5.0

result = divide(10, 0)
print(result.error)  # ZeroDivisionError('division by zero')
```

**機能:**

- 例外の自動キャッチとFailureへの変換
- 完全な型推論による関数シグネチャの保持
- `functools.wraps` によるメタデータの維持
- 元の戻り値型TをResult[T, Exception]として返す

**型シグネチャ:**

```python
def try_result(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]: ...
```

## 使用例

### 基本的な使用法

```python
from rdetoolkit.result import Success, Failure, Result

def divide(a: int, b: int) -> Result[float, str]:
    """2つの数値を除算し、Result型を返す。"""
    if b == 0:
        return Failure("Division by zero")
    return Success(a / b)

# 結果を処理
result = divide(10, 2)
if result.is_success():
    print(f"結果: {result.unwrap()}")  # 結果: 5.0
else:
    print(f"エラー: {result.error}")
```

### map()による関数合成

```python
from rdetoolkit.result import Success, Failure

# 変換をチェーン化
result = Success(5).map(lambda x: x * 2).map(lambda x: x + 1)
print(result.unwrap())  # 11

# Failureはチェーンを短絡評価
result = Failure("error").map(lambda x: x * 2).map(lambda x: x + 1)
print(result.error)  # "error"
```

### 型安全なエラーハンドリング

```python
from pathlib import Path
from rdetoolkit.result import Success, Failure, Result

def read_config(path: Path) -> Result[dict, str]:
    """明示的なエラーハンドリングで設定ファイルを読み込む。"""
    if not path.exists():
        return Failure(f"ファイルが見つかりません: {path}")

    try:
        with open(path) as f:
            import json
            config = json.load(f)
        return Success(config)
    except json.JSONDecodeError as e:
        return Failure(f"不正なJSON: {e}")
    except Exception as e:
        return Failure(f"読み込みエラー: {e}")

# 型チェッカーは成功と失敗の両方のケースを理解
result: Result[dict, str] = read_config(Path("config.json"))
match result:
    case Success(config):
        print(f"設定を読み込みました: {config}")
    case Failure(error):
        print(f"読み込みに失敗しました: {error}")
```

### 既存の例外ベースコードとの統合

```python
from rdetoolkit.result import Success, Failure, Result
from rdetoolkit.exceptions import StructuredError

def legacy_function() -> tuple:
    """例外を送出する既存の関数。"""
    # StructuredErrorを送出する可能性のある実装
    pass

def safe_legacy_function() -> Result[tuple, StructuredError]:
    """Resultベースのインターフェースを提供するラッパー。"""
    try:
        data = legacy_function()
        return Success(data)
    except StructuredError as e:
        return Failure(e)

# エラーが型シグネチャで明示的に
result = safe_legacy_function()
if not result.is_success():
    error = result.error
    print(f"エラーコード: {error.ecode}")
    print(f"エラーメッセージ: {error.emsg}")
```

## 型アノテーション

ジェネリック型パラメータによる完全な型ヒントサポート：

```python
from typing import TypeVar
from rdetoolkit.result import Result, Success, Failure

T = TypeVar('T')
E = TypeVar('E')

def process_data(data: list[T]) -> Result[list[T], ValueError]:
    """型安全なデータ処理。"""
    if not data:
        return Failure(ValueError("空のデータ"))
    return Success(data)

# 型チェッカーが推論: Result[list[int], ValueError]
result = process_data([1, 2, 3])
```

## デザインパターン

### Railway-Oriented Programming

失敗する可能性のある複数の操作をチェーン化：

```python
from rdetoolkit.result import Success, Failure, Result

def validate_input(data: str) -> Result[str, str]:
    if not data:
        return Failure("空の入力")
    return Success(data)

def parse_number(data: str) -> Result[int, str]:
    try:
        return Success(int(data))
    except ValueError:
        return Failure(f"数値ではありません: {data}")

def validate_positive(num: int) -> Result[int, str]:
    if num <= 0:
        return Failure("正の数である必要があります")
    return Success(num)

# バリデーションをチェーン化
def process_input(data: str) -> Result[int, str]:
    result = validate_input(data)
    if not result.is_success():
        return result

    result = parse_number(result.unwrap())
    if not result.is_success():
        return result

    return validate_positive(result.unwrap())

# 使用例
result = process_input("42")
print(result.unwrap())  # 42

result = process_input("-5")
print(result.error)  # "正の数である必要があります"
```

## ベストプラクティス

### Result型を使用するタイミング

✅ **Result型を使用する場合:**

- エラーハンドリングが主要な関心事である
- エラーが予期され、回復可能である
- シグネチャで明示的なエラー型が必要
- 関数合成チェーンを構築する
- 型安全なコードと統合する

❌ **例外を使用する場合:**

- エラーが真に例外的である（稀）
- 自動的なエラー伝播が必要
- 既存の例外ベースAPIと連携する
- エラーが即座に実行を停止すべき

### 命名規則

```python
# Result返却バリアントには _result サフィックスを付ける
def check_files() -> tuple:  # 元の例外ベース
    """失敗時にStructuredErrorを送出。"""
    pass

def check_files_result() -> Result[tuple, StructuredError]:  # Resultベース
    """明示的なResult型を返す。"""
    pass
```

### エラー型の選択

```python
# 正確なハンドリングのための特定のエラー型
def parse_config() -> Result[Config, ConfigError]:
    pass

# 複数のエラー型のためのユニオン型
def load_data() -> Result[Data, FileNotFoundError | ValueError]:
    pass

# シンプルなケースのための文字列エラー
def validate_input(s: str) -> Result[str, str]:
    pass
```

## 実装の詳細

### 不変性

`Success` と `Failure` は両方ともfrozen dataclassです：

```python
result = Success(42)
result.value = 99  # ❌ FrozenInstanceErrorを送出
```

### メモリ効率

メモリオーバーヘッド削減のため `slots=True` を使用：

```python
@dataclass(frozen=True, slots=True)
class Success(Generic[T]):
    value: T
```

### 型安全性の保証

- 完全なmypyとpyrightサポート
- ジェネリック型パラメータの推論
- Python 3.10+での網羅的パターンマッチング
- 実行時の型チェックオーバーヘッドなし

## 移行ガイド

### 例外ベースからResultベースへ

**変更前（例外ベース）:**

```python
def check_files(paths: list[Path]) -> list[Path]:
    """無効なパスに対してValueErrorを送出。"""
    if not paths:
        raise ValueError("パスが提供されていません")
    return paths
```

**変更後（Resultベース）:**

```python
from rdetoolkit.result import Success, Failure, Result

def check_files_result(paths: list[Path]) -> Result[list[Path], ValueError]:
    """明示的なエラーハンドリングでResultを返す。"""
    if not paths:
        return Failure(ValueError("パスが提供されていません"))
    return Success(paths)
```

**後方互換性:**

```python
def check_files(paths: list[Path]) -> list[Path]:
    """例外ベースインターフェースを維持するレガシー関数。"""
    result = check_files_result(paths)
    if not result.is_success():
        raise result.error
    return result.unwrap()
```

## 関連項目

- [エラーハンドリング](errors.md) - エラーコード定義と構造化エラー
- [例外](exceptions.md) - 例外階層
- [ワークフロー](workflows.md) - Result統合を伴うワークフロー実行

## 参照

- **型安全性**: ジェネリック型による完全なmypy/pyrightサポート
- **関数型プログラミング**: `map()` による合成可能な操作
- **パターンマッチング**: Python 3.10+ match/caseサポート

!!! tip "ベストプラクティス"
    エラーが予期され回復可能なドメインロジックにはResult型を推奨します。真に例外的なケースや統合境界には例外を使用してください。
