"""Permanent compatibility checks for the v1 Tier 1 public surface.

Equivalence partitions prepared before implementation:

| API family | Partition | Expected | Test IDs |
| --- | --- | --- | --- |
| package/module exports | maintained public imports | imports resolve | TC-H4-TIER1-001..003 |
| JSON/metadata utilities | valid UTF-8 data | round trip and metadata write | TC-H4-TIER1-004..006 |
| errors/logger | success and raised exception | v1 types and file formats persist | TC-H4-TIER1-007..009 |
| models/path types | minimal valid values | instances are constructible | TC-H4-TIER1-010..011 |
| invoice utilities | minimal valid invoice and workbook | helpers perform their public operation | TC-H4-TIER1-012..014 |
| validators/images | valid documents and invalid image size | validate or raise the documented type | TC-H4-TIER1-015..016 |

Boundary values prepared before implementation:

| API family | Boundary | Expected | Test IDs |
| --- | --- | --- | --- |
| metadata | one constant, zero variable rows | one value is serialized | TC-H4-TIER1-005 |
| path models | empty raw-file tuple and optional paths | construction succeeds | TC-H4-TIER1-010 |
| error file | caller-selected filename | exact two-line v1 format | TC-H4-TIER1-008 |
| feature update | zero feature fields | invoice remains valid and unchanged | TC-H4-TIER1-014 |
| thumbnail | width zero | ``StructuredError`` propagates | TC-H4-TIER1-016 |

``write_job_errorlog_file`` is intentionally pinned from ``rdetoolkit.errors``.
The original H4 survey incorrectly attributed it to ``rdelogger``; the corrected
surface preserves the existing API instead of inventing a new re-export.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import pytest

import rdetoolkit
from rdetoolkit import img2thumb, rde2util
from rdetoolkit.core import detect_encoding
from rdetoolkit.errors import (
    StructuredError as ErrorsStructuredError,
    catch_exception_with_message,
    handle_exception,
    write_job_errorlog_file,
)
from rdetoolkit.exceptions import (
    InvoiceSchemaValidationError,
    MetadataValidationError,
    StructuredError,
)
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.invoicefile import (
    ExcelInvoiceFile,
    InvoiceFile,
    apply_magic_variable,
    backup_invoice_json_files,
    check_exist_rawfiles,
    overwrite_invoicefile_for_dpfterm,
    read_excelinvoice,
    update_description_with_features,
)
from rdetoolkit.models.config import Config, SystemSettings
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson, Properties
from rdetoolkit.models.metadata import MetadataItem
from rdetoolkit.models.rde2types import (
    MetaType,
    RdeDatasetPaths,
    RdeInputDirPaths,
    RdeOutputResourcePath,
    RepeatedMetaType,
)
from rdetoolkit.rde2util import (
    CharDecEncoding,
    Meta,
    StorageDir,
    castval,
    read_from_json_file,
    write_to_json_file,
)
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.validation import invoice_validate, metadata_validate


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _output_paths(root: Path) -> RdeOutputResourcePath:
    paths = {name: root / name for name in (
        "raw",
        "nonshared_raw",
        "structured",
        "main_image",
        "other_image",
        "meta",
        "thumbnail",
        "logs",
        "invoice",
        "temp",
    )}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return RdeOutputResourcePath(
        raw=paths["raw"],
        nonshared_raw=paths["nonshared_raw"],
        rawfiles=(),
        struct=paths["structured"],
        main_image=paths["main_image"],
        other_image=paths["other_image"],
        meta=paths["meta"],
        thumbnail=paths["thumbnail"],
        logs=paths["logs"],
        invoice=paths["invoice"],
        invoice_schema_json=root / "invoice.schema.json",
        invoice_org=root / "invoice_org.json",
        temp=paths["temp"],
    )


def test_package_and_module_exports__tc_h4_tier1_001() -> None:
    """TC-H4-TIER1-001: package, version, and rde2util imports remain public."""
    # Given: the imports used by maintained structured programs
    # When: resolving the top-level version and module export
    exports = (rdetoolkit.__version__, rdetoolkit.rde2util, rde2util)
    # Then: the version is populated and both module paths resolve identically
    assert exports[0]
    assert exports[1] is exports[2]


def test_core_detect_encoding_reexport__tc_h4_tier1_002(tmp_path: Path) -> None:
    """TC-H4-TIER1-002: Phase K must retain ``rdetoolkit.core.detect_encoding``."""
    # Given: a real UTF-8 file and the exact canary import path from Plan §9.1-b
    source = tmp_path / "日本語.txt"
    source.write_text("互換性", encoding="utf-8")
    # When: detecting through the compatibility re-export in rdetoolkit.core
    encoding = detect_encoding(str(source))
    # Then: the public path returns the file's encoding
    assert encoding.lower().replace("-", "_") == "utf_8"


def test_imported_tier1_symbols_are_the_expected_kinds__tc_h4_tier1_003() -> None:
    """TC-H4-TIER1-003: all maintained Tier 1 symbols resolve from public modules."""
    # Given: the complete H4 Tier 1 import inventory
    callables = (
        CharDecEncoding,
        StorageDir,
        castval,
        read_from_json_file,
        write_to_json_file,
        InvoiceFile,
        ExcelInvoiceFile,
        apply_magic_variable,
        update_description_with_features,
        read_excelinvoice,
        check_exist_rawfiles,
        backup_invoice_json_files,
        overwrite_invoicefile_for_dpfterm,
        invoice_validate,
        metadata_validate,
        get_logger,
        InvoiceSchemaJson,
        MetadataItem,
        img2thumb.resize_image,
    )
    # When: checking their runtime import results
    # Then: every maintained symbol is callable from its public path
    assert all(callable(symbol) for symbol in callables)


def test_fileops_json_round_trip__tc_h4_tier1_004(tmp_path: Path) -> None:
    """TC-H4-TIER1-004: fileops read and write JSON without changing values."""
    # Given: a Unicode JSON payload
    path = tmp_path / "payload.json"
    payload = {"name": "測定", "count": 1}
    # When: writing and reading through the public helpers
    returned = writef_json(path, payload)
    observed = readf_json(path)
    # Then: both helpers preserve the payload
    assert returned == payload
    assert observed == payload


def test_meta_writes_constant_metadata__tc_h4_tier1_005(tmp_path: Path) -> None:
    """TC-H4-TIER1-005: Meta assigns and writes real metadata content."""
    # Given: a one-field metadata definition and a Meta instance
    definition = tmp_path / "metadata-def.json"
    output = tmp_path / "metadata.json"
    _write_json(definition, {"temperature": {"name": {"ja": "温度", "en": "Temperature"}, "schema": {"type": "number"}}})
    metadata = Meta(definition)
    # When: assigning and serializing one constant value
    assignment = metadata.assign_vals({"temperature": "20.5"})
    metadata.writefile(str(output))
    # Then: the value is recorded as numeric metadata
    assert assignment["assigned"] == {"temperature"}
    assert readf_json(output)["constant"]["temperature"]["value"] == 20.5


def test_deprecated_rde2util_json_and_cast_helpers__tc_h4_tier1_006(tmp_path: Path) -> None:
    """TC-H4-TIER1-006: legacy rde2util helpers keep their minimal behavior."""
    # Given: an output path and a JSON value
    path = tmp_path / "legacy.json"
    payload = {"enabled": True}
    # When: using the maintained deprecated JSON helpers and scalar caster
    with pytest.warns(DeprecationWarning):
        write_to_json_file(path, payload)
    with pytest.warns(DeprecationWarning):
        observed = read_from_json_file(path)
    # Then: JSON and scalar conversion remain compatible
    assert observed == payload
    assert castval("7", "integer", None) == 7


def test_storage_dir_and_character_detection__tc_h4_tier1_007(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-H4-TIER1-007: StorageDir and CharDecEncoding operate on real paths."""
    # Given: a clean working directory and a UTF-8 text file
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "text.txt"
    source.write_text("日本語", encoding="utf-8")
    # When: creating the data directory and detecting the text encoding
    with pytest.warns(DeprecationWarning):
        data_dir = StorageDir.get_datadir(True)
    encoding = CharDecEncoding.detect_text_file_encoding(source)
    # Then: both legacy helpers return usable results
    assert Path(data_dir).is_dir()
    assert encoding == "utf_8"


def test_errors_surface_and_decorator__tc_h4_tier1_008() -> None:
    """TC-H4-TIER1-008: errors exports the exception, decorator, and converter."""
    # Given: the exception alias and a decorated failing function
    @catch_exception_with_message(error_message="converted", error_code=42)
    def fail() -> None:
        message = "source"
        raise ValueError(message)

    # When: the decorated function fails
    with pytest.raises(StructuredError) as captured:
        fail()
    converted = handle_exception(ValueError("plain"), error_code=43)
    # Then: both paths yield the canonical StructuredError class and codes
    assert ErrorsStructuredError is StructuredError
    assert captured.value.ecode == 42
    assert isinstance(converted, StructuredError)
    assert converted.ecode == 43


def test_errors_write_job_file_corrected_binding__tc_h4_tier1_009(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-H4-TIER1-009: corrected errors binding writes the v1 job-failure format."""
    # Given: a caller-selected filename under an isolated data root
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    # When: writing through rdetoolkit.errors.write_job_errorlog_file
    with pytest.warns(DeprecationWarning):
        write_job_errorlog_file(404, "Not Found", filename="custom.failed")
    # Then: the exact two-line v1 format is retained
    assert (tmp_path / "data" / "custom.failed").read_text(encoding="utf-8") == (
        "ErrorCode=404\nErrorMessage=Not Found\n"
    )


def test_config_and_rde2_path_types_construct__tc_h4_tier1_010(tmp_path: Path) -> None:
    """TC-H4-TIER1-010: config and callback path types remain constructible."""
    # Given: minimal config, legacy aliases, and empty output resources
    config = Config(system=SystemSettings(extended_mode=None))
    meta: MetaType = {"count": 1}
    repeated: RepeatedMetaType = {"count": [1, 2]}
    inputs = RdeInputDirPaths(tmp_path / "input", tmp_path / "invoice", tmp_path / "tasksupport", config)
    outputs = _output_paths(tmp_path / "out")
    dataset = RdeDatasetPaths(inputs, outputs)
    # When: reading their public attributes
    # Then: aliases hold values and path models preserve constructor arguments
    assert meta == {"count": 1}
    assert repeated == {"count": [1, 2]}
    assert inputs.config is config
    assert outputs.rawfiles == ()
    assert dataset.inputdata == inputs.inputdata


def test_schema_metadata_and_validation_exceptions__tc_h4_tier1_011() -> None:
    """TC-H4-TIER1-011: public Pydantic models and validation errors construct."""
    # Given: minimal valid schema and metadata values
    schema = InvoiceSchemaJson(properties=Properties())
    metadata = MetadataItem(constant={}, variable=[])
    # When: constructing the two documented validation exception types
    exceptions = (InvoiceSchemaValidationError("invoice"), MetadataValidationError("metadata"))
    # Then: models serialize and exceptions retain their messages
    assert schema.model_dump(by_alias=True)["type"] == "object"
    assert metadata.model_dump() == {"constant": {}, "variable": []}
    assert [str(error) for error in exceptions] == ["invoice", "metadata"]


def test_logger_writes_to_requested_file__tc_h4_tier1_012(tmp_path: Path) -> None:
    """TC-H4-TIER1-012: get_logger writes through its requested file handler."""
    # Given: a unique public logger and destination
    destination = tmp_path / "logs" / "compat.log"
    logger = get_logger("rdetoolkit.compat.h4", file_path=destination, level=logging.INFO)
    # When: emitting a message
    logger.info("tier1")
    for handler in logger.handlers:
        handler.flush()
    # Then: the configured destination contains it
    assert "tier1" in destination.read_text(encoding="utf-8")


def test_invoice_classes_and_sheet_helpers__tc_h4_tier1_013(tmp_path: Path) -> None:
    """TC-H4-TIER1-013: invoice classes and Excel helpers perform minimal reads."""
    # Given: a JSON invoice, a generated ExcelInvoice fixture, and its raw file
    invoice_path = tmp_path / "invoice.json"
    _write_json(invoice_path, {"basic": {"dataName": "name"}, "custom": {}})
    workbook = Path(__file__).parents[1] / "contract" / "fixtures" / "inputs" / "excelinvoice" / "data" / "inputdata" / "excelinvoice_multi.xlsx"
    invoice = InvoiceFile(invoice_path)
    excel = ExcelInvoiceFile(workbook)
    raw = tmp_path / "sample.dat"
    raw.touch()
    # When: reading through the class and deprecated wrapper and ordering raw files
    with pytest.warns(DeprecationWarning):
        wrapped, _, _ = read_excelinvoice(workbook)
    ordered = check_exist_rawfiles(pd.DataFrame({"data_file_names/name": [raw.name]}), [raw])
    # Then: the public helpers expose the same usable content
    assert invoice["basic"]["dataName"] == "name"
    assert wrapped.equals(excel.dfexcelinvoice)
    assert ordered == [raw]


def test_invoice_mutation_helpers__tc_h4_tier1_014(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-H4-TIER1-014: maintained invoice mutation helpers update real files."""
    # Given: minimal invoice/schema files and output resources
    invoice_path = tmp_path / "invoice.json"
    schema_path = tmp_path / "invoice.schema.json"
    raw_path = tmp_path / "sample.dat"
    _write_json(invoice_path, {"basic": {"dataName": "${filename}", "description": ""}, "custom": {"value": ""}})
    _write_json(schema_path, {"properties": {"custom": {"properties": {"value": {"type": "string"}}}}})
    raw_path.touch()
    # When: applying DPF values and a filename magic variable
    overwrite_invoicefile_for_dpfterm(readf_json(invoice_path), invoice_path, schema_path, {"value": "updated"})
    expanded = apply_magic_variable(invoice_path, raw_path)
    # Then: both public mutations are persisted
    assert expanded["basic"]["dataName"] == "sample.dat"
    assert readf_json(invoice_path)["custom"]["value"] == "updated"

    # Given: the legacy data/invoice layout and a zero-feature metadata definition
    monkeypatch.chdir(tmp_path)
    data_invoice = tmp_path / "data" / "invoice" / "invoice.json"
    _write_json(data_invoice, readf_json(invoice_path))
    with pytest.warns(DeprecationWarning):
        backup = backup_invoice_json_files(None, None)
    resources = _output_paths(tmp_path / "resources")
    _write_json(resources.invoice_schema_json, schema_path.read_text(encoding="utf-8") and readf_json(schema_path))
    _write_json(resources.meta / "metadata.json", {"constant": {}, "variable": []})
    metadata_def = tmp_path / "metadata-def.json"
    _write_json(metadata_def, {})
    # When: updating a description with no feature entries
    update_description_with_features(resources, data_invoice, metadata_def)
    # Then: backup lookup and no-feature update remain safe
    assert backup == Path("data/invoice/invoice.json")
    assert readf_json(data_invoice)["basic"]["description"] == ""


def test_validation_helpers_accept_minimal_documents__tc_h4_tier1_015(tmp_path: Path) -> None:
    """TC-H4-TIER1-015: invoice and metadata validators accept valid documents."""
    # Given: minimal documents satisfying their public schemas
    invoice = tmp_path / "invoice.json"
    schema = tmp_path / "invoice.schema.json"
    metadata = tmp_path / "metadata.json"
    _write_json(
        invoice,
        {
            "datasetId": "dataset",
            "basic": {
                "dateSubmitted": "2026-08-24",
                "dataOwnerId": "0" * 56,
                "dataName": "compat",
            },
        },
    )
    _write_json(schema, {"type": "object", "properties": {}})
    _write_json(metadata, {"constant": {}, "variable": []})
    # When: validating through the compatibility module
    invoice_validate(invoice, schema)
    metadata_validate(metadata)
    # Then: both calls complete without raising


def test_img2thumb_raises_structured_error_at_zero_width__tc_h4_tier1_016(tmp_path: Path) -> None:
    """TC-H4-TIER1-016: img2thumb retains its invalid-dimension error contract."""
    # Given: the smallest invalid width boundary
    source = tmp_path / "image.png"
    # When: attempting a zero-width resize
    with pytest.raises(StructuredError):
        img2thumb.resize_image(source, width=0)
    # Then: the public helper raises the maintained structured exception
