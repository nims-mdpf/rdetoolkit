# Result Type - Type-Safe Error Handling

## Purpose

The `result` module provides a type-safe alternative to exception-based error handling through the Result type pattern. It enables explicit error handling with compile-time type checking, making error paths visible in function signatures.

## Overview

The Result type pattern wraps successful values in `Success[T]` or errors in `Failure[E]`, allowing functions to explicitly declare both success and failure cases in their return type.

### Key Benefits

- **Explicit Error Handling**: Function signatures clearly indicate potential failures
- **Type Safety**: Full type inference and checking with mypy/pyright
- **Functional Composition**: Chain operations with `map()` method
- **Immutable**: Frozen dataclasses prevent accidental modification
- **Memory Efficient**: Uses slots for reduced memory overhead

## Core Types

### Success[T]

Represents a successful result containing a value of type `T`.

```python
from rdetoolkit.result import Success

# Create a successful result
result = Success(42)
print(result.value)  # 42
print(result.is_success())  # True
```

**Attributes:**

- `value: T` - The wrapped success value

**Methods:**

- `is_success() -> bool` - Always returns `True` for Success
- `map(f: Callable[[T], U]) -> Success[U]` - Transform the value
- `unwrap() -> T` - Extract the value

### Failure[E]

Represents a failure result containing an error of type `E`.

```python
from rdetoolkit.result import Failure

# Create a failure result
result = Failure(ValueError("Invalid input"))
print(result.error)  # ValueError("Invalid input")
print(result.is_success())  # False
```

**Attributes:**

- `error: E` - The wrapped error value

**Methods:**

- `is_success() -> bool` - Always returns `False` for Failure
- `map(f: Callable) -> Failure[E]` - Returns self unchanged (short-circuits)
- `unwrap() -> Never` - Raises the wrapped error (or a ValueError with type info if the error is not an Exception)

### Result Type Alias

```python
Result[T, E] = Success[T] | Failure[E]
```

A union type representing either success or failure.

### try_result Decorator

The `try_result` decorator converts exception-based functions into Result-returning functions automatically.

```python
from rdetoolkit.result import try_result

@try_result
def divide(a: int, b: int) -> float:
    """Division that may raise ZeroDivisionError."""
    return a / b

# Returns Result[float, Exception]
result = divide(10, 2)
print(result.unwrap())  # 5.0

result = divide(10, 0)
print(result.error)  # ZeroDivisionError('division by zero')
```

**Features:**

- Automatic exception catching and conversion to Failure
- Preserves function signatures with full type inference
- Uses `functools.wraps` to maintain metadata
- Returns `Result[T, Exception]` where T is the original return type

**Type Signature:**

```python
def try_result(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]: ...
```

## Usage Examples

### Basic Usage

```python
from rdetoolkit.result import Success, Failure, Result

def divide(a: int, b: int) -> Result[float, str]:
    """Divide two numbers, returning Result type."""
    if b == 0:
        return Failure("Division by zero")
    return Success(a / b)

# Handle the result
result = divide(10, 2)
if result.is_success():
    print(f"Result: {result.unwrap()}")  # Result: 5.0
else:
    print(f"Error: {result.error}")
```

### Functional Composition with map()

```python
from rdetoolkit.result import Success, Failure

# Chain transformations
result = Success(5).map(lambda x: x * 2).map(lambda x: x + 1)
print(result.unwrap())  # 11

# Failure short-circuits the chain
result = Failure("error").map(lambda x: x * 2).map(lambda x: x + 1)
print(result.error)  # "error"
```

### Type-Safe Error Handling

```python
from pathlib import Path
from rdetoolkit.result import Success, Failure, Result

def read_config(path: Path) -> Result[dict, str]:
    """Read configuration file with explicit error handling."""
    if not path.exists():
        return Failure(f"File not found: {path}")

    try:
        with open(path) as f:
            import json
            config = json.load(f)
        return Success(config)
    except json.JSONDecodeError as e:
        return Failure(f"Invalid JSON: {e}")
    except Exception as e:
        return Failure(f"Read error: {e}")

# Type checker understands both success and failure cases
result: Result[dict, str] = read_config(Path("config.json"))
match result:
    case Success(config):
        print(f"Loaded config: {config}")
    case Failure(error):
        print(f"Failed to load: {error}")
```

### Integration with Existing Exception-Based Code

```python
from rdetoolkit.result import Success, Failure, Result
from rdetoolkit.exceptions import StructuredError

def legacy_function() -> tuple:
    """Existing function that raises exceptions."""
    # Implementation that may raise StructuredError
    pass

def safe_legacy_function() -> Result[tuple, StructuredError]:
    """Wrapper providing Result-based interface."""
    try:
        data = legacy_function()
        return Success(data)
    except StructuredError as e:
        return Failure(e)

# Now errors are explicit in the type signature
result = safe_legacy_function()
if not result.is_success():
    error = result.error
    print(f"Error code: {error.ecode}")
    print(f"Error message: {error.emsg}")
```

## Type Annotations

Full type hint support with generic type parameters:

```python
from typing import TypeVar
from rdetoolkit.result import Result, Success, Failure

T = TypeVar('T')
E = TypeVar('E')

def process_data(data: list[T]) -> Result[list[T], ValueError]:
    """Type-safe data processing."""
    if not data:
        return Failure(ValueError("Empty data"))
    return Success(data)

# Type checker infers: Result[list[int], ValueError]
result = process_data([1, 2, 3])
```

## Design Patterns

### Railway-Oriented Programming

Chain multiple operations that may fail:

```python
from rdetoolkit.result import Success, Failure, Result

def validate_input(data: str) -> Result[str, str]:
    if not data:
        return Failure("Empty input")
    return Success(data)

def parse_number(data: str) -> Result[int, str]:
    try:
        return Success(int(data))
    except ValueError:
        return Failure(f"Not a number: {data}")

def validate_positive(num: int) -> Result[int, str]:
    if num <= 0:
        return Failure("Must be positive")
    return Success(num)

# Chain validations
def process_input(data: str) -> Result[int, str]:
    result = validate_input(data)
    if not result.is_success():
        return result

    result = parse_number(result.unwrap())
    if not result.is_success():
        return result

    return validate_positive(result.unwrap())

# Usage
result = process_input("42")
print(result.unwrap())  # 42

result = process_input("-5")
print(result.error)  # "Must be positive"
```

## Best Practices

### When to Use Result Type

✅ **Use Result when:**

- Error handling is a primary concern
- Errors are expected and recoverable
- You want explicit error types in signatures
- Building functional composition chains
- Integrating with type-safe code

❌ **Use exceptions when:**

- Errors are truly exceptional (rare)
- You want automatic error propagation
- Working with existing exception-based APIs
- Errors should halt execution immediately

### Naming Conventions

```python
# Suffix with _result for Result-returning variants
def check_files() -> tuple:  # Original exception-based
    """Raises StructuredError on failure."""
    pass

def check_files_result() -> Result[tuple, StructuredError]:  # Result-based
    """Returns explicit Result type."""
    pass
```

### Error Type Choices

```python
# Specific error types for precise handling
def parse_config() -> Result[Config, ConfigError]:
    pass

# Union types for multiple error types
def load_data() -> Result[Data, FileNotFoundError | ValueError]:
    pass

# String errors for simple cases
def validate_input(s: str) -> Result[str, str]:
    pass
```

## Implementation Details

### Immutability

Both `Success` and `Failure` are frozen dataclasses:

```python
result = Success(42)
result.value = 99  # ❌ Raises FrozenInstanceError
```

### Memory Efficiency

Uses `slots=True` for reduced memory overhead:

```python
@dataclass(frozen=True, slots=True)
class Success(Generic[T]):
    value: T
```

### Type Safety Guarantees

- Full mypy and pyright support
- Generic type parameter inference
- Exhaustive pattern matching with Python 3.10+
- No runtime type checking overhead

## Migration Guide

### From Exception-Based to Result-Based

**Before (Exception-based):**

```python
def check_files(paths: list[Path]) -> list[Path]:
    """Raises ValueError on invalid paths."""
    if not paths:
        raise ValueError("No paths provided")
    return paths
```

**After (Result-based):**

```python
from rdetoolkit.result import Success, Failure, Result

def check_files_result(paths: list[Path]) -> Result[list[Path], ValueError]:
    """Returns Result with explicit error handling."""
    if not paths:
        return Failure(ValueError("No paths provided"))
    return Success(paths)
```

**Backward Compatibility:**

```python
def check_files(paths: list[Path]) -> list[Path]:
    """Legacy function maintaining exception-based interface."""
    result = check_files_result(paths)
    if not result.is_success():
        raise result.error
    return result.unwrap()
```

## Related

- [Error Handling](errors.md) - Error code definitions and structured errors
- [Exceptions](exceptions.md) - Exception hierarchy
- [Workflows](workflows.md) - Workflow execution with Result integration

## See Also

- **Type Safety**: Full mypy/pyright support with generic types
- **Functional Programming**: Composable operations with `map()`
- **Pattern Matching**: Python 3.10+ match/case support

!!! tip "Best Practice"
    Prefer Result types for domain logic where errors are expected and recoverable. Use exceptions for truly exceptional cases and integration boundaries.
