"""Unit tests for internal helper functions in csv2graph.py.

This module tests internal helper functions:
- resolve_column_index: Convert column specifier (int/str) to DataFrame index
- _parse_headers: Parse DataFrame headers into (series, label, unit) tuples
- _format_axis_label: Format axis label from parsed header
- _normalize_y_specs: Normalize y column specification into a list

EP/BV Tables:

Table 1: resolve_column_index - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-001     │ Valid int column                  │ TC-EP-HELPER-001 │
│ EP-002     │ Valid str column                  │ TC-EP-HELPER-002 │
│ EP-003     │ Invalid str column                │ TC-EP-HELPER-003 │
│ EP-004     │ Ambiguous column (duplicates)     │ TC-EP-HELPER-004 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 2: resolve_column_index - Boundary Value Analysis
┌────────────┬───────────────────────────────────┬──────────────────┐
│ BV Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ BV-001     │ Column index 0 (first)            │ TC-BV-HELPER-001 │
│ BV-002     │ Column index n-1 (last)           │ TC-BV-HELPER-002 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 3: _parse_headers - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-005     │ Standard headers                  │ TC-EP-HELPER-005 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 4: _parse_headers - Boundary Value Analysis
┌────────────┬───────────────────────────────────┬──────────────────┐
│ BV Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ BV-003     │ Empty DataFrame                   │ TC-BV-HELPER-003 │
│ BV-004     │ Single column                     │ TC-BV-HELPER-004 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 5: _format_axis_label - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-006     │ Label with unit                   │ TC-EP-HELPER-006 │
│ EP-007     │ Label without unit                │ TC-EP-HELPER-007 │
│ EP-008     │ Unparsed header (None)            │ TC-EP-HELPER-008 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 6: _normalize_y_specs - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-009     │ None input                        │ TC-EP-HELPER-009 │
│ EP-010     │ Single int                        │ TC-EP-HELPER-010 │
│ EP-011     │ Single str                        │ TC-EP-HELPER-011 │
│ EP-012     │ List of mixed types               │ TC-EP-HELPER-012 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 7: _normalize_y_specs - Boundary Value Analysis
┌────────────┬───────────────────────────────────┬──────────────────┐
│ BV Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ BV-005     │ Empty list                        │ TC-BV-HELPER-005 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 8: _normalize_direction_filter - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-DIR-001 │ None input                        │ TC-EP-DIR-001    │
│ EP-DIR-002 │ Empty list                        │ TC-EP-DIR-002    │
│ EP-DIR-003 │ Single string                     │ TC-EP-DIR-003    │
│ EP-DIR-004 │ List of strings                   │ TC-EP-DIR-004    │
│ EP-DIR-005 │ List with None values             │ TC-EP-DIR-005    │
│ EP-DIR-006 │ Enum values                       │ TC-EP-DIR-006    │
│ EP-DIR-007 │ Empty filters, no colors          │ TC-EP-DIR-007    │
│ EP-DIR-008 │ Filters, no colors                │ TC-EP-DIR-008    │
│ EP-DIR-009 │ Filters with colors               │ TC-EP-DIR-009    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 9: _normalize_direction_filter - Boundary Value Analysis
┌────────────┬───────────────────────────────────┬──────────────────┐
│ BV Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ BV-DIR-001 │ Single element list               │ TC-BV-DIR-001    │
│ BV-DIR-002 │ All None values                   │ TC-BV-DIR-002    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 10: _build_direction_config - Boundary Value Analysis
┌────────────┬───────────────────────────────────┬──────────────────┐
│ BV Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ BV-DIR-003 │ Single filter                     │ TC-BV-DIR-003    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 11: _determine_titles - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-OUT-001 │ Both None                         │ TC-EP-OUT-001    │
│ EP-OUT-002 │ Title only specified              │ TC-EP-OUT-002    │
│ EP-OUT-003 │ Name only specified               │ TC-EP-OUT-003    │
│ EP-OUT-004 │ Both specified                    │ TC-EP-OUT-004    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 12: _determine_titles - Boundary Value Analysis
┌────────────┬───────────────────────────────────┬──────────────────┐
│ BV Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ BV-OUT-001 │ Empty strings                     │ TC-BV-OUT-001    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 13: _determine_formats - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-OUT-005 │ Default (both False)              │ TC-EP-OUT-005    │
│ EP-OUT-006 │ HTML file output                  │ TC-EP-OUT-006    │
│ EP-OUT-007 │ Return fig, no HTML               │ TC-EP-OUT-007    │
│ EP-OUT-008 │ Return fig with HTML              │ TC-EP-OUT-008    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 14: _resolve_plot_mode - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-OUT-009 │ overlay mode                      │ TC-EP-OUT-009    │
│ EP-OUT-010 │ individual mode                   │ TC-EP-OUT-010    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 15: _normalize_axis_limits - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-OUT-011 │ None input                        │ TC-EP-OUT-011    │
│ EP-OUT-012 │ Valid tuple with both bounds      │ TC-EP-OUT-012    │
│ EP-OUT-013 │ Partial (start None)              │ TC-EP-OUT-013    │
│ EP-OUT-014 │ Partial (end None)                │ TC-EP-OUT-014    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 16: _resolve_no_individual_flag - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-OUT-015 │ Explicit True                     │ TC-EP-OUT-015    │
│ EP-OUT-016 │ Explicit False                    │ TC-EP-OUT-016    │
│ EP-OUT-017 │ Auto (overlay, single y)          │ TC-EP-OUT-017    │
│ EP-OUT-018 │ Auto (overlay, multi y)           │ TC-EP-OUT-018    │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 17: _build_matplotlib_artifacts - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-RENDER-001 │ PNG results only               │ TC-EP-RENDER-004 │
│ EP-RENDER-002 │ Mixed PNG + HTML formats       │ TC-EP-RENDER-005 │
│ EP-RENDER-003 │ Empty RenderCollections        │ TC-EP-RENDER-006 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 18: _build_matplotlib_artifacts - Boundary Value Analysis
┌────────────┬───────────────────────────────────┬──────────────────┐
│ BV Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ BV-RENDER-001 │ Single render result           │ TC-BV-RENDER-002 │
└────────────┴───────────────────────────────────┴──────────────────┘

Table 19: RenderCollections.all_results - Equivalence Partitioning
┌────────────┬───────────────────────────────────┬──────────────────┐
│ EP Class   │ Test Condition                    │ Test Case ID     │
├────────────┼───────────────────────────────────┼──────────────────┤
│ EP-RENDER-004 │ Overlay + individual results   │ TC-EP-RENDER-007 │
│ EP-RENDER-005 │ Both empty lists               │ TC-EP-RENDER-008 │
└────────────┴───────────────────────────────────┴──────────────────┘
"""

from __future__ import annotations

import pandas as pd
import pytest

from rdetoolkit.graph.api.csv2graph import (
    _format_axis_label,
    _normalize_y_specs,
    _parse_headers,
    _resolve_no_individual_flag,
    _resolve_plot_mode,
)
from rdetoolkit.graph.strategies.render_coordinator import build_matplotlib_artifacts
from rdetoolkit.graph.config import (
    determine_formats,
    determine_titles,
    normalize_axis_limits,
)
from rdetoolkit.graph.models import (
    DirectionConfig,
    MatplotlibArtifact,
    NormalizedColumns,
    PlotMode,
    RenderCollections,
    RenderResult,
    build_direction_config,
    normalize_direction_filter,
)
from rdetoolkit.graph.normalizers import resolve_column_index


class TestResolveColumnIndex:
    """Test resolve_column_index() helper function."""

    def test_resolve_valid_int_column__tc_ep_helper_001(self):
        """Valid int column returns unchanged."""
        # Given: DataFrame with 3 columns
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "C": [5, 6]})
        column = 1

        # When: Resolving int column
        result = resolve_column_index(df, column)

        # Then: Returns the same integer index
        assert result == 1

    def test_resolve_valid_str_column__tc_ep_helper_002(self):
        """Valid str column returns resolved index."""
        # Given: DataFrame with named columns
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4], "C": [5, 6]})
        column = "B"

        # When: Resolving string column name
        result = resolve_column_index(df, column)

        # Then: Returns the integer index
        assert result == 1

    def test_resolve_invalid_str_column__tc_ep_helper_003(self):
        """Invalid str column raises KeyError."""
        # Given: DataFrame with specific columns
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        column = "NonExistent"

        # When/Then: Resolving non-existent column raises KeyError
        with pytest.raises(KeyError):
            resolve_column_index(df, column)

    def test_resolve_ambiguous_column_name__tc_ep_helper_004(self):
        """Ambiguous column name (duplicates) raises ValueError."""
        # Given: DataFrame with duplicate column names
        df = pd.DataFrame([[1, 2, 3]], columns=["A", "A", "B"])
        column = "A"

        # When/Then: Resolving ambiguous column raises ValueError
        with pytest.raises(ValueError, match="resolved to a slice"):
            resolve_column_index(df, column)

    def test_resolve_column_index_zero__tc_bv_helper_001(self):
        """Column index 0 (first column) resolves correctly."""
        # Given: DataFrame with multiple columns
        df = pd.DataFrame({"X": [1], "Y": [2], "Z": [3]})
        column = 0

        # When: Resolving first column
        result = resolve_column_index(df, column)

        # Then: Returns 0
        assert result == 0

    def test_resolve_column_index_last__tc_bv_helper_002(self):
        """Column index n-1 (last column) resolves correctly."""
        # Given: DataFrame with 3 columns
        df = pd.DataFrame({"X": [1], "Y": [2], "Z": [3]})
        column = 2  # Last column index

        # When: Resolving last column
        result = resolve_column_index(df, column)

        # Then: Returns 2
        assert result == 2


class TestParseHeaders:
    """Test _parse_headers() helper function."""

    def test_parse_standard_headers__tc_ep_helper_005(self):
        """Standard headers return list of tuples."""
        # Given: DataFrame with structured headers
        df = pd.DataFrame({
            "Time (s)": [1, 2],
            "Voltage (V)": [3.5, 4.0],
            "Current": [0.1, 0.2],
        })

        # When: Parsing headers
        result = _parse_headers(df)

        # Then: Returns list of (series, label, unit) tuples
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, tuple) for item in result)
        assert all(len(item) == 3 for item in result)

    def test_parse_empty_dataframe__tc_bv_helper_003(self):
        """Empty DataFrame returns empty list."""
        # Given: Empty DataFrame with no columns
        df = pd.DataFrame()

        # When: Parsing headers
        result = _parse_headers(df)

        # Then: Returns empty list
        assert result == []

    def test_parse_single_column__tc_bv_helper_004(self):
        """Single column returns single-element list."""
        # Given: DataFrame with single column
        df = pd.DataFrame({"Temperature (K)": [273.15, 298.15]})

        # When: Parsing headers
        result = _parse_headers(df)

        # Then: Returns list with one tuple
        assert len(result) == 1
        assert isinstance(result[0], tuple)
        assert len(result[0]) == 3


class TestFormatAxisLabel:
    """Test _format_axis_label() helper function."""

    def test_format_label_with_unit__tc_ep_helper_006(self):
        """Label with unit returns 'Label (unit)'."""
        # Given: Parsed header with label and unit
        column_name = "Voltage (V)"
        parsed = (None, "Voltage", "V")

        # When: Formatting axis label
        result = _format_axis_label(column_name, parsed)

        # Then: Returns formatted label with unit
        assert result == "Voltage (V)"

    def test_format_label_without_unit__tc_ep_helper_007(self):
        """Label without unit returns 'Label'."""
        # Given: Parsed header with label but no unit
        column_name = "Current"
        parsed = (None, "Current", None)

        # When: Formatting axis label
        result = _format_axis_label(column_name, parsed)

        # Then: Returns label without unit
        assert result == "Current"

    def test_format_unparsed_header__tc_ep_helper_008(self):
        """Unparsed header (None) returns str(column_name)."""
        # Given: Unparsed header (None)
        column_name = "RawColumnName"
        parsed = None

        # When: Formatting axis label
        result = _format_axis_label(column_name, parsed)

        # Then: Returns string representation of column name
        assert result == "RawColumnName"


class TestNormalizeYSpecs:
    """Test _normalize_y_specs() helper function."""

    def test_normalize_none_input__tc_ep_helper_009(self):
        """None input returns None."""
        # Given: None as input
        y_cols = None

        # When: Normalizing y specs
        result = _normalize_y_specs(y_cols)

        # Then: Returns None
        assert result is None

    def test_normalize_single_int__tc_ep_helper_010(self):
        """Single int returns list with one int."""
        # Given: Single integer
        y_cols = 1

        # When: Normalizing y specs
        result = _normalize_y_specs(y_cols)

        # Then: Returns list containing the integer
        assert result == [1]

    def test_normalize_single_str__tc_ep_helper_011(self):
        """Single str returns list with one str."""
        # Given: Single string
        y_cols = "Voltage"

        # When: Normalizing y specs
        result = _normalize_y_specs(y_cols)

        # Then: Returns list containing the string
        assert result == ["Voltage"]

    def test_normalize_list_of_mixed__tc_ep_helper_012(self):
        """List of mixed types returns list."""
        # Given: List with mixed int and str
        y_cols = [0, "Voltage", 2, "Current"]

        # When: Normalizing y specs
        result = _normalize_y_specs(y_cols)

        # Then: Returns list with all elements
        assert result == [0, "Voltage", 2, "Current"]

    def test_normalize_empty_list__tc_bv_helper_005(self):
        """Empty list returns empty list."""
        # Given: Empty list
        y_cols: list[int | str] = []

        # When: Normalizing y specs
        result = _normalize_y_specs(y_cols)

        # Then: Returns empty list
        assert result == []


class MockEnum:
    """Mock enum class for testing enum value extraction."""

    def __init__(self, value: str):
        self.value = value


class TestNormalizeDirectionFilter:
    """Test normalize_direction_filter() helper function."""

    def test_normalize_direction_filter_none__tc_ep_dir_001(self):
        """None input returns empty list."""
        # Given: None as input
        direction_filter = None

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns empty list
        assert result == []

    def test_normalize_direction_filter_empty_list__tc_ep_dir_002(self):
        """Empty list returns empty list."""
        # Given: Empty list
        direction_filter: list[str] = []

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns empty list
        assert result == []

    def test_normalize_direction_filter_single_string__tc_ep_dir_003(self):
        """Single string returns list with one string."""
        # Given: Single string
        direction_filter = "Charge"

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns list containing the string
        assert result == ["Charge"]

    def test_normalize_direction_filter_list_of_strings__tc_ep_dir_004(self):
        """List of strings returns list of strings."""
        # Given: List of strings
        direction_filter = ["Charge", "Discharge"]

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns list with all strings
        assert result == ["Charge", "Discharge"]

    def test_normalize_direction_filter_with_none_values__tc_ep_dir_005(self):
        """List with None values filters out None."""
        # Given: List with None values
        direction_filter = ["Charge", None, "Discharge"]

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns list with None values filtered out
        assert result == ["Charge", "Discharge"]

    def test_normalize_direction_filter_enum_values__tc_ep_dir_006(self):
        """Enum values extract .value attribute."""
        # Given: List with enum-like objects
        direction_filter = [MockEnum("Charge"), MockEnum("Rest")]

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns list with extracted .value strings
        assert result == ["Charge", "Rest"]

    def test_normalize_direction_filter_single_element_list__tc_bv_dir_001(self):
        """Single element list returns single element list."""
        # Given: List with one element
        direction_filter = ["Charge"]

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns list with one element
        assert result == ["Charge"]

    def test_normalize_direction_filter_all_none__tc_bv_dir_002(self):
        """List with all None values returns empty list."""
        # Given: List with only None values
        direction_filter = [None, None]

        # When: Normalizing direction filter
        result = normalize_direction_filter(direction_filter)

        # Then: Returns empty list
        assert result == []


class TestBuildDirectionConfig:
    """Test build_direction_config() helper function."""

    def test_build_direction_config_empty__tc_ep_dir_007(self):
        """Empty filters, no colors returns minimal DirectionConfig."""
        # Given: Empty filters and no custom colors
        filters: list[str] = []
        direction_colors = None

        # When: Building direction config
        result = build_direction_config(
            filters=filters,
            direction_colors=direction_colors,
        )

        # Then: Returns DirectionConfig with empty filters and default colors
        assert isinstance(result, DirectionConfig)
        assert result.filters == []
        assert result.use_custom_colors is False
        assert "Charge" in result.colors  # Default colors exist

    def test_build_direction_config_with_filters__tc_ep_dir_008(self):
        """Filters, no colors returns DirectionConfig with filters."""
        # Given: Filters and no custom colors
        filters = ["Charge", "Discharge"]
        direction_colors = None

        # When: Building direction config
        result = build_direction_config(
            filters=filters,
            direction_colors=direction_colors,
        )

        # Then: Returns DirectionConfig with filters and default colors
        assert isinstance(result, DirectionConfig)
        assert result.filters == ["Charge", "Discharge"]
        assert result.use_custom_colors is False

    def test_build_direction_config_with_colors__tc_ep_dir_009(self):
        """Filters with colors returns DirectionConfig with custom colors."""
        # Given: Filters with custom colors
        filters = ["Charge", "Discharge"]
        direction_colors = {"Charge": "orange", "Discharge": "purple"}

        # When: Building direction config
        result = build_direction_config(
            filters=filters,
            direction_colors=direction_colors,
        )

        # Then: Returns DirectionConfig with custom colors
        assert isinstance(result, DirectionConfig)
        assert result.filters == ["Charge", "Discharge"]
        assert result.use_custom_colors is True
        assert result.colors["Charge"] == "orange"
        assert result.colors["Discharge"] == "purple"

    def test_build_direction_config_single_filter__tc_bv_dir_003(self):
        """Single filter returns valid DirectionConfig."""
        # Given: Single filter
        filters = ["Charge"]
        direction_colors = None

        # When: Building direction config
        result = build_direction_config(
            filters=filters,
            direction_colors=direction_colors,
        )

        # Then: Returns DirectionConfig with single filter
        assert isinstance(result, DirectionConfig)
        assert result.filters == ["Charge"]
        assert result.use_custom_colors is False


class TestDetermineTitles:
    """Test determine_titles() helper function."""

    def test_determine_titles_both_none__tc_ep_out_001(self):
        """Both None returns (None, 'plot')."""
        # Given: Both title and name are None
        title = None
        name = None

        # When: Determining titles
        display_title, base_filename = determine_titles(title=title, name=name)

        # Then: Returns (None, 'plot')
        assert display_title is None
        assert base_filename == "plot"

    def test_determine_titles_title_only__tc_ep_out_002(self):
        """Title only specified returns (title, title)."""
        # Given: Only title is specified
        title = "My Graph"
        name = None

        # When: Determining titles
        display_title, base_filename = determine_titles(title=title, name=name)

        # Then: Returns (title, title)
        assert display_title == "My Graph"
        assert base_filename == "My Graph"

    def test_determine_titles_name_only__tc_ep_out_003(self):
        """Name only specified returns (name, name)."""
        # Given: Only name is specified
        title = None
        name = "output"

        # When: Determining titles
        display_title, base_filename = determine_titles(title=title, name=name)

        # Then: Returns (name, name)
        assert display_title == "output"
        assert base_filename == "output"

    def test_determine_titles_both_specified__tc_ep_out_004(self):
        """Both specified returns (title, name)."""
        # Given: Both title and name are specified
        title = "Title"
        name = "name"

        # When: Determining titles
        display_title, base_filename = determine_titles(title=title, name=name)

        # Then: Returns (title, name)
        assert display_title == "Title"
        assert base_filename == "name"

    def test_determine_titles_empty_strings__tc_bv_out_001(self):
        """Empty strings returns ('', 'plot')."""
        # Given: Empty strings for both title and name
        title = ""
        name = ""

        # When: Determining titles
        display_title, base_filename = determine_titles(title=title, name=name)

        # Then: Returns ('', 'plot') because empty string is falsy for name fallback
        assert display_title == ""
        assert base_filename == "plot"


class TestDetermineFormats:
    """Test determine_formats() helper function."""

    def test_determine_formats_default__tc_ep_out_005(self):
        """Default (both False) returns ['png']."""
        # Given: Both html and return_fig are False
        html = False
        return_fig = False

        # When: Determining formats
        result = determine_formats(html=html, return_fig=return_fig)

        # Then: Returns ['png']
        assert result == ["png"]

    def test_determine_formats_html_file__tc_ep_out_006(self):
        """HTML file output returns ['png', 'html']."""
        # Given: html is True, return_fig is False
        html = True
        return_fig = False

        # When: Determining formats
        result = determine_formats(html=html, return_fig=return_fig)

        # Then: Returns ['png', 'html']
        assert result == ["png", "html"]

    def test_determine_formats_return_fig_no_html__tc_ep_out_007(self):
        """Return fig, no HTML returns ['png']."""
        # Given: return_fig is True, html is False
        html = False
        return_fig = True

        # When: Determining formats
        result = determine_formats(html=html, return_fig=return_fig)

        # Then: Returns ['png']
        assert result == ["png"]

    def test_determine_formats_return_fig_with_html__tc_ep_out_008(self):
        """Return fig with HTML returns ['png'] (html skipped)."""
        # Given: Both html and return_fig are True
        html = True
        return_fig = True

        # When: Determining formats
        result = determine_formats(html=html, return_fig=return_fig)

        # Then: Returns ['png'] because html is skipped when return_fig is True
        assert result == ["png"]


class TestResolvePlotMode:
    """Test _resolve_plot_mode() helper function."""

    def test_resolve_plot_mode_overlay__tc_ep_out_009(self):
        """Overlay mode returns PlotMode.OVERLAY."""
        # Given: mode is 'overlay'
        mode = "overlay"

        # When: Resolving plot mode
        result = _resolve_plot_mode(mode)

        # Then: Returns PlotMode.OVERLAY
        assert result == PlotMode.OVERLAY

    def test_resolve_plot_mode_individual__tc_ep_out_010(self):
        """Individual mode returns PlotMode.INDIVIDUAL."""
        # Given: mode is 'individual'
        mode = "individual"

        # When: Resolving plot mode
        result = _resolve_plot_mode(mode)

        # Then: Returns PlotMode.INDIVIDUAL
        assert result == PlotMode.INDIVIDUAL


class TestNormalizeAxisLimits:
    """Test normalize_axis_limits() helper function."""

    def test_normalize_axis_limits_none__tc_ep_out_011(self):
        """None input returns None."""
        # Given: None as input
        limits = None

        # When: Normalizing axis limits
        result = normalize_axis_limits(limits)

        # Then: Returns None
        assert result is None

    def test_normalize_axis_limits_valid__tc_ep_out_012(self):
        """Valid tuple with both bounds returns same tuple."""
        # Given: Tuple with both start and end
        limits = (0.0, 10.0)

        # When: Normalizing axis limits
        result = normalize_axis_limits(limits)

        # Then: Returns the same tuple
        assert result == (0.0, 10.0)

    def test_normalize_axis_limits_partial_start__tc_ep_out_013(self):
        """Partial (start None) returns None."""
        # Given: Tuple with None start
        limits = (None, 10.0)

        # When: Normalizing axis limits
        result = normalize_axis_limits(limits)

        # Then: Returns None
        assert result is None

    def test_normalize_axis_limits_partial_end__tc_ep_out_014(self):
        """Partial (end None) returns None."""
        # Given: Tuple with None end
        limits = (0.0, None)

        # When: Normalizing axis limits
        result = normalize_axis_limits(limits)

        # Then: Returns None
        assert result is None


class TestResolveNoIndividualFlag:
    """Test _resolve_no_individual_flag() helper function."""

    def test_resolve_no_individual_explicit_true__tc_ep_out_015(self):
        """Explicit True returns True."""
        # Given: requested is True
        requested = True
        plot_mode = PlotMode.OVERLAY
        normalized = NormalizedColumns(
            x_col=0,
            y_cols=[1],
            direction_cols=[],
            derived_x_label="X",
            derived_y_label="Y",
        )

        # When: Resolving no_individual flag
        result = _resolve_no_individual_flag(
            requested=requested,
            plot_mode=plot_mode,
            normalized=normalized,
        )

        # Then: Returns True
        assert result is True

    def test_resolve_no_individual_explicit_false__tc_ep_out_016(self):
        """Explicit False returns False."""
        # Given: requested is False
        requested = False
        plot_mode = PlotMode.OVERLAY
        normalized = NormalizedColumns(
            x_col=0,
            y_cols=[1],
            direction_cols=[],
            derived_x_label="X",
            derived_y_label="Y",
        )

        # When: Resolving no_individual flag
        result = _resolve_no_individual_flag(
            requested=requested,
            plot_mode=plot_mode,
            normalized=normalized,
        )

        # Then: Returns False
        assert result is False

    def test_resolve_no_individual_auto_overlay_single__tc_ep_out_017(self):
        """Auto with overlay and single y returns True."""
        # Given: requested is None, overlay mode with single y column
        requested = None
        plot_mode = PlotMode.OVERLAY
        normalized = NormalizedColumns(
            x_col=0,
            y_cols=[1],
            direction_cols=[],
            derived_x_label="X",
            derived_y_label="Y",
        )

        # When: Resolving no_individual flag
        result = _resolve_no_individual_flag(
            requested=requested,
            plot_mode=plot_mode,
            normalized=normalized,
        )

        # Then: Returns True (auto-detect: overlay with 1 y column)
        assert result is True

    def test_resolve_no_individual_auto_overlay_multi__tc_ep_out_018(self):
        """Auto with overlay and multiple y returns False."""
        # Given: requested is None, overlay mode with multiple y columns
        requested = None
        plot_mode = PlotMode.OVERLAY
        normalized = NormalizedColumns(
            x_col=0,
            y_cols=[1, 2],
            direction_cols=[],
            derived_x_label="X",
            derived_y_label="Y",
        )

        # When: Resolving no_individual flag
        result = _resolve_no_individual_flag(
            requested=requested,
            plot_mode=plot_mode,
            normalized=normalized,
        )

        # Then: Returns False (auto-detect: overlay with 2+ y columns)
        assert result is False


class TestBuildMatplotlibArtifacts:
    """Test _build_matplotlib_artifacts() helper function."""

    def test_build_matplotlib_artifacts_png_only__tc_ep_render_004(self):
        """PNG results only returns list of MatplotlibArtifact."""
        # Given: RenderCollections with PNG results
        fig1 = object()  # Simple placeholder for figure
        fig2 = object()
        collections = RenderCollections(
            overlay=[
                RenderResult(figure=fig1, filename="overlay.png", format="png"),
            ],
            individual=[
                RenderResult(figure=fig2, filename="individual_1.png", format="png"),
            ],
        )

        # When: Building matplotlib artifacts
        result = build_matplotlib_artifacts(collections)

        # Then: Returns list of MatplotlibArtifact with PNG files
        assert len(result) == 2
        assert all(isinstance(artifact, MatplotlibArtifact) for artifact in result)
        assert result[0].filename == "overlay.png"
        assert result[0].figure is fig1
        assert result[0].metadata == {"format": "png"}
        assert result[1].filename == "individual_1.png"
        assert result[1].figure is fig2
        assert result[1].metadata == {"format": "png"}

    def test_build_matplotlib_artifacts_mixed_formats__tc_ep_render_005(self):
        """Mixed PNG + HTML formats returns only PNG artifacts."""
        # Given: RenderCollections with PNG and HTML results
        fig1 = object()
        fig2 = object()
        fig3 = object()
        collections = RenderCollections(
            overlay=[
                RenderResult(figure=fig1, filename="overlay.png", format="png"),
                RenderResult(figure=fig2, filename="overlay.html", format="html"),
            ],
            individual=[
                RenderResult(figure=fig3, filename="individual_1.png", format="png"),
            ],
        )

        # When: Building matplotlib artifacts
        result = build_matplotlib_artifacts(collections)

        # Then: Returns only PNG artifacts (HTML filtered out)
        assert len(result) == 2
        assert result[0].filename == "overlay.png"
        assert result[0].figure is fig1
        assert result[1].filename == "individual_1.png"
        assert result[1].figure is fig3

    def test_build_matplotlib_artifacts_empty__tc_ep_render_006(self):
        """Empty RenderCollections returns empty list."""
        # Given: Empty RenderCollections
        collections = RenderCollections(
            overlay=[],
            individual=[],
        )

        # When: Building matplotlib artifacts
        result = build_matplotlib_artifacts(collections)

        # Then: Returns empty list
        assert result == []

    def test_build_matplotlib_artifacts_single__tc_bv_render_002(self):
        """Single render result returns single artifact."""
        # Given: RenderCollections with single result
        fig = object()
        collections = RenderCollections(
            overlay=[
                RenderResult(figure=fig, filename="plot.png", format="png"),
            ],
            individual=[],
        )

        # When: Building matplotlib artifacts
        result = build_matplotlib_artifacts(collections)

        # Then: Returns single artifact
        assert len(result) == 1
        assert result[0].filename == "plot.png"
        assert result[0].figure is fig
        assert result[0].metadata == {"format": "png"}


class TestRenderCollectionsAllResults:
    """Test RenderCollections.all_results() method."""

    def test_render_collections_all_results_combines__tc_ep_render_007(self):
        """Overlay + individual results returns combined list."""
        # Given: RenderCollections with both overlay and individual results
        fig1 = object()
        fig2 = object()
        fig3 = object()
        collections = RenderCollections(
            overlay=[
                RenderResult(figure=fig1, filename="overlay.png", format="png"),
                RenderResult(figure=fig2, filename="overlay.html", format="html"),
            ],
            individual=[
                RenderResult(figure=fig3, filename="individual_1.png", format="png"),
            ],
        )

        # When: Getting all results
        result = collections.all_results()

        # Then: Returns combined list preserving order (overlay first, then individual)
        assert len(result) == 3
        assert result[0].filename == "overlay.png"
        assert result[0].figure is fig1
        assert result[1].filename == "overlay.html"
        assert result[1].figure is fig2
        assert result[2].filename == "individual_1.png"
        assert result[2].figure is fig3

    def test_render_collections_all_results_empty__tc_ep_render_008(self):
        """Both empty lists returns empty list."""
        # Given: RenderCollections with empty lists
        collections = RenderCollections(
            overlay=[],
            individual=[],
        )

        # When: Getting all results
        result = collections.all_results()

        # Then: Returns empty list
        assert result == []
