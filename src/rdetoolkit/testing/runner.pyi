import os
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from rdetoolkit.report.run_report import RunReport
from rdetoolkit.templates.base import ProcessingTemplate
from rdetoolkit.types import RdeConfig

ARTIFACT_ACCESS: ContextVar[list[PurePosixPath] | None]

@dataclass(frozen=True)
class RdeIterationSummary:
    index: int
    datatile_id: str
    status: str
    error_code: int | None = None
    error_name: str | None = None
    error_message: str | None = None

@dataclass(frozen=True)
class RdeTestResult:
    report: RunReport
    project_root: Path
    data_root: Path
    report_path: Path | None
    events_path: Path | None
    diagnostics_path: Path | None
    job_failed_path: Path | None
    @property
    def status(self) -> str: ...
    @property
    def iterations(self) -> tuple[RdeIterationSummary, ...]: ...
    def artifact_path(self, name: str | os.PathLike[str]) -> Path: ...
    def assert_success(self) -> None: ...
    def failure_summary(self, *, expected_status: str) -> str: ...
    def read_bytes(self, name: str | os.PathLike[str], *, max_bytes: int | None = ...) -> bytes: ...
    def read_text(self, name: str | os.PathLike[str], *, encoding: str = "utf-8", max_bytes: int | None = ...) -> str: ...
    def read_json(self, name: str | os.PathLike[str], *, max_bytes: int | None = ...) -> Any: ...
    def read_csv(
        self, name: str | os.PathLike[str], *, encoding: str = "utf-8", max_bytes: int | None = ...,
    ) -> list[dict[str, str]]: ...
    def iter_csv(self, name: str | os.PathLike[str], *, encoding: str = "utf-8") -> Iterator[dict[str, str]]: ...
    def assert_status(self, expected: str) -> None: ...
    def assert_error_code(self, code: int) -> None: ...
    def assert_artifact(self, name: str | os.PathLike[str], *, exists: bool = True) -> None: ...
    def assert_tree(
        self,
        expected: Iterable[str | os.PathLike[str]],
        *,
        root: str | os.PathLike[str] | None = None,
        ignore: Iterable[str] = (),
    ) -> None: ...
    def assert_json_subset(self, name: str | os.PathLike[str], expected: Mapping[str, Any]) -> None: ...
    def assert_json_equal(self, name: str | os.PathLike[str], expected: Any) -> None: ...
    def assert_csv_columns(self, name: str | os.PathLike[str], columns: Iterable[str], *, exact: bool = False) -> None: ...
    def assert_csv_rows(self, name: str | os.PathLike[str], expected: Sequence[Mapping[str, str]]) -> None: ...
    def assert_metadata_valid(
        self,
        name: str | os.PathLike[str] = "meta/metadata.json",
        *,
        definition: str | os.PathLike[str] | None = "tasksupport/metadata-def.json",
    ) -> None: ...
    def assert_invoice_valid(
        self,
        name: str | os.PathLike[str] = "invoice/invoice.json",
        *,
        schema: str | os.PathLike[str] = "tasksupport/invoice.schema.json",
    ) -> None: ...
    def assert_snapshot(
        self,
        artifact: str | os.PathLike[str],
        golden: str | os.PathLike[str],
        *,
        ignore_fields: Iterable[str] = (),
        ignore_columns: Iterable[str] = (),
        ignore_files: Iterable[str] = (),
        max_bytes: int = ...,
        allow_raw: bool = False,
    ) -> None: ...
    def assert_checks(self, *checks: Callable[[RdeTestResult], object]) -> None: ...

class RdeTestRunner:
    base_dir: Path
    def __init__(self, base_dir: Path) -> None: ...
    def run(
        self,
        *,
        flow: Callable[..., Any] | type[ProcessingTemplate],
        project: str | os.PathLike[str],
        config: RdeConfig | Mapping[str, Any] | None = None,
    ) -> RdeTestResult: ...
    @property
    def results(self) -> tuple[RdeTestResult, ...]: ...

def retained_runs_report(results: Sequence[RdeTestResult]) -> str: ...
def relative_artifact(name: str | os.PathLike[str]) -> PurePosixPath: ...
def _collect_result(report: RunReport, *, project_root: Path, data_root: Path) -> RdeTestResult: ...
