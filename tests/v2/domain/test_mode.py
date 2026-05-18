"""Tests for v2 domain mode resolution.

EP Table:
| API                    | Partition       | Rationale        | Expected checker    | Test ID   |
|------------------------|-----------------|------------------|---------------------|-----------|
| selected_input_checker | smarttable file | file discriminator | SmartTableChecker  | TC-EP-001 |
| selected_input_checker | excel invoice   | file discriminator | ExcelInvoiceChecker | TC-EP-002 |
| selected_input_checker | rdeformat mode  | mode flag         | RDEFormatChecker    | TC-EP-003 |
| selected_input_checker | multidatatile   | mode flag         | MultiFileChecker    | TC-EP-004 |
| selected_input_checker | default         | fallback          | InvoiceChecker      | TC-EP-005 |

BV Table:
| API                    | Boundary        | Rationale        | Expected            | Test ID   |
|------------------------|-----------------|------------------|---------------------|-----------|
| selected_input_checker | mode is None    | default boundary | InvoiceChecker      | TC-BV-001 |
"""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.models.rde2types import RdeInputDirPaths


def _srcpaths(tmp_path: Path) -> RdeInputDirPaths:
    return RdeInputDirPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
    )


class TestSelectedInputChecker:
    """Tests for mode checker selection."""

    def test_smarttable_file_wins__tc_ep_001(self, tmp_path: Path) -> None:
        """TC-EP-001: smarttable files select SmartTableChecker."""
        from rdetoolkit.domain.mode import selected_input_checker
        from rdetoolkit.impl.input_controller import SmartTableChecker

        # Given: inputdata contains a SmartTable file
        srcpaths = _srcpaths(tmp_path)
        srcpaths.inputdata.mkdir(parents=True)
        (srcpaths.inputdata / "smarttable_data.csv").write_text("display\nbasic/dataName\n", encoding="utf-8")

        # When: selecting the checker
        checker = selected_input_checker(srcpaths, tmp_path / "unpacked", None)

        # Then: SmartTable mode is selected
        assert isinstance(checker, SmartTableChecker)

    def test_excel_invoice_file_wins__tc_ep_002(self, tmp_path: Path) -> None:
        """TC-EP-002: *_excel_invoice.xlsx selects ExcelInvoiceChecker."""
        from rdetoolkit.domain.mode import selected_input_checker
        from rdetoolkit.impl.input_controller import ExcelInvoiceChecker

        # Given: inputdata contains an Excel invoice marker file
        srcpaths = _srcpaths(tmp_path)
        srcpaths.inputdata.mkdir(parents=True)
        (srcpaths.inputdata / "case_excel_invoice.xlsx").touch()

        # When: selecting the checker
        checker = selected_input_checker(srcpaths, tmp_path / "unpacked", None)

        # Then: ExcelInvoice mode is selected
        assert isinstance(checker, ExcelInvoiceChecker)

    def test_rdeformat_mode_selects_rdeformat__tc_ep_003(self, tmp_path: Path) -> None:
        """TC-EP-003: rdeformat mode selects RDEFormatChecker."""
        from rdetoolkit.domain.mode import selected_input_checker
        from rdetoolkit.impl.input_controller import RDEFormatChecker

        # Given: no file discriminator and rdeformat mode
        srcpaths = _srcpaths(tmp_path)
        srcpaths.inputdata.mkdir(parents=True)

        # When: selecting the checker
        checker = selected_input_checker(srcpaths, tmp_path / "unpacked", "rdeformat")

        # Then: RDEFormatChecker is selected
        assert isinstance(checker, RDEFormatChecker)

    def test_multidatatile_mode_selects_multifile__tc_ep_004(self, tmp_path: Path) -> None:
        """TC-EP-004: MultiDataTile mode selects MultiFileChecker."""
        from rdetoolkit.domain.mode import selected_input_checker
        from rdetoolkit.impl.input_controller import MultiFileChecker

        # Given: no file discriminator and MultiDataTile mode
        srcpaths = _srcpaths(tmp_path)
        srcpaths.inputdata.mkdir(parents=True)

        # When: selecting the checker
        checker = selected_input_checker(srcpaths, tmp_path / "unpacked", "MultiDataTile")

        # Then: MultiFileChecker is selected
        assert isinstance(checker, MultiFileChecker)

    def test_none_mode_selects_invoice__tc_bv_001(self, tmp_path: Path) -> None:
        """TC-BV-001: None mode falls back to InvoiceChecker."""
        from rdetoolkit.domain.mode import selected_input_checker
        from rdetoolkit.impl.input_controller import InvoiceChecker

        # Given: no file discriminator and no mode
        srcpaths = _srcpaths(tmp_path)
        srcpaths.inputdata.mkdir(parents=True)

        # When: selecting the checker
        checker = selected_input_checker(srcpaths, tmp_path / "unpacked", None)

        # Then: invoice mode is selected
        assert isinstance(checker, InvoiceChecker)
