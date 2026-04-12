"""Test SmartTableInvoiceInitializer behavior with equivalence partitioning and boundary values.

Equivalence Partitioning:

| Input/State Partition                                   | Expected Outcome                                       | Test ID     |
| ------------------------------------------------------- | ------------------------------------------------------ | ----------- |
| Multiple SmartTable rows with fresh processors per row  | sample.ownerId is set to basic.dataOwnerId             | TC-EP-001   |
| Missing SmartTable row CSV in SmartTable mode           | Raises StructuredError                                 | TC-EP-002   |
| basic.dataOwnerId is missing in original invoice        | Logs warning, preserves original sample.ownerId        | TC-EP-003   |
| SmartTable CSV contains sample/ownerId column           | sample.ownerId uses CSV value, not basic.dataOwnerId   | TC-EP-004   |
| sample/names specified, sample/sampleId absent          | sampleId=None, other dummy fields cleared              | TC-EP-005   |
| sample/names specified, sample/sampleId = UUID          | sampleId preserved, other fields unchanged             | TC-EP-006   |
| Neither sample/names nor sample/sampleId specified      | All original sample fields unchanged                   | TC-EP-007   |
| sample/names given, sample/sampleId column present=""  | sampleId=None, other fields cleared                    | TC-EP-008   |
| sample/names only; Issue #389 ownerId correction        | sample.ownerId = basic.dataOwnerId after clearing      | TC-EP-009   |
| sample/names with fixed-header blank sample columns     | Cleared structures remain, not removed                 | TC-EP-010   |
| sample/names + UUID + blank sample field                | Explicit sampleId kept; blank field removed            | TC-EP-011   |
| Original invoice has sample.generalAttributes = null   | generalAttributes.<termId> written without error       | TC-EP-012   |
| Original invoice has sample.specificAttributes = null  | specificAttributes.<classId>.<termId> written ok       | TC-EP-013   |

Boundary Value:

| Boundary                                     | Expected Outcome                            | Test ID   |
| -------------------------------------------- | ------------------------------------------- | --------- |
| First invocation with SmartTable row         | sample.ownerId set to basic.dataOwnerId     | TC-BV-001 |
| smarttable_file is None                      | Raises ValueError                           | TC-BV-002 |
| basic.dataOwnerId is empty string            | Logs warning, preserves original ownerId    | TC-BV-003 |
| sample/sampleId = empty string ""            | Treated as absent; new sample clearing runs | TC-BV-004 |
| sample/sampleId = valid UUID string          | No clearing; sampleId preserved             | TC-BV-005 |
| sample/sampleId = whitespace-only "   "      | Treated as absent; new sample clearing runs | TC-BV-006 |
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


def test_smarttable_invoice_initializer_uses_csv_owner_id_when_specified__tc_ep_004(tmp_path: Path) -> None:
    """TC-EP-004: SmartTable CSV sample/ownerId takes precedence over basic.dataOwnerId."""
    # Given: SmartTable row with sample/ownerId column explicitly specified
    invoice_org, schema_path = _copy_sample_invoice_files(tmp_path)
    original_invoice = json.loads(invoice_org.read_text())
    data_owner_id = original_invoice["basic"]["dataOwnerId"]

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

    # Then: CSV value takes precedence over basic.dataOwnerId
    assert output_invoice["sample"]["ownerId"] == csv_owner_id
    assert output_invoice["sample"]["ownerId"] != data_owner_id


# ---------------------------------------------------------------------------
# Issue #455: New sample clearing when sample/names is specified without sampleId
# ---------------------------------------------------------------------------


def _build_invoice_with_dummy_sample(base_dir: Path) -> tuple[Path, Path, dict]:
    """Copy sample files and inject a non-empty dummy sampleId into the invoice."""
    invoice_org, schema_path = _copy_sample_invoice_files(base_dir)
    original = json.loads(invoice_org.read_text())

    # Inject a realistic dummy sampleId so we can verify it gets cleared
    dummy_sample_id = "aaaabbbb-1111-2222-3333-ccccddddeeee"
    original["sample"]["sampleId"] = dummy_sample_id
    original["sample"]["description"] = "Dummy description"
    original["sample"]["composition"] = "Dummy composition"
    original["sample"]["referenceUrl"] = "https://dummy.example.com"
    for attr in original["sample"].get("generalAttributes", []):
        attr["value"] = "dummy_value"
    for attr in original["sample"].get("specificAttributes", []):
        attr["value"] = "dummy_value"
    invoice_org.write_text(json.dumps(original))
    return invoice_org, schema_path, original


def _make_context(
    base_dir: Path,
    invoice_org: Path,
    schema_path: Path,
    invoice_dir: Path,
    row: Path,
) -> ProcessingContext:
    """Build a minimal ProcessingContext for SmartTable tests."""
    smarttable_file = base_dir / "inputdata" / "smarttable_sample.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )
    resource_paths = _build_resource_paths(
        base_dir, invoice_dir, invoice_org, schema_path, row,
    )
    return ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )


def _build_restructured_invoice(base_dir: Path) -> tuple[Path, Path, dict]:
    """Copy a restructured invoice fixture with null sample attribute containers."""
    tasksupport_dir = base_dir / "tasksupport"
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    invoice_dir = base_dir / "invoice"
    invoice_dir.mkdir(parents=True, exist_ok=True)

    invoice_org = invoice_dir / "invoice.json"
    schema_path = tasksupport_dir / "invoice.schema.json"

    shutil.copy(Path("tests/samplefile/invoice_restructured.json"), invoice_org)
    shutil.copy(Path("tests/samplefile/invoice.schema.full.json"), schema_path)

    original = json.loads(invoice_org.read_text())
    return invoice_org, schema_path, original


def test_smarttable_clears_dummy_sample_when_names_only__tc_ep_005(tmp_path: Path) -> None:
    """TC-EP-005: sample/names given without sample/sampleId clears all dummy sample fields."""
    # Given: original invoice has a dummy sampleId and filled dummy fields
    invoice_org, schema_path, _ = _build_invoice_with_dummy_sample(tmp_path)
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {"sample/names": "New Sample"})

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: dummy sampleId is cleared
    assert output["sample"]["sampleId"] is None
    # Then: dummy text fields are cleared
    assert output["sample"]["description"] is None
    assert output["sample"]["composition"] is None
    assert output["sample"]["referenceUrl"] is None
    # Then: names is set from CSV
    assert output["sample"]["names"] == ["New Sample"]
    # Then: generalAttributes values are cleared (structure preserved)
    for attr in output["sample"].get("generalAttributes", []):
        assert attr["value"] is None
    # Then: specificAttributes values are cleared (structure preserved)
    for attr in output["sample"].get("specificAttributes", []):
        assert attr["value"] is None


def test_smarttable_preserves_sample_id_when_uuid_given__tc_ep_006(tmp_path: Path) -> None:
    """TC-EP-006: sample/names + explicit sample/sampleId UUID preserves existing sample reference."""
    # Given: original invoice has a dummy sampleId; CSV overrides it with a real UUID
    invoice_org, schema_path, _ = _build_invoice_with_dummy_sample(tmp_path)
    explicit_uuid = "12345678-abcd-ef01-2345-6789abcdef01"
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {
        "sample/names": "Existing Sample",
        "sample/sampleId": explicit_uuid,
    })

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: sampleId is set to the explicitly provided UUID (no clearing)
    assert output["sample"]["sampleId"] == explicit_uuid
    # Then: names is updated
    assert output["sample"]["names"] == ["Existing Sample"]
    # Then: dummy fields are NOT cleared when sampleId is provided
    assert output["sample"]["description"] == "Dummy description"


def test_smarttable_preserves_original_when_no_sample_columns__tc_ep_007(tmp_path: Path) -> None:
    """TC-EP-007: No sample/ columns in CSV; all original sample fields are preserved."""
    # Given: original invoice has a non-empty sampleId and other sample data
    invoice_org, schema_path, original = _build_invoice_with_dummy_sample(tmp_path)
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {"basic/dataName": "Only Basic Update"})

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: original sample fields are intact (no sample/names = no clearing)
    assert output["sample"]["sampleId"] == original["sample"]["sampleId"]
    assert output["sample"]["description"] == "Dummy description"
    assert output["sample"]["composition"] == "Dummy composition"


def test_smarttable_clears_dummy_sample_when_sampleid_empty__tc_ep_008(tmp_path: Path) -> None:
    """TC-EP-008: sample/names given with empty sample/sampleId column → new sample clearing."""
    # Given: CSV has sample/names AND sample/sampleId as empty string (explicit clear)
    invoice_org, schema_path, _ = _build_invoice_with_dummy_sample(tmp_path)
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    # sample/sampleId column present with empty value
    _write_smarttable_row(row0, {"sample/names": "Brand New", "sample/sampleId": ""})

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: new-sample clearing applies because sampleId was not a non-empty value
    assert output["sample"]["sampleId"] is None
    assert output["sample"]["description"] is None
    assert output["sample"]["names"] == ["Brand New"]


def test_smarttable_ownerid_corrected_after_new_sample_clearing__tc_ep_009(tmp_path: Path) -> None:
    """TC-EP-009: Issue #389 ownerId correction still works correctly after new-sample clearing."""
    # Given: original invoice has a dummy sampleId; CSV has only sample/names
    invoice_org, schema_path, original = _build_invoice_with_dummy_sample(tmp_path)
    expected_owner_id = original["basic"]["dataOwnerId"]
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {"sample/names": "New Sample"})

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: sampleId is cleared (new-sample clearing ran)
    assert output["sample"]["sampleId"] is None
    # Then: ownerId is set to basic.dataOwnerId (Issue #389 logic preserved)
    assert output["sample"]["ownerId"] == expected_owner_id


def test_smarttable_preserves_cleared_sample_fields_for_blank_fixed_headers__tc_ep_010(
    tmp_path: Path,
) -> None:
    """TC-EP-010: Blank fixed-header sample columns must not remove new-sample cleared structure."""
    # Given: original invoice has dummy values and SmartTable includes blank sample columns
    invoice_org, schema_path, original = _build_invoice_with_dummy_sample(tmp_path)
    general_attr = original["sample"]["generalAttributes"][0]
    specific_attr = original["sample"]["specificAttributes"][0]
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {
        "sample/names": "Brand New Fixed Header",
        "sample/sampleId": "",
        "sample/description": "",
        f"sample/generalAttributes.{general_attr['termId']}": "",
        (
            "sample/specificAttributes."
            f"{specific_attr['classId']}.{specific_attr['termId']}"
        ): "",
    })

    # When: processing the new-sample row
    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: cleared scalar fields remain in their normalized empty form
    assert output["sample"]["sampleId"] is None
    assert output["sample"]["description"] is None
    # Then: cleared attribute entries are preserved instead of being deleted
    assert any(
        attr["termId"] == general_attr["termId"] and attr["value"] is None
        for attr in output["sample"]["generalAttributes"]
    )
    assert any(
        attr["classId"] == specific_attr["classId"]
        and attr["termId"] == specific_attr["termId"]
        and attr["value"] is None
        for attr in output["sample"]["specificAttributes"]
    )


def test_smarttable_existing_sample_still_clears_blank_fields__tc_ep_011(tmp_path: Path) -> None:
    """TC-EP-011: Existing-sample rows still use generic blank-cell clearing for sample fields."""
    # Given: original invoice has dummy values and SmartTable references an existing sample
    invoice_org, schema_path, _ = _build_invoice_with_dummy_sample(tmp_path)
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    explicit_uuid = "12345678-abcd-ef01-2345-6789abcdef01"
    _write_smarttable_row(row0, {
        "sample/names": "Existing Sample",
        "sample/sampleId": explicit_uuid,
        "sample/description": "",
    })

    # When: processing the existing-sample row
    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: explicit sampleId is preserved
    assert output["sample"]["sampleId"] == explicit_uuid
    # Then: blank sample fields still follow generic clearing semantics
    assert "description" not in output["sample"]


def test_smarttable_normalizes_null_general_attributes_before_assignment__tc_ep_012(
    tmp_path: Path,
) -> None:
    """TC-EP-012: Null generalAttributes containers are normalized before SmartTable assignment."""
    # Given: a restructured invoice whose generalAttributes container is null
    invoice_org, schema_path, original = _build_restructured_invoice(tmp_path)
    assert original["sample"]["generalAttributes"] is None
    term_id = "7cc57dfb-8b70-4b3a-5315-fbce4cbf73d0"
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {f"sample/generalAttributes.{term_id}": "pellet"})

    # When: processing a SmartTable row that targets sample/generalAttributes.<termId>
    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: the null container is normalized and the requested term is written
    assert isinstance(output["sample"]["generalAttributes"], list)
    assert output["sample"]["generalAttributes"] == [
        {"termId": term_id, "value": "pellet"},
    ]


def test_smarttable_normalizes_null_specific_attributes_before_assignment__tc_ep_013(
    tmp_path: Path,
) -> None:
    """TC-EP-013: Null specificAttributes containers are normalized before SmartTable assignment."""
    # Given: a restructured invoice whose specificAttributes container is null
    invoice_org, schema_path, original = _build_restructured_invoice(tmp_path)
    assert original["sample"]["specificAttributes"] is None
    class_id = "01cb3c01-37a4-5a43-d8ca-f523ca99a75b"
    term_id = "3250c45d-0ed6-1438-43b5-eb679918604a"
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {
        f"sample/specificAttributes.{class_id}.{term_id}": "single crystal",
    })

    # When: processing a SmartTable row that targets sample/specificAttributes.<classId>.<termId>
    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: the null container is normalized and the requested class/term entry is written
    assert isinstance(output["sample"]["specificAttributes"], list)
    assert output["sample"]["specificAttributes"] == [
        {
            "classId": class_id,
            "termId": term_id,
            "value": "single crystal",
        },
    ]


def test_smarttable_empty_sampleid_boundary_triggers_clearing__tc_bv_004(tmp_path: Path) -> None:
    """TC-BV-004: Boundary — sample/sampleId present as empty string triggers new-sample clearing."""
    # Given: invoice with dummy sampleId; CSV explicitly clears sampleId with ""
    invoice_org, schema_path, _ = _build_invoice_with_dummy_sample(tmp_path)
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {
        "sample/names": "Sample BV-004",
        "sample/sampleId": "",
    })

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: empty sampleId in CSV is treated as "no sampleId" → clearing applies
    assert output["sample"]["sampleId"] is None
    assert output["sample"]["description"] is None


def test_smarttable_uuid_sampleid_boundary_preserves_reference__tc_bv_005(tmp_path: Path) -> None:
    """TC-BV-005: Boundary — valid UUID in sample/sampleId column prevents clearing."""
    # Given: invoice with dummy sampleId; CSV sets a real UUID
    invoice_org, schema_path, _ = _build_invoice_with_dummy_sample(tmp_path)
    uuid_value = "fedcba98-7654-3210-fedc-ba9876543210"
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {
        "sample/names": "Sample BV-005",
        "sample/sampleId": uuid_value,
    })

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: UUID is preserved; no new-sample clearing
    assert output["sample"]["sampleId"] == uuid_value
    # description still holds the dummy value (no clearing happened)
    assert output["sample"]["description"] == "Dummy description"


def test_smarttable_whitespace_sampleid_triggers_clearing__tc_bv_006(tmp_path: Path) -> None:
    """TC-BV-006: Boundary — whitespace-only sample/sampleId is treated as absent → clearing runs.

    Regression for Copilot review comment: 'value.strip()' must be used so that
    cells containing only spaces are not mistaken for a valid sampleId reference.
    """
    # Given: invoice with dummy sampleId; CSV has sample/sampleId = "   " (spaces only)
    invoice_org, schema_path, _ = _build_invoice_with_dummy_sample(tmp_path)
    row0 = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    _write_smarttable_row(row0, {
        "sample/names": "Brand New BV-006",
        "sample/sampleId": "   ",
    })

    context = _make_context(tmp_path, invoice_org, schema_path, invoice_org.parent, row0)
    SmartTableInvoiceInitializer().process(context)
    output = json.loads((invoice_org.parent / "invoice.json").read_text())

    # Then: whitespace-only sampleId is equivalent to absent → new-sample clearing applies
    assert output["sample"]["sampleId"] is None
    assert output["sample"]["description"] is None
    assert output["sample"]["names"] == ["Brand New BV-006"]
