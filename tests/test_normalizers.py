"""Unit tests for column normalizers and validators."""

from __future__ import annotations

import pandas as pd
import pytest

from rdetoolkit.graph.normalizers import ColumnNormalizer, validate_column_specs
from rdetoolkit.graph.exceptions import ColumnNotFoundError


# =============================================================================
# ColumnNormalizer Tests
# =============================================================================


def test_column_normalizer_to_index_int():
    """Test to_index with integer input."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    assert normalizer.to_index(0) == 0
    assert normalizer.to_index(2) == 2


def test_column_normalizer_to_index_str():
    """Test to_index with string column name."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    assert normalizer.to_index("A") == 0
    assert normalizer.to_index("C") == 2


def test_column_normalizer_to_index_out_of_range():
    """Test to_index with out-of-range index."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    with pytest.raises(ColumnNotFoundError, match="out of range"):
        normalizer.to_index(10)


def test_column_normalizer_to_index_invalid_name():
    """Test to_index with non-existent column name."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    with pytest.raises(ColumnNotFoundError, match="not found"):
        normalizer.to_index("Z")


def test_column_normalizer_to_name_int():
    """Test to_name with integer input."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    assert normalizer.to_name(0) == "A"
    assert normalizer.to_name(2) == "C"


def test_column_normalizer_to_name_str():
    """Test to_name with string column name."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    assert normalizer.to_name("A") == "A"
    assert normalizer.to_name("B") == "B"


def test_column_normalizer_normalize_columns_single_int():
    """Test normalize_columns with single integer."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns(0)
    assert result == ["A"]


def test_column_normalizer_normalize_columns_list_ints():
    """Test normalize_columns with list of integers."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns([0, 2])
    assert result == ["A", "C"]


def test_column_normalizer_normalize_columns_single_str():
    """Test normalize_columns with single string."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns("A")
    assert result == ["A"]


def test_column_normalizer_normalize_columns_list_strs():
    """Test normalize_columns with list of strings."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns(["A", "C"])
    assert result == ["A", "C"]


def test_column_normalizer_normalize_columns_mixed():
    """Test normalize_columns with mixed int and string."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns([0, "C"])
    assert result == ["A", "C"]


def test_column_normalizer_normalize_columns_none_default_all():
    """Test normalize_columns with None (default all columns)."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns(None)
    assert result == ["A", "B", "C"]


def test_column_normalizer_normalize_columns_none_with_exclude():
    """Test normalize_columns with None and exclude parameter."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns(None, exclude=[0])
    assert result == ["B", "C"]


def test_column_normalizer_normalize_columns_none_no_default():
    """Test normalize_columns with None and default_all=False."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns(None, default_all=False)
    assert result == []


def test_column_normalizer_normalize_x_y_pairs_single_x_multiple_y():
    """Test normalize_x_y_pairs with single x and multiple y."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_x_y_pairs(0, [1, 2])
    assert result == [("A", "B"), ("A", "C")]


def test_column_normalizer_normalize_x_y_pairs_matching_lengths():
    """Test normalize_x_y_pairs with matching x and y lengths."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_x_y_pairs([0, 1], [2, 3])
    assert result == [("A", "C"), ("B", "D")]


def test_column_normalizer_normalize_x_y_pairs_y_none():
    """Test normalize_x_y_pairs with y_cols=None (use all except x)."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_x_y_pairs(0, None)
    assert result == [("A", "B"), ("A", "C")]


def test_column_normalizer_normalize_x_y_pairs_length_mismatch():
    """Test normalize_x_y_pairs with mismatched lengths."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4], "E": [5]})
    normalizer = ColumnNormalizer(df)

    with pytest.raises(ValueError, match="must be equal"):
        normalizer.normalize_x_y_pairs([0, 1], [2, 3, 4])


def test_column_normalizer_normalize_direction_cols_basic():
    """Test normalize_direction_cols with basic input."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_direction_cols([3, 3], 2)
    assert result == [3, 3]


def test_column_normalizer_normalize_direction_cols_with_none():
    """Test normalize_direction_cols with None entries."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_direction_cols([3, None, 3], 3)
    assert result == [3, None, 3]


def test_column_normalizer_normalize_direction_cols_fewer_than_y():
    """Test normalize_direction_cols with fewer entries than y_cols."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_direction_cols([3], 3)
    assert result == [3, None, None]  # Padded with None


def test_column_normalizer_normalize_direction_cols_none_input():
    """Test normalize_direction_cols with None input."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_direction_cols(None, 2)
    assert result == [None, None]


def test_column_normalizer_normalize_direction_cols_more_than_y():
    """Test normalize_direction_cols with more entries than y_cols."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})
    normalizer = ColumnNormalizer(df)

    with pytest.raises(ValueError, match="cannot exceed"):
        normalizer.normalize_direction_cols([3, 3, 3], 2)


def test_column_normalizer_with_unit_names():
    """Test ColumnNormalizer with column names containing units."""
    df = pd.DataFrame({"Time (s)": [1], "Current (mA)": [2], "Voltage (V)": [3]})
    normalizer = ColumnNormalizer(df)

    result = normalizer.normalize_columns(["Time (s)", "Voltage (V)"])
    assert result == ["Time (s)", "Voltage (V)"]


# =============================================================================
# validate_column_specs Tests
# =============================================================================


def test_validate_column_specs_basic():
    """Test validate_column_specs with basic valid input."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})

    result = validate_column_specs(df, x_col=0, y_cols=[1, 2])

    assert result["x_cols"] == ["A"]
    assert result["y_cols"] == ["B", "C"]
    assert result["pairs"] == [("A", "B"), ("A", "C")]
    assert result["direction_cols"] == [None, None]


def test_validate_column_specs_with_direction():
    """Test validate_column_specs with direction columns."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})

    result = validate_column_specs(df, x_col=0, y_cols=[1, 2], direction_cols=[3, 3])

    assert result["direction_cols"] == [3, 3]


def test_validate_column_specs_x_none_defaults_to_0():
    """Test validate_column_specs with x_col=None (defaults to 0)."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})

    result = validate_column_specs(df, x_col=None, y_cols=[1, 2])

    assert result["x_cols"] == ["A"]  # Defaults to column 0


def test_validate_column_specs_y_none_uses_all_except_x():
    """Test validate_column_specs with y_cols=None."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})

    result = validate_column_specs(df, x_col=0, y_cols=None)

    assert result["y_cols"] == ["B", "C"]  # All except x_col


def test_validate_column_specs_matching_x_y_counts():
    """Test validate_column_specs with matching x and y counts."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})

    result = validate_column_specs(df, x_col=[0, 1], y_cols=[2, 3])

    assert result["pairs"] == [("A", "C"), ("B", "D")]


def test_validate_column_specs_invalid_column():
    """Test validate_column_specs with invalid column specification."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})

    with pytest.raises(ColumnNotFoundError):
        validate_column_specs(df, x_col="Z", y_cols=[1, 2])


def test_validate_column_specs_direction_cols_too_many():
    """Test validate_column_specs with too many direction_cols."""
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})

    with pytest.raises(ValueError, match="cannot exceed"):
        validate_column_specs(df, x_col=0, y_cols=[1, 2], direction_cols=[3, 3, 3])


def test_validate_column_specs_direction_col_single_str():
    """Single string direction column is normalized correctly."""
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "dir": ["x", "y"]})

    result = validate_column_specs(df, x_col=0, y_cols=[1], direction_cols="dir")

    assert result["direction_cols"] == [2]


def test_validate_column_specs_direction_col_single_int():
    """Single integer direction column is normalized correctly."""
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "dir": ["x", "y"]})

    result = validate_column_specs(df, x_col=0, y_cols=[1], direction_cols=2)

    assert result["direction_cols"] == [2]
