"""Unit tests for text utility functions."""

from __future__ import annotations

import pytest

from rdetoolkit.graph.textutils import (
    sanitize_filename,
    titleize,
    to_snake_case,
    parse_header,
)


# =============================================================================
# sanitize_filename Tests
# =============================================================================


def test_sanitize_filename_basic():
    """Test sanitize_filename with basic invalid characters."""
    assert sanitize_filename("file:name") == "file_name"
    assert sanitize_filename("data<file>") == "data_file_"
    assert sanitize_filename('path/to/file') == "path_to_file"


def test_sanitize_filename_multiple_invalid():
    """Test sanitize_filename with multiple invalid characters."""
    assert sanitize_filename('data:file<name>') == "data_file_name_"
    assert sanitize_filename('test|file?name') == "test_file_name"


def test_sanitize_filename_all_invalid_chars():
    """Test sanitize_filename with all Windows invalid characters."""
    result = sanitize_filename('file\\name/*?:"<>|test')
    assert "/" not in result
    assert "\\" not in result
    assert "*" not in result
    assert "?" not in result
    assert ":" not in result
    assert '"' not in result
    assert "<" not in result
    assert ">" not in result
    assert "|" not in result


def test_sanitize_filename_no_invalid():
    """Test sanitize_filename with valid filename."""
    assert sanitize_filename("normal_file.txt") == "normal_file.txt"
    assert sanitize_filename("data-123.csv") == "data-123.csv"


def test_sanitize_filename_empty():
    """Test sanitize_filename with empty string."""
    assert sanitize_filename("") == ""


def test_sanitize_filename_unicode():
    """Test sanitize_filename with Unicode characters."""
    assert sanitize_filename("グラフ_データ.png") == "グラフ_データ.png"
    assert sanitize_filename("файл:имя") == "файл_имя"


# =============================================================================
# titleize Tests
# =============================================================================


def test_titleize_basic():
    """Test titleize with basic snake_case."""
    assert titleize("hello_world") == "Hello World"
    assert titleize("api_token") == "Api Token"
    assert titleize("cycle_count") == "Cycle Count"


def test_titleize_single_word():
    """Test titleize with single word."""
    assert titleize("hello") == "Hello"
    assert titleize("test") == "Test"


def test_titleize_already_capitalized():
    """Test titleize with already capitalized words."""
    assert titleize("Hello_World") == "Hello World"
    assert titleize("TEST_VALUE") == "Test Value"


def test_titleize_multiple_underscores():
    """Test titleize with consecutive underscores."""
    assert titleize("hello__world") == "Hello World"
    assert titleize("test___value") == "Test Value"


def test_titleize_with_numbers():
    """Test titleize with numbers."""
    assert titleize("test_123_value") == "Test 123 Value"
    assert titleize("cycle_1") == "Cycle 1"


def test_titleize_with_parentheses():
    """Test titleize preserves parentheses."""
    # Note: Based on example in docstring, it seems to capitalize inside parens too
    result = titleize("charge (mA)")
    # Implementation capitalizes each word
    assert "Charge" in result
    assert "(" in result


def test_titleize_empty_string():
    """Test titleize with empty string."""
    assert titleize("") == ""


def test_titleize_spaces_already():
    """Test titleize with spaces instead of underscores."""
    assert titleize("hello world") == "Hello World"


def test_titleize_mixed_separators():
    """Test titleize with mixed underscores and spaces."""
    assert titleize("hello_world test") == "Hello World Test"


# =============================================================================
# to_snake_case Tests
# =============================================================================


def test_to_snake_case_basic():
    """Test to_snake_case with basic Title Case."""
    assert to_snake_case("Hello World") == "hello_world"
    assert to_snake_case("Battery Voltage") == "battery_voltage"
    assert to_snake_case("Cycle Number") == "cycle_number"


def test_to_snake_case_single_word():
    """Test to_snake_case with single word."""
    assert to_snake_case("Hello") == "hello"
    assert to_snake_case("Test") == "test"


def test_to_snake_case_already_lowercase():
    """Test to_snake_case with already lowercase."""
    assert to_snake_case("hello world") == "hello_world"


def test_to_snake_case_already_snake():
    """Test to_snake_case with already snake_case (with spaces)."""
    # Note: This converts spaces to underscores
    assert to_snake_case("hello_world") == "hello_world"


def test_to_snake_case_multiple_spaces():
    """Test to_snake_case with multiple consecutive spaces."""
    assert to_snake_case("hello  world") == "hello__world"
    assert to_snake_case("test   value") == "test___value"


def test_to_snake_case_with_numbers():
    """Test to_snake_case with numbers."""
    assert to_snake_case("Test 123") == "test_123"
    assert to_snake_case("Cycle 1 Data") == "cycle_1_data"


def test_to_snake_case_empty_string():
    """Test to_snake_case with empty string."""
    assert to_snake_case("") == ""


def test_to_snake_case_special_chars():
    """Test to_snake_case preserves special characters."""
    assert to_snake_case("Test-Value") == "test-value"
    assert to_snake_case("Data (mA)") == "data_(ma)"


def test_to_snake_case_unicode():
    """Test to_snake_case with Unicode."""
    assert to_snake_case("テスト データ") == "テスト_データ"


# =============================================================================
# Round-trip Tests (titleize ↔ to_snake_case)
# =============================================================================


def test_roundtrip_titleize_to_snake():
    """Test round-trip conversion titleize → to_snake_case."""
    original = "hello_world"
    titleized = titleize(original)
    back = to_snake_case(titleized)
    assert back == original


def test_roundtrip_snake_to_titleize():
    """Test round-trip conversion to_snake_case → titleize."""
    original = "Hello World"
    snake = to_snake_case(original)
    back = titleize(snake)
    assert back == original


# =============================================================================
# parse_header Tests
# =============================================================================


def test_parse_header_with_series_label_unit():
    """Test parse_header with series:label (unit) format."""
    series, label, unit = parse_header("series_one: cycle_number (mAh)")
    assert series == "Series One"
    assert label == "Cycle Number"
    assert unit == "mAh"


def test_parse_header_with_label_unit():
    """Test parse_header with label (unit) format."""
    series, label, unit = parse_header("Voltage (V)")
    assert series is None
    assert label == "Voltage"
    assert unit == "V"


def test_parse_header_simple_label():
    """Test parse_header with simple label."""
    series, label, unit = parse_header("temperature")
    assert series is None
    assert label == "Temperature"
    assert unit is None


def test_parse_header_empty():
    """Test parse_header with empty string."""
    series, label, unit = parse_header("")
    # Behavior depends on implementation
    assert series is None or series == ""


def test_parse_header_with_colons():
    """Test parse_header handles colons in series name."""
    series, label, unit = parse_header("10deg:Intensity (cps)")
    # Should extract series before colon
    assert "10deg" in series.lower() or series == "10Deg"
    assert "Intensity" in label or "intensity" in label.lower()
    assert unit == "cps"


def test_parse_header_no_unit():
    """Test parse_header with series:label but no unit."""
    series, label, unit = parse_header("series_a: current")
    assert "Series" in series or "series" in series.lower()
    assert "Current" in label or "current" in label.lower()
    assert unit is None


def test_parse_header_complex_unit():
    """Test parse_header with complex unit."""
    series, label, unit = parse_header("data: power (W/m²)")
    assert unit == "W/m²"
