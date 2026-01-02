"""Magic variable test design.

Equivalence Partitioning
========================

| API                   | Input/State Partition                                  | Rationale                                         | Expected Outcome                                        | Test ID        |
| --------------------- | ------------------------------------------------------ | ------------------------------------------------- | ------------------------------------------------------- | -------------- |
| `apply_magic_variable` | Valid mix of filename/invoice/metadata/sample values   | Happy path covers all supported sources           | Combined name built from each magic source              | `TC-EP-001`    |
| `apply_magic_variable` | Optional invoice field provided as empty string        | Verify skip + warning without `__` artifacts      | Placeholder removed, warning logged, string intact      | `TC-EP-002`    |
| `apply_magic_variable` | Metadata constant key missing                          | Error path when constant lookup fails             | Raise `StructuredError` referencing missing constant    | `TC-EP-003`    |
| `apply_magic_variable` | Invoice custom field missing                           | Error path when invoice field absent              | Raise `StructuredError` referencing missing field       | `TC-EP-004`    |
| `apply_magic_variable` | Sample names array empty                               | Edge case dedicated by requirements               | Raise `StructuredError` for empty names                 | `TC-EP-005`    |
| `apply_magic_variable` | Metadata file missing                                  | Failure on unavailable metadata.json              | Raise `StructuredError` mentioning metadata requirement | `TC-EP-006`    |
| `apply_magic_variable` | Template without any magic variables                   | No substitution required                          | Return empty dict without touching dataName             | `TC-EP-007`    |
| `apply_magic_variable` | Unsupported sample field requested                     | Guardrail for unsupported pattern                 | Raise `StructuredError` about unsupported field         | `TC-EP-008`    |
| `apply_magic_variable` | Unsupported metadata scope (`variable`)                | Guardrail for disallowed metadata partitions      | Raise `StructuredError` about unsupported metadata use  | `TC-EP-009`    |

Boundary Values
===============

| API                   | Boundary                                 | Rationale                                    | Expected Outcome                                             | Test ID     |
| --------------------- | ---------------------------------------- | -------------------------------------------- | ------------------------------------------------------------ | ----------- |
| `apply_magic_variable` | `sample.names = ['alpha', '', 'beta']`   | Ensure blank entries do not create double `_` | Joined string `alpha_beta`; tied to `TC-EP-001`              | `TC-BV-001` |
| `apply_magic_variable` | `sample.names = []`                      | Empty array should raise per requirements     | `StructuredError` raised; tied to `TC-EP-005`                | `TC-BV-002` |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.invoicefile import apply_magic_variable
from rdetoolkit.models.rde2types import RdeDatasetPaths, RdeInputDirPaths, RdeOutputResourcePath


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _create_dataset(
    tmp_path: Path,
    *,
    data_name_template: str,
    custom: dict | None = None,
    sample_names: list[str] | None = None,
    metadata: dict | None = None,
) -> tuple[Path, Path, RdeDatasetPaths]:
    base_dir = tmp_path / "dataset"
    invoice_dir = base_dir / "invoice"
    invoice_path = invoice_dir / "invoice.json"
    invoice_org_path = base_dir / "invoice_org" / "invoice.json"
    meta_dir = base_dir / "meta"
    meta_file_path = meta_dir / "metadata.json"
    raw_dir = base_dir / "raw"
    raw_file_path = raw_dir / "input.txt"

    invoice_payload = {
        "datasetId": "DS-001",
        "basic": {
            "dataName": data_name_template,
            "experimentId": "EXP-42",
            "dateSubmitted": "2024-01-01",
            "description": "desc",
        },
        "custom": custom or {},
        "sample": {
            "names": sample_names or [],
            "composition": None,
            "referenceUrl": None,
            "description": None,
        },
    }
    _write_json(invoice_path, invoice_payload)
    _write_json(invoice_org_path, invoice_payload)

    if metadata is not None:
        _write_json(meta_file_path, metadata)
    else:
        meta_dir.mkdir(parents=True, exist_ok=True)

    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file_path.write_text("", encoding="utf-8")

    other_dirs = ["inputdata", "tasksupport", "nonshared_raw", "structured", "main_image", "other_image", "thumbnail", "logs"]
    for dirname in other_dirs:
        (base_dir / dirname).mkdir(parents=True, exist_ok=True)

    srcpaths = RdeInputDirPaths(
        inputdata=base_dir / "inputdata",
        invoice=invoice_dir,
        tasksupport=base_dir / "tasksupport",
    )

    output_paths = RdeOutputResourcePath(
        raw=raw_dir,
        nonshared_raw=base_dir / "nonshared_raw",
        rawfiles=(raw_file_path,),
        struct=base_dir / "structured",
        main_image=base_dir / "main_image",
        other_image=base_dir / "other_image",
        meta=meta_dir,
        thumbnail=base_dir / "thumbnail",
        logs=base_dir / "logs",
        invoice=invoice_dir,
        invoice_schema_json=base_dir / "tasksupport" / "invoice.schema.json",
        invoice_org=invoice_org_path,
    )

    dataset_paths = RdeDatasetPaths(srcpaths, output_paths)
    return invoice_path, raw_file_path, dataset_paths


def test_apply_magic_variable_combines_sources__tc_ep_001(tmp_path: Path) -> None:
    # Given: template referencing filename, invoice fields, metadata constant, and sample names
    metadata_payload = {"constant": {"project_code": {"value": "PRJ01"}}}
    custom_payload = {"batch": "B-9"}
    sample_names = ["alpha", "", "beta"]
    template = "${invoice:custom:batch}_${invoice:basic:experimentId}_${invoice:sample:names}_${metadata:constant:project_code}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom=custom_payload,
        sample_names=sample_names,
        metadata=metadata_payload,
    )

    # When: applying magic variables with all supported data sources
    result = apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)

    # Then: final name stitches together each resolved value
    assert result["basic"]["dataName"] == "B-9_EXP-42_alpha_beta_PRJ01_input.txt"


def test_apply_magic_variable_trims_blank_segments_and_logs_warning__tc_ep_002(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # Given: optional custom field rendered empty to trigger skip + warning
    template = "prefix_${invoice:custom:optional}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"optional": ""},
        sample_names=["only"],
        metadata={"constant": {}},
    )
    caplog.set_level("WARNING", logger="rdetoolkit.invoicefile")

    # When: applying magic variables where one value resolves to empty
    result = apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)

    # Then: underscores are not doubled and warning records the skipped placeholder
    assert result["basic"]["dataName"] == "prefix_input.txt"
    assert any("invoice:custom:optional" in rec.message for rec in caplog.records)


def test_apply_magic_variable_metadata_constant_missing__tc_ep_003(tmp_path: Path) -> None:
    # Given: metadata.json lacks the referenced constant key
    template = "${metadata:constant:missing}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"batch": "B-9"},
        sample_names=["s1"],
        metadata={"constant": {}},
    )

    # When/Then: resolving the constant raises a StructuredError with details
    with pytest.raises(StructuredError) as exc_info:
        apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)
    assert "metadata.constant['missing']" in str(exc_info.value)


def test_apply_magic_variable_missing_invoice_field__tc_ep_004(tmp_path: Path) -> None:
    # Given: template references a custom field that does not exist
    template = "${invoice:custom:not_there}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"other": "value"},
        sample_names=["s1"],
        metadata={"constant": {}},
    )

    # When/Then: processing fails with a StructuredError mentioning the missing field
    with pytest.raises(StructuredError) as exc_info:
        apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)
    assert "custom.not_there" in str(exc_info.value)


def test_apply_magic_variable_errors_on_empty_sample_names__tc_ep_005(tmp_path: Path) -> None:
    # Given: template requires sample.names but the array is empty
    template = "${invoice:sample:names}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"batch": "B-9"},
        sample_names=[],
        metadata={"constant": {}},
    )

    # When/Then: resolver raises an error describing the empty names constraint
    with pytest.raises(StructuredError) as exc_info:
        apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)
    assert "sample.names is empty" in str(exc_info.value)


def test_apply_magic_variable_requires_metadata_file_for_constant__tc_ep_006(tmp_path: Path) -> None:
    # Given: metadata.json is absent even though template references a constant
    template = "${metadata:constant:project_code}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"batch": "B-9"},
        sample_names=["s1"],
        metadata=None,
    )

    # When/Then: resolver fails fast because metadata.json is mandatory in this case
    with pytest.raises(StructuredError) as exc_info:
        apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)
    assert "metadata.json is required" in str(exc_info.value)


def test_apply_magic_variable_returns_empty_when_no_patterns__tc_ep_007(tmp_path: Path) -> None:
    # Given: dataName lacks any magic variable syntax
    template = "static_name"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"batch": "B-9"},
        sample_names=["s1"],
        metadata={"constant": {}},
    )

    # When: applying magic variables detects no placeholders
    result = apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)

    # Then: no mutation occurs and an empty dict is returned
    assert result == {}
    with invoice_path.open(encoding="utf-8") as handle:
        assert json.load(handle)["basic"]["dataName"] == "static_name"


def test_apply_magic_variable_rejects_unsupported_sample_field__tc_ep_008(tmp_path: Path) -> None:
    # Given: template references an unsupported sample attribute
    template = "${invoice:sample:ownerId}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"batch": "B-9"},
        sample_names=["s1"],
        metadata={"constant": {}},
    )

    # When/Then: resolver raises a StructuredError highlighting the unsupported field
    with pytest.raises(StructuredError) as exc_info:
        apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)
    assert "Unsupported sample field 'ownerId'" in str(exc_info.value)


def test_apply_magic_variable_rejects_metadata_variable_scope__tc_ep_009(tmp_path: Path) -> None:
    # Given: template references metadata.variable scope which must remain unsupported
    template = "${metadata:variable:dynamic}_${filename}"
    invoice_path, raw_file_path, dataset_paths = _create_dataset(
        tmp_path,
        data_name_template=template,
        custom={"batch": "B-9"},
        sample_names=["s1"],
        metadata={"constant": {}, "variable": []},
    )

    # When/Then: resolver raises a StructuredError about the unsupported metadata scope
    with pytest.raises(StructuredError) as exc_info:
        apply_magic_variable(invoice_path, raw_file_path, dataset_paths=dataset_paths)
    assert "Unsupported metadata field 'variable'" in str(exc_info.value)
