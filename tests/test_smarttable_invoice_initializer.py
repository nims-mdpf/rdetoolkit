"""
Equivalence Partitioning
| API                                   | Input/State Partition                                     | Rationale                                                     | Expected Outcome                                      | Test ID       |
| ------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------- | ------------- |
| `SmartTableInvoiceInitializer.process` | Multiple SmartTable rows with fresh processors per row    | Pipelines re-instantiate processors for each row              | Later invoices retain `sample.ownerId` after mutation | `TC-EP-001`   |
| `SmartTableInvoiceInitializer.process` | Missing SmartTable row CSV in SmartTable mode              | Invalid SmartTable input should be rejected                    | Raises `StructuredError`                              | `TC-EP-002`   |

Boundary Value
| API                                   | Boundary                                      | Rationale                                                    | Expected Outcome                                      | Test ID       |
| ------------------------------------- | --------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------- | ------------- |
| `SmartTableInvoiceInitializer.process` | First vs. subsequent invocation per invoice   | Cache must survive across pipeline instances and mutations   | Later invoices retain `sample.ownerId` after mutation | `TC-BV-001`   |
| `SmartTableInvoiceInitializer.process` | `smarttable_file` is `None`                    | SmartTable mode should be enforced                           | Raises `ValueError`                                   | `TC-BV-002`   |
"""

from __future__ import annotations

import csv
import json
import shutil
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
def reset_initializer_cache() -> None:
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
    # Given: two SmartTable rows and an original invoice containing ownerId
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    expected_owner_id = json.loads(invoice_org.read_text())["sample"]["ownerId"]
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

    # Then: the later invoice still includes the original ownerId
    assert output_invoice["sample"]["ownerId"] == expected_owner_id


def test_smarttable_invoice_initializer_uses_base_owner_on_first_invocation__tc_bv_001(tmp_path: Path) -> None:
    # Given: a SmartTable row without ownerId override
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    expected_owner_id = json.loads(invoice_org.read_text())["sample"]["ownerId"]
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

    # Then: ownerId remains from the original invoice template
    assert output_invoice["sample"]["ownerId"] == expected_owner_id


def test_smarttable_invoice_initializer_requires_row_csv__tc_ep_002(tmp_path: Path) -> None:
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
