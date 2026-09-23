"""Tests for v2 domain invoice facade.

EP Table:
| API           | Partition       | Rationale       | Expected      | Test ID   |
|---------------|-----------------|-----------------|---------------|-----------|
| load_invoice  | json invoice    | standard input  | InvoiceData   | TC-EP-001 |
| load_invoice  | missing file    | error path      | FileNotFoundError | TC-EP-002 |

BV Table:
| API           | Boundary        | Rationale       | Expected      | Test ID   |
|---------------|-----------------|-----------------|---------------|-----------|
| load_invoice  | empty object    | minimal JSON    | raw == {}     | TC-BV-001 |

Session D2 addendum (invoice construction, decisions_pre_D2.md Ruling 1):

    TC-EP-D2-001/002 -- invariant modes (invoice/multidatatile/rdeformat):
        invoice/invoice.json is read ONCE per run and the same non-None
        InvoiceData is injected into every tile's RunContext.invoice.
        Missing invoice.json behaves exactly like v1 -- these tests reuse
        rdetoolkit.domain.invoice.load_invoice's existing contract
        (FileNotFoundError, see TC-EP-002 above) rather than inventing new
        semantics.
    TC-EP-D2-003/004 -- per-row modes (excelinvoice/smarttable): a per-tile
        invoice.json is built by delegating to v1 machinery. This test file
        pins the concrete delegation functions this session adds to
        rdetoolkit.domain.invoice (Design.md/PhaseD_prompts.md leave the
        exact names to this session):

            def build_excelinvoice_tile_invoice(
                *, excel_path: Path, invoice_org: Path,
                invoice_schema_path: Path, dist_path: Path, idx: int,
            ) -> InvoiceData:
                '''Delegates to
                rdetoolkit.invoicefile.ExcelInvoiceFile(excel_path)
                .overwrite(invoice_org, dist_path, invoice_schema_path, idx),
                then loads dist_path back via load_invoice() (session_d2.md
                Conflict #5's lightweight excelinvoice path).'''

            def build_smarttable_tile_invoice(
                *, smarttable_rowfile: Path, invoice_org: Path,
                invoice_schema_path: Path, dist_path: Path,
                rawfiles: tuple[Path, ...] = (),
            ) -> InvoiceData:
                '''Adapts tile paths into a ProcessingContext /
                RdeOutputResourcePath and delegates to
                rdetoolkit.processing.processors.invoice
                .SmartTableInvoiceInitializer.process, then loads dist_path
                back via load_invoice() (session_d2.md Conflict #5's
                heavier smarttable path -- an adapter, not a
                reimplementation).'''
    TC-EP-D2-005 -- regression guard: the original 3 tests above (TC-EP-001,
        TC-EP-002, TC-BV-001) stay GREEN and unmodified.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InvoiceData, IterationInfo, RdeConfig


class TestInvoiceFacade:
    """Tests for invoice facade helpers."""

    def test_load_json_invoice__tc_ep_001(self, tmp_path: Path) -> None:
        """TC-EP-001: JSON invoice loads into InvoiceData."""
        from rdetoolkit.domain.invoice import load_invoice

        # Given: an invoice JSON file
        invoice_path = tmp_path / "invoice.json"
        invoice_path.write_text(json.dumps({"basic": {"dataName": "sample"}}), encoding="utf-8")

        # When: loading invoice data
        invoice = load_invoice(invoice_path)

        # Then: raw data and mode are exposed
        assert invoice.raw["basic"]["dataName"] == "sample"
        assert invoice.mode == "invoice"

    def test_missing_invoice_raises__tc_ep_002(self, tmp_path: Path) -> None:
        """TC-EP-002: missing invoice file raises FileNotFoundError."""
        from rdetoolkit.domain.invoice import load_invoice

        # Given: a missing invoice path
        invoice_path = tmp_path / "missing.json"

        # When / Then: loading fails
        with pytest.raises(FileNotFoundError, match="Invoice file does not exist"):
            load_invoice(invoice_path)

    def test_empty_invoice_object__tc_bv_001(self, tmp_path: Path) -> None:
        """TC-BV-001: empty JSON object is a valid minimal invoice payload."""
        from rdetoolkit.domain.invoice import load_invoice

        # Given: an empty JSON invoice
        invoice_path = tmp_path / "invoice.json"
        invoice_path.write_text("{}", encoding="utf-8")

        # When: loading invoice data
        invoice = load_invoice(invoice_path)

        # Then: raw data is empty
        assert invoice.raw == {}


def _build_multidatatile_root(tmp_path: Path, file_count: int, *, with_invoice: bool = True) -> Path:
    """Build a v2 Runner root with ``file_count`` loose input files (multidatatile mode)."""
    root = tmp_path / "run_root"
    (root / "inputdata").mkdir(parents=True)
    for i in range(file_count):
        (root / "inputdata" / f"file_{i}.txt").write_text(f"data-{i}", encoding="utf-8")
    (root / "unpacked").mkdir()
    (root / "invoice").mkdir()
    if with_invoice:
        (root / "invoice" / "invoice.json").write_text(
            json.dumps({"basic": {"dataName": "seed"}}),
            encoding="utf-8",
        )
    (root / "tasksupport").mkdir()
    return root


def _build_invoice_mode_root(tmp_path: Path, *, with_invoice: bool = True) -> Path:
    """Build a v2 Runner root with a single loose input file (invoice mode, one tile)."""
    return _build_multidatatile_root(tmp_path, 1, with_invoice=with_invoice)


def _build_rdeformat_root(tmp_path: Path, groups: dict[str, list[str]]) -> Path:
    """Build a v2 Runner root whose inputdata/ contains an RDEFormat-shaped zip.

    Mirrors ``tests/v2/runner/test_iterator.py``'s ``_write_rdeformat_zip``
    helper (replicated inline per this session's "never import tests/ root
    helpers" rule): each top-level folder name inside the zip becomes one tile.
    """
    root = tmp_path / "run_root"
    (root / "inputdata").mkdir(parents=True)
    zip_path = root / "inputdata" / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for folder, filenames in groups.items():
            for filename in filenames:
                zf.writestr(f"{folder}/{filename}", "dummy-content")
    (root / "unpacked").mkdir()
    (root / "invoice").mkdir()
    (root / "invoice" / "invoice.json").write_text(
        json.dumps({"basic": {"dataName": "seed"}}),
        encoding="utf-8",
    )
    (root / "tasksupport").mkdir()
    return root


class TestInvariantModeInvoiceInjection:
    """TC-EP-D2-001: invoice/multidatatile/rdeformat read invoice.json once
    and inject the SAME non-None InvoiceData into every tile.
    """

    def test_invoice_mode_single_tile_gets_non_none_invoice__tc_ep_d2_001a(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = _build_invoice_mode_root(tmp_path)
        monkeypatch.chdir(root)

        received: list[object] = []

        @node
        def _capture(invoice: InvoiceData) -> None:
            received.append(invoice)

        @flow
        def _pipeline(invoice: InvoiceData) -> None:
            _capture(invoice)

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "test-ep-d2-001a"

        runner.iterate(_pipeline, ModeKind.invoice, RdeConfig())

        assert len(received) == 1
        assert received[0] is not None
        assert received[0].raw["basic"]["dataName"] == "seed"

    def test_multidatatile_mode_same_invoice_object_every_tile__tc_ep_d2_001b(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = _build_multidatatile_root(tmp_path, 3)
        monkeypatch.chdir(root)

        received: list[object] = []

        @node
        def _capture(invoice: InvoiceData) -> None:
            received.append(invoice)

        @flow
        def _pipeline(invoice: InvoiceData) -> None:
            _capture(invoice)

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "test-ep-d2-001b"

        runner.iterate(_pipeline, ModeKind.multidatatile, RdeConfig())

        assert len(received) == 3
        assert all(invoice is not None for invoice in received)
        assert all(invoice is received[0] for invoice in received), (
            "invoice/invoice.json must be read ONCE and the SAME InvoiceData "
            "injected into every tile (decisions_pre_D2.md Ruling 1)"
        )

    def test_rdeformat_mode_same_invoice_object_every_tile__tc_ep_d2_001c(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = _build_rdeformat_root(tmp_path, {"0000": ["f0.txt"], "0001": ["f1.txt"]})
        monkeypatch.chdir(root)

        received: list[object] = []

        @node
        def _capture(invoice: InvoiceData) -> None:
            received.append(invoice)

        @flow
        def _pipeline(invoice: InvoiceData) -> None:
            _capture(invoice)

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "test-ep-d2-001c"

        runner.iterate(_pipeline, ModeKind.rdeformat, RdeConfig())

        assert len(received) == 2
        assert all(invoice is not None for invoice in received)
        assert all(invoice is received[0] for invoice in received)


class TestInvariantModeMissingInvoiceMatchesV1:
    """TC-EP-D2-002: missing invoice/invoice.json behaves exactly like v1 --
    no invented semantics. Pinned to load_invoice's existing FileNotFoundError
    contract (TC-EP-002 above), since D2.6a reuses load_invoice as-is.
    """

    def test_missing_invoice_json_raises_file_not_found_error__tc_ep_d2_002(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = _build_invoice_mode_root(tmp_path, with_invoice=False)
        monkeypatch.chdir(root)

        @flow
        def _pipeline(iteration: IterationInfo) -> None:
            return None

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "test-ep-d2-002"

        with pytest.raises(FileNotFoundError):
            runner.iterate(_pipeline, ModeKind.invoice, RdeConfig())


def _write_minimal_excel_invoice(path: Path, data_rows: list[list[str]]) -> None:
    """Write a minimal ExcelInvoiceFile-compatible workbook with one
    "basic/dataName" data column.

    Mirrors the real invoiceList_format_id / category-row / field-name-row /
    label-row / data-rows layout parsed by
    ``rdetoolkit.invoicefile._sheet_processing._process_invoice_sheet``
    (replicated inline, not imported from tests/fixtures).
    """
    header_and_data = [
        ["", "basic"],
        ["name", "dataName"],
        ["filename label", "data name label"],
        *data_rows,
    ]
    df = pd.DataFrame(header_and_data, columns=["invoiceList_format_id", "Sample_RDE_DataSet"])
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="invoice_form", index=False)


class TestExcelinvoiceTileInvoiceDelegation:
    """TC-EP-D2-003: excelinvoice builds a per-row, per-tile invoice.json by
    delegating to ExcelInvoiceFile.overwrite (session_d2.md Conflict #5).
    """

    def test_build_excelinvoice_tile_invoice_delegates_to_v1_overwrite__tc_ep_d2_003(
        self,
        tmp_path: Path,
    ) -> None:
        from rdetoolkit.domain.invoice import build_excelinvoice_tile_invoice  # noqa: PLC0415

        excel_path = tmp_path / "sample_excel_invoice.xlsx"
        _write_minimal_excel_invoice(
            excel_path,
            [["test_child1.txt", "excel_value_0"], ["test_child2.txt", "excel_value_1"]],
        )
        invoice_org = tmp_path / "invoice_org.json"
        invoice_org.write_text(json.dumps({"basic": {"dataName": "orig"}}), encoding="utf-8")
        schema_path = tmp_path / "invoice.schema.json"
        schema_path.write_text(json.dumps({"properties": {}}), encoding="utf-8")
        dist_path = tmp_path / "divided" / "0000" / "invoice" / "invoice.json"

        invoice = build_excelinvoice_tile_invoice(
            excel_path=excel_path,
            invoice_org=invoice_org,
            invoice_schema_path=schema_path,
            dist_path=dist_path,
            idx=0,
        )

        assert dist_path.exists(), "the per-tile invoice.json must actually be written to dist_path"
        on_disk = json.loads(dist_path.read_text(encoding="utf-8"))
        assert on_disk["basic"]["dataName"] == "excel_value_0"
        assert invoice.raw["basic"]["dataName"] == "excel_value_0"
        assert invoice.mode == "invoice"

    def test_build_excelinvoice_tile_invoice_second_row__tc_ep_d2_003b(self, tmp_path: Path) -> None:
        """idx=1 must pick the second Excel data row (row-index addressing)."""
        from rdetoolkit.domain.invoice import build_excelinvoice_tile_invoice  # noqa: PLC0415

        excel_path = tmp_path / "sample_excel_invoice.xlsx"
        _write_minimal_excel_invoice(
            excel_path,
            [["test_child1.txt", "excel_value_0"], ["test_child2.txt", "excel_value_1"]],
        )
        invoice_org = tmp_path / "invoice_org.json"
        invoice_org.write_text(json.dumps({"basic": {"dataName": "orig"}}), encoding="utf-8")
        schema_path = tmp_path / "invoice.schema.json"
        schema_path.write_text(json.dumps({"properties": {}}), encoding="utf-8")
        dist_path = tmp_path / "divided" / "0001" / "invoice" / "invoice.json"

        invoice = build_excelinvoice_tile_invoice(
            excel_path=excel_path,
            invoice_org=invoice_org,
            invoice_schema_path=schema_path,
            dist_path=dist_path,
            idx=1,
        )

        assert invoice.raw["basic"]["dataName"] == "excel_value_1"


class TestSmarttableTileInvoiceDelegation:
    """TC-EP-D2-004: smarttable builds a per-row, per-tile invoice.json by
    delegating (via a ProcessingContext adapter) to
    SmartTableInvoiceInitializer.process (session_d2.md Conflict #5).
    """

    def test_build_smarttable_tile_invoice_delegates_to_v1_initializer__tc_ep_d2_004(
        self,
        tmp_path: Path,
    ) -> None:
        from rdetoolkit.domain.invoice import build_smarttable_tile_invoice  # noqa: PLC0415

        rowfile = tmp_path / "fsmarttable_row_0.csv"
        rowfile.write_text("basic/dataName\nsmarttable_value_0\n", encoding="utf-8")
        invoice_org = tmp_path / "invoice_org.json"
        invoice_org.write_text(json.dumps({"basic": {"dataName": "orig"}}), encoding="utf-8")
        schema_path = tmp_path / "invoice.schema.json"
        schema_path.write_text(json.dumps({"properties": {}}), encoding="utf-8")
        dist_path = tmp_path / "divided" / "0000" / "invoice" / "invoice.json"

        invoice, row_data = build_smarttable_tile_invoice(
            smarttable_rowfile=rowfile,
            invoice_org=invoice_org,
            invoice_schema_path=schema_path,
            dist_path=dist_path,
        )

        assert dist_path.exists(), "the per-tile invoice.json must actually be written to dist_path"
        on_disk = json.loads(dist_path.read_text(encoding="utf-8"))
        assert on_disk["basic"]["dataName"] == "smarttable_value_0"
        assert invoice.raw["basic"]["dataName"] == "smarttable_value_0"
        assert invoice.mode == "invoice"
        # Session I-REVIEW-A ruling #2: the row dictionary is returned, not
        # retained anywhere a concurrent run could reach.
        assert row_data == {"basic/dataName": "smarttable_value_0"}


class TestExistingInvoiceFacadeUnaffected:
    """TC-EP-D2-005: regression guard -- the pre-D2 load_invoice tests above
    (TC-EP-001/002, TC-BV-001) are unmodified by this session; this test just
    documents/pins that expectation explicitly for the Acceptance Surface.
    """

    def test_load_invoice_signature_unchanged__tc_ep_d2_005(self) -> None:
        import inspect  # noqa: PLC0415

        from rdetoolkit.domain.invoice import load_invoice  # noqa: PLC0415

        params = list(inspect.signature(load_invoice).parameters)
        assert params == ["invoice_path", "schema_path"]
