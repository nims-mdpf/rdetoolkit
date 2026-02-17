"""Tests for magic variable resolution.

This module tests the extraction of magic variable components
from _legacy.py to _magic_variable.py.
"""

from __future__ import annotations


def test_magic_variable_resolver_import():
    """Verify MagicVariableResolver can be imported."""
    from rdetoolkit.invoicefile import MagicVariableResolver

    assert MagicVariableResolver is not None


def test_load_metadata_import():
    """Verify _load_metadata can be imported."""
    from rdetoolkit.invoicefile import _load_metadata

    assert callable(_load_metadata)


def test_apply_magic_variable_import():
    """Verify apply_magic_variable can be imported."""
    from rdetoolkit.invoicefile import apply_magic_variable

    assert callable(apply_magic_variable)


def test_backward_compatibility():
    """Verify backward compatibility of imports."""
    from rdetoolkit.invoicefile import (
        MagicVariableResolver,
        _load_metadata,
        apply_magic_variable,
    )

    assert MagicVariableResolver is not None
    assert callable(_load_metadata)
    assert callable(apply_magic_variable)


def test_magic_variable_resolver_from_module():
    """Verify MagicVariableResolver can be imported directly from module."""
    from rdetoolkit.invoicefile._magic_variable import MagicVariableResolver

    assert MagicVariableResolver is not None


def test_apply_magic_variable_from_module():
    """Verify apply_magic_variable can be imported directly from module."""
    from rdetoolkit.invoicefile._magic_variable import apply_magic_variable

    assert callable(apply_magic_variable)


def test_load_metadata_from_module():
    """Verify _load_metadata can be imported directly from module."""
    from rdetoolkit.invoicefile._magic_variable import _load_metadata

    assert callable(_load_metadata)
