"""Invoice validation timing contracts for issue #647.

EP table (each row expands over the listed mode/entry partitions):
| ID | Partition | Expected |
| --- | --- | --- |
| ROW | ExcelInvoice/SmartTable, callback/flow, required row-only field | success |
| CB | invoice/MultiDataTile/RDEformat callback fills required field | success |
| FINAL | all deferred entries, field remains missing | 4001 after preparation |
| EARLY | invoice/MultiDataTile/RDEformat flow, required field missing | 4001 before flow |
| FILE | all modes/entries, invoice or schema absent | 4003 before user code |
| SCHEMA | all modes/entries, invalid schema definition | 4001 before user code |
| SEAM | Runner subclass overriding ``pre_validate(config)`` and calling super | row-only field still succeeds |

BV table:
| ID | Boundary | Expected |
| --- | --- | --- |
| ROW | two Excel / three SmartTable rows | every final invoice has its row value |
| CB | one invoice tile / multiple MDT and RDEformat tiles | every callback can fill the field |
| FINAL | no producer supplies the one required field | validation still rejects output |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from openpyxl import load_workbook

from rdetoolkit import flow, workflows
from rdetoolkit.api.request import build_run_request
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.runner import Runner
from rdetoolkit.types import InputPaths, RdeConfig
from tests.v2.contract.fixtures import _generate

MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")
ROW_MODES = ("excelinvoice", "smarttable")
DEFERRED = [(mode, entry) for mode in MODES for entry in ("callback", "flow") if entry == "callback" or mode in ROW_MODES]
FIELD = "measurement_condition"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _workspace(root: Path, mode: str, *, rows_supply_field: bool) -> None:
    _generate.materialize_sut_case(mode, root)
    schema_path = root / "data/tasksupport/invoice.schema.json"
    schema = _read(schema_path)
    if "custom" not in schema.setdefault("required", []):
        schema["required"].append("custom")
    custom = schema["properties"].setdefault("custom", {"type": "object", "properties": {}})
    custom.setdefault("label", {"ja": "固有情報", "en": "Custom"})
    custom.setdefault("required", []).append(FIELD)
    custom["properties"][FIELD] = {"type": "string", "label": {"ja": "測定条件", "en": "Condition"}}
    _write(schema_path, schema)
    invoice_path = root / "data/invoice/invoice.json"
    invoice = _read(invoice_path)
    invoice.setdefault("custom", {}).pop(FIELD, None)
    _write(invoice_path, invoice)
    if rows_supply_field:
        workbook_path = next((root / "data/inputdata").glob("*.xlsx"))
        workbook = load_workbook(workbook_path)
        sheet = workbook["invoice_form"] if mode == "excelinvoice" else workbook.active
        column = sheet.max_column + 1
        if mode == "excelinvoice":
            values = [None, "custom", FIELD, "Condition", *[f"cond {index}" for index in range(sheet.max_row - 4)]]
        else:
            values = ["Condition", f"custom/{FIELD}", *[f"cond {index}" for index in range(sheet.max_row - 2)]]
        for row, value in enumerate(values, start=1):
            sheet.cell(row=row, column=column, value=value)
        workbook.save(workbook_path)
        workbook.close()


def _invoke(mode: str, entry: str, calls: list[Path], *, fill: bool = False) -> None:
    def callback(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
        calls.append(resource_paths.invoice / "invoice.json")
        if fill:
            invoice = _read(calls[-1])
            invoice["custom"][FIELD] = "callback condition"
            _write(calls[-1], invoice)

    @flow
    def pipeline(paths: InputPaths) -> None:
        calls.append(paths.inputdata)

    config = _generate.oracle_config(mode)
    if entry == "callback":
        workflows.run(custom_dataset_function=callback, config=config)
    else:
        workflows.run(flow=pipeline, config=config, exit_on_failure=True)


@pytest.mark.parametrize(("mode", "table_format"), [("excelinvoice", "xlsx"), ("smarttable", "xlsx"), ("smarttable", "csv")])
@pytest.mark.parametrize("entry", ("callback", "flow"))
def test_required_field_from_rows__row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, table_format: str, entry: str) -> None:
    # Given: the required field exists only in the table rows.
    _workspace(tmp_path, mode, rows_supply_field=True)
    if table_format == "csv":
        workbook = next((tmp_path / "data/inputdata").glob("*.xlsx"))
        pd.read_excel(workbook, header=None).to_csv(workbook.with_suffix(".csv"), index=False, header=False)
        workbook.unlink()
    monkeypatch.chdir(tmp_path)
    calls: list[Path] = []
    # When: executing the public callback or flow entry.
    _invoke(mode, entry, calls)
    # Then: all final invoices validate with their own row's value.
    assert calls
    invoices = [tmp_path / "data/invoice/invoice.json", *sorted((tmp_path / "data/divided").glob("*/invoice/invoice.json"))]
    if mode == "smarttable":
        assert {_read(path)["basic"]["dataName"]: _read(path)["custom"][FIELD] for path in invoices} == {f"smarttable_value_{index}": f"cond {index}" for index in range(3)}
    else:
        assert [_read(path)["custom"][FIELD] for path in invoices] == ["cond 0", "cond 1"]
    assert not (tmp_path / "data/job.failed").exists()


@pytest.mark.parametrize("mode", ("invoice", "multidatatile", "rdeformat"))
def test_callback_can_supply_required_field__cb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    # Given: a required custom field is absent from the uploaded invoice.
    _workspace(tmp_path, mode, rows_supply_field=False)
    monkeypatch.chdir(tmp_path)
    calls: list[Path] = []
    # When: the legacy callback supplies it.
    _invoke(mode, "callback", calls, fill=True)
    # Then: the run succeeds and every callback output contains the value.
    assert calls
    assert all(_read(path)["custom"][FIELD] == "callback condition" for path in calls)
    assert not (tmp_path / "data/job.failed").exists()


@pytest.mark.parametrize(("mode", "entry"), DEFERRED)
def test_missing_final_field_is_rejected__final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, entry: str) -> None:
    # Given: neither the rows nor user code supply the required field.
    _workspace(tmp_path, mode, rows_supply_field=False)
    monkeypatch.chdir(tmp_path)
    calls: list[Path] = []
    # When / Then: the public entry still raises SystemExit(1) and records 4001.
    with pytest.raises(SystemExit) as exc:
        _invoke(mode, entry, calls)
    assert exc.value.code == 1
    failure = (tmp_path / "data/job.failed").read_text(encoding="utf-8")
    assert failure.startswith("ErrorCode=4001\n")
    assert FIELD in failure
    assert (tmp_path / "data/raw").is_dir()


@pytest.mark.parametrize("mode", ("invoice", "multidatatile", "rdeformat"))
def test_flow_retains_early_validation__early(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    # Given: a non-row flow entry and an incomplete source invoice.
    _workspace(tmp_path, mode, rows_supply_field=False)
    monkeypatch.chdir(tmp_path)
    calls: list[Path] = []
    # When / Then: early validation fails before invoking the flow.
    with pytest.raises(SystemExit) as exc:
        _invoke(mode, "flow", calls)
    assert exc.value.code == 1
    assert (tmp_path / "data/job.failed").read_text(encoding="utf-8").startswith("ErrorCode=4001\n")
    assert calls == []
    assert not (tmp_path / "data/raw").exists()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("entry", ("callback", "flow"))
@pytest.mark.parametrize("defect", ("invoice", "schema", "invalid_schema"))
def test_preflight_checks_remain__file_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, entry: str, defect: str) -> None:
    # Given: a missing source file or invalid schema, even when validation is deferred.
    _workspace(tmp_path, mode, rows_supply_field=mode in ROW_MODES)
    path = tmp_path / ("data/invoice/invoice.json" if defect == "invoice" else "data/tasksupport/invoice.schema.json")
    if defect == "invalid_schema":
        _write(path, {"properties": {"custom": {"type": "invalid-type"}}})
    else:
        path.unlink()
    monkeypatch.chdir(tmp_path)
    calls: list[Path] = []
    # When / Then: structure/schema errors stop before user code with the existing code.
    with pytest.raises(SystemExit) as exc:
        _invoke(mode, entry, calls)
    assert exc.value.code == 1
    code = 4001 if defect == "invalid_schema" else 4003
    assert (tmp_path / "data/job.failed").read_text(encoding="utf-8").startswith(f"ErrorCode={code}\n")
    assert calls == []
    assert not (tmp_path / "data/raw").exists()


def test_rc1_pre_validate_override_keeps_deferral__seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a Runner subclass written against the rc1 ``pre_validate(config)`` seam.
    _workspace(tmp_path, "smarttable", rows_supply_field=True)
    monkeypatch.chdir(tmp_path)
    seen: list[str] = []

    class _Rc1Runner(Runner):
        def pre_validate(self, config: RdeConfig) -> None:
            seen.append("pre_validate")
            super().pre_validate(config)

    @flow
    def pipeline(paths: InputPaths) -> None:
        seen.append("flow")

    request = build_run_request(flow=pipeline, custom_dataset_function=None, config=_generate.oracle_config("smarttable"), root=tmp_path)
    # When: the run drives the override through the lifecycle.
    data = tmp_path / "data"
    report = _Rc1Runner(root=tmp_path, inputdata_path=data / "inputdata", unpacked_dir_path=data / "temp").run(request)
    # Then: the override is called and the rows still complete the invoice.
    assert report.status == "success"
    assert seen == ["pre_validate", "flow", "flow", "flow"]
    assert not (tmp_path / "data/job.failed").exists()
