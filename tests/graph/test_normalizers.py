"""Unit tests for rdetoolkit.graph.normalizers module.

This module tests column specification normalization logic.
"""

from __future__ import annotations

import pandas as pd
import pytest

from rdetoolkit.graph.exceptions import ColumnNotFoundError
from rdetoolkit.graph.normalizers import ColumnNormalizer, validate_column_specs


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Sample DataFrame for testing."""
    return pd.DataFrame({
        'voltage': [1.0, 2.0, 3.0],
        'current': [0.1, 0.2, 0.3],
        'power': [0.1, 0.4, 0.9],
        'direction': ['charge', 'charge', 'discharge'],
    })


class TestColumnNormalizerToIndex:
    """Test ColumnNormalizer.to_index() method."""

    def test_converts_valid_index_to_index(self, sample_df: pd.DataFrame):
        """Valid index is returned as-is."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.to_index(0) == 0
        assert normalizer.to_index(1) == 1
        assert normalizer.to_index(3) == 3

    def test_converts_valid_name_to_index(self, sample_df: pd.DataFrame):
        """Valid column name is converted to index."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.to_index('voltage') == 0
        assert normalizer.to_index('current') == 1
        assert normalizer.to_index('power') == 2
        assert normalizer.to_index('direction') == 3

    def test_raises_on_out_of_range_index(self, sample_df: pd.DataFrame):
        """Out of range index raises ColumnNotFoundError."""
        normalizer = ColumnNormalizer(sample_df)

        with pytest.raises(ColumnNotFoundError, match="out of range"):
            normalizer.to_index(4)

        with pytest.raises(ColumnNotFoundError, match="out of range"):
            normalizer.to_index(-1)

    def test_raises_on_invalid_column_name(self, sample_df: pd.DataFrame):
        """Invalid column name raises ColumnNotFoundError."""
        normalizer = ColumnNormalizer(sample_df)

        with pytest.raises(ColumnNotFoundError, match="not found"):
            normalizer.to_index('nonexistent')

    def test_raises_on_invalid_type(self, sample_df: pd.DataFrame):
        """Invalid type raises TypeError."""
        normalizer = ColumnNormalizer(sample_df)

        with pytest.raises(TypeError, match="must be int or str"):
            normalizer.to_index([0])  # type: ignore


class TestColumnNormalizerToName:
    """Test ColumnNormalizer.to_name() method."""

    def test_converts_valid_index_to_name(self, sample_df: pd.DataFrame):
        """Valid index is converted to column name."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.to_name(0) == 'voltage'
        assert normalizer.to_name(1) == 'current'
        assert normalizer.to_name(2) == 'power'

    def test_converts_valid_name_to_name(self, sample_df: pd.DataFrame):
        """Valid column name is returned as-is."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.to_name('voltage') == 'voltage'
        assert normalizer.to_name('current') == 'current'

    def test_raises_on_out_of_range_index(self, sample_df: pd.DataFrame):
        """Out of range index raises ColumnNotFoundError."""
        normalizer = ColumnNormalizer(sample_df)

        with pytest.raises(ColumnNotFoundError, match="out of range"):
            normalizer.to_name(4)

    def test_raises_on_invalid_column_name(self, sample_df: pd.DataFrame):
        """Invalid column name raises ColumnNotFoundError."""
        normalizer = ColumnNormalizer(sample_df)

        with pytest.raises(ColumnNotFoundError, match="not found"):
            normalizer.to_name('nonexistent')


class TestColumnNormalizerNormalizeColumns:
    """Test ColumnNormalizer.normalize_columns() method."""

    def test_normalizes_single_index(self, sample_df: pd.DataFrame):
        """Single index is normalized to list with column name."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.normalize_columns(0) == ['voltage']
        assert normalizer.normalize_columns(2) == ['power']

    def test_normalizes_single_name(self, sample_df: pd.DataFrame):
        """Single name is normalized to list with column name."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.normalize_columns('current') == ['current']

    def test_normalizes_list_of_indices(self, sample_df: pd.DataFrame):
        """List of indices is normalized to list of names."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.normalize_columns([0, 2]) == ['voltage', 'power']
        assert normalizer.normalize_columns([1, 3]) == ['current', 'direction']

    def test_normalizes_list_of_names(self, sample_df: pd.DataFrame):
        """List of names is normalized to list of names."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.normalize_columns(['voltage', 'current']) == ['voltage', 'current']

    def test_normalizes_mixed_list(self, sample_df: pd.DataFrame):
        """Mixed list of indices and names is normalized."""
        normalizer = ColumnNormalizer(sample_df)
        assert normalizer.normalize_columns([0, 'current', 2]) == ['voltage', 'current', 'power']

    def test_normalizes_none_to_all_columns(self, sample_df: pd.DataFrame):
        """None with default_all=True returns all columns."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_columns(None)
        assert result == ['voltage', 'current', 'power', 'direction']

    def test_normalizes_none_with_exclude(self, sample_df: pd.DataFrame):
        """None with exclude returns all columns except excluded ones."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_columns(None, exclude=[0])
        assert result == ['current', 'power', 'direction']

        result = normalizer.normalize_columns(None, exclude=['voltage', 'direction'])
        assert result == ['current', 'power']

    def test_normalizes_none_with_default_all_false(self, sample_df: pd.DataFrame):
        """None with default_all=False returns empty list."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_columns(None, default_all=False)
        assert result == []

    def test_raises_on_invalid_column_in_list(self, sample_df: pd.DataFrame):
        """Invalid column in list raises ColumnNotFoundError."""
        normalizer = ColumnNormalizer(sample_df)

        with pytest.raises(ColumnNotFoundError):
            normalizer.normalize_columns([0, 'nonexistent'])


class TestColumnNormalizerNormalizeXYPairs:
    """Test ColumnNormalizer.normalize_x_y_pairs() method."""

    def test_single_x_with_explicit_y_list(self, sample_df: pd.DataFrame):
        """Single x with y list creates pairs with same x."""
        normalizer = ColumnNormalizer(sample_df)
        pairs = normalizer.normalize_x_y_pairs(0, [1, 2])
        assert pairs == [('voltage', 'current'), ('voltage', 'power')]

    def test_single_x_with_none_y(self, sample_df: pd.DataFrame):
        """Single x with None y uses all columns except x."""
        normalizer = ColumnNormalizer(sample_df)
        pairs = normalizer.normalize_x_y_pairs(0, None)
        assert pairs == [
            ('voltage', 'current'),
            ('voltage', 'power'),
            ('voltage', 'direction'),
        ]

    def test_single_x_name_with_y_names(self, sample_df: pd.DataFrame):
        """Single x name with y names creates pairs."""
        normalizer = ColumnNormalizer(sample_df)
        pairs = normalizer.normalize_x_y_pairs('voltage', ['current', 'power'])
        assert pairs == [('voltage', 'current'), ('voltage', 'power')]

    def test_multiple_x_with_matching_y(self, sample_df: pd.DataFrame):
        """Multiple x with matching length y creates corresponding pairs."""
        normalizer = ColumnNormalizer(sample_df)
        pairs = normalizer.normalize_x_y_pairs([0, 1], [2, 3])
        assert pairs == [('voltage', 'power'), ('current', 'direction')]

    def test_multiple_x_names_with_y_names(self, sample_df: pd.DataFrame):
        """Multiple x names with y names creates corresponding pairs."""
        normalizer = ColumnNormalizer(sample_df)
        pairs = normalizer.normalize_x_y_pairs(
            ['voltage', 'current'],
            ['power', 'direction'],
        )
        assert pairs == [('voltage', 'power'), ('current', 'direction')]

    def test_raises_on_length_mismatch(self, sample_df: pd.DataFrame):
        """Length mismatch between multiple x and y raises ValueError."""
        normalizer = ColumnNormalizer(sample_df)

        with pytest.raises(ValueError, match="must be equal"):
            normalizer.normalize_x_y_pairs([0, 1], [2])

        with pytest.raises(ValueError, match="must be equal"):
            normalizer.normalize_x_y_pairs([0, 1, 2], [1, 2])


class TestColumnNormalizerNormalizeDirectionCols:
    """Test ColumnNormalizer.normalize_direction_cols() method."""

    def test_normalizes_none_to_none_list(self, sample_df: pd.DataFrame):
        """None direction_cols returns list of None."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_direction_cols(None, y_cols_count=3)
        assert result == [None, None, None]

    def test_normalizes_indices(self, sample_df: pd.DataFrame):
        """Direction column indices are preserved."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_direction_cols([3, None, 3], y_cols_count=3)
        assert result == [3, None, 3]

    def test_normalizes_names_to_indices(self, sample_df: pd.DataFrame):
        """Direction column names are converted to indices."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_direction_cols(['direction'], y_cols_count=1)
        assert result == [3]

    def test_pads_with_none_if_shorter(self, sample_df: pd.DataFrame):
        """Shorter direction_cols is padded with None."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_direction_cols([3], y_cols_count=3)
        assert result == [3, None, None]

    def test_raises_if_longer(self, sample_df: pd.DataFrame):
        """Longer direction_cols raises ValueError."""
        normalizer = ColumnNormalizer(sample_df)

        # Linter-modified implementation raises error on length exceeding y_cols_count
        with pytest.raises(ValueError, match="cannot exceed"):
            normalizer.normalize_direction_cols([3, 3, 3, 3], y_cols_count=2)


class TestValidateColumnSpecs:
    """Test validate_column_specs() function."""

    def test_validates_basic_specs(self, sample_df: pd.DataFrame):
        """Basic column specifications are validated."""
        result = validate_column_specs(sample_df, x_col=0, y_cols=[1, 2])

        assert result['x_cols'] == ['voltage']
        assert result['y_cols'] == ['current', 'power']
        assert result['pairs'] == [('voltage', 'current'), ('voltage', 'power')]
        assert result['direction_cols'] == [None, None]

    def test_defaults_x_col_to_zero(self, sample_df: pd.DataFrame):
        """None x_col defaults to 0."""
        result = validate_column_specs(sample_df, x_col=None, y_cols=[1])

        assert result['x_cols'] == ['voltage']
        assert result['pairs'] == [('voltage', 'current')]

    def test_validates_with_direction_cols(self, sample_df: pd.DataFrame):
        """Direction columns are validated."""
        result = validate_column_specs(
            sample_df,
            x_col=0,
            y_cols=[1, 2],
            direction_cols=[3, None],
        )

        assert result['direction_cols'] == [3, None]

    def test_validates_with_column_names(self, sample_df: pd.DataFrame):
        """Column names are validated."""
        result = validate_column_specs(
            sample_df,
            x_col='voltage',
            y_cols=['current', 'power'],
        )

        assert result['x_cols'] == ['voltage']
        assert result['y_cols'] == ['current', 'power']

    def test_raises_on_invalid_column(self, sample_df: pd.DataFrame):
        """Invalid column specification raises ColumnNotFoundError."""
        with pytest.raises(ColumnNotFoundError):
            validate_column_specs(sample_df, x_col='nonexistent')

    def test_raises_on_invalid_pairing(self, sample_df: pd.DataFrame):
        """Invalid pairing raises ValueError."""
        with pytest.raises(ValueError):
            validate_column_specs(sample_df, x_col=[0, 1], y_cols=[2])


class TestColumnNormalizerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_handles_empty_dataframe(self):
        """Empty DataFrame is handled gracefully."""
        df = pd.DataFrame()
        normalizer = ColumnNormalizer(df)

        # normalize_columns with None should return empty list
        assert normalizer.normalize_columns(None) == []

    def test_handles_single_column_dataframe(self):
        """Single column DataFrame is handled."""
        df = pd.DataFrame({'A': [1, 2, 3]})
        normalizer = ColumnNormalizer(df)

        assert normalizer.to_name(0) == 'A'
        assert normalizer.normalize_columns(None) == ['A']

    def test_handles_duplicate_column_names(self):
        """DataFrame with duplicate column names (edge case)."""
        # Note: pandas allows duplicate column names
        df = pd.DataFrame([[1, 2]], columns=['A', 'A'])
        normalizer = ColumnNormalizer(df)

        # to_index returns first occurrence
        assert normalizer.to_index('A') == 0

    def test_preserves_column_order(self, sample_df: pd.DataFrame):
        """Column order is preserved in normalization."""
        normalizer = ColumnNormalizer(sample_df)
        result = normalizer.normalize_columns([2, 0, 1])
        assert result == ['power', 'voltage', 'current']


class TestColumnNormalizerLegacyBehavior:
    """Test Legacy-compatible behavior patterns."""

    def test_legacy_y_cols_none_excludes_x(self, sample_df: pd.DataFrame):
        """Legacy: y_cols=None excludes x_col from result."""
        normalizer = ColumnNormalizer(sample_df)

        # Legacy: if y_cols is None: y_cols = all except x_col
        pairs = normalizer.normalize_x_y_pairs(0, None)
        y_cols = [y for _, y in pairs]

        assert 'voltage' not in y_cols
        assert len(y_cols) == 3  # All columns except voltage

    def test_legacy_single_x_with_multiple_y(self, sample_df: pd.DataFrame):
        """Legacy: single x is paired with each y."""
        normalizer = ColumnNormalizer(sample_df)

        # Legacy: if len(x_cols) == 1: x_cols = x_cols * len(y_cols)
        pairs = normalizer.normalize_x_y_pairs(0, [1, 2, 3])

        assert len(pairs) == 3
        assert all(x == 'voltage' for x, _ in pairs)

    def test_legacy_multiple_x_multiple_y_equal_length(self, sample_df: pd.DataFrame):
        """Legacy: equal length x and y are paired element-wise."""
        normalizer = ColumnNormalizer(sample_df)

        pairs = normalizer.normalize_x_y_pairs([0, 1], [2, 3])

        assert pairs == [('voltage', 'power'), ('current', 'direction')]

    def test_legacy_direction_cols_padding(self, sample_df: pd.DataFrame):
        """Legacy: direction_cols shorter than y_cols is padded with None."""
        normalizer = ColumnNormalizer(sample_df)

        result = normalizer.normalize_direction_cols([3], y_cols_count=3)

        assert result == [3, None, None]
