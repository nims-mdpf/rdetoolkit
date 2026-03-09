"""Property tests for SmartTable custom type casting (issue 429).

Equivalence Partitioning:
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `SmartTableInvoiceInitializer.process` | Schema `number` with generated valid numeric strings | Verifies robust handling across numeric text variations | Generated values stay numeric and validation passes | `TC-EP-429-009` |
| `SmartTableInvoiceInitializer.process` | Schema `number` with generated invalid numeric strings | Verifies invalid numeric text is rejected before schema validation | Raises `StructuredError` | `TC-EP-429-010` |
| `SmartTableInvoiceInitializer.process` | Schema `boolean` with generated valid boolean strings | Verifies robust boolean parsing for SmartTable text values | Generated invoice values are always booleans and validation passes | `TC-EP-429-011` |
| `SmartTableInvoiceInitializer.process` | Schema `boolean` with generated invalid boolean strings | Verifies unsupported boolean text is rejected early | Raises `StructuredError` | `TC-EP-429-012` |

Boundary Value:
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `SmartTableInvoiceInitializer.process` | Numeric strings around zero (`"-1"`, `"0"`, `"1"`, `"0.0"`) | Low-magnitude values previously at risk of string leakage | Always stored as numeric values | `TC-BV-429-008` |
| `SmartTableInvoiceInitializer.process` | Boolean case variants (`"TRUE"`, `"FALSE"`, `"true"`, `"false"`) | Excel/user input case differences | Always stored as booleans | `TC-BV-429-009` |

Execution commands:
    python -m pytest tests/property/test_smarttable_invoice_initializer_issue_429.py -q
    tox -e py312-module -- tests/property/test_smarttable_invoice_initializer_issue_429.py
"""

from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path
import tempfile

import pytest
import pandas as pd

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.rde2types import (
    RdeInputDirPaths,
    RdeOutputResourcePath,
    create_default_config,
)
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer
from rdetoolkit.validation import invoice_validate
from tests.property.strategies import finite_floats

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
    field_schema: dict[str, object],
) -> None:
    """Insert a custom field into the sample invoice schema."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["custom"]["properties"][field_name] = field_schema
    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_context(
    tmp_path: Path,
    *,
    row: dict[str, str],
    field_name: str,
    field_schema: dict[str, object],
) -> tuple[ProcessingContext, Path]:
    """Create a SmartTable processing context for property tests."""
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


@st.composite
def valid_number_strings(draw: st.DrawFn) -> str:
    """Generate SmartTable-compatible numeric strings."""
    return draw(
        st.one_of(
            st.integers(min_value=-(10**6), max_value=10**6).map(str),
            finite_floats.map(repr),
        ),
    )


def _is_invalid_number_string(value: str) -> bool:
    """Return True when the given text cannot be parsed as int or float."""
    if value[:1] in "+-.0123456789":
        return False
    try:
        int(value)
    except ValueError:
        try:
            float(value)
        except ValueError:
            return True
    return False


def _is_csv_missing_string(value: str) -> bool:
    """Return True when the SmartTable CSV loader normalizes the text to missing."""
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["value"])
    writer.writeheader()
    writer.writerow({"value": value})
    csv_buffer.seek(0)

    parsed = pd.read_csv(csv_buffer, dtype=str).iloc[0, 0]
    return bool(pd.isna(parsed) or parsed == "")


def _is_invalid_boolean_string(value: str) -> bool:
    """Return True when the given text is not a supported boolean token."""
    return value.strip().lower() not in {"true", "false"}


invalid_number_strings = st.text(min_size=1, max_size=20).filter(
    lambda value: _is_invalid_number_string(value) and not _is_csv_missing_string(value),
)
invalid_boolean_strings = st.text(min_size=1, max_size=20).filter(
    lambda value: _is_invalid_boolean_string(value) and not _is_csv_missing_string(value),
)


@pytest.mark.property
@settings(max_examples=30, deadline=None)
@given(raw_value=valid_number_strings())
def test_smarttable_number_property_preserves_numeric_type__tc_ep_429_009(
    raw_value: str,
) -> None:
    """TC-EP-429-009: Valid numeric strings are always stored as numbers."""
    # Given: a schema-defined SmartTable number field with generated numeric text
    with tempfile.TemporaryDirectory() as temp_dir:
        SmartTableInvoiceInitializer.clear_base_invoice_cache()
        context, invoice_path = _build_context(
            Path(temp_dir),
            row={"custom/process_key_temperature": raw_value},
            field_name="process_key_temperature",
            field_schema={
                "label": {"ja": "温度", "en": "Temperature"},
                "type": "number",
            },
        )

        # When: processing the SmartTable row
        SmartTableInvoiceInitializer().process(context)

        # Then: the stored invoice value is always numeric and validation passes
        invoice_data = json.loads(invoice_path.read_text(encoding="utf-8"))
        assert isinstance(invoice_data["custom"]["process_key_temperature"], (int, float))
        invoice_validate(invoice_path, context.schema_path)


@pytest.mark.property
@settings(max_examples=30, deadline=None)
@given(raw_value=invalid_number_strings)
def test_smarttable_number_property_rejects_invalid_strings__tc_ep_429_010(
    raw_value: str,
) -> None:
    """TC-EP-429-010: Invalid numeric strings are rejected before validation."""
    # Given: a schema-defined SmartTable number field with generated invalid text
    with tempfile.TemporaryDirectory() as temp_dir:
        SmartTableInvoiceInitializer.clear_base_invoice_cache()
        context, _ = _build_context(
            Path(temp_dir),
            row={"custom/process_key_temperature": raw_value},
            field_name="process_key_temperature",
            field_schema={
                "label": {"ja": "温度", "en": "Temperature"},
                "type": "number",
            },
        )

        # When/Then: processing fails with a cast error
        with pytest.raises(
            StructuredError,
            match=(
                "Value for invoice.json field 'custom.process_key_temperature' "
                "does not match the type defined in invoice.schema.json "
                "\\(expected: number\\)\\."
            ),
        ):
            SmartTableInvoiceInitializer().process(context)


@pytest.mark.property
@settings(max_examples=20, deadline=None)
@given(raw_value=st.sampled_from(["TRUE", "FALSE", "true", "false"]))
def test_smarttable_boolean_property_preserves_boolean_type__tc_ep_429_011(
    raw_value: str,
) -> None:
    """TC-EP-429-011: Valid boolean strings are always stored as booleans."""
    # Given: a schema-defined SmartTable boolean field with supported text
    with tempfile.TemporaryDirectory() as temp_dir:
        SmartTableInvoiceInitializer.clear_base_invoice_cache()
        context, invoice_path = _build_context(
            Path(temp_dir),
            row={"custom/enable_feature": raw_value},
            field_name="enable_feature",
            field_schema={
                "label": {"ja": "有効化", "en": "Enable feature"},
                "type": "boolean",
            },
        )

        # When: processing the SmartTable row
        SmartTableInvoiceInitializer().process(context)

        # Then: the stored invoice value is always boolean and validation passes
        invoice_data = json.loads(invoice_path.read_text(encoding="utf-8"))
        assert isinstance(invoice_data["custom"]["enable_feature"], bool)
        invoice_validate(invoice_path, context.schema_path)


@pytest.mark.property
@settings(max_examples=20, deadline=None)
@given(raw_value=invalid_boolean_strings)
def test_smarttable_boolean_property_rejects_invalid_strings__tc_ep_429_012(
    raw_value: str,
) -> None:
    """TC-EP-429-012: Invalid boolean strings are rejected before validation."""
    # Given: a schema-defined SmartTable boolean field with unsupported text
    with tempfile.TemporaryDirectory() as temp_dir:
        SmartTableInvoiceInitializer.clear_base_invoice_cache()
        context, _ = _build_context(
            Path(temp_dir),
            row={"custom/enable_feature": raw_value},
            field_name="enable_feature",
            field_schema={
                "label": {"ja": "有効化", "en": "Enable feature"},
                "type": "boolean",
            },
        )

        # When/Then: processing fails with a boolean parse error
        with pytest.raises(
            StructuredError,
            match=(
                "Value for invoice.json field 'custom.enable_feature' "
                "does not match the type defined in invoice.schema.json "
                "\\(expected: boolean\\)\\."
            ),
        ):
            SmartTableInvoiceInitializer().process(context)
