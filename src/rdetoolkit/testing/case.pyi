import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pytest import MarkDecorator

from rdetoolkit.templates.base import ProcessingTemplate
from rdetoolkit.testing.runner import RdeTestResult
from rdetoolkit.types import RdeConfig

MARKER_NAME: str

class RdeCaseError(ValueError): ...

@dataclass(frozen=True)
class RdeCase:
    flow: Callable[..., Any]
    project: Path
    expect_status: str = "success"
    expect_files: tuple[PurePosixPath, ...] = ()
    expect_error_code: int | None = None
    expect_phase: str | None = None
    config: RdeConfig | Mapping[str, Any] | None = None
    checks: tuple[Callable[[RdeTestResult], object], ...] = ()

def rde_case(
    *,
    flow: Callable[..., Any] | type[ProcessingTemplate],
    project: str | os.PathLike[str],
    expect_status: str = "success",
    expect_files: Sequence[str | os.PathLike[str]] = (),
    expect_error_code: int | None = None,
    expect_phase: str | None = None,
    config: RdeConfig | Mapping[str, Any] | None = None,
    checks: Sequence[Callable[[RdeTestResult], object]] = (),
) -> MarkDecorator: ...
def case_from_marker(args: Sequence[object], kwargs: Mapping[str, object], *, rootpath: Path) -> RdeCase: ...
def check_case(case: RdeCase, result: RdeTestResult) -> list[str]: ...
def missing_rde_run_message(nodeid: str) -> str: ...
def missing_marker_message(nodeid: str) -> str: ...
