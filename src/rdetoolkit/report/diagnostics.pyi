from typing import Any

DIAGNOSTICS_SCHEMA_VERSION: str

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
def envelope(diagnostics: list[dict[str, Any]], **extra: Any) -> dict[str, Any]: ...
def safe_error(error: object) -> dict[str, Any]: ...
