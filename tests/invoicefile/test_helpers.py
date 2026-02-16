"""Tests for invoicefile._helpers module."""

from __future__ import annotations

import re
from pathlib import Path


def test_helpers_imports():
    """Verify all helper utilities can be imported."""
    from rdetoolkit.invoicefile._helpers import (
        EX_GENERALTERM,
        EX_SPECIFICTERM,
        MAGIC_VARIABLE_PATTERN,
        STATIC_DIR,
        _ensure_chardet,
        _ensure_logger,
        _ensure_openpyxl_styles,
        _ensure_openpyxl_utils,
        _ensure_pandas,
        _ensure_validation_error,
        logger,
    )

    # Verify constants
    assert isinstance(STATIC_DIR, Path)
    assert isinstance(EX_GENERALTERM, Path)
    assert isinstance(EX_SPECIFICTERM, Path)
    assert isinstance(MAGIC_VARIABLE_PATTERN, re.Pattern)

    # Verify lazy loaders work
    assert _ensure_pandas() is not None
    assert _ensure_logger() is not None
    assert logger is not None


def test_static_dir_path_correct():
    """Verify STATIC_DIR points to correct location."""
    from rdetoolkit.invoicefile._helpers import STATIC_DIR

    # Should point to src/rdetoolkit/static
    assert STATIC_DIR.name == "static"
    assert STATIC_DIR.exists()


def test_csv_files_exist():
    """Verify CSV template files exist at expected locations."""
    from rdetoolkit.invoicefile._helpers import EX_GENERALTERM, EX_SPECIFICTERM

    assert EX_GENERALTERM.exists()
    assert EX_SPECIFICTERM.exists()
    assert EX_GENERALTERM.suffix == ".csv"
    assert EX_SPECIFICTERM.suffix == ".csv"


def test_lazy_import_pandas():
    """Verify pandas lazy import returns pandas module."""
    from rdetoolkit.invoicefile._helpers import _ensure_pandas

    pd = _ensure_pandas()
    assert hasattr(pd, "DataFrame")


def test_lazy_import_openpyxl_styles():
    """Verify openpyxl styles lazy import returns correct classes."""
    from rdetoolkit.invoicefile._helpers import _ensure_openpyxl_styles

    Border, Font, Side = _ensure_openpyxl_styles()
    assert Border is not None
    assert Font is not None
    assert Side is not None


def test_lazy_import_openpyxl_utils():
    """Verify openpyxl utils lazy import returns get_column_letter."""
    from rdetoolkit.invoicefile._helpers import _ensure_openpyxl_utils

    get_column_letter = _ensure_openpyxl_utils()
    assert callable(get_column_letter)


def test_lazy_import_chardet():
    """Verify chardet lazy import returns chardet module."""
    from rdetoolkit.invoicefile._helpers import _ensure_chardet

    chardet = _ensure_chardet()
    assert hasattr(chardet, "detect")


def test_lazy_import_validation_error():
    """Verify ValidationError lazy import returns exception class."""
    from rdetoolkit.invoicefile._helpers import _ensure_validation_error

    ValidationError = _ensure_validation_error()
    assert issubclass(ValidationError, Exception)


def test_lazy_import_logger():
    """Verify logger lazy import returns get_logger function."""
    from rdetoolkit.invoicefile._helpers import _ensure_logger

    get_logger = _ensure_logger()
    assert callable(get_logger)


def test_magic_variable_pattern():
    """Verify MAGIC_VARIABLE_PATTERN matches expected patterns."""
    from rdetoolkit.invoicefile._helpers import MAGIC_VARIABLE_PATTERN

    # Should match ${variable_name}
    assert MAGIC_VARIABLE_PATTERN.search("${test}")
    assert MAGIC_VARIABLE_PATTERN.search("prefix ${var} suffix")
    assert MAGIC_VARIABLE_PATTERN.search("${complex_name_123}")

    # Should not match invalid patterns
    assert not MAGIC_VARIABLE_PATTERN.search("$test")
    assert not MAGIC_VARIABLE_PATTERN.search("{test}")
    assert not MAGIC_VARIABLE_PATTERN.search("${}")
