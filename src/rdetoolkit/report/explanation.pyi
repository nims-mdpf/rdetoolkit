from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdetoolkit.report.run_report import RunReport

EXPLAIN_COMMAND: str

class IterationNotInReportError(LookupError): ...

@dataclass(frozen=True, slots=True)
class Explanation:
    document: dict[str, Any]
    entries: tuple[dict[str, Any], ...]
    report: RunReport

def explain_report(path: Path, *, iteration: int | None = None, full_traceback: bool = False) -> Explanation: ...
def render_text(explanation: Explanation, report_path: Path, *, full_traceback: bool = False) -> str: ...
