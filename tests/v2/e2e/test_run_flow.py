"""End-to-end tests: run(flow=pipeline) across >=3 modes, compared against
dynamically-generated v1 goldens (Session D2, TC-E2E-001..007).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §6.3, §6.4, §8.3, §11.
Session authority: local/develop/v2/tasks/session_d2.md D2.7(a)-(e);
PhaseD_prompts.md D2.7(d) (excelinvoice must be exercised through REAL mode
auto-detection dispatch, recovering session_b2.md's TC-GOLD-002 gap) and
D2.7(e) (excelinvoice/smarttable per-tile invoice.json CONTENT parity, not
just directory-tree existence, recovering session_d1.md Decision D1-D's
flagged gap).

Golden principle (non-negotiable, matches
tests/v2/golden/test_dir_tree_parity.py's header comment): every "expected"
value in this file is produced by an ACTUAL v1 run
(``rdetoolkit.workflows.run``) against a fixture built under ``tmp_path`` --
never a hand-written directory list or hand-written invoice.json content.

Fixture helpers in this file are self-contained (no ``from tests.fixtures
import ...``, no ``from tests.<v1 file> import ...`` -- this session's
"never import tests/ root helpers" rule); they intentionally re-derive small
pieces of ``tests/v2/golden/test_dir_tree_parity.py``'s and
``tests/v2/runner/test_iterator.py``'s already-proven fixture shapes rather
than importing those modules.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, IterationInfo, RdeConfig
from rdetoolkit.workflows import _run_legacy as v1_run

# v1 RdeOutputResourcePath field -> on-disk directory basename, matching
# runner/paths.py's _DIRNAMES and the golden test's _OUTPUT_FIELD_TO_DIRNAME.
_OUTPUT_DIRNAMES = (
    "structured",
    "meta",
    "main_image",
    "other_image",
    "thumbnail",
    "attachment",
    "nonshared_raw",
    "raw",
    "invoice",
    "logs",
)

_SMARTTABLE_CONTRACT_DATA = (
    Path(__file__).resolve().parents[1]
    / "contract"
    / "fixtures"
    / "inputs"
    / "smarttable"
    / "data"
)


@contextmanager
def _chdir(path: Path) -> Generator[None, None, None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _no_op_v1_fn(srcpaths: object, resource_paths: object) -> None:
    return None


def _v1_config(*, extended_mode: str | None = None) -> Config:
    return Config(
        system=SystemSettings(extended_mode=extended_mode, save_raw=True, save_thumbnail_image=True, magic_variable=False),
        multidata_tile=MultiDataTileSettings(ignore_errors=False),
    )


# v1's built-in invoice_basic_and_sample.schema_.json requires top-level
# "datasetId"/"basic", and "basic" requires "dateSubmitted"/"dataOwnerId"/
# "dataName" (dataOwnerId must match ^([0-9a-zA-Z]{56})$). This is separate
# from -- and always enforced in addition to -- the caller-supplied
# invoice.schema.json.
_SEED_INVOICE_JSON: dict = {
    "datasetId": "seed-dataset",
    "basic": {
        "dateSubmitted": "2026-07-10",
        "dataOwnerId": "0" * 56,
        "dataName": "seed",
    },
}

def _build_data_fixture(
    root: Path,
    *,
    input_files: dict[str, str] | None = None,
    invoice_schema: dict | None = None,
    invoice_json: dict | None = None,
) -> None:
    """Build a minimal ``data/{inputdata,invoice,tasksupport,unpacked}`` tree
    usable by BOTH ``v1_run`` (cwd-relative ``data/...``) and the v2 Runner
    (given explicit ``inputdata_path=root/"data"/"inputdata"``): the two
    checker families share the same detection code
    (``domain.mode.selected_input_checker``), so one fixture drives both.
    """
    inputdata = root / "data" / "inputdata"
    inputdata.mkdir(parents=True)
    resolved_input_files = {"test_single.txt": "dummy"} if input_files is None else input_files
    for name, content in resolved_input_files.items():
        (inputdata / name).write_text(content, encoding="utf-8")
    (root / "data" / "invoice").mkdir(parents=True)
    (root / "data" / "invoice" / "invoice.json").write_text(
        json.dumps(_SEED_INVOICE_JSON if invoice_json is None else invoice_json),
        encoding="utf-8",
    )
    (root / "data" / "tasksupport").mkdir(parents=True)
    (root / "data" / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps({"properties": {}} if invoice_schema is None else invoice_schema),
        encoding="utf-8",
    )
    (root / "data" / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (root / "data" / "unpacked").mkdir(parents=True)


def _make_v2_runner(root: Path) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "unpacked",
    )


def _noop_pipeline(tag: str = "default"):  # noqa: ANN201
    """Build a fresh no-op flow with a unique @node id per call.

    A unique ``tag`` is required because the node registry rejects a
    duplicate node id (RdeRegistryError E2001) -- calling this factory more
    than once per test session would otherwise collide on the same nested
    function's qualname.
    """

    @node(id=f"e2e_noop_{tag}")
    def _noop(paths: InputPaths) -> None:
        return None

    @flow
    def _pipeline(paths: InputPaths) -> None:
        _noop(paths)

    return _pipeline


class TestTreeParityInvoiceMode:
    """TC-E2E-001: invoice mode -- directory tree matches a real v1 run."""

    def test_invoice_mode_tree_matches_v1_golden__tc_e2e_001(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        v1_root = tmp_path / "v1"
        _build_data_fixture(v1_root)
        with _chdir(v1_root):
            v1_run(custom_dataset_function=_no_op_v1_fn, config=_v1_config())

        v2_root = tmp_path / "v2"
        _build_data_fixture(v2_root)
        pipeline = _noop_pipeline("e2e001")
        with _chdir(v2_root):
            runner = _make_v2_runner(v2_root)
            runner.run_id = "e2e-invoice-tree"
            runner.iterate(pipeline, ModeKind.invoice, RdeConfig())

        for dirname in _OUTPUT_DIRNAMES:
            assert (v1_root / "data" / dirname).is_dir(), f"v1 fixture must have produced data/{dirname}/"
            assert (v2_root / "data" / dirname).is_dir(), f"v2 run must have produced data/{dirname}/"


class TestTreeParityMultidatatileMode:
    """TC-E2E-002: multidatatile mode (2 tiles) -- divided/ tree matches a real v1 run."""

    def test_multidatatile_mode_tree_matches_v1_golden__tc_e2e_002(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        files = {"a.txt": "a", "b.txt": "b"}

        v1_root = tmp_path / "v1"
        _build_data_fixture(v1_root, input_files=files)
        with _chdir(v1_root):
            v1_run(custom_dataset_function=_no_op_v1_fn, config=_v1_config(extended_mode="MultiDataTile"))

        v2_root = tmp_path / "v2"
        _build_data_fixture(v2_root, input_files=files)
        pipeline = _noop_pipeline("e2e002")
        with _chdir(v2_root):
            runner = _make_v2_runner(v2_root)
            runner.run_id = "e2e-multidatatile-tree"
            runner.iterate(pipeline, ModeKind.multidatatile, RdeConfig())

        for idx in range(2):
            expected_relative = "data" if idx == 0 else f"data/divided/{idx:04d}"
            for dirname in _OUTPUT_DIRNAMES:
                v1_dir = v1_root / expected_relative / dirname
                v2_dir = v2_root / expected_relative / dirname
                assert v1_dir.is_dir(), f"v1 fixture must have produced {v1_dir}"
                assert v2_dir.is_dir(), f"v2 run must have produced {v2_dir}"


def _write_minimal_excel_invoice(path: Path, data_rows: list[list[str]]) -> None:
    """Write a minimal ExcelInvoiceFile-compatible workbook with
    "basic/dataName" and "basic/dataOwnerId" columns (see
    tests/v2/domain/test_invoice.py's identically-named helper -- duplicated
    here since each test file is self-contained per this session's rules).

    A "basic/dataOwnerId" column is included (constant per row) because
    ExcelInvoiceFile.overwrite resets untouched "basic" fields to None
    (ExcelInvoiceFile._initialize_non_sample) before applying the row data;
    v1's invoice_basic_and_sample.schema_.json requires "dataOwnerId" to
    still be a valid 56-char string afterward.
    """
    owner_id = "0" * 56
    header_and_data = [
        ["", "basic", "basic"],
        ["name", "dataName", "dataOwnerId"],
        ["filename label", "data name label", "data owner id label"],
        *([*row, owner_id] for row in data_rows),
    ]
    df = pd.DataFrame(header_and_data, columns=["invoiceList_format_id", "Sample_RDE_DataSet", ""])
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="invoice_form", index=False)


class TestExcelinvoiceRealModeDispatch:
    """TC-E2E-003: excelinvoice is verified through REAL mode auto-detection
    dispatch (session_b2.md TC-GOLD-002 gap, PhaseD_prompts.md D2.7(d)) --
    not a forced folder-generation-function shortcut.
    """

    def test_excelinvoice_auto_detected_and_dispatched_for_real__tc_e2e_003(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "run_root"
        # No loose files alongside the Excel file: v1's ExcelInvoiceChecker
        # rejects "other" non-excel/zip input files when an Excel invoice is
        # present (impl/input_controller.py._detect_invalid_other_files).
        _build_data_fixture(root, input_files={})
        _write_minimal_excel_invoice(
            root / "data" / "inputdata" / "sample_excel_invoice.xlsx",
            [["test_child1.txt", "excel_value_0"], ["test_child2.txt", "excel_value_1"]],
        )
        pipeline = _noop_pipeline("e2e003")

        with _chdir(root):
            runner = _make_v2_runner(root)
            runner.run_id = "e2e-excelinvoice-dispatch"
            report = runner.run(pipeline)

        assert isinstance(report, RunReport)
        assert report.mode == "excelinvoice", "mode must be auto-detected from the Excel file's presence, not forced"
        assert len(report.iterations) == 2
        assert (root / "data" / "divided" / "0001" / "structured").is_dir()


class TestRunReportSchemaConformance:
    """TC-E2E-004: RunReport (schema_version/iterations) matches the Design
    §8.3 shape -- as loosely typed as session_d2.md's own Current-State
    Survey specifies (iterations stays list[dict], no schema class; see that
    survey's explicit note that Design §8.3's JSON example only requires a
    dict-list shape, not that every illustrative key name is reproduced
    verbatim).
    """

    def test_run_report_has_schema_version_and_iteration_entries__tc_e2e_004(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "run_root"
        _build_data_fixture(root)
        pipeline = _noop_pipeline("e2e004")

        with _chdir(root):
            runner = _make_v2_runner(root)
            runner.run_id = "e2e-schema"
            report = runner.run(pipeline)

        payload = report.to_dict()
        assert payload["schema_version"] == "2"
        for key in ("run_id", "status", "flow_id", "mode", "started_at", "duration_ms", "config_digest", "iterations", "warnings"):
            assert key in payload

        assert len(payload["iterations"]) == 1
        entry = payload["iterations"][0]
        assert "status" in entry
        assert entry["status"] == "completed"


class TestJobFailedArtifact:
    """TC-E2E-005: a failing run writes data/job.failed with an int catalog code."""

    def test_failed_run_writes_job_failed_with_int_code__tc_e2e_005(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "run_root"
        _build_data_fixture(root)

        @node
        def _boom(iteration: IterationInfo) -> None:
            msg = "tile boom"
            raise ValueError(msg)

        @flow
        def _failing_pipeline(iteration: IterationInfo) -> None:
            _boom(iteration)

        with _chdir(root):
            runner = _make_v2_runner(root)
            runner.run_id = "e2e-job-failed"
            report = runner.run(_failing_pipeline)

        assert report.status == "failed"
        job_failed_path = root / "data" / "job.failed"
        assert job_failed_path.exists()
        content = job_failed_path.read_text(encoding="utf-8")
        assert "ErrorCode=" in content
        code_line = next(line for line in content.splitlines() if line.startswith("ErrorCode="))
        code_value = code_line.removeprefix("ErrorCode=").strip()
        assert code_value.isdigit(), f"job.failed ErrorCode must be an int code, got {code_value!r}"


class TestExcelinvoiceContentParity:
    """TC-E2E-006: excelinvoice per-tile invoice.json CONTENT (not just tree
    existence) matches a real v1 excelinvoice-mode run (decisions_pre_D2.md
    Ruling 1, recovering session_d1.md Decision D1-D's flagged gap).
    """

    def test_per_tile_invoice_json_content_matches_v1__tc_e2e_006(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Given: three Excel rows and identical v1/v2 source invoices
        rows = [
            ["test_child1.txt", "excel_value_0"],
            ["test_child2.txt", "excel_value_1"],
            ["test_child3.txt", "excel_value_2"],
        ]

        v1_root = tmp_path / "v1"
        # No loose files alongside the Excel file (see TC-E2E-003's comment).
        _build_data_fixture(v1_root, input_files={})
        _write_minimal_excel_invoice(v1_root / "data" / "inputdata" / "sample_excel_invoice.xlsx", rows)
        with _chdir(v1_root):
            v1_run(custom_dataset_function=_no_op_v1_fn, config=_v1_config())

        v2_root = tmp_path / "v2"
        _build_data_fixture(v2_root, input_files={})
        original_invoice = (v2_root / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8")
        _write_minimal_excel_invoice(v2_root / "data" / "inputdata" / "sample_excel_invoice.xlsx", rows)
        pipeline = _noop_pipeline("e2e006")

        # When: the real v2 excelinvoice lifecycle processes all rows
        with _chdir(v2_root):
            runner = _make_v2_runner(v2_root)
            runner.run_id = "e2e-excelinvoice-content"
            runner.run(pipeline)

        # Then: tile contents match v1 and the backed-up source stays pristine
        v1_tile0 = json.loads((v1_root / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        v2_tile0 = json.loads((v2_root / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        assert v1_tile0["basic"]["dataName"] == v2_tile0["basic"]["dataName"] == "excel_value_0"

        v1_tile1 = json.loads((v1_root / "data" / "divided" / "0001" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        v2_tile1 = json.loads((v2_root / "data" / "divided" / "0001" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        assert v1_tile1["basic"]["dataName"] == v2_tile1["basic"]["dataName"] == "excel_value_1"

        v1_tile2 = json.loads((v1_root / "data" / "divided" / "0002" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        v2_tile2 = json.loads((v2_root / "data" / "divided" / "0002" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        assert v1_tile2["basic"]["dataName"] == v2_tile2["basic"]["dataName"] == "excel_value_2"
        assert (v2_root / "data" / "temp" / "invoice_org.json").read_text(encoding="utf-8") == original_invoice


class TestSmarttableContentParity:
    """TC-E2E-007: smarttable per-tile invoice.json CONTENT matches a real
    v1 smarttable-mode run (decisions_pre_D2.md Ruling 1, D2.7(e)).
    """

    def test_per_tile_invoice_json_content_matches_v1__tc_e2e_007(
        self,
        tmp_path: Path,
    ) -> None:
        # Given: the committed spec-complete workbook and zip-backed mappings
        v1_root = tmp_path / "v1"
        shutil.copytree(_SMARTTABLE_CONTRACT_DATA, v1_root / "data")
        v1_rawfiles: list[set[str]] = []

        def _capture_v1(
            srcpaths: object,
            resource_paths: RdeOutputResourcePath,
        ) -> None:
            del srcpaths
            v1_rawfiles.append({path.name for path in resource_paths.rawfiles})

        # When: v1 executes the real SmartTable splitter and invoice pipeline
        with _chdir(v1_root):
            v1_run(custom_dataset_function=_capture_v1, config=_v1_config())

        v2_root = tmp_path / "v2"
        shutil.copytree(_SMARTTABLE_CONTRACT_DATA, v2_root / "data")
        v2_rawfiles: list[set[str]] = []

        @flow
        def _capture_v2(paths: InputPaths) -> None:
            v2_rawfiles.append({path.name for path in paths.rawfiles})

        # And: v2 auto-detects and executes the same real workbook
        with _chdir(v2_root):
            runner = _make_v2_runner(v2_root)
            runner.run_id = "e2e-smarttable-content"
            report = runner.run(_capture_v2)

        # Then: all three row invoices retain v1/v2 content parity
        invoice_relatives = (
            Path("data/invoice/invoice.json"),
            Path("data/divided/0001/invoice/invoice.json"),
            Path("data/divided/0002/invoice/invoice.json"),
        )
        expected_names = ("smarttable_value_2", "smarttable_value_0", "smarttable_value_1")
        for relative, expected_name in zip(invoice_relatives, expected_names, strict=True):
            v1_invoice = json.loads((v1_root / relative).read_text(encoding="utf-8"))
            v2_invoice = json.loads((v2_root / relative).read_text(encoding="utf-8"))
            assert v1_invoice["basic"]["dataName"] == v2_invoice["basic"]["dataName"] == expected_name

        # And: row splitting plus zip-backed file mapping ran in both paths
        assert report.mode == "smarttable"
        assert len(report.iterations) == 3
        assert len(v1_rawfiles) == len(v2_rawfiles) == 3
        assert any("row0.txt" in files for files in v1_rawfiles)
        assert any("行1.txt" in files for files in v1_rawfiles)
        assert any("row0.txt" in files for files in v2_rawfiles)
        assert any("行1.txt" in files for files in v2_rawfiles)
