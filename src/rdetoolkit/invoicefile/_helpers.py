"""Helper utilities for invoicefile package.

This module provides lazy import helpers and shared constants used across
the invoicefile package modules.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Module constants
STATIC_DIR = Path(__file__).parent.parent / "static"
EX_GENERALTERM = STATIC_DIR / "ex_generalterm.csv"
EX_SPECIFICTERM = STATIC_DIR / "ex_specificterm.csv"
MAGIC_VARIABLE_PATTERN = re.compile(r"\$\{([^{}]+)\}")


def _ensure_pandas() -> Any:
    """Lazy import of pandas library."""
    import pandas as pd

    return pd


def _ensure_openpyxl_styles() -> tuple[Any, Any, Any]:
    """Lazy import of openpyxl style classes."""
    from openpyxl.styles import Border, Font, Side

    return Border, Font, Side


def _ensure_openpyxl_utils() -> Any:
    """Lazy import of openpyxl utilities."""
    from openpyxl.utils import get_column_letter

    return get_column_letter


def _ensure_chardet() -> Any:
    """Lazy import of chardet library."""
    import chardet

    return chardet


def _ensure_validation_error() -> type[Exception]:
    """Lazy import of pydantic ValidationError."""
    from pydantic import ValidationError

    return ValidationError


def _ensure_logger() -> Callable[..., Any]:
    """Lazy import of rdetoolkit logger."""
    from rdetoolkit.rdelogger import get_logger

    return get_logger


# Module-level logger instance
logger = _ensure_logger()(__name__)
