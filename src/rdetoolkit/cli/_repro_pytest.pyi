from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUSES: tuple[str, ...]

@dataclass(frozen=True)
class ArchivedRun:
    run_id: str | None
    status: str | None
    error_code: int | None

def parse_ref(ref: str) -> tuple[str, tuple[str, ...]]: ...
def archived_run(report_text: str) -> ArchivedRun: ...
def project_problems(project: Path, files: Mapping[str, tuple[int, str]], config_digest: str) -> list[str]: ...
def summarize(problems: Sequence[str]) -> str: ...
def project_expression(project: Path, output: Path) -> tuple[str, bool]: ...
def provenance_notes(manifest: Mapping[str, Any], verified_files: int | None) -> tuple[list[str], list[str]]: ...
def render_test(
    *,
    module: str,
    attributes: Sequence[str],
    project: str,
    run: ArchivedRun,
    expect_status: str | None,
    notes: Sequence[str],
) -> str: ...
