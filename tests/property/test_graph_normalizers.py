"""Property-based tests for rdetoolkit.graph.normalizers.

Tests invariants and edge cases for data normalization functions using Hypothesis.
This complements example-based tests by exploring a wide range of random inputs.
"""

from __future__ import annotations

import pandas as pd
import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import assume, given, strategies as st

from rdetoolkit.graph.exceptions import ColumnNotFoundError
from rdetoolkit.graph.normalizers import ColumnNormalizer, validate_column_specs
from tests.property.strategies import finite_floats, valid_column_names


# Custom strategies for normalizers
@st.composite
def dataframe_with_columns(draw, columns: list[str]) -> pd.DataFrame:
    """Generate DataFrame with specified columns.

    Args:
        draw: Hypothesis draw function
        columns: List of column names

    Returns:
        DataFrame with specified columns containing finite float values
    """
    n_rows = draw(st.integers(min_value=1, max_value=100))
    data = {col: draw(st.lists(finite_floats, min_size=n_rows, max_size=n_rows)) for col in columns}
    return pd.DataFrame(data)


@st.composite
def xy_pair_columns(draw) -> tuple[str, str]:
    """Generate valid x/y column pair names.

    Returns:
        Tuple of (x_col, y_col) with different names
    """
    x_col = draw(valid_column_names)
    y_col = draw(valid_column_names)
    assume(x_col != y_col)  # Ensure different column names
    return x_col, y_col


@st.composite
def direction_spec_list(draw, max_size: int = 10) -> list[int | str | None]:
    """Generate valid direction column specifications.

    Args:
        draw: Hypothesis draw function
        max_size: Maximum list size

    Returns:
        List of direction specifications (indices, names, or None)
    """
    return draw(
        st.lists(
            st.one_of(
                st.integers(min_value=0, max_value=10),
                valid_column_names,
                st.none(),
            ),
            min_size=1,
            max_size=max_size,
        ),
    )


@pytest.mark.property
class TestNormalizeXYPairsProperties:
    """Property-based tests for ColumnNormalizer.normalize_x_y_pairs()."""

    @given(
        x_col=valid_column_names,
        y_col=valid_column_names,
        data=st.data(),
    )
    def test_single_x_single_y_creates_one_pair(
        self,
        x_col: str,
        y_col: str,
        data: st.DataObject,
    ):
        """Property: Single x and single y columns create exactly one pair.

        Given: DataFrame with x and y columns
        When: Normalizing x-y pairs with single x and single y
        Then: Result is a list with exactly one (x, y) tuple
        """
        # Given: DataFrame with x and y columns
        assume(x_col != y_col)
        df = data.draw(dataframe_with_columns([x_col, y_col]))
        normalizer = ColumnNormalizer(df)

        # When: Normalizing x-y pairs
        result = normalizer.normalize_x_y_pairs(x_col, [y_col])

        # Then: Result has exactly one pair
        assert len(result) == 1
        assert result[0] == (x_col, y_col)

    @given(
        x_col=valid_column_names,
        y_cols=st.lists(valid_column_names, min_size=1, max_size=10, unique=True),
        data=st.data(),
    )
    def test_single_x_multiple_y_pairs_with_same_x(
        self,
        x_col: str,
        y_cols: list[str],
        data: st.DataObject,
    ):
        """Property: Single x with multiple y creates pairs all using same x.

        Given: DataFrame with one x column and multiple y columns
        When: Normalizing x-y pairs with single x and multiple y
        Then: All pairs have the same x column
        """
        # Given: DataFrame with x and y columns
        assume(x_col not in y_cols)
        all_cols = [x_col] + y_cols
        df = data.draw(dataframe_with_columns(all_cols))
        normalizer = ColumnNormalizer(df)

        # When: Normalizing x-y pairs
        result = normalizer.normalize_x_y_pairs(x_col, y_cols)

        # Then: All pairs have same x
        assert len(result) == len(y_cols)
        assert all(x == x_col for x, _ in result)
        assert [y for _, y in result] == y_cols

    @given(
        x_cols=st.lists(valid_column_names, min_size=2, max_size=5, unique=True),
        data=st.data(),
    )
    def test_multiple_x_equal_y_creates_paired_tuples(
        self,
        x_cols: list[str],
        data: st.DataObject,
    ):
        """Property: Equal-length x and y lists create element-wise pairs.

        Given: DataFrame with equal number of x and y columns
        When: Normalizing x-y pairs with matching lengths
        Then: Pairs are created element-wise (zip behavior)
        """
        # Given: Generate y_cols different from x_cols
        y_cols = data.draw(
            st.lists(
                valid_column_names,
                min_size=len(x_cols),
                max_size=len(x_cols),
                unique=True,
            ),
        )
        assume(set(x_cols).isdisjoint(set(y_cols)))

        all_cols = x_cols + y_cols
        df = data.draw(dataframe_with_columns(all_cols))
        normalizer = ColumnNormalizer(df)

        # When: Normalizing x-y pairs
        result = normalizer.normalize_x_y_pairs(x_cols, y_cols)

        # Then: Pairs are element-wise
        assert result == list(zip(x_cols, y_cols))

    @given(
        x_cols=st.lists(valid_column_names, min_size=2, max_size=5, unique=True),
        y_cols=st.lists(valid_column_names, min_size=1, max_size=5, unique=True),
        data=st.data(),
    )
    def test_length_mismatch_raises_valueerror(
        self,
        x_cols: list[str],
        y_cols: list[str],
        data: st.DataObject,
    ):
        """Property: Mismatched lengths (except single x) raise ValueError.

        Given: DataFrame with different numbers of x and y columns
        When: Normalizing x-y pairs with mismatched lengths
        Then: ValueError is raised unless x_cols has exactly one element
        """
        # Given: Ensure different lengths and no overlap
        assume(len(x_cols) != len(y_cols))
        assume(len(x_cols) > 1)  # Not single x case
        assume(set(x_cols).isdisjoint(set(y_cols)))

        all_cols = x_cols + y_cols
        df = data.draw(dataframe_with_columns(all_cols))
        normalizer = ColumnNormalizer(df)

        # When/Then: Should raise ValueError
        with pytest.raises(ValueError, match="must be equal"):
            normalizer.normalize_x_y_pairs(x_cols, y_cols)

    @given(
        x_col=valid_column_names,
        data=st.data(),
    )
    def test_y_cols_none_excludes_x_col(
        self,
        x_col: str,
        data: st.DataObject,
    ):
        """Property: y_cols=None uses all columns except x_col.

        Given: DataFrame with multiple columns
        When: Normalizing with y_cols=None
        Then: All columns except x_col are used as y columns
        """
        # Given: DataFrame with at least 2 columns
        other_cols = data.draw(
            st.lists(valid_column_names, min_size=1, max_size=5, unique=True),
        )
        assume(x_col not in other_cols)

        all_cols = [x_col] + other_cols
        df = data.draw(dataframe_with_columns(all_cols))
        normalizer = ColumnNormalizer(df)

        # When: Normalizing with y_cols=None
        result = normalizer.normalize_x_y_pairs(x_col, None)

        # Then: All columns except x_col are used
        y_columns = [y for _, y in result]
        assert set(y_columns) == set(other_cols)
        assert x_col not in y_columns


@pytest.mark.property
class TestNormalizeDirectionColsProperties:
    """Property-based tests for ColumnNormalizer.normalize_direction_cols()."""

    @given(
        y_cols_count=st.integers(min_value=1, max_value=20),
        data=st.data(),
    )
    def test_none_direction_fills_with_none(
        self,
        y_cols_count: int,
        data: st.DataObject,
    ):
        """Property: direction_cols=None creates list of None with correct length.

        Given: y_cols_count specification
        When: direction_cols is None
        Then: Result is list of None with length equal to y_cols_count
        """
        # Given: DataFrame (any columns)
        cols = data.draw(
            st.lists(valid_column_names, min_size=1, max_size=10, unique=True),
        )
        df = data.draw(dataframe_with_columns(cols))
        normalizer = ColumnNormalizer(df)

        # When: Normalizing with None direction_cols
        result = normalizer.normalize_direction_cols(None, y_cols_count)

        # Then: All elements are None
        assert len(result) == y_cols_count
        assert all(val is None for val in result)

    @given(
        direction_count=st.integers(min_value=1, max_value=5),
        extra_count=st.integers(min_value=1, max_value=5),
        data=st.data(),
    )
    def test_shorter_list_pads_with_none(
        self,
        direction_count: int,
        extra_count: int,
        data: st.DataObject,
    ):
        """Property: Shorter direction list is padded with None to match y_cols.

        Given: direction_specs shorter than y_cols_count
        When: Normalizing direction columns
        Then: Result is padded with None to match y_cols_count
        """
        # Given: y_cols_count larger than direction_count
        y_cols_count = direction_count + extra_count

        cols = data.draw(
            st.lists(
                valid_column_names,
                min_size=max(y_cols_count, 6),
                max_size=max(y_cols_count + 5, 10),
                unique=True,
            ),
        )
        df = data.draw(dataframe_with_columns(cols))
        normalizer = ColumnNormalizer(df)

        direction_specs = data.draw(
            st.lists(
                st.one_of(st.integers(min_value=0, max_value=len(cols) - 1), st.none()),
                min_size=direction_count,
                max_size=direction_count,
            ),
        )

        # When: Normalizing direction columns
        # Cast to satisfy mypy - direction_specs is list[int | None] which is compatible
        result = normalizer.normalize_direction_cols(
            direction_specs,  # type: ignore[arg-type]
            y_cols_count,
        )

        # Then: Length matches y_cols_count
        assert len(result) == y_cols_count
        # Initial elements match input
        assert result[:direction_count] == direction_specs
        # Remaining elements are None
        assert all(val is None for val in result[direction_count:])

    @given(
        direction_count=st.integers(min_value=3, max_value=10),
        y_cols_count=st.integers(min_value=1, max_value=5),
        data=st.data(),
    )
    def test_longer_list_raises_valueerror(
        self,
        direction_count: int,
        y_cols_count: int,
        data: st.DataObject,
    ):
        """Property: direction list longer than y_cols raises ValueError.

        Given: direction_specs longer than y_cols_count
        When: Normalizing direction columns
        Then: ValueError is raised
        """
        # Given: direction_specs longer than y_cols_count
        assume(direction_count > y_cols_count)

        cols = data.draw(
            st.lists(
                valid_column_names,
                min_size=max(direction_count, 5),
                max_size=15,
                unique=True,
            ),
        )
        df = data.draw(dataframe_with_columns(cols))
        normalizer = ColumnNormalizer(df)

        direction_specs = data.draw(
            st.lists(
                st.one_of(st.integers(min_value=0, max_value=len(cols) - 1), st.none()),
                min_size=direction_count,
                max_size=direction_count,
            ),
        )

        # When/Then: Should raise ValueError
        with pytest.raises(ValueError, match="cannot exceed"):
            normalizer.normalize_direction_cols(
                direction_specs,  # type: ignore[arg-type]
                y_cols_count,
            )

    @given(
        direction_names=st.lists(valid_column_names, min_size=1, max_size=5, unique=True),
        data=st.data(),
    )
    def test_converts_names_to_indices(
        self,
        direction_names: list[str],
        data: st.DataObject,
    ):
        """Property: Column names are converted to their indices.

        Given: direction_specs with column names
        When: Normalizing direction columns
        Then: Names are converted to corresponding indices
        """
        # Given: DataFrame with direction columns
        other_cols = data.draw(
            st.lists(valid_column_names, min_size=0, max_size=5, unique=True),
        )
        assume(set(direction_names).isdisjoint(set(other_cols)))

        all_cols = direction_names + other_cols
        df = data.draw(dataframe_with_columns(all_cols))
        normalizer = ColumnNormalizer(df)

        y_cols_count = len(direction_names)

        # When: Normalizing with column names
        result = normalizer.normalize_direction_cols(
            direction_names,  # type: ignore[arg-type]
            y_cols_count,
        )

        # Then: Names are converted to indices
        expected_indices = [all_cols.index(name) for name in direction_names]
        assert result == expected_indices


@pytest.mark.property
class TestValidateColumnSpecsProperties:
    """Property-based tests for validate_column_specs() function."""

    @given(
        x_col=valid_column_names,
        y_cols=st.lists(valid_column_names, min_size=1, max_size=5, unique=True),
        data=st.data(),
    )
    def test_output_pairs_match_input_columns(
        self,
        x_col: str,
        y_cols: list[str],
        data: st.DataObject,
    ):
        """Property: Output pairs correctly match input x and y columns.

        Given: Valid x_col and y_cols specifications
        When: Validating column specs
        Then: Output pairs match the input column structure
        """
        # Given: DataFrame with x and y columns
        assume(x_col not in y_cols)
        all_cols = [x_col] + y_cols
        df = data.draw(dataframe_with_columns(all_cols))

        # When: Validating column specs
        result = validate_column_specs(df, x_col=x_col, y_cols=y_cols)

        # Then: Pairs match expected structure
        assert result["x_cols"] == [x_col]
        assert result["y_cols"] == y_cols
        assert result["pairs"] == [(x_col, y) for y in y_cols]

    @given(
        x_cols=st.lists(valid_column_names, min_size=2, max_size=5, unique=True),
        data=st.data(),
    )
    def test_equal_length_xy_creates_zipped_pairs(
        self,
        x_cols: list[str],
        data: st.DataObject,
    ):
        """Property: Equal-length x and y create element-wise pairs.

        Given: Equal number of x and y columns
        When: Validating column specs
        Then: Pairs are created by zipping x and y
        """
        # Given: Generate y_cols different from x_cols
        y_cols = data.draw(
            st.lists(
                valid_column_names,
                min_size=len(x_cols),
                max_size=len(x_cols),
                unique=True,
            ),
        )
        assume(set(x_cols).isdisjoint(set(y_cols)))

        all_cols = x_cols + y_cols
        df = data.draw(dataframe_with_columns(all_cols))

        # When: Validating column specs
        result = validate_column_specs(df, x_col=x_cols, y_cols=y_cols)

        # Then: Pairs are zipped
        assert result["pairs"] == list(zip(x_cols, y_cols))

    @given(
        invalid_col=valid_column_names,
        data=st.data(),
    )
    def test_invalid_column_raises_error(
        self,
        invalid_col: str,
        data: st.DataObject,
    ):
        """Property: Invalid column specification raises ColumnNotFoundError.

        Given: DataFrame without the specified column
        When: Validating with non-existent column
        Then: ColumnNotFoundError is raised
        """
        # Given: DataFrame without invalid_col
        valid_cols = data.draw(
            st.lists(valid_column_names, min_size=1, max_size=5, unique=True),
        )
        assume(invalid_col not in valid_cols)

        df = data.draw(dataframe_with_columns(valid_cols))

        # When/Then: Should raise ColumnNotFoundError
        with pytest.raises(ColumnNotFoundError):
            validate_column_specs(df, x_col=invalid_col, y_cols=None)

    @given(data=st.data())
    def test_x_col_none_defaults_to_zero(self, data: st.DataObject):
        """Property: x_col=None defaults to first column (index 0).

        Given: DataFrame with multiple columns
        When: x_col is None
        Then: First column is used as x
        """
        # Given: DataFrame with at least 2 columns to have y_cols
        cols = data.draw(
            st.lists(valid_column_names, min_size=2, max_size=5, unique=True),
        )
        df = data.draw(dataframe_with_columns(cols))

        y_cols = cols[1:]  # Use remaining columns as y

        # When: Validating with x_col=None
        result = validate_column_specs(df, x_col=None, y_cols=y_cols)

        # Then: First column is used as x
        assert result["x_cols"] == [cols[0]]
        assert result["y_cols"] == y_cols

    @given(
        direction_specs=st.lists(
            st.one_of(st.integers(min_value=0, max_value=5), st.none()),
            min_size=1,
            max_size=5,
        ),
        data=st.data(),
    )
    def test_direction_cols_length_consistency(
        self,
        direction_specs: list[int | None],
        data: st.DataObject,
    ):
        """Property: Direction cols list matches y_cols count.

        Given: Valid direction_specs
        When: Validating column specs
        Then: Resulting direction_cols has same length as y_cols
        """
        # Given: DataFrame with enough columns
        cols = data.draw(
            st.lists(
                valid_column_names,
                min_size=max(6, max((d for d in direction_specs if d is not None), default=0) + 1),
                max_size=10,
                unique=True,
            ),
        )
        df = data.draw(dataframe_with_columns(cols))

        y_cols = cols[1 : len(direction_specs) + 1]

        # Filter valid indices
        valid_direction_specs = [d if d is None or d < len(cols) else None for d in direction_specs]

        # When: Validating column specs
        result = validate_column_specs(
            df,
            x_col=cols[0],
            y_cols=y_cols,
            direction_cols=valid_direction_specs,
        )

        # Then: direction_cols length matches y_cols
        assert len(result["direction_cols"]) == len(y_cols)
