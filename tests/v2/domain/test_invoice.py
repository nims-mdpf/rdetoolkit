"""Tests for v2 domain invoice facade.

EP Table:
| API           | Partition       | Rationale       | Expected      | Test ID   |
|---------------|-----------------|-----------------|---------------|-----------|
| load_invoice  | json invoice    | standard input  | InvoiceData   | TC-EP-001 |
| load_invoice  | missing file    | error path      | FileNotFoundError | TC-EP-002 |

BV Table:
| API           | Boundary        | Rationale       | Expected      | Test ID   |
|---------------|-----------------|-----------------|---------------|-----------|
| load_invoice  | empty object    | minimal JSON    | raw == {}     | TC-BV-001 |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestInvoiceFacade:
    """Tests for invoice facade helpers."""

    def test_load_json_invoice__tc_ep_001(self, tmp_path: Path) -> None:
        """TC-EP-001: JSON invoice loads into InvoiceData."""
        from rdetoolkit.domain.invoice import load_invoice

        # Given: an invoice JSON file
        invoice_path = tmp_path / "invoice.json"
        invoice_path.write_text(json.dumps({"basic": {"dataName": "sample"}}), encoding="utf-8")

        # When: loading invoice data
        invoice = load_invoice(invoice_path)

        # Then: raw data and mode are exposed
        assert invoice.raw["basic"]["dataName"] == "sample"
        assert invoice.mode == "invoice"

    def test_missing_invoice_raises__tc_ep_002(self, tmp_path: Path) -> None:
        """TC-EP-002: missing invoice file raises FileNotFoundError."""
        from rdetoolkit.domain.invoice import load_invoice

        # Given: a missing invoice path
        invoice_path = tmp_path / "missing.json"

        # When / Then: loading fails
        with pytest.raises(FileNotFoundError, match="Invoice file does not exist"):
            load_invoice(invoice_path)

    def test_empty_invoice_object__tc_bv_001(self, tmp_path: Path) -> None:
        """TC-BV-001: empty JSON object is a valid minimal invoice payload."""
        from rdetoolkit.domain.invoice import load_invoice

        # Given: an empty JSON invoice
        invoice_path = tmp_path / "invoice.json"
        invoice_path.write_text("{}", encoding="utf-8")

        # When: loading invoice data
        invoice = load_invoice(invoice_path)

        # Then: raw data is empty
        assert invoice.raw == {}
