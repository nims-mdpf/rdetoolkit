"""Regression tests for SmartTable custom type casting (issue 429).

Equivalence Partitioning:
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `SmartTableInvoiceInitializer.process` | `custom/process_key_temperature` is schema `number` and value is an integer string | Reproduces the reported numeric SmartTable path | Stores a numeric value and validation passes | `TC-EP-429-001` |
| `SmartTableInvoiceInitializer.process` | `custom/process_key_temperature` is schema `number` and value is a decimal string | Confirms decimal number conversion | `invoice.json` stores a float and validation passes | `TC-EP-429-002` |
| `SmartTableInvoiceInitializer.process` | `custom/process_key_temperature` is schema `number` and value is not numeric | Confirms invalid numeric input fails early | Raises `StructuredError` with cast failure details | `TC-EP-429-005` |
| `SmartTableInvoiceInitializer.process` | `custom/process_key_temperature` is schema `integer` and value is a decimal string | Confirms integer-only schema rejects decimal text | Raises `StructuredError` with cast failure details | `TC-EP-429-006` |
| `SmartTableInvoiceInitializer.process` | `custom/enable_feature` is schema `boolean` and value is not a valid boolean string | Confirms boolean parsing fails early | Raises `StructuredError` with cast failure details | `TC-EP-429-007` |
| `SmartTableInvoiceInitializer.process` | SmartTable references a `custom/...` field missing from schema | Prevents silent string fallback when schema lookup fails | Raises `StructuredError` with schema lookup details | `TC-EP-429-008` |

Boundary Value:
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `SmartTableInvoiceInitializer.process` | `number` with `"30"` | Reported lower-complexity reproduction value | Stores `30` as a numeric value | `TC-BV-429-001` |
| `SmartTableInvoiceInitializer.process` | `number` with `"30.5"` | Decimal boundary for number conversion | Stores `30.5` as `float` | `TC-BV-429-002` |
| `SmartTableInvoiceInitializer.process` | `integer` with `"30.1"` | Decimal boundary rejected by integer schema | Raises `StructuredError` | `TC-BV-429-004` |
| `SmartTableInvoiceInitializer.process` | `boolean` with `"yes"` | Non-supported truthy text boundary | Raises `StructuredError` | `TC-BV-429-006` |

Execution commands:
    python -m pytest tests/test_smarttable_invoice_initializer_issue_429.py -q
    tox -e py312-module -- tests/test_smarttable_invoice_initializer_issue_429.py
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
from rdetoolkit.validation import invoice_validate


@pytest.fixture(autouse=True)
def reset_initializer_cache() -> Generator[None, None, None]:
    """Reset the SmartTable cache between tests."""
    SmartTableInvoiceInitializer.clear_base_invoice_cache()
    yield
    SmartTableInvoiceInitializer.clear_base_invoice_cache()


def _copy_issue_429_invoice_files(base_dir: Path) -> tuple[Path, Path]:
    """Copy sample invoice assets into an isolated work area."""
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
    """Create a single SmartTable row CSV file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=row.keys())
        writer.writeheader()
        writer.writerow(row)


def _update_custom_schema_field(
    schema_path: Path,
    *,
    field_name: str,
    field_schema: dict[str, object] | None,
) -> None:
    """Insert or remove a custom field in the sample invoice schema."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    custom_properties = schema["properties"]["custom"]["properties"]

    custom_properties.pop(field_name, None)
    if field_schema is not None:
        custom_properties[field_name] = field_schema

    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_context(
    tmp_path: Path,
    *,
    row: dict[str, str],
    field_name: str,
    field_schema: dict[str, object] | None,
) -> tuple[ProcessingContext, Path]:
    """Create a SmartTable processing context for issue 429 tests."""
    invoice_org, schema_path = _copy_issue_429_invoice_files(tmp_path)
    _update_custom_schema_field(
        schema_path,
        field_name=field_name,
        field_schema=field_schema,
    )

    rowfile = tmp_path / "temp" / "fsmarttable_issue_429_0000.csv"
    _write_smarttable_row(rowfile, row)

    smarttable_file = tmp_path / "inputdata" / "smarttable_issue_429.xlsx"
    smarttable_file.parent.mkdir(parents=True, exist_ok=True)
    smarttable_file.touch()

    resource_paths = RdeOutputResourcePath(
        raw=tmp_path / "raw",
        nonshared_raw=tmp_path / "nonshared_raw",
        rawfiles=(rowfile,),
        struct=tmp_path / "structured",
        main_image=tmp_path / "main_image",
        other_image=tmp_path / "other_image",
        meta=tmp_path / "meta",
        thumbnail=tmp_path / "thumbnail",
        logs=tmp_path / "logs",
        invoice=invoice_org.parent,
        invoice_schema_json=schema_path,
        invoice_org=invoice_org,
        smarttable_rowfile=rowfile,
        temp=tmp_path / "temp",
        invoice_patch=tmp_path / "invoice_patch",
        attachment=tmp_path / "attachment",
    )

    srcpaths = RdeInputDirPaths(
        inputdata=smarttable_file.parent,
        invoice=invoice_org.parent,
        tasksupport=schema_path.parent,
        config=create_default_config(),
    )

    context = ProcessingContext(
        index="0000",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=smarttable_file,
    )
    return context, context.invoice_dst_filepath


def test_smarttable_number_string_is_cast_to_number_and_validates__tc_ep_429_001(
    tmp_path: Path,
) -> None:
    """TC-EP-429-001: Integer-like number strings are stored as numeric values."""
    # Given: a schema-defined SmartTable number field with integer text
    context, invoice_path = _build_context(
        tmp_path,
        row={"custom/process_key_temperature": "30"},
        field_name="process_key_temperature",
        field_schema={
            "label": {"ja": "温度", "en": "Temperature"},
            "type": "number",
        },
    )

    # When: processing the SmartTable row
    SmartTableInvoiceInitializer().process(context)

    # Then: the stored invoice value is numeric and schema validation passes
    invoice_data = json.loads(invoice_path.read_text(encoding="utf-8"))
    assert invoice_data["custom"]["process_key_temperature"] == 30
    assert isinstance(invoice_data["custom"]["process_key_temperature"], int)
    invoice_validate(invoice_path, context.schema_path)


def test_smarttable_decimal_string_is_cast_to_float_and_validates__tc_ep_429_002(
    tmp_path: Path,
) -> None:
    """TC-EP-429-002: Decimal number strings are stored as floats."""
    # Given: a schema-defined SmartTable number field with decimal text
    context, invoice_path = _build_context(
        tmp_path,
        row={"custom/process_key_temperature": "30.5"},
        field_name="process_key_temperature",
        field_schema={
            "label": {"ja": "温度", "en": "Temperature"},
            "type": "number",
        },
    )

    # When: processing the SmartTable row
    SmartTableInvoiceInitializer().process(context)

    # Then: the stored invoice value is float and schema validation passes
    invoice_data = json.loads(invoice_path.read_text(encoding="utf-8"))
    assert invoice_data["custom"]["process_key_temperature"] == 30.5
    assert isinstance(invoice_data["custom"]["process_key_temperature"], float)
    invoice_validate(invoice_path, context.schema_path)


def test_smarttable_invalid_number_string_fails_early__tc_ep_429_005(
    tmp_path: Path,
) -> None:
    """TC-EP-429-005: Non-numeric text for a number field raises StructuredError."""
    # Given: a schema-defined SmartTable number field with invalid numeric text
    context, _ = _build_context(
        tmp_path,
        row={"custom/process_key_temperature": "abc"},
        field_name="process_key_temperature",
        field_schema={
            "label": {"ja": "温度", "en": "Temperature"},
            "type": "number",
        },
    )

    # When/Then: processing fails before invoice validation
    with pytest.raises(
        StructuredError,
        match=(
            "Value for invoice.json field 'custom.process_key_temperature' "
            "does not match the type defined in invoice.schema.json "
            "\\(expected: number\\)\\."
        ),
    ):
        SmartTableInvoiceInitializer().process(context)


def test_smarttable_decimal_string_rejected_by_integer_schema__tc_ep_429_006(
    tmp_path: Path,
) -> None:
    """TC-EP-429-006: Decimal text cannot be stored in an integer field."""
    # Given: a schema-defined SmartTable integer field with decimal text
    context, _ = _build_context(
        tmp_path,
        row={"custom/process_key_temperature": "30.1"},
        field_name="process_key_temperature",
        field_schema={
            "label": {"ja": "温度", "en": "Temperature"},
            "type": "integer",
        },
    )

    # When/Then: processing fails before invoice validation
    with pytest.raises(
        StructuredError,
        match=(
            "Value for invoice.json field 'custom.process_key_temperature' "
            "does not match the type defined in invoice.schema.json "
            "\\(expected: integer\\)\\."
        ),
    ):
        SmartTableInvoiceInitializer().process(context)


def test_smarttable_invalid_boolean_string_fails_early__tc_ep_429_007(
    tmp_path: Path,
) -> None:
    """TC-EP-429-007: Unsupported boolean text raises StructuredError."""
    # Given: a schema-defined SmartTable boolean field with unsupported text
    context, _ = _build_context(
        tmp_path,
        row={"custom/enable_feature": "yes"},
        field_name="enable_feature",
        field_schema={
            "label": {"ja": "有効化", "en": "Enable feature"},
            "type": "boolean",
        },
    )

    # When/Then: processing fails before invoice validation
    with pytest.raises(
        StructuredError,
        match=(
            "Value for invoice.json field 'custom.enable_feature' "
            "does not match the type defined in invoice.schema.json "
            "\\(expected: boolean\\)\\."
        ),
    ):
        SmartTableInvoiceInitializer().process(context)


def test_smarttable_missing_custom_schema_field_fails_early__tc_ep_429_008(
    tmp_path: Path,
) -> None:
    """TC-EP-429-008: Missing custom schema fields no longer fall back to strings."""
    # Given: a SmartTable custom field that does not exist in invoice.schema.json
    context, _ = _build_context(
        tmp_path,
        row={"custom/process_key_temperature": "30"},
        field_name="process_key_temperature",
        field_schema=None,
    )

    # When/Then: processing fails with a schema lookup error
    with pytest.raises(
        StructuredError,
        match="Field 'custom.process_key_temperature' is not defined in invoice.schema.json\\.",
    ):
        SmartTableInvoiceInitializer().process(context)
