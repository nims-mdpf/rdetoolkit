from __future__ import annotations

from typing import TypeVar, Generic, Callable, Never, ParamSpec

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
P = ParamSpec("P")

class Success(Generic[T]):
    """Represents successful result containing a value.

    This is an immutable frozen dataclass with slots for memory efficiency.
    """

    value: T
    def __init__(self, value: T) -> None: ...
    def is_success(self) -> bool: ...
    def map(self, f: Callable[[T], U]) -> Success[U] | Failure[E]: ...
    def unwrap(self) -> T: ...

class Failure(Generic[E]):
    """Represents failure result containing an error.

    This is an immutable frozen dataclass with slots for memory efficiency.
    """

    error: E
    def __init__(self, error: E) -> None: ...
    def is_success(self) -> bool: ...
    def map(self, f: Callable[[T], U]) -> Failure[E]: ...
    def unwrap(self) -> Never: ...

Result = Success[T] | Failure[E]

def try_result(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]: ...
