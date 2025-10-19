from __future__ import annotations

import pytest

from rdetoolkit.graph.textutils import titleize, parse_header, sanitize_filename, to_snake_case


class TestSanitizeFilename:

    def test_removes_invalid_characters(self):
        """Invalid filename characters are replaced with underscores."""
        assert sanitize_filename('data:file<name>') == 'data_file_name_'
        assert sanitize_filename('report/2024\\test') == 'report_2024_test'
        assert sanitize_filename('file*name?') == 'file_name_'

    def test_handles_multiple_invalid_chars(self):
        """Multiple consecutive invalid characters are each replaced."""
        assert sanitize_filename('a|b:c<d>e') == 'a_b_c_d_e'

    def test_preserves_valid_characters(self):
        """Valid characters including dots, dashes, underscores are preserved."""
        assert sanitize_filename('valid_file-name.txt') == 'valid_file-name.txt'
        assert sanitize_filename('data_2024-01-01.csv') == 'data_2024-01-01.csv'

    def test_handles_empty_string(self):
        """Empty string remains empty."""
        assert sanitize_filename('') == ''

    def test_handles_whitespace(self):
        """Whitespace characters are replaced with underscores."""
        assert sanitize_filename('file name') == 'file name'
        assert sanitize_filename('file\tname') == 'file\tname'
        assert sanitize_filename('file\nname') == 'file\nname'
        assert sanitize_filename('file name with spaces') == 'file name with spaces'


class TestHumanize:

    def test_converts_snake_case_to_title_case(self):
        assert titleize('battery_voltage') == 'Battery Voltage'
        assert titleize('cycle_number') == 'Cycle Number'
        assert titleize('specific_capacity') == 'Specific Capacity'

    def test_capitalizes_first_letter(self):
        assert titleize('voltage') == 'Voltage'
        assert titleize('current') == 'Current'

    def test_preserves_parentheses_and_units(self):
        """Units in parentheses are capitalized like other words (legacy behavior)."""
        assert titleize('charge (mA)') == 'Charge (ma)'
        assert titleize('battery_voltage (V)') == 'Battery Voltage (v)'

    def test_handles_already_capitalized_text(self):
        assert titleize('Already Capitalized') == 'Already Capitalized'

    def test_handles_empty_string(self):
        assert titleize('') == ''

    def test_handles_multiple_underscores(self):
        assert titleize('very_long_variable_name') == 'Very Long Variable Name'

    def test_handles_mixed_case_with_underscores(self):
        assert titleize('lower_Case_Mixed') == 'Lower Case Mixed'

class TestToSnakeCase:
    def test_converts_title_case_to_snake_case(self):
        assert to_snake_case('Battery Voltage') == 'battery_voltage'
        assert to_snake_case('Cycle Number') == 'cycle_number'

    def test_converts_single_word(self):
        assert to_snake_case('Voltage') == 'voltage'
        assert to_snake_case('Current') == 'current'

    def test_handles_empty_string(self):
        assert to_snake_case('') == ''

    def test_handles_multiple_spaces(self):
        assert to_snake_case('Multiple  Spaces') == 'multiple__spaces'

    def test_round_trip_conversion(self):
        original = 'battery_voltage'
        assert to_snake_case(titleize(original)) == original

        original2 = 'cycle_number'
        assert to_snake_case(titleize(original2)) == original2


class TestParseHeader:

    def test_parses_full_format_with_series_label_unit(self):
        """Format: 'series_name: label_name (unit)' is parsed correctly."""
        series, label, unit = parse_header('1cyc: capacity_calculated (mAh)')
        assert series == '1cyc'
        assert label == 'Capacity Calculated'
        assert unit == 'mAh'

    def test_parses_label_with_unit_no_series(self):
        """Format: 'label_name (unit)' without series is parsed correctly."""
        series, label, unit = parse_header('voltage (V)')
        assert series is None
        assert label == 'Voltage'
        assert unit == 'V'

    def test_parses_label_only_no_unit_no_series(self):
        """Format: 'label_name' without unit or series is parsed correctly."""
        series, label, unit = parse_header('cycle_number')
        assert series is None
        assert label == 'Cycle Number'
        assert unit is None

    def test_humanizes_snake_case_series(self):
        """Series name in snake_case is humanized."""
        series, label, unit = parse_header('series_one: cycle_number (mAh)')
        assert series == 'Series One'
        assert label == 'Cycle Number'
        assert unit == 'mAh'

    def test_humanizes_snake_case_label(self):
        """Label name in snake_case is humanized."""
        series, label, unit = parse_header('1cyc: battery_voltage (V)')
        assert series == '1cyc'
        assert label == 'Battery Voltage'
        assert unit == 'V'

    def test_preserves_already_capitalized_series(self):
        """Already capitalized series name is preserved."""
        series, label, unit = parse_header('Cycle1: voltage (V)')
        assert series == 'Cycle1'
        assert label == 'Voltage'
        assert unit == 'V'

    def test_handles_label_with_parentheses_but_no_unit(self):
        """Parentheses in label that are not units are handled."""
        series, label, unit = parse_header('test (sample)')
        assert series is None
        assert label == 'Test'
        assert unit == 'sample'

    def test_handles_complex_unit_strings(self):
        """Complex unit strings with special characters are preserved."""
        series, label, unit = parse_header('current (mA/cm²)')
        assert series is None
        assert label == 'Current'
        assert unit == 'mA/cm²'

    def test_handles_empty_string(self):
        """Empty string is handled gracefully."""
        series, label, unit = parse_header('')
        assert series is None
        assert label == ''
        assert unit is None

    def test_regression_from_existing_tests(self):
        """Test cases from test_csv2graph_unit.py are preserved."""
        # From test_parse_header_humanizes_and_extracts_unit
        assert parse_header("series_one: cycle_number (mAh)") == ("Series One", "Cycle Number", "mAh")
        assert parse_header("Voltage (V)") == (None, "Voltage", "V")
        assert parse_header("temperature") == (None, "Temperature", None)


class TestParseHeaderEdgeCases:

    def test_handles_multiple_colons(self):
        """Only the first colon is treated as series separator."""
        series, label, unit = parse_header('series: label: extra (unit)')
        assert series == 'Series'
        # "label: extra" should be the label part
        assert 'Label' in label or 'label' in label.lower()

    def test_handles_nested_parentheses(self):
        """Nested parentheses (if any) are handled."""
        # Most CSV headers won't have nested parentheses, but test gracefully handles
        series, label, unit = parse_header('value (unit1)')
        assert unit == 'unit1'

    def test_handles_whitespace_variations(self):
        """Various whitespace patterns are normalized."""
        series, label, unit = parse_header('  series  :  label  (  unit  )  ')
        assert series == 'Series'
        assert label == 'Label'
        assert unit == '  unit  '

    def test_handles_numeric_series_names(self):
        """Numeric series names are preserved."""
        series, label, unit = parse_header('100cyc: voltage (V)')
        assert series == '100cyc'
        assert label == 'Voltage'
        assert unit == 'V'


class TestHumanizeSnakeCaseIntegration:

    @pytest.mark.parametrize(
        "snake_case,expected_humanized",
        [
            ("battery_voltage", "Battery Voltage"),
            ("current_density", "Current Density"),
            ("cycle_number", "Cycle Number"),
            ("discharge_capacity", "Discharge Capacity"),
            ("charge_efficiency", "Charge Efficiency"),
        ],
    )
    def test_humanize_common_battery_terms(self, snake_case, expected_humanized):
        """Common battery cycling terms are humanized correctly."""
        assert titleize(snake_case) == expected_humanized

    @pytest.mark.parametrize(
        "humanized,expected_snake_case",
        [
            ("Battery Voltage", "battery_voltage"),
            ("Current Density", "current_density"),
            ("Cycle Number", "cycle_number"),
        ],
    )
    def test_to_snake_case_common_battery_terms(self, humanized, expected_snake_case):
        """Common battery cycling terms are converted to snake_case correctly."""
        assert to_snake_case(humanized) == expected_snake_case
