"""Tests for StructuredInvoiceSaver processor.

Equivalence Partitioning Table
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `StructuredInvoiceSaver.process` | Flag enabled with existing invoice | Happy path ensures structured copy succeeds | Structured invoice file created | TC-EP-001 |
| `StructuredInvoiceSaver.process` | Flag disabled regardless of source | Configuration should short-circuit copy | No structured invoice emitted | TC-EP-002 |
| `StructuredInvoiceSaver.process` | Flag enabled but invoice missing | Error propagation for absent source | Raises `FileNotFoundError` | TC-EP-003 |

Boundary Value Table
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `StructuredInvoiceSaver.process` | `save_invoice_to_structured` toggled True/False | Upper/lower boundary of feature flag | Copy occurs only when True | TC-BV-001 |
| `StructuredInvoiceSaver.process` | Source file existence vs absence | Boundary on external dependency availability | Success when present, error when absent | TC-BV-002 |

Pytest execution commands
- `pytest tests/processing/test_structured_invoice_saver.py -q`
- `tox`
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.models.config import Config, SystemSettings
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.processors.structured import StructuredInvoiceSaver


def _build_context(
    *,
    tmp_path: Path,
    save_to_structured: bool,
    invoice_org: Path,
) -> ProcessingContext:
    """Create a ProcessingContext tailored for StructuredInvoiceSaver tests."""
    config = Config(system=SystemSettings(save_invoice_to_structured=save_to_structured))
    input_paths = RdeInputDirPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
        config=config,
    )
    resource_paths = RdeOutputResourcePath(
        raw=tmp_path / "raw",
        nonshared_raw=tmp_path / "nonshared_raw",
        rawfiles=(),
        struct=tmp_path / "structured",
        main_image=tmp_path / "main_image",
        other_image=tmp_path / "other_image",
        meta=tmp_path / "meta",
        thumbnail=tmp_path / "thumbnail",
        logs=tmp_path / "logs",
        invoice=tmp_path / "invoice_dst",
        invoice_schema_json=tmp_path / "invoice_schema.json",
        invoice_org=invoice_org,
    )
    return ProcessingContext(
        index="0001",
        srcpaths=input_paths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="multidatatile",
    )


def test_structured_invoice_saver_copies_invoice__tc_ep_001(tmp_path: Path) -> None:
    """TC-EP-001 / TC-BV-001"""
    # Given: save-to-structured enabled and an existing invoice source
    invoice_org = tmp_path / "tasksupport" / "invoice_org.json"
    invoice_org.parent.mkdir(parents=True, exist_ok=True)
    invoice_org.write_text('{"id": 1}', encoding="utf-8")
    context = _build_context(tmp_path=tmp_path, save_to_structured=True, invoice_org=invoice_org)
    saver = StructuredInvoiceSaver()

    # When: executing the structured invoice saver
    saver.process(context)

    # Then: the structured directory contains a copied invoice file
    structured_invoice = context.resource_paths.struct / "invoice.json"
    assert structured_invoice.exists()
    assert structured_invoice.read_text(encoding="utf-8") == invoice_org.read_text(encoding="utf-8")


def test_structured_invoice_saver_noop_when_flag_disabled__tc_ep_002(tmp_path: Path) -> None:
    """TC-EP-002 / TC-BV-001"""
    # Given: save-to-structured disabled even though the source invoice exists
    invoice_org = tmp_path / "tasksupport" / "invoice_org.json"
    invoice_org.parent.mkdir(parents=True, exist_ok=True)
    invoice_org.write_text("{}", encoding="utf-8")
    context = _build_context(tmp_path=tmp_path, save_to_structured=False, invoice_org=invoice_org)
    saver = StructuredInvoiceSaver()

    # When: executing the structured invoice saver
    saver.process(context)

    # Then: no structured invoice file is created
    structured_invoice = context.resource_paths.struct / "invoice.json"
    assert not structured_invoice.exists()


def test_structured_invoice_saver_raises_when_missing_source__tc_ep_003(tmp_path: Path) -> None:
    """TC-EP-003 / TC-BV-002"""
    # Given: save-to-structured enabled but the source invoice is absent
    missing_invoice = tmp_path / "tasksupport" / "invoice_org.json"
    context = _build_context(tmp_path=tmp_path, save_to_structured=True, invoice_org=missing_invoice)
    saver = StructuredInvoiceSaver()

    # When/Then: processing raises FileNotFoundError for the missing source
    with pytest.raises(FileNotFoundError, match="Original invoice not found"):
        saver.process(context)
