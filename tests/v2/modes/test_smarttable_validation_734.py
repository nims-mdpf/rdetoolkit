"""Acceptance cases for #705.

# SmartTable mapping preflight EP/BV table

| API | Partition / boundary | Expected | Test ID |
| --- | --- | --- | --- |
| validate | valid custom/meta/basic/sample/attribute mappings with rawless empty cells | no diagnostics, no writes | ST734-P01 |
| validate | CSV, TSV, XLSX | same diagnostics and physical row numbers | ST734-P02 |
| validate | header-only / entirely blank data row | no diagnostics | ST734-B01 |
| validate | missing metadata definition | row 2, meta column, reason | ST734-N01 |
| validate | unknown custom / meta key | row 2, precise column | ST734-N02 |
| validate | unsupported or variable metadata | row 2, expected supported type | ST734-N03 |
| validate | malformed basic/sample/attribute/inputdata paths, unknown mapping prefix | row 2 diagnostic | ST734-N04 |
| validate | duplicate original mapping headers | row 2 diagnostic before pandas mangling | ST734-N05 |
| validate | invalid later boolean/integer/number cells | physical row 4; no payload in diagnostic | ST734-N06 |
| validate | metadata invalid boolean/integer casting | physical data row, no payload | ST734-N07 |
| validate | missing/unreadable table or schema | structured safe diagnostic | ST734-N08 |
| ensure | invalid table | RdeValidationError 4005 with structured detail | ST734-N09 |
| Runner | invalid later row | zero flow invocations, no row CSV extraction | ST734-N10 |
| Runner | legacy callback invalid later row | original per-row contract remains | ST734-L01 |
| validate | descriptive non-mapping column | ignored as legacy | ST734-P03 |

Additional defensive cases extend ST734-N08 with malformed nested schema and propagation of catalogued run interruption during reading/casting. ST734-L01 is checked by the unchanged frozen `test_smarttable_v17_contract_k0.py`, `test_smarttable_builder_contract_k2.py`, and `test_smarttable_invoice_builder_i6_c.py` corpora. All new negative cases assert structured diagnostic location/type; execution errors assert RdeValidationError and catalog4005.

"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from rdetoolkit.errors import RdeValidationError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.modes.smarttable_validation import ensure_smarttable_valid, validate_smarttable_mapping


def _files(
    root: Path,
    headers: list[str],
    rows: list[list[str]],
    *,
    suffix: str = ".csv",
    metadata: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    table = root / f"smarttable_case{suffix}"
    values = [["display"] * len(headers), headers, *rows]
    if suffix == ".xlsx":
        pd.DataFrame(values).to_excel(table, header=False, index=False)
    else:
        with table.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream, delimiter="\t" if suffix == ".tsv" else ",").writerows(values)
    schema = root / "invoice.schema.json"
    writef_json(
        schema,
        {
            "type": "object",
            "properties": {
                "custom": {
                    "type": "object",
                    "properties": {
                        "flag": {"type": "boolean"},
                        "count": {"type": "integer"},
                        "value": {"type": "number"},
                        "text": {"type": "string"},
                    },
                }
            },
        },
    )
    definition = root / "metadata-def.json"
    if metadata is not None:
        writef_json(definition, metadata)
    return table, schema, definition


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None for path in root.rglob("*")}


@pytest.mark.parametrize("suffix", [".csv", ".tsv", ".xlsx"])
def test_valid_mappings_are_read_only__st734_p01_p02(tmp_path: Path, suffix: str) -> None:
    # Given: every supported mapping family and a row without raw inputs
    files = _files(
        tmp_path,
        ["basic/dataName", "sample/names", "sample/ownerId", "sample/generalAttributes.term", "sample/specificAttributes.cls.term", "custom/flag", "custom/count", "custom/value", "meta/temperature", "inputdata1", "Notes"],
        [["name", "new sample", "owner", "term", "value", "true", "12", "1.5", "300 K", "", "descriptive"]],
        suffix=suffix,
        metadata={"temperature": {"schema": {"type": "number"}, "unit": "K"}},
    )
    before = _snapshot(tmp_path)
    # When: validating the original table twice
    first = validate_smarttable_mapping(*files)
    second = validate_smarttable_mapping(*files)
    # Then: the deterministic result accepts the casters and writes nothing
    assert first == second == ()
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("rows", [[], [["", ""]]])
def test_empty_cells_and_header_only_are_valid__st734_b01(tmp_path: Path, rows: list[list[str]]) -> None:
    # Given: zero data rows or an empty rawless row
    files = _files(tmp_path, ["basic/dataName", "custom/count"], rows)
    # When: validating without a metadata definition
    diagnostics = validate_smarttable_mapping(*files)
    # Then: empty values keep their existing clearing behavior
    assert diagnostics == ()


@pytest.mark.parametrize(
    ("header", "reason"),
    [
        ("custom/unknown", "unknown_custom_field"),
        ("basic/unknown", "unknown_invoice_field"),
        ("sample/unknown", "unknown_invoice_field"),
        ("sample/generalAttributes.", "invalid_mapping_path"),
        ("sample/specificAttributes.only", "invalid_mapping_path"),
        ("sample/specificAttributes..term", "invalid_mapping_path"),
        ("custom/", "invalid_mapping_path"),
        ("meta/", "invalid_mapping_path"),
        ("typo/field", "unknown_mapping_prefix"),
        ("inputdataX", "invalid_mapping_path"),
    ],
)
def test_bad_header_reports_mapping_not_value__st734_n02_n04(tmp_path: Path, header: str, reason: str) -> None:
    # Given: an unsupported mapping header whose cell is sensitive
    files = _files(tmp_path, ["basic/dataName", header], [["name", "SECRET-PAYLOAD"]])
    # When: validating every header before rows
    diagnostics = validate_smarttable_mapping(*files)
    # Then: the physical header row and corrective hint are safe to serialize
    assert len(diagnostics) == 1
    assert diagnostics[0].row == 2
    assert diagnostics[0].column == header
    assert diagnostics[0].reason == reason
    assert diagnostics[0].suggestion
    assert "SECRET-PAYLOAD" not in json.dumps(asdict(diagnostics[0]))


@pytest.mark.parametrize(
    ("metadata", "reason"),
    [
        (None, "missing_metadata_definition"),
        ({}, "unknown_metadata_field"),
        ({"flag": {"variable": True, "schema": {"type": "boolean"}}}, "variable_metadata"),
        ({"flag": {"schema": {"type": "object"}}}, "unsupported_metadata_type"),
    ],
)
def test_metadata_definition_is_checked_before_rows__st734_n01_n03(tmp_path: Path, metadata: dict[str, Any] | None, reason: str) -> None:
    # Given: even a header-only table must have a compatible metadata mapping
    files = _files(tmp_path, ["meta/flag"], [], metadata=metadata)
    # When: validating the metadata contract
    diagnostics = validate_smarttable_mapping(*files)
    # Then: a structured header diagnostic identifies the reason
    assert len(diagnostics) == 1
    assert diagnostics[0].row == 2
    assert diagnostics[0].column == "meta/flag"
    assert diagnostics[0].reason == reason


@pytest.mark.parametrize("suffix", [".csv", ".tsv", ".xlsx"])
def test_duplicate_original_header_is_not_pandas_mangled__st734_n05(tmp_path: Path, suffix: str) -> None:
    # Given: pandas would rename this duplicate mapping to custom/count.1
    files = _files(tmp_path, ["custom/count", "custom/count"], [["1", "2"]], suffix=suffix)
    # When: inspecting the original physical mapping row
    diagnostics = validate_smarttable_mapping(*files)
    # Then: the diagnostic names the actual duplicate rather than an invented key
    assert [(item.row, item.column, item.reason) for item in diagnostics] == [(2, "custom/count", "duplicate_mapping")]


@pytest.mark.parametrize(
    ("header", "valid", "invalid", "expected"),
    [
        ("custom/flag", "true", "SECRET", "boolean"),
        ("custom/count", "2", "SECRET", "integer"),
        ("custom/count", "2", "2.5", "integer"),
        ("custom/value", "1.5", "SECRET", "number"),
        ("meta/flag", "true", "SECRET", "boolean"),
        ("meta/count", "2", "SECRET", "integer"),
    ],
)
def test_later_invalid_cell_has_physical_row_and_type__st734_n06_n07(tmp_path: Path, header: str, valid: str, invalid: str, expected: str) -> None:
    # Given: a valid first data row and an invalid second data row
    metadata = {"flag": {"schema": {"type": "boolean"}}, "count": {"schema": {"type": "integer"}}}
    files = _files(tmp_path, [header], [[valid], [invalid]], metadata=metadata)
    # When: checking every row before any row is registered
    diagnostics = validate_smarttable_mapping(*files)
    # Then: the diagnostic locates physical row 4 and never includes the cell
    assert len(diagnostics) == 1
    assert diagnostics[0].row == 4
    assert diagnostics[0].column == header
    assert diagnostics[0].expected_type == expected
    assert diagnostics[0].reason == "invalid_cell_type"
    assert "SECRET" not in json.dumps(asdict(diagnostics[0]))


def test_missing_input_reports_safe_error__st734_n08(tmp_path: Path) -> None:
    # Given: a path whose file has not been uploaded
    missing = tmp_path / "smarttable_missing.csv"
    # When: asking for a read-only validation
    diagnostics = validate_smarttable_mapping(missing, tmp_path / "schema.json", tmp_path / "metadata-def.json")
    # Then: unreadability is represented as a structured diagnostic
    assert diagnostics[0].reason == "unreadable_table"


def test_catalogued_error_contains_structured_diagnostics__st734_n09(tmp_path: Path) -> None:
    # Given: a SmartTable whose second row is invalid
    table, schema, _ = _files(tmp_path / "inputdata", ["custom/count"], [["1"], ["SECRET"]])
    tasksupport = tmp_path / "tasksupport"
    tasksupport.mkdir()
    schema.rename(tasksupport / "invoice.schema.json")
    # When: enforcing the mapping contract
    with pytest.raises(RdeValidationError) as caught:
        ensure_smarttable_valid(table.parent, tasksupport)
    # Then: the public error carries the catalog code and redacted row information
    assert caught.value.code == 4005
    assert caught.value.detail["diagnostics"][0]["row"] == 4
    assert "SECRET" not in json.dumps(caught.value.to_dict())


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20).map(lambda text: "invalid_" + text))
def test_invalid_integer_diagnostics_are_deterministic__st734_n06_property(tmp_path: Path, value: str) -> None:
    # Given: nonnumeric text cannot represent the integer metadata contract
    files = _files(tmp_path, ["custom/count"], [[value]])
    # When: inspecting the same snapshot twice
    first = validate_smarttable_mapping(*files)
    second = validate_smarttable_mapping(*files)
    # Then: diagnostics depend on the location and declared type, not the raw value
    assert first == second
    assert first[0].reason == "invalid_cell_type"


def test_runner_rejects_later_invalid_row_before_flow__st734_n10(tmp_path: Path) -> None:
    # Given: the registered fixture with one good and one bad integer row
    from rdetoolkit.core.flow import flow
    from rdetoolkit.runner.lifecycle import Runner
    from tests.v2.contract.fixtures import _generate

    _generate._materialize_oracle_case("smarttable", tmp_path)
    inputdata = tmp_path / "data" / "inputdata"
    for existing in inputdata.glob("smarttable_*"):
        existing.unlink()
    table, schema, _ = _files(tmp_path / "table-source", ["custom/count"], [["1"], ["SECRET"]])
    table.rename(inputdata / table.name)
    schema_path = tmp_path / "data" / "tasksupport" / "invoice.schema.json"
    original_schema = readf_json(schema_path)
    original_schema["properties"]["custom"]["properties"]["count"] = {"type": "integer", "label": {"ja": "count", "en": "count"}}
    writef_json(schema_path, original_schema)
    calls: list[int] = []

    @flow(id="test.smarttable.preflight.734")
    def pipeline() -> None:
        calls.append(1)

    # When: the normal v2 Runner validates the complete table
    report = Runner(root=tmp_path, inputdata_path=inputdata, unpacked_dir_path=tmp_path / "data" / "temp").run(pipeline)
    # Then: no earlier row invokes user code or generates row CSVs
    assert report.status == "failed"
    assert calls == []
    assert report.error is not None
    assert report.error["code"] == 4005
    assert not list((tmp_path / "data" / "temp").glob("fsmarttable*"))


@pytest.mark.parametrize("schema_value", [None, [], {"properties": {"custom": {"properties": {"count": {"type": "object"}}}}}, {"properties": {"custom": {"properties": {"count": {}}}}}])
def test_invalid_schema_is_reported_safely__st734_n08_schema(tmp_path: Path, schema_value: Any) -> None:
    # Given: an unreadable, non-object, or unsupported custom declaration
    table, schema, metadata = _files(tmp_path, ["custom/count"], [["1"]])
    if schema_value is None:
        schema.unlink()
    else:
        schema.write_text(json.dumps(schema_value), encoding="utf-8")
    # When: checking the table's declared custom destination
    diagnostics = validate_smarttable_mapping(table, schema, metadata)
    # Then: the schema problem is a safe structured validation result
    assert diagnostics[0].reason in {"invalid_invoice_schema", "unsupported_custom_type"}


def test_absent_mapping_headers_are_reported__st734_n04_empty(tmp_path: Path) -> None:
    # Given: descriptive columns without an actual mapping destination
    files = _files(tmp_path, ["Notes"], [["SECRET"]])
    # When: checking the original headers
    diagnostics = validate_smarttable_mapping(*files)
    # Then: missing mapping headers are identified on physical row 2
    assert diagnostics[0].row == 2
    assert diagnostics[0].reason == "missing_mapping_headers"


def test_ensure_accepts_valid_and_absent_tables__st734_p03(tmp_path: Path) -> None:
    # Given: a valid text mapping and no metadata requirement
    table, schema, _ = _files(tmp_path / "inputdata", ["custom/text"], [["abc"]])
    tasksupport = tmp_path / "tasksupport"
    tasksupport.mkdir()
    schema.rename(tasksupport / "invoice.schema.json")
    # When: validating a normal table and a directory without SmartTable inputs
    ensure_smarttable_valid(table.parent, tasksupport)
    ensure_smarttable_valid(tmp_path / "absent", tasksupport)
    # Then: validation produces no registration directories
    assert not (tmp_path / "divided").exists()


def test_metadata_without_type_retains_legacy_text__st734_p01_optional_type(tmp_path: Path) -> None:
    # Given: legacy metadata without a type declaration retains text values
    files = _files(tmp_path, ["meta/text"], [["value"]], metadata={"text": {"schema": {}}})
    # When: checking the compatible optional type
    diagnostics = validate_smarttable_mapping(*files)
    # Then: the value is accepted by the existing metadata caster
    assert diagnostics == ()


@pytest.mark.parametrize("stage", ["table", "schema", "metadata", "cell"])
def test_interruption_is_never_a_mapping_diagnostic__st734_n08_interrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str) -> None:
    # Given: a run interruption while reading or casting an otherwise valid table
    from rdetoolkit.errors import RdeExecutionError
    from rdetoolkit.modes import smarttable_validation

    files = _files(tmp_path, ["meta/text"], [["value"]], metadata={"text": {"schema": {"type": "string"}}})
    original = smarttable_validation.readf_json

    def interrupt(*args: Any, **kwargs: Any) -> Any:
        if stage == "metadata" and args[0] != files[2]:
            return original(*args, **kwargs)
        raise RdeExecutionError(code=3004, message="interrupted")

    if stage == "table":
        monkeypatch.setattr(smarttable_validation.pd, "read_csv", interrupt)
    elif stage == "cell":
        monkeypatch.setattr(smarttable_validation, "castval", interrupt)
    else:
        monkeypatch.setattr(smarttable_validation, "readf_json", interrupt)
    # When: the preflight encounters the external interruption
    with pytest.raises(RdeExecutionError) as caught:
        validate_smarttable_mapping(*files)
    # Then: the catalogued interruption remains observable by the Runner
    assert caught.value.code == 3004


def test_malformed_custom_schema_never_raises_payload_error__st734_n08_nested(tmp_path: Path) -> None:
    # Given: a malformed nested custom schema is still an object at the root
    table, schema, metadata = _files(tmp_path, ["custom/count"], [["SECRET"]])
    writef_json(schema, {"properties": {"custom": []}})
    # When: the caller requests structured validation diagnostics
    diagnostics = validate_smarttable_mapping(table, schema, metadata)
    # Then: the invalid declaration is reported without an AttributeError or value
    assert diagnostics[0].reason == "unknown_custom_field"
    assert "SECRET" not in json.dumps(asdict(diagnostics[0]))


def test_schema_declared_standard_fields_are_accepted__st734_schema_fields(tmp_path: Path) -> None:
    # Given: an explicit standard-section destination outside the fallback vocabulary.
    table, schema, metadata = _files(tmp_path, ["basic/dateName", "sample/externalReference"], [["local", "reference"]])
    content = readf_json(schema)
    content["properties"]["basic"] = {"properties": {"dateName": {"type": "string"}}}
    content["properties"]["sample"] = {"properties": {"externalReference": {"type": "string"}}}
    writef_json(schema, content)
    # When: validating the declared invoice mapping before rows execute.
    result = validate_smarttable_mapping(table, schema, metadata)
    # Then: the actual schema owns accepted destinations.
    assert result == ()
