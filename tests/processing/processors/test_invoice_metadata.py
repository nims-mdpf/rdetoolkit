"""SmartTable metadata mapping tests."""

# Equivalence Partitioning Table
# | API                                 | Input/State Partition                               | Rationale                                   | Expected Outcome                                             | Test ID     |
# | ----------------------------------- | ---------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------- | ----------- |
# | `SmartTableInvoiceInitializer.process` | predefined meta column                               | verify it can write to metadata.json | converted values are written to metadata.json constant | `TC-EP-001` |
# | `SmartTableInvoiceInitializer.process` | existing metadata.json has the same key              | verify other fields are preserved on overwrite | only target key is overwritten; other keys and variable are preserved | `TC-EP-002` |
# | `SmartTableInvoiceInitializer.process` | metadata-def.json is missing                         | verify it is skipped for backward compatibility | metadata.json is not created and processing continues | `TC-EP-003` |
# | `SmartTableInvoiceInitializer.process` | meta value is empty/NaN                              | verify boundary behavior for invalid values | metadata.json is not created and the value is skipped | `TC-EP-004` |
# | `SmartTableInvoiceInitializer.process` | key not defined in metadata-def                       | schema mismatch negative case | `StructuredError` is raised | `TC-EP-005` |
# | `SmartTableInvoiceInitializer.process` | value cannot be converted                             | type validation negative case | `StructuredError` is raised | `TC-EP-006` |
# | `SmartTableInvoiceInitializer.process` | definition with `variable` flag                        | unsupported option negative case | `StructuredError` is raised | `TC-EP-007` |
# | `SmartTableInvoiceInitializer.process` | metadata-def is not an object                          | file format invalid case | `StructuredError` is raised | `TC-EP-008` |

# Boundary Value Table
# | API                                 | Boundary                          | Rationale                      | Expected Outcome                                   | Test ID     |
# | ----------------------------------- | --------------------------------- | ------------------------------ | --------------------------------------------------- | ----------- |
# | `SmartTableInvoiceInitializer.process` | minimum input boundary for empty/NaN value | verify lower bound for write condition | metadata.json is not created and the value is skipped | `TC-BV-001` |
# | `SmartTableInvoiceInitializer.process` | overwrite boundary for existing definition | verify retention behavior on overwrite | only target key is overwritten and other fields are preserved | `TC-BV-002` |

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer


def _write_metadata_def(context, payload: dict[str, dict[str, object]]) -> None:
    context.metadata_def_path.parent.mkdir(parents=True, exist_ok=True)
    with open(context.metadata_def_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def _write_smarttable_row(context, columns: list[str], values: list[str]) -> None:
    csv_path = context.resource_paths.rawfiles[0]
    dataframe = pd.DataFrame([values], columns=columns)
    dataframe.to_csv(csv_path, index=False)


def _remove_metadata_files(context) -> None:
    if context.metadata_path.exists():
        context.metadata_path.unlink()


def _read_metadata(context) -> dict[str, object]:
    with open(context.metadata_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_process_meta_columns_writes_metadata(smarttable_processing_context) -> None:
    """複数の meta 列が metadata.json に書き込まれることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: SmartTable row with metadata-def and meta column
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
            },
            "temperature": {
                "name": {"ja": "温度", "en": "Temperature"},
                "schema": {"type": "number"},
                "unit": "C",
            },
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "meta/temperature", "basic/dataName"],
        ["Smart memo", "42.5", "dataset"],
    )

    # When: processing the SmartTable row
    processor.process(context)

    # Then: recorded in metadata.json with type conversion and units
    metadata = _read_metadata(context)
    assert metadata["constant"]["comment"] == {"value": "Smart memo"}
    assert metadata["constant"]["temperature"] == {"value": 42.5, "unit": "C"}
    assert metadata["variable"] == []


def test_process_metadata_overwrites_existing_value(smarttable_processing_context) -> None:
    """既存 metadata.json の定義が上書きされることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: existing metadata.json and target meta column
    context.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(context.metadata_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "constant": {
                    "comment": {"value": "old", "unit": "note"},
                    "other": {"value": "preserve"},
                },
                "variable": [{"cycle": {"value": "A"}}],
            },
            handle,
        )
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
                "unit": "updated-unit",
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["new comment", "dataset"],
    )

    # When: processing the SmartTable row
    processor.process(context)

    # Then: only the target key is updated and other fields are preserved
    metadata = _read_metadata(context)
    assert metadata["constant"]["comment"] == {
        "value": "new comment",
        "unit": "updated-unit",
    }
    assert metadata["constant"]["other"] == {"value": "preserve"}
    assert metadata["variable"] == [{"cycle": {"value": "A"}}]


def test_process_metadata_def_missing_skips_without_error(smarttable_processing_context) -> None:
    """metadata-def.json が無い場合はスキップされることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: metadata-def missing with only meta column set
    _remove_metadata_files(context)
    if context.metadata_def_path.exists():
        context.metadata_def_path.unlink()
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["note", "dataset"],
    )

    # When: processing the SmartTable row
    processor.process(context)

    # Then: metadata.json is not created and processing completes
    assert not context.metadata_path.exists()


def test_process_metadata_skips_empty_values(smarttable_processing_context) -> None:
    """meta 値が空文字の場合は書き込みが行われないことを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: empty meta value with predefined metadata-def
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["", "dataset"],
    )

    # When: processing the SmartTable row
    processor.process(context)

    # Then: metadata.json is not created
    assert not context.metadata_path.exists()


def test_process_metadata_key_missing_definition_raises(smarttable_processing_context) -> None:
    """定義されていない meta キーはエラーとなることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: meta key not present in metadata-def
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/missing", "basic/dataName"],
        ["value", "dataset"],
    )

    # When/Then: StructuredError is raised for undefined key
    with pytest.raises(StructuredError, match="Metadata definition not found for key: missing"):
        processor.process(context)


def test_process_metadata_type_cast_failure_raises(smarttable_processing_context) -> None:
    """型変換できない値が指定された場合のエラーを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: non-numeric value for integer definition
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "count": {
                "name": {"ja": "回数", "en": "Count"},
                "schema": {"type": "integer"},
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/count", "basic/dataName"],
        ["invalid", "dataset"],
    )

    # When/Then: StructuredError is raised due to type conversion failure
    with pytest.raises(StructuredError, match="Failed to cast metadata value for key: count"):
        processor.process(context)


def test_process_metadata_variable_definition_raises(smarttable_processing_context) -> None:
    """variable 定義はサポート外であることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: metadata-def with variable flag
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
                "variable": 1,
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["note", "dataset"],
    )

    # When/Then: StructuredError is raised for variable definition
    with pytest.raises(StructuredError, match="Variable metadata is not supported for SmartTable meta mapping: comment"):
        processor.process(context)


def test_process_metadata_invalid_definition_format_raises(smarttable_processing_context) -> None:
    """metadata-def がオブジェクト以外の場合のエラーを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: metadata-def with a list at top level
    context.metadata_def_path.parent.mkdir(parents=True, exist_ok=True)
    with open(context.metadata_def_path, "w", encoding="utf-8") as handle:
        json.dump([{"comment": "invalid"}], handle)
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["note", "dataset"],
    )

    # When/Then: StructuredError is raised for invalid format
    with pytest.raises(StructuredError, match="metadata-def.json must contain an object at the top level"):
        processor.process(context)

