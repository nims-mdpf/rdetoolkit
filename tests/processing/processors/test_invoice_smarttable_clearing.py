"""Test design tables for SmartTable invoice row clearing.

Equivalence Partitioning

| API                                   | Input/State Partition                                             | Rationale                               | Expected Outcome                                | Test ID      |
| ------------------------------------- | ----------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------ | ------------ |
| `SmartTableInvoiceInitializer.process` | Invoice already contains prior row values and SmartTable cells are `NaN` | Prevent inheriting stale row content    | Empty cells clear existing invoice fields        | `TC-EP-001` |
| `SmartTableInvoiceInitializer.process` | Invoice already contains prior row values and SmartTable provides new values | Confirm normal overwrite after reset    | Provided values replace previous invoice content | `TC-EP-002` |

Boundary Value Analysis

| API                                   | Boundary                               | Rationale                        | Expected Outcome                        | Test ID      |
| ------------------------------------- | -------------------------------------- | -------------------------------- | --------------------------------------- | ------------ |
| `SmartTableInvoiceInitializer.process` | Empty-string SmartTable cells (lower bound of provided content) | Ensure blanks do not inherit old data | Invoice fields are cleared/not inherited | `TC-BV-001` |
"""

import json
from pathlib import Path

import pandas as pd
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer


def _write_invoice(path: Path, *, description: str, composition: str, sample_description: str) -> None:
    """Helper to seed invoice_org with existing values."""
    payload = {
        "basic": {"dataName": "previous", "description": description},
        "custom": {"common_data_type": "previous_type"},
        "sample": {
            "names": ["previous_sample"],
            "composition": composition,
            "description": sample_description,
            "generalAttributes": [],
            "specificAttributes": [],
        },
    }
    path.write_text(json.dumps(payload))


class TestSmartTableRowClearing:
    """SmartTable rows should not inherit values from earlier rows."""

    def test_smarttable_clears_nan_cells__tc_ep_001(self, smarttable_processing_context) -> None:
        """Empty SmartTable cells represented as NaN should clear prior invoice values."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Given: invoice_org already contains previous row content
        invoice_org = context.resource_paths.invoice_org
        _write_invoice(invoice_org, description="old-desc", composition="old-comp", sample_description="old-sample-desc")
        csv_path = context.smarttable_rowfile
        assert csv_path is not None
        pd.DataFrame(
            {
                "basic/dataName": ["test2"],
                "basic/description": [pd.NA],
                "sample/names": ["sample-2"],
                "sample/composition": [pd.NA],
                "sample/description": [pd.NA],
                "custom/common_data_type": ["サンプル元"],
            },
        ).to_csv(csv_path, index=False)

        # When: processing the SmartTable row
        processor.process(context)

        # Then: previously populated fields are cleared instead of inherited
        output = json.loads(context.invoice_dst_filepath.read_text())
        assert output["basic"]["dataName"] == "test2"
        assert output["basic"].get("description") in (None, "")
        assert output["sample"].get("composition") in (None, "")
        assert output["sample"].get("description") in (None, "")

    def test_smarttable_overwrites_with_new_values__tc_ep_002(self, smarttable_processing_context) -> None:
        """Provided SmartTable values should overwrite existing invoice content."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Given: invoice_org has stale values while SmartTable provides replacements
        invoice_org = context.resource_paths.invoice_org
        _write_invoice(invoice_org, description="stale-desc", composition="stale-comp", sample_description="stale-sample-desc")
        csv_path = context.smarttable_rowfile
        assert csv_path is not None
        pd.DataFrame(
            {
                "basic/dataName": ["test3"],
                "basic/description": ["new-desc"],
                "sample/names": ["sample-3"],
                "sample/composition": ["new-comp"],
                "sample/description": ["new-sample-desc"],
                "custom/common_data_type": ["新規タイプ"],
            },
        ).to_csv(csv_path, index=False)

        # When: processing the SmartTable row
        processor.process(context)

        # Then: invoice fields reflect the new row values
        output = json.loads(context.invoice_dst_filepath.read_text())
        assert output["basic"]["dataName"] == "test3"
        assert output["basic"]["description"] == "new-desc"
        assert output["sample"]["names"] == ["sample-3"]
        assert output["sample"]["composition"] == "new-comp"
        assert output["sample"]["description"] == "new-sample-desc"
        assert output["custom"]["common_data_type"] == "新規タイプ"

    def test_smarttable_clears_empty_string_cells__tc_bv_001(self, smarttable_processing_context) -> None:
        """Empty-string SmartTable cells should also clear prior invoice values."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Given: invoice_org contains earlier row data and SmartTable sends empty strings
        invoice_org = context.resource_paths.invoice_org
        _write_invoice(invoice_org, description="carryover-desc", composition="carryover-comp", sample_description="carryover-sample")
        csv_path = context.smarttable_rowfile
        assert csv_path is not None
        pd.DataFrame(
            {
                "basic/dataName": ["test4"],
                "basic/description": [""],
                "sample/names": ["sample-4"],
                "sample/composition": [""],
                "sample/description": [""],
            },
        ).to_csv(csv_path, index=False)

        # When: processing the SmartTable row
        processor.process(context)

        # Then: previously stored values are removed instead of carried forward
        output = json.loads(context.invoice_dst_filepath.read_text())
        assert output["basic"]["dataName"] == "test4"
        assert output["basic"].get("description") in (None, "")
        assert output["sample"].get("composition") in (None, "")
        assert output["sample"].get("description") in (None, "")
