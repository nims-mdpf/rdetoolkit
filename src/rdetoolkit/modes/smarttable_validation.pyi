from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class SmartTableDiagnostic:
    row: int
    column: str
    expected_type: str
    reason: str
    suggestion: str

def validate_smarttable_mapping(table_path: Path, invoice_schema_path: Path, metadata_def_path: Path) -> tuple[SmartTableDiagnostic, ...]: ...
def ensure_smarttable_valid(inputdata_path: Path, tasksupport_path: Path) -> None: ...
