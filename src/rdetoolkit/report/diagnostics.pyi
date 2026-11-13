from typing import Any

DIAGNOSTICS_SCHEMA_VERSION: str
DIAGNOSTICS_FORMAT: str
MAX_ENTRIES: int
MAX_IDENTIFIER_LENGTH: int

def diagnostic(
    *,
    code: int | None,
    severity: str,
    name: str,
    message: str,
    remediation: str,
    subject: str,
    location: dict[str, Any] | None = None,
) -> dict[str, Any]: ...
def envelope(diagnostics: list[dict[str, Any]], *, truncated: bool = False, **extra: Any) -> dict[str, Any]: ...
def safe_identifier(value: object) -> str | None: ...
def safe_error(error: object) -> dict[str, Any]: ...
