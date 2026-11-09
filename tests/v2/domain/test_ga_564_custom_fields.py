"""GA564 EP/BV: invoice custom fields and builders use the real invoice shape."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.domain.invoice import load_invoice
from rdetoolkit.nodes import parse_invoice_meta
from rdetoolkit.testing import make_invoice
from rdetoolkit.types import InvoiceData


def test_real_invoice_custom_is_parsed__ga564_ep_1(tmp_path: Path) -> None:
    """GA564-EP-1: only the actual custom section feeds metadata assignment."""
    # Given: an on-disk invoice with unrelated top-level system fields
    path = tmp_path / "invoice.json"
    path.write_text(json.dumps({"datasetId": "test", "basic": {}, "custom": {"temperature": 42}}), encoding="utf-8")
    definition = tmp_path / "metadata-def.json"
    definition.write_text(json.dumps({"temperature": {"schema": {"type": "number"}}}), encoding="utf-8")
    invoice = load_invoice(path)
    # When: reading custom fields and using the public metadata node
    custom = invoice.get_custom_fields()
    metadata = parse_invoice_meta(invoice, definition)
    # Then: invoice system fields never replace the measurement fields
    assert custom == {"temperature": 42}
    assert metadata.custom == custom


@pytest.mark.parametrize("raw", [{"leaked": 42}, {"custom": None}, {"custom": []}, {"custom": "invalid"}, {"custom": {}}])
def test_missing_or_invalid_custom_never_leaks_top_level__ga564_bv_1(raw: dict[str, Any]) -> None:
    """GA564-BV-1: absent or malformed sections never expose system fields."""
    # Given: an invoice without a custom object
    invoice = InvoiceData(raw=raw)
    # When: extracting custom fields
    custom = invoice.get_custom_fields()
    # Then: there are no custom fields
    assert custom == {}


def test_custom_keys_are_not_filtered_by_spelling__ga564_bv_2() -> None:
    """GA564-BV-2: underscores inside the custom object are user data."""
    # Given: an explicit custom field with an underscore
    invoice = InvoiceData(raw={"custom": {"_measurement": 42}, "basic": {}})
    # When: reading its custom fields
    custom = invoice.get_custom_fields()
    # Then: the custom object is preserved verbatim
    assert custom == {"_measurement": 42}


@pytest.mark.parametrize("overrides", [{"temperature": 42}, {"custom": {"temperature": 42}, "basic": {"dataName": "real"}}])
def test_builder_uses_nested_custom__ga564_ep_2_3(overrides: dict[str, Any]) -> None:
    """GA564-EP-2/3: shorthand values and explicit invoice sections are realistic."""
    # Given: either field shorthand or explicit invoice sections
    # When: constructing a public test invoice
    invoice = make_invoice(overrides)
    # Then: custom fields live in the same location as a real invoice.json
    assert invoice.raw["custom"] == {"temperature": 42}
    assert "temperature" not in invoice.raw
    assert invoice.get_custom_fields() == {"temperature": 42}
