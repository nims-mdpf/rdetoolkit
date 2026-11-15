from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar, Union

if sys.version_info >= (3, 11):
    from typing import Never, ParamSpec, TypeAlias
else:
    from typing_extensions import Never, ParamSpec, TypeAlias

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
P = ParamSpec("P")

# Declared as frozen dataclasses because that is what the runtime builds
# (``dataclass(frozen=True, slots=True)``): the payload is read-only, instances
# compare by value, and ``__match_args__`` allows ``case Success(value):``.
@dataclass(frozen=True, slots=True)
class Success(Generic[T]):
    """Represents successful result containing a value.

    This is an immutable frozen dataclass with slots.
    """

    value: T
    def is_success(self) -> bool: ...
    def is_failure(self) -> bool: ...
    def map(self, f: Callable[[T], U]) -> Success[U]: ...
    def unwrap(self) -> T: ...
    def unwrap_or_else(self, default_fn: Callable[[E], T]) -> T: ...

@dataclass(frozen=True, slots=True)
class Failure(Generic[E]):
    """Represents failure result containing an error.

    This is an immutable frozen dataclass with slots.
    """

    error: E
    def is_success(self) -> bool: ...
    def is_failure(self) -> bool: ...
    def map(self, f: Callable[[Any], Any]) -> Failure[E]: ...
    def unwrap(self) -> Never: ...
    def unwrap_or_else(self, default_fn: Callable[[E], T]) -> T: ...

Result: TypeAlias = Union[Success[T], Failure[E]]

def try_result(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]: ...

__all__ = [
    "Result",
    "Success",
    "Failure",
    "try_result",
]
