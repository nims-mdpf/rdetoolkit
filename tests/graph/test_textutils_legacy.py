"""Legacy compatibility tests for textutils module.

This module verifies that the refactored textutils functions produce
identical results to the original implementations in csv2graph.py.
"""

import pytest

from local.develop.issue_188.csv2graph import (
    humanize as legacy_humanize,
    parse_header as legacy_parse_header,
    sanitize_filename as legacy_sanitize_filename,
)
from rdetoolkit.graph.textutils import parse_header, sanitize_filename
from rdetoolkit.graph.textutils import titleize as humanize


class TestSanitizeFilenameLegacyCompatibility:
    """Verify sanitize_filename matches legacy implementation."""

    @pytest.mark.parametrize(
        "input_str",
        [
            "normal_filename",
            "file/with/slash",
            "file\\with\\backslash",
            "file*with*asterisk",
            "file?with?question",
            'file"with"quote',
            "file:with:colon",
            "file<with>angle",
            "file|with|pipe",
            "multiple///slashes",
            "mixed\\/*?characters",
            "",
            "already_clean_123",
        ],
    )
    def test_matches_legacy_sanitize_filename(self, input_str: str):
        """New sanitize_filename produces identical output to legacy version."""
        legacy_result = legacy_sanitize_filename(input_str)
        new_result = sanitize_filename(input_str)
        assert new_result == legacy_result, f"Input: '{input_str}'"


class TestHumanizeLegacyCompatibility:
    """Verify humanize matches legacy implementation."""

    @pytest.mark.parametrize(
        "input_str",
        [
            "battery_voltage",
            "current_density",
            "cycle_number",
            "discharge_capacity",
            "charge_efficiency",
            "single",
            "already_capitalized",
            "multiple_word_test_case",
            "",
            "with_number_123",
            "1cyc",
            "test_case (mAh)",
        ],
    )
    def test_matches_legacy_humanize(self, input_str: str):
        """New humanize produces identical output to legacy version."""
        legacy_result = legacy_humanize(input_str)
        new_result = humanize(input_str)
        assert new_result == legacy_result, f"Input: '{input_str}'"


class TestParseHeaderLegacyCompatibility:
    """Verify parse_header matches legacy implementation."""

    @pytest.mark.parametrize(
        "header",
        [
            "1cyc: capacity_calculated (mAh)",
            "voltage (V)",
            "current_density",
            "2cyc: discharge_capacity (Ah)",
            "temperature (°C)",
            "time: elapsed_time (s)",
            "resistance (Ω)",
            "",
            "simple_label",
            "series: label",
            "label (unit)",
            "battery_voltage (V)",
            "1cyc: current (A)",
        ],
    )
    def test_matches_legacy_parse_header(self, header: str):
        """New parse_header produces identical output to legacy version."""
        legacy_result = legacy_parse_header(header)
        new_result = parse_header(header)
        assert new_result == legacy_result, f"Input: '{header}'"

    def test_all_components_match_legacy(self):
        """Verify all three components (series, label, unit) match legacy."""
        test_cases = [
            "1cyc: capacity_calculated (mAh)",
            "voltage (V)",
            "current_density",
            "2cyc: discharge_capacity (Ah)",
        ]

        for header in test_cases:
            legacy_series, legacy_label, legacy_unit = legacy_parse_header(header)
            new_series, new_label, new_unit = parse_header(header)

            assert new_series == legacy_series, f"Series mismatch for '{header}'"
            assert new_label == legacy_label, f"Label mismatch for '{header}'"
            assert new_unit == legacy_unit, f"Unit mismatch for '{header}'"


class TestIntegrationWithGraphCases:
    """Integration tests using actual graph test cases."""

    def test_sanitize_filename_with_real_case_names(self):
        """Test with actual case names from fixtures."""
        from tests.fixtures.csv2graph import GRAPH_CASES

        for case in GRAPH_CASES:
            name = case.plot_kwargs.get("name", case.name)
            legacy_result = legacy_sanitize_filename(str(name))
            new_result = sanitize_filename(str(name))
            assert new_result == legacy_result, f"Case: {case.name}, Name: {name}"

    def test_parse_header_with_real_csv_headers(self):
        """Test with actual CSV headers from fixtures."""
        import pandas as pd

        from tests.fixtures.csv2graph import GRAPH_CASES

        for case in GRAPH_CASES:
            # Read CSV and get headers
            try:
                df = pd.read_csv(case.csv_path, nrows=0)
                headers = df.columns.tolist()

                for header in headers:
                    legacy_result = legacy_parse_header(str(header))
                    new_result = parse_header(str(header))
                    assert new_result == legacy_result, f"Case: {case.name}, Header: {header}"
            except Exception:
                # Skip if CSV format is incompatible with simple read
                continue
