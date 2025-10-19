import os
import pandas as pd
import pytest

# CI / Actions 上では実行しない
if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
    pytest.skip("Skipping legacy compatibility tests on CI.", allow_module_level=True)

from local.develop.issue_188.csv2graph import process_csv as legacy_process_csv
from rdetoolkit.graph.parsers import CSVParser
from tests.fixtures.csv2graph import GRAPH_CASES


class TestCSVParserLegacyCompatibility:
    """Verify CSVParser produces identical results to legacy process_csv."""

    @pytest.mark.parametrize("case", GRAPH_CASES)
    def test_dataframe_matches_legacy(self, case):
        """Parsed DataFrame matches legacy exactly."""
        legacy_df, legacy_meta = legacy_process_csv(str(case.csv_path))
        new_df, new_meta = CSVParser.parse(case.csv_path)

        # DataFrame完全一致
        pd.testing.assert_frame_equal(new_df, legacy_df)

    @pytest.mark.parametrize("case", GRAPH_CASES)
    def test_metadata_matches_legacy(self, case):
        """Metadata dict matches legacy."""
        legacy_df, legacy_meta = legacy_process_csv(str(case.csv_path))
        new_df, new_meta = CSVParser.parse(case.csv_path)

        # メタデータキーと値の一致
        assert new_meta['xaxis_label'] == legacy_meta['xaxis_label']
        assert new_meta['yaxis_label'] == legacy_meta['yaxis_label']
