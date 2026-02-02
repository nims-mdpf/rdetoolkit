"""Test SmartTableInvoiceInitializer behavior with equivalence partitioning and boundary values.

Equivalence Partitioning:
| API                                   | Input/State Partition                                     | Rationale                                                     | Expected Outcome                                      | Test ID       |
| ------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------- | ------------- |
| `SmartTableInvoiceInitializer.process` | Multiple SmartTable rows with fresh processors per row    | Pipelines re-instantiate processors for each row              | sample.ownerId is set to basic.dataOwnerId            | `TC-EP-001`   |
| `SmartTableInvoiceInitializer.process` | Missing SmartTable row CSV in SmartTable mode              | Invalid SmartTable input should be rejected                    | Raises `StructuredError`                              | `TC-EP-002`   |
| `SmartTableInvoiceInitializer.process` | basic.dataOwnerId is missing in original invoice           | Defensive handling when required field is absent              | Logs warning, preserves original sample.ownerId       | `TC-EP-003`   |
| `SmartTableInvoiceInitializer.process` | SmartTable CSV contains sample/ownerId column              | basic.dataOwnerId should take precedence over CSV value       | sample.ownerId is set to basic.dataOwnerId            | `TC-EP-004`   |

Boundary Value:
| API                                   | Boundary                                      | Rationale                                                    | Expected Outcome                                      | Test ID       |
| ------------------------------------- | --------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------- | ------------- |
| `SmartTableInvoiceInitializer.process` | First invocation with SmartTable row          | Automatic ownerId assignment from basic.dataOwnerId          | sample.ownerId is set to basic.dataOwnerId            | `TC-BV-001`   |
| `SmartTableInvoiceInitializer.process` | `smarttable_file` is `None`                    | SmartTable mode should be enforced                           | Raises `ValueError`                                   | `TC-BV-002`   |
| `SmartTableInvoiceInitializer.process` | basic.dataOwnerId is empty string              | Defensive handling when field is empty                       | Logs warning, preserves original sample.ownerId       | `TC-BV-003`   |
"""

from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Generator
from pathlib import Path

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.rde2types import (
    RdeInputDirPaths,
    RdeOutputResourcePath,
    create_default_config,
)
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer


@pytest.fixture(autouse=True)
def reset_initializer_cache() -> Generator[None, None, None]:
    """Ensure SmartTable initializer cache isolation per test."""
    SmartTableInvoiceInitializer._BASE_INVOICE_CACHE.clear()
    yield
    SmartTableInvoiceInitializer._BASE_INVOICE_CACHE.clear()


def _copy_sample_invoice_files(base_dir: Path) -> tuple[Path, Path]:
    """Copy sample invoice and schema into an isolated work area."""
    tasksupport_dir = base_dir / "tasksupport"
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    invoice_dir = base_dir / "invoice"
    invoice_dir.mkdir(parents=True, exist_ok=True)

    invoice_org = invoice_dir / "invoice.json"
    schema_path = tasksupport_dir / "invoice.schema.json"

    shutil.copy(Path("tests/samplefile/invoice.json"), invoice_org)
    shutil.copy(Path("tests/samplefile/invoice.schema.json"), schema_path)

    return invoice_org, schema_path


def _write_smarttable_row(csv_path: Path, row: dict[str, str]) -> None:
    """Create a SmartTable row CSV with the provided data."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=row.keys())
        writer.writeheader()
        writer.writerow(row)


def _build_resource_paths(
    base_dir: Path,
    invoice_dir: Path,
    invoice_org: Path,
    schema_path: Path,
    rowfile: Path | None,
) -> RdeOutputResourcePath:
    """Construct a resource path bundle for SmartTable processing."""
    return RdeOutputResourcePath(
        raw=base_dir / "raw",
        nonshared_raw=base_dir / "nonshared_raw",
        rawfiles=(rowfile,) if rowfile else (),
        struct=base_dir / "structured",
        main_image=base_dir / "main_image",
        other_image=base_dir / "other_image",
        meta=base_dir / "meta",
        thumbnail=base_dir / "thumbnail",
        logs=base_dir / "logs",
        invoice=invoice_dir,
        invoice_schema_json=schema_path,
        invoice_org=invoice_org,
        smarttable_rowfile=rowfile,
        temp=base_dir / "temp",
        invoice_patch=base_dir / "invoice_patch",
        attachment=base_dir / "attachment",
    )


def test_smarttable_invoice_initializer_preserves_owner_id_after_source_mutation__tc_ep_001(tmp_path: Path) -> None:
    """TC-EP-001: Multiple SmartTable rows with fresh processors per row preserve basic.dataOwnerId."""
    # Given: two SmartTable rows and an original invoice containing ownerId
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    original_invoice = json.loads(invoice_org.read_text())
    # ownerId should be set from basic.dataOwnerId, not sample.ownerId
    expected_owner_id = original_invoice["basic"]["dataOwnerId"]
    smarttable_file = tmp_path / "inputdata" / "smarttable_sample.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    row1 = tmp_path / "temp" / "fsmarttable_case_0001.csv"
    _write_smarttable_row(row0, {"sample/names": "sample-one"})
    _write_smarttable_row(row1, {"sample/names": "sample-two", "sample/relatedSample[0]": "sample-one"})

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )

    resource_paths_first = _build_resource_paths(
        tmp_path, invoice_org.parent, invoice_org, schema_path, row0,
    )
    context_first = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths_first,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )
    initializer_first = SmartTableInvoiceInitializer()
    initializer_first.process(context_first)

    # And: the invoice source is externally mutated to drop ownerId
    mutated_invoice = json.loads(invoice_org.read_text())
    mutated_invoice["sample"].pop("ownerId", None)
    invoice_org.write_text(json.dumps(mutated_invoice))

    # When: processing the second SmartTable row with a new pipeline instance and mutated source
    divided_invoice_dir = tmp_path / "divided" / "0001" / "invoice"
    resource_paths_second = _build_resource_paths(
        tmp_path, divided_invoice_dir, invoice_org, schema_path, row1,
    )
    context_second = ProcessingContext(
        index="1",
        srcpaths=srcpaths,
        resource_paths=resource_paths_second,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )
    initializer_second = SmartTableInvoiceInitializer()
    initializer_second.process(context_second)

    output_invoice = json.loads((divided_invoice_dir / "invoice.json").read_text())

    # Then: sample.ownerId is set to basic.dataOwnerId
    assert output_invoice["sample"]["ownerId"] == expected_owner_id


def test_smarttable_invoice_initializer_sets_owner_id_from_data_owner__tc_bv_001(tmp_path: Path) -> None:
    """TC-BV-001: First invocation with SmartTable row sets sample.ownerId from basic.dataOwnerId."""
    # Given: a SmartTable row without ownerId override
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    original_invoice = json.loads(invoice_org.read_text())
    # ownerId should be set from basic.dataOwnerId
    expected_owner_id = original_invoice["basic"]["dataOwnerId"]
    smarttable_file = tmp_path / "inputdata" / "smarttable_sample.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {"sample/names": "sample-one"})

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )
    initializer = SmartTableInvoiceInitializer()

    resource_paths = _build_resource_paths(
        tmp_path, invoice_org.parent, invoice_org, schema_path, row0,
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )

    # When: processing the first row
    initializer.process(context)
    output_invoice = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: ownerId is set to basic.dataOwnerId
    assert output_invoice["sample"]["ownerId"] == expected_owner_id


def test_smarttable_invoice_initializer_requires_row_csv__tc_ep_002(tmp_path: Path) -> None:
    """TC-EP-002: Missing SmartTable row CSV in SmartTable mode raises StructuredError."""
    # Given: SmartTable mode without a generated row CSV
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    smarttable_file = tmp_path / "inputdata" / "smarttable_sample.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )
    initializer = SmartTableInvoiceInitializer()

    resource_paths = _build_resource_paths(
        tmp_path, invoice_org.parent, invoice_org, schema_path, None,
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )

    # When/Then: processing without a row CSV fails early
    with pytest.raises(StructuredError, match="No SmartTable row CSV file found"):
        initializer.process(context)


def test_smarttable_invoice_initializer_requires_smarttable_mode__tc_bv_002(tmp_path: Path) -> None:
    """TC-BV-002: smarttable_file is None raises ValueError."""
    # Given: SmartTable initializer invoked without smarttable mode enabled
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {"sample/names": "sample-one"})

    srcpaths = RdeInputDirPaths(
        inputdata=row0.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )
    initializer = SmartTableInvoiceInitializer()

    resource_paths = _build_resource_paths(
        tmp_path, invoice_org.parent, invoice_org, schema_path, row0,
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=None,
    )

    # When/Then: SmartTable processing rejects contexts without smarttable_file
    with pytest.raises(ValueError, match="SmartTable file not provided"):
        initializer.process(context)


def test_smarttable_invoice_initializer_warns_when_data_owner_id_missing__tc_ep_003(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """TC-EP-003: basic.dataOwnerId missing logs warning and preserves original sample.ownerId."""
    # Given: an original invoice without basic.dataOwnerId
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    original_invoice = json.loads(invoice_org.read_text())
    original_sample_owner_id = original_invoice["sample"]["ownerId"]

    # Remove dataOwnerId to simulate missing value
    del original_invoice["basic"]["dataOwnerId"]
    invoice_org.write_text(json.dumps(original_invoice))

    smarttable_file = tmp_path / "inputdata" / "smarttable_sample.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {"sample/names": "sample-one"})

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )
    initializer = SmartTableInvoiceInitializer()

    resource_paths = _build_resource_paths(
        tmp_path, invoice_org.parent, invoice_org, schema_path, row0,
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )

    # When: processing with missing basic.dataOwnerId
    with caplog.at_level("WARNING"):
        initializer.process(context)

    output_invoice = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: warning is logged and sample.ownerId is preserved from original
    assert "basic.dataOwnerId is missing or empty" in caplog.text
    assert output_invoice["sample"]["ownerId"] == original_sample_owner_id


def test_smarttable_invoice_initializer_warns_when_data_owner_id_empty__tc_bv_003(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """TC-BV-003: basic.dataOwnerId empty string logs warning and preserves original sample.ownerId."""
    # Given: an original invoice with empty basic.dataOwnerId
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    original_invoice = json.loads(invoice_org.read_text())
    original_sample_owner_id = original_invoice["sample"]["ownerId"]

    # Set dataOwnerId to empty string
    original_invoice["basic"]["dataOwnerId"] = ""
    invoice_org.write_text(json.dumps(original_invoice))

    smarttable_file = tmp_path / "inputdata" / "smarttable_sample.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {"sample/names": "sample-one"})

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )
    initializer = SmartTableInvoiceInitializer()

    resource_paths = _build_resource_paths(
        tmp_path, invoice_org.parent, invoice_org, schema_path, row0,
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )

    # When: processing with empty basic.dataOwnerId
    with caplog.at_level("WARNING"):
        initializer.process(context)

    output_invoice = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: warning is logged and sample.ownerId is preserved from original
    assert "basic.dataOwnerId is missing or empty" in caplog.text
    assert output_invoice["sample"]["ownerId"] == original_sample_owner_id


def test_smarttable_invoice_initializer_overrides_csv_owner_id_with_data_owner__tc_ep_004(tmp_path: Path) -> None:
    """TC-EP-004: SmartTable CSV sample/ownerId is overridden by basic.dataOwnerId."""
    # Given: SmartTable row with sample/ownerId column
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    original_invoice = json.loads(invoice_org.read_text())
    expected_owner_id = original_invoice["basic"]["dataOwnerId"]

    smarttable_file = tmp_path / "inputdata" / "smarttable_sample.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    # SmartTable CSV includes sample/ownerId column with different value
    csv_owner_id = "DifferentOwnerIdFromCSVaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {
        "sample/names": "sample-one",
        "sample/ownerId": csv_owner_id,
    })

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )
    initializer = SmartTableInvoiceInitializer()

    resource_paths = _build_resource_paths(
        tmp_path, invoice_org.parent, invoice_org, schema_path, row0,
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )

    # When: processing with both CSV ownerId and basic.dataOwnerId
    initializer.process(context)
    output_invoice = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: basic.dataOwnerId takes precedence over CSV value
    assert output_invoice["sample"]["ownerId"] == expected_owner_id
    assert output_invoice["sample"]["ownerId"] != csv_owner_id
