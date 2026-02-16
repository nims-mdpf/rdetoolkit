"""Tests for SmartTableFile class."""

from __future__ import annotations


def test_smarttable_file_import():
    """Verify SmartTableFile can be imported."""
    from rdetoolkit.invoicefile import SmartTableFile

    assert SmartTableFile is not None


def test_smarttable_backward_compatibility():
    """Verify backward compatibility of SmartTableFile import."""
    from rdetoolkit.invoicefile import SmartTableFile

    # Verify class has expected methods
    assert hasattr(SmartTableFile, "read_table")
    assert hasattr(SmartTableFile, "generate_row_csvs_with_file_mapping")
    assert hasattr(SmartTableFile, "_validate_file")
    assert hasattr(SmartTableFile, "_find_file_by_relative_path")


def test_smarttable_from_new_module():
    """Verify SmartTableFile can be imported from new module."""
    from rdetoolkit.invoicefile._smarttable import SmartTableFile

    assert SmartTableFile is not None


def test_smarttable_same_class():
    """Verify SmartTableFile from different imports is the same class."""
    from rdetoolkit.invoicefile import SmartTableFile as SmartTableFile1
    from rdetoolkit.invoicefile._smarttable import SmartTableFile as SmartTableFile2

    assert SmartTableFile1 is SmartTableFile2
