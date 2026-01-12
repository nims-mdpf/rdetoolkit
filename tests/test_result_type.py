"""Comprehensive unit tests for Result type pattern module.

Tests cover Success, Failure, Result type alias, and try_result decorator
with focus on type safety, immutability, and functional composition.
"""

from __future__ import annotations

import pytest

from rdetoolkit.result import Success, Failure, Result, try_result


# =============================================================================
# Success Class Tests
# =============================================================================


def test_success_creation():
    """Test Success instance creation with value."""
    result = Success(42)
    assert result.value == 42


def test_success_creation_with_various_types():
    """Test Success with different value types."""
    assert Success(42).value == 42
    assert Success("hello").value == "hello"
    assert Success([1, 2, 3]).value == [1, 2, 3]
    assert Success({"key": "value"}).value == {"key": "value"}
    assert Success(None).value is None


def test_success_is_success():
    """Test Success.is_success() returns True."""
    result = Success(42)
    assert result.is_success() is True


def test_success_unwrap():
    """Test Success.unwrap() returns the value."""
    result = Success(42)
    assert result.unwrap() == 42


def test_success_map_transformation():
    """Test Success.map() applies transformation function."""
    result = Success(5)
    mapped = result.map(lambda x: x * 2)
    assert isinstance(mapped, Success)
    assert mapped.unwrap() == 10


def test_success_map_chaining():
    """Test Success.map() supports method chaining."""
    result = Success(5).map(lambda x: x * 2).map(lambda x: x + 1)
    assert result.unwrap() == 11


def test_success_map_type_transformation():
    """Test Success.map() can change value type."""
    result = Success(42).map(str)
    assert result.unwrap() == "42"
    assert isinstance(result.unwrap(), str)


def test_success_immutability():
    """Test Success is immutable (frozen dataclass)."""
    result = Success(42)
    with pytest.raises(AttributeError):  # FrozenInstanceError is a subclass
        result.value = 99  # type: ignore


def test_success_repr():
    """Test Success string representation."""
    result = Success(42)
    assert repr(result) == "Success(value=42)"


def test_success_equality():
    """Test Success equality comparison."""
    assert Success(42) == Success(42)
    assert Success(42) != Success(43)
    assert Success("hello") == Success("hello")


# =============================================================================
# Failure Class Tests
# =============================================================================


def test_failure_creation():
    """Test Failure instance creation with error."""
    error = ValueError("test error")
    result = Failure(error)
    assert result.error == error


def test_failure_creation_with_various_error_types():
    """Test Failure with different error types."""
    value_error = Failure(ValueError("value error"))
    assert isinstance(value_error.error, ValueError)

    type_error = Failure(TypeError("type error"))
    assert isinstance(type_error.error, TypeError)

    custom_error = Failure("string error")
    assert custom_error.error == "string error"


def test_failure_is_success():
    """Test Failure.is_success() returns False."""
    result = Failure(ValueError("error"))
    assert result.is_success() is False


def test_failure_unwrap_raises_exception():
    """Test Failure.unwrap() raises the wrapped exception."""
    error = ValueError("test error")
    result = Failure(error)

    with pytest.raises(ValueError, match="test error"):
        result.unwrap()


def test_failure_unwrap_with_non_exception():
    """Test Failure.unwrap() with non-Exception error raises ValueError."""
    result = Failure("string error")

    with pytest.raises(ValueError, match="string error"):
        result.unwrap()


def test_failure_map_returns_self():
    """Test Failure.map() returns self unchanged (short-circuit)."""
    error = ValueError("error")
    result = Failure(error)
    mapped = result.map(lambda x: x * 2)

    assert mapped is result
    assert mapped.error == error


def test_failure_map_chaining():
    """Test Failure.map() short-circuits through chains."""
    error = ValueError("error")
    result = Failure(error).map(lambda x: x * 2).map(lambda x: x + 1)

    assert isinstance(result, Failure)
    assert result.error == error


def test_failure_immutability():
    """Test Failure is immutable (frozen dataclass)."""
    result = Failure(ValueError("error"))
    with pytest.raises(AttributeError):  # FrozenInstanceError is a subclass
        result.error = TypeError("new error")  # type: ignore


def test_failure_repr():
    """Test Failure string representation."""
    error = ValueError("test")
    result = Failure(error)
    assert "Failure(error=ValueError('test'))" in repr(result)


def test_failure_equality():
    """Test Failure equality comparison."""
    error1 = ValueError("test")
    error2 = ValueError("test")

    # Same error instance
    result1 = Failure(error1)
    result2 = Failure(error1)
    assert result1 == result2

    # Different error instances (even with same message)
    result3 = Failure(error2)
    assert result1 != result3  # Different object instances


# =============================================================================
# Result Type Usage Tests
# =============================================================================


def test_result_type_annotation():
    """Test Result type can be used in type annotations."""

    def divide(a: int, b: int) -> Result[float, str]:
        if b == 0:
            return Failure("Division by zero")
        return Success(a / b)

    result = divide(10, 2)
    assert isinstance(result, Success)
    assert result.unwrap() == 5.0

    result = divide(10, 0)
    assert isinstance(result, Failure)
    assert result.error == "Division by zero"


def test_result_pattern_matching():
    """Test Result types work with isinstance checking."""

    def divide(a: int, b: int) -> Result[float, str]:
        if b == 0:
            return Failure("Division by zero")
        return Success(a / b)

    result = divide(10, 2)
    # Use isinstance instead of match for Python 3.9 compatibility
    if isinstance(result, Success):
        output = f"Result: {result.value}"
    elif isinstance(result, Failure):
        output = f"Error: {result.error}"
    else:
        output = "Unknown"

    assert output == "Result: 5.0"


# =============================================================================
# try_result Decorator Tests
# =============================================================================


def test_try_result_success_case():
    """Test try_result decorator wraps successful execution in Success."""

    @try_result
    def divide(a: int, b: int) -> float:
        return a / b

    result = divide(10, 2)
    assert isinstance(result, Success)
    assert result.unwrap() == 5.0


def test_try_result_exception_case():
    """Test try_result decorator wraps exceptions in Failure."""

    @try_result
    def divide(a: int, b: int) -> float:
        return a / b

    result = divide(10, 0)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ZeroDivisionError)


def test_try_result_preserves_function_metadata():
    """Test try_result preserves original function metadata."""

    @try_result
    def example_function(x: int) -> int:
        """Example function docstring."""
        return x * 2

    assert example_function.__name__ == "example_function"
    assert example_function.__doc__ == "Example function docstring."


def test_try_result_with_multiple_exception_types():
    """Test try_result catches different exception types."""

    @try_result
    def parse_and_divide(s: str, divisor: int) -> float:
        value = int(s)  # May raise ValueError
        return value / divisor  # May raise ZeroDivisionError

    # ValueError case
    result = parse_and_divide("not a number", 2)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ValueError)

    # ZeroDivisionError case
    result = parse_and_divide("10", 0)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ZeroDivisionError)

    # Success case
    result = parse_and_divide("10", 2)
    assert isinstance(result, Success)
    assert result.unwrap() == 5.0


def test_try_result_with_no_arguments():
    """Test try_result with function that takes no arguments."""

    @try_result
    def get_value() -> int:
        return 42

    result = get_value()
    assert isinstance(result, Success)
    assert result.unwrap() == 42


def test_try_result_with_keyword_arguments():
    """Test try_result preserves keyword arguments."""

    @try_result
    def multiply(a: int, b: int = 2) -> int:
        return a * b

    result = multiply(5, b=3)
    assert isinstance(result, Success)
    assert result.unwrap() == 15

    result = multiply(5)
    assert isinstance(result, Success)
    assert result.unwrap() == 10


def test_try_result_with_none_return():
    """Test try_result with function returning None."""

    @try_result
    def do_nothing() -> None:
        pass

    result = do_nothing()
    assert isinstance(result, Success)
    assert result.unwrap() is None


def test_try_result_with_complex_return_type():
    """Test try_result with functions returning complex types."""

    @try_result
    def create_dict() -> dict[str, int]:
        return {"a": 1, "b": 2}

    result = create_dict()
    assert isinstance(result, Success)
    assert result.unwrap() == {"a": 1, "b": 2}


# =============================================================================
# Integration and Edge Case Tests
# =============================================================================


def test_success_failure_interaction():
    """Test Success and Failure can be used interchangeably."""
    results: list[Result[int, str]] = [
        Success(42),
        Failure("error"),
        Success(100),
    ]

    success_values = [r.unwrap() for r in results if r.is_success()]
    assert success_values == [42, 100]

    failure_errors = [r.error for r in results if not r.is_success()]
    assert failure_errors == ["error"]


def test_try_result_with_existing_result_usage():
    """Test try_result can be combined with manual Result creation."""

    @try_result
    def risky_operation(x: int) -> int:
        if x < 0:
            msg = "Negative value"
            raise ValueError(msg)
        return x * 2

    def safe_wrapper(x: int) -> Result[int, str]:
        if x == 0:
            return Failure("Zero not allowed")

        result = risky_operation(x)
        if not result.is_success():
            return Failure(f"Operation failed: {result.error}")

        return result  # type: ignore

    # Test different paths
    assert safe_wrapper(5).unwrap() == 10
    assert safe_wrapper(0).error == "Zero not allowed"
    assert "Negative value" in str(safe_wrapper(-5).error)


def test_map_with_exception_in_transform():
    """Test map behavior when transformation function raises exception."""

    def bad_transform(x: int) -> int:
        msg = "Transform failed"
        raise RuntimeError(msg)

    result = Success(42)

    # map should propagate the exception since it's not wrapped
    with pytest.raises(RuntimeError, match="Transform failed"):
        result.map(bad_transform)


def test_nested_result_types():
    """Test Result can contain Result as value (nested Results)."""
    inner = Success(42)
    outer = Success(inner)

    assert isinstance(outer, Success)
    assert isinstance(outer.unwrap(), Success)
    assert outer.unwrap().unwrap() == 42


def test_result_with_callable_value():
    """Test Result can wrap callable values."""

    def example_func() -> int:
        return 42

    result = Success(example_func)
    assert result.unwrap()() == 42


def test_failure_with_exception_chain():
    """Test Failure preserves exception chain."""
    try:
        try:
            inner_msg = "Inner error"
            raise ValueError(inner_msg)
        except ValueError as e:
            outer_msg = "Outer error"
            raise TypeError(outer_msg) from e
    except TypeError as e:
        result = Failure(e)

    assert isinstance(result.error, TypeError)
    assert isinstance(result.error.__cause__, ValueError)


def test_result_memory_efficiency():
    """Test Result uses slots for memory efficiency."""
    success = Success(42)
    failure = Failure("error")

    # Frozen dataclass with slots should not have __dict__
    assert not hasattr(success, "__dict__")
    assert not hasattr(failure, "__dict__")


# =============================================================================
# Type Safety and Generic Tests
# =============================================================================


def test_success_generic_type_preservation():
    """Test Success preserves generic type information."""
    int_result: Success[int] = Success(42)
    str_result: Success[str] = Success("hello")
    list_result: Success[list[int]] = Success([1, 2, 3])

    assert isinstance(int_result.value, int)
    assert isinstance(str_result.value, str)
    assert isinstance(list_result.value, list)


def test_failure_generic_type_preservation():
    """Test Failure preserves generic error type information."""
    exception_result: Failure[Exception] = Failure(ValueError("error"))
    str_result: Failure[str] = Failure("error string")

    assert isinstance(exception_result.error, Exception)
    assert isinstance(str_result.error, str)


def test_try_result_return_type_annotation():
    """Test try_result returns correctly typed Result."""

    @try_result
    def get_int() -> int:
        return 42

    # The decorator should return Result[int, Exception]
    result: Result[int, Exception] = get_int()
    assert isinstance(result, Success)
    assert isinstance(result.unwrap(), int)
