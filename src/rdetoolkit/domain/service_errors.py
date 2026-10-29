"""Catalog-backed errors for common domain services."""

from __future__ import annotations

from typing import Any

from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError, RdeInternalError, RdeValidationError


def execution_error(code: int, message: str) -> RdeExecutionError:
    """Create a catalogued domain execution error.

    Args:
        code: Integer code present in ``ERROR_CATALOG``.
        message: Operation-specific failure detail.

    Returns:
        Catalogued execution error.
    """
    return _error(RdeExecutionError, code, message)


def validation_error(code: int, message: str) -> RdeValidationError:
    """Create a catalogued domain validation error.

    Args:
        code: Integer code present in ``ERROR_CATALOG``.
        message: Validation failure detail.

    Returns:
        Catalogued validation error.
    """
    return _error(RdeValidationError, code, message)


def internal_error(code: int, message: str) -> RdeInternalError:
    """Create a catalogued domain internal error.

    Args:
        code: Integer code present in ``ERROR_CATALOG``.
        message: Invariant failure detail.

    Returns:
        Catalogued internal error.
    """
    return _error(RdeInternalError, code, message)


def _error(error_type: type[Any], code: int, message: str) -> Any:
    definition = ERROR_CATALOG[code]
    rendered = f"{message} Remediation: {definition.remediation}"
    return error_type(code=code, name=definition.name, message=rendered)
