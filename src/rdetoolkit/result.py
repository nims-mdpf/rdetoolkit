"""Result type pattern for explicit error handling.

This module provides Success and Failure types for type-safe error handling,
enabling explicit representation of success and failure cases in function signatures.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Generic, Never, ParamSpec, TypeVar

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
P = ParamSpec("P")


@dataclass(frozen=True, slots=True)
class Success(Generic[T]):
    """Represents successful result containing a value.

    Args:
        value: The successful result value

    Example:
        >>> result = Success(42)
        >>> result.value
        42
        >>> result.is_success()
        True
    """

    value: T

    def is_success(self) -> bool:
        """Check if result is successful.

        Returns:
            Always True for Success instances
        """
        return True

    def map(self, f: Callable[[T], U]) -> Success[U] | Failure[E]:
        """Transform the success value using provided function.

        Args:
            f: Function to transform the value

        Returns:
            Success with transformed value

        Example:
            >>> Success(5).map(lambda x: x * 2)
            Success(value=10)
        """
        return Success(f(self.value))

    def unwrap(self) -> T:
        """Extract the success value.

        Returns:
            The wrapped value

        Example:
            >>> Success(42).unwrap()
            42
        """
        return self.value


@dataclass(frozen=True, slots=True)
class Failure(Generic[E]):
    """Represents failure result containing an error.

    Args:
        error: The error value (typically an Exception)

    Example:
        >>> result = Failure(ValueError("Invalid input"))
        >>> result.error
        ValueError('Invalid input')
        >>> result.is_success()
        False
    """

    error: E

    def is_success(self) -> bool:
        """Check if result is successful.

        Returns:
            Always False for Failure instances
        """
        return False

    def map(self, f: Callable[[Any], Any]) -> Failure[E]:
        """Mapping over a Failure returns the same Failure.

        Args:
            f: Function (ignored for Failure)

        Returns:
            Self (unchanged Failure)

        Example:
            >>> Failure(ValueError()).map(lambda x: x * 2)
            Failure(error=ValueError())
        """
        return self

    def unwrap(self) -> Never:
        """Attempt to extract value from Failure raises exception.

        Raises:
            The wrapped error if it's an Exception
            ValueError with string representation otherwise

        Example:
            >>> Failure(ValueError("test")).unwrap()
            Traceback (most recent call last):
            ValueError: test
        """
        if isinstance(self.error, Exception):
            raise self.error
        raise ValueError(str(self.error))


# Type alias for Result type (Success or Failure)
Result = Success[T] | Failure[E]


def try_result(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]:
    """Decorator to convert exception-based function to Result-returning function.

    Wraps a function that may raise exceptions, converting it to return a Result type.
    Successful execution returns Success with the return value.
    Any exception raised returns Failure with the exception.

    Args:
        func: Function that may raise exceptions

    Returns:
        Wrapped function returning Result[T, Exception]

    Example:
        >>> @try_result
        ... def divide(a: int, b: int) -> float:
        ...     return a / b
        ...
        >>> result = divide(10, 2)
        >>> result.unwrap()
        5.0
        >>> result = divide(10, 0)
        >>> isinstance(result.error, ZeroDivisionError)
        True

    Type Safety:
        The decorator preserves function signatures and provides full type inference:

        >>> @try_result
        ... def parse_int(s: str) -> int:
        ...     return int(s)
        ...
        >>> result: Result[int, Exception] = parse_int("42")
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[T, Exception]:
        try:
            return Success(func(*args, **kwargs))
        except Exception as e:
            return Failure(e)

    return wrapper


__all__ = [
    "Result",
    "Success",
    "Failure",
    "try_result",
]
