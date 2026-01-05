from __future__ import annotations

import sys
from typing import Any, Callable, Generic, TypeVar, Union

if sys.version_info >= (3, 11):
    from typing import Never, ParamSpec, TypeAlias
else:
    from typing_extensions import Never, ParamSpec, TypeAlias

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
P = ParamSpec("P")

class Success(Generic[T]):
    """Represents successful result containing a value.

    This is an immutable frozen dataclass (slots when supported).
    """

    value: T
    def __init__(self, value: T) -> None: ...
    def is_success(self) -> bool: ...
    def map(self, f: Callable[[T], U]) -> Success[U]: ...
    def unwrap(self) -> T: ...

class Failure(Generic[E]):
    """Represents failure result containing an error.

    This is an immutable frozen dataclass (slots when supported).
    """

    error: E
    def __init__(self, error: E) -> None: ...
    def is_success(self) -> bool: ...
    def map(self, f: Callable[[Any], Any]) -> Failure[E]: ...
    def unwrap(self) -> Never: ...

Result: TypeAlias = Union[Success[T], Failure[E]]

def try_result(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]: ...
