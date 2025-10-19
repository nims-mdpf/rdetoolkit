from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from rdetoolkit.graph.exceptions import ColumnNotFoundError


class ColumnNormalizer:
    """Normalize column specifications for plotting operations.

    This class handles the conversion of various column specification formats
    (indices, names, lists, None) into a consistent internal representation.

    Example:
        >>> df = pd.DataFrame({'A': [1, 2], 'B': [3, 4], 'C': [5, 6]})
        >>> normalizer = ColumnNormalizer(df)
        >>> normalizer.normalize_columns([0, 'B'])
        ['A', 'B']
        >>> normalizer.normalize_columns(None, exclude=[0])
        ['B', 'C']
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._column_names = list(df.columns)

    def to_index(self, col_spec: int | str) -> int:
        """Convert column specification to index.

        Args:
            col_spec: Column index or name

        Returns:
            Column index (0-based)

        Raises:
            ColumnNotFoundError: If column name not found in DataFrame

        Example:
            >>> normalizer.to_index('voltage')
            0
            >>> normalizer.to_index(2)
            2

        """
        if isinstance(col_spec, int):
            if col_spec < 0 or col_spec >= len(self._column_names):
                emsg = f"Column index {col_spec} out of range [0, {len(self._column_names)})"
                raise ColumnNotFoundError(emsg)
            return col_spec

        if isinstance(col_spec, str):
            try:
                return self._column_names.index(col_spec)
            except ValueError as e:
                emsg = f"Column name '{col_spec}' not found in DataFrame columns: {self._column_names}"
                raise ColumnNotFoundError(emsg) from e

        emsg = f"Column specification must be int or str, got {type(col_spec)}"
        raise TypeError(emsg)

    def to_name(self, col_spec: int | str) -> str:
        """Convert column specification to name.

        Args:
            col_spec: Column index or name

        Returns:
            Column name

        Raises:
            ColumnNotFoundError: If column index out of range or name not found

        Example:
            >>> normalizer.to_name(0)
            'voltage'
            >>> normalizer.to_name('current')
            'current'

        """
        if isinstance(col_spec, str):
            if col_spec not in self._column_names:
                emsg = f"Column name '{col_spec}' not found in DataFrame columns: {self._column_names}"
                raise ColumnNotFoundError(emsg)
            return col_spec

        if isinstance(col_spec, int):
            if col_spec < 0 or col_spec >= len(self._column_names):
                emsg = f"Column index {col_spec} out of range [0, {len(self._column_names)})"
                raise ColumnNotFoundError(emsg)
            return self._column_names[col_spec]

        emsg = f"Column specification must be int or str, got {type(col_spec)}"
        raise TypeError(emsg)

    def normalize_columns(
        self,
        col_spec: int | str | Sequence[int | str] | None,
        exclude: Sequence[int | str] | None = None,
        default_all: bool = True,
    ) -> list[str]:
        """Normalize column specification to list of column names.

        Args:
            col_spec: Column specification (index, name, sequence, or None)
            exclude: Columns to exclude when col_spec is None
            default_all: If True and col_spec is None, return all columns (excluding `exclude`)

        Returns:
            List of column names

        Raises:
            ColumnNotFoundError: If any specified column not found

        Example:
            >>> normalizer.normalize_columns([0, 'B'])
            ['A', 'B']
            >>> normalizer.normalize_columns(None, exclude=[0])
            ['B', 'C']
            >>> normalizer.normalize_columns('voltage')
            ['voltage']

        """
        if col_spec is None:
            if not default_all:
                return []

            exclude_indices = {
                self.to_index(exc)
                for exc in (exclude or [])
            }

            return [
                name for i, name in enumerate(self._column_names)
                if i not in exclude_indices
            ]

        if isinstance(col_spec, (int, str)):
            return [self.to_name(col_spec)]
        if isinstance(col_spec, Sequence) and not isinstance(col_spec, (str, bytes)):
            return [self.to_name(col) for col in col_spec]

        emsg = f"Invalid column specification type: {type(col_spec)}"
        raise TypeError(emsg)

    def normalize_x_y_pairs(
        self,
        x_col: int | str | Sequence[int | str],
        y_cols: Sequence[int | str] | None = None,
    ) -> list[tuple[str, str]]:
        """Normalize x and y column specifications into pairs.

        x_col: X column specification (single entry or sequence)
        - If x_col is single and y_cols is None: use all columns except x_col as y
        - If x_col is single and y_cols is a sequence: pair x_col with each y
        - If x_col is a sequence and y_cols is a sequence: pair corresponding elements
        - If lengths mismatch: raise ValueError

        Args:
            x_col: X column specification (single entry or sequence)
            y_cols: Y column specifications (sequence or None)

        Returns:
            List of (x_name, y_name) tuples

        Raises:
            ValueError: If x_col and y_cols lengths don't match
            ColumnNotFoundError: If any column not found

        Example:
            >>> normalizer.normalize_x_y_pairs(0, [1, 2])
            [('A', 'B'), ('A', 'C')]
            >>> normalizer.normalize_x_y_pairs([0, 1], [2, 3])
            [('A', 'C'), ('B', 'D')]
        """
        x_names = self.normalize_columns(x_col)

        if y_cols is None:
            exclude_specs: list[int | str] = list(x_names)
            y_names = self.normalize_columns(None, exclude=exclude_specs)
        else:
            y_names = self.normalize_columns(y_cols)

        if len(x_names) == 1:
            return [(x_names[0], y_name) for y_name in y_names]
        if len(x_names) == len(y_names):
            return list(zip(x_names, y_names))

        emsg = (
            f"x_col length ({len(x_names)}) and y_cols length ({len(y_names)}) "
            f"must be equal or x_col must be a single column"
        )
        raise ValueError(emsg)

    def normalize_direction_cols(
        self,
        direction_cols: list[int | str | None] | None,
        y_cols_count: int,
    ) -> list[int | None]:
        """Normalize direction column specifications.

        Direction columns are used for filtering data by direction (e.g., charge/discharge).
        Each y column can have an optional corresponding direction column.

        Args:
            direction_cols: Direction column specifications (indices, names, or None)
            y_cols_count: Number of y columns to match

        Returns:
            List of direction column indices (None for no direction filtering)

        Example:
            >>> normalizer.normalize_direction_cols([3, None, 4], 3)
            [3, None, 4]
            >>> normalizer.normalize_direction_cols(['dir1', 'dir2'], 2)
            [3, 4]
        """
        if direction_cols is None:
            return [None] * y_cols_count

        result: list[int | None] = []
        for col_spec in direction_cols:
            if col_spec is None:
                result.append(None)
                continue

            if not isinstance(col_spec, (int, str)):
                emsg = (
                    "Direction column specification must be int, str, or None, "
                    f"got {type(col_spec)}"
                )
                raise TypeError(emsg)

            result.append(self.to_index(col_spec))

        if len(result) > y_cols_count:
            emsg = (
                f"direction_cols length ({len(result)}) cannot exceed number of y columns "
                f"({y_cols_count})"
            )
            raise ValueError(emsg)

        while len(result) < y_cols_count:
            result.append(None)

        return result


def validate_column_specs(
    df: pd.DataFrame,
    x_col: int | str | Sequence[int | str] | None = None,
    y_cols: Sequence[int | str] | None = None,
    direction_cols: int | str | Sequence[int | str | None] | None = None,
) -> dict[str, Any]:
    """Validate and normalize all column specifications.

    This is a convenience function that creates a ColumnNormalizer and
    validates all column specifications in one call.

    Args:
        df: DataFrame to validate against
        x_col: X column specification
        y_cols: Y column specifications
        direction_cols: Direction column specifications

    Returns:
        Dictionary with normalized column specifications:
        - 'x_cols': List of x column names
        - 'y_cols': List of y column names
        - 'pairs': List of (x_name, y_name) tuples
        - 'direction_cols': List of direction column indices

    Raises:
        ColumnNotFoundError: If any column not found
        ValueError: If column specifications are invalid

    Example:
        >>> result = validate_column_specs(df, x_col=0, y_cols=[1, 2])
        >>> result['pairs']
        [('voltage', 'current'), ('voltage', 'power')]
    """
    normalizer = ColumnNormalizer(df)
    x_col = 0 if x_col is None else x_col

    pairs = normalizer.normalize_x_y_pairs(x_col, y_cols)
    x_cols = list(dict.fromkeys(x for x, _ in pairs))
    y_cols_names = [y for _, y in pairs]

    if direction_cols is None:
        normalized_direction_specs: list[int | str | None] | None = None
    elif isinstance(direction_cols, (int, str)) or direction_cols is None:
        normalized_direction_specs = [direction_cols]
    else:
        normalized_direction_specs = list(direction_cols)

    direction_indices = normalizer.normalize_direction_cols(
        normalized_direction_specs,
        len(y_cols_names),
    )

    return {
        'x_cols': x_cols,
        'y_cols': y_cols_names,
        'pairs': pairs,
        'direction_cols': direction_indices,
    }
