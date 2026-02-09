"""Result type pattern for explicit error handling.

This module provides Success and Failure types for type-safe error handling,
enabling explicit representation of success and failure cases in function signatures.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, Generic, Never, ParamSpec, TypeAlias, TypeVar, Union

from typing_extensions import dataclass_transform

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
P = ParamSpec("P")
C = TypeVar("C")


@dataclass_transform(frozen_default=True)
def _frozen_dataclass(cls: type[C]) -> type[C]:
    return dataclass(frozen=True, slots=True)(cls)


@_frozen_dataclass
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

    def is_failure(self) -> bool:
        """Check if result is a failure.

        Returns:
            Always False for Success instances
        """
        return False

    def map(self, f: Callable[[T], U]) -> Success[U]:
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

    def unwrap_or_else(self, default_fn: Callable[[E], T]) -> T:
        """Returns the contained success value, ignoring the default function.

        For Success instances, returns the wrapped value without calling default_fn.
        This enables lazy evaluation of defaults - the default computation is
        skipped entirely when the result is successful.

        Args:
            default_fn: A callable that would compute a default value from an error.
                Not called for Success instances.

        Returns:
            The wrapped success value.

        Example:
            >>> result = Success(42)
            >>> result.unwrap_or_else(lambda e: 0)
            42

            >>> result = Success("hello")
            >>> result.unwrap_or_else(lambda e: "default")
            'hello'
        """
        return self.value


@_frozen_dataclass
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

    def is_failure(self) -> bool:
        """Check if result is a failure.

        Returns:
            Always True for Failure instances
        """
        return True

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
            ValueError with type information otherwise

        Example:
            >>> Failure(ValueError("test")).unwrap()
            Traceback (most recent call last):
            ValueError: test
        """
        if isinstance(self.error, Exception):
            raise self.error
        emsg = f"Failure error is not an Exception: {self.error!r} (type={type(self.error).__name__})"
        raise ValueError(emsg)

    def unwrap_or_else(self, default_fn: Callable[[E], T]) -> T:
        """Computes a default value from the error using the provided function.

        For Failure instances, calls default_fn with the contained error and
        returns the result. This enables error-dependent default value computation.

        Args:
            default_fn: A callable that takes the error and returns a default value.

        Returns:
            The result of calling default_fn with the contained error.

        Example:
            >>> result: Result[int, str] = Failure("not found")
            >>> result.unwrap_or_else(lambda e: len(e))
            9

            >>> result = Failure(ValueError("invalid"))
            >>> result.unwrap_or_else(lambda e: 0)
            0

            >>> result = Failure("error")
            >>> result.unwrap_or_else(lambda e: f"default: {e}")
            'default: error'
        """
        return default_fn(self.error)


# Type alias for Result type (Success or Failure)
Result: TypeAlias = Union[Success[T], Failure[E]]


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
