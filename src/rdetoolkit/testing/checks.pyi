from collections.abc import Callable, Iterable
from typing import TypeVar

from rdetoolkit.testing.runner import RdeTestResult

CHECK_ID_ATTRIBUTE: str

_CheckT = TypeVar("_CheckT", bound=Callable[..., object])

def rde_check(*, id: str) -> Callable[[_CheckT], _CheckT]: ...
def check_id(check: Callable[..., object]) -> str: ...
def run_checks(result: RdeTestResult, checks: Iterable[Callable[[RdeTestResult], object]]) -> list[str]: ...
