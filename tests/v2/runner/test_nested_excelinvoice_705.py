"""ExcelInvoice folder-order regression partitions for PR #758.

| ID | Partition or boundary | Expected |
|----|-----------------------|----------|
| XI-P1 | parent and child both contain files | parent invoice stays with parent file |
| XI-B1 | adjacent sibling folders | workbook order still determines groups |
| XI-N1 | three folder groups for two workbook rows | catalogued layout error 4006 |
| XI-N2 | unreadable workbook | catalogued layout error 4006 |
"""

from pathlib import Path, PurePosixPath

import pytest
from openpyxl import load_workbook

from rdetoolkit.errors import RdeValidationError
from rdetoolkit.impl.input_controller import ExcelInvoiceChecker
from rdetoolkit.runner.input_snapshot import discover_input_snapshot
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, InvoiceData, RdeConfig
from tests.v2.contract.fixtures import _generate


def _project(root: Path, folders: tuple[str, str]) -> Path:
    _generate.materialize_case(_generate.oracle_case("v1/excelinvoice/ok"), root)
    inputdata = root / "data/inputdata"
    workbook_path = next(inputdata.glob("*.xlsx"))
    workbook = load_workbook(workbook_path)
    sheet = workbook["invoice_form"]
    sheet["A5"], sheet["A6"] = (PurePosixPath(folder).name for folder in folders)
    sheet["B5"], sheet["B6"] = "parent invoice", "child invoice"
    workbook.save(workbook_path)
    workbook.close()
    _generate.rewrite_excelinvoice_archive(root, {f"{folders[0]}/zz.txt": b"parent", f"{folders[1]}/aa.txt": b"child"})
    (root / "rdeconfig.yaml").write_text("system:\n  extended_mode: excelinvoice\n", encoding="utf-8")
    return inputdata


@pytest.mark.parametrize("folders", [("parent", "parent/child"), ("parent", "child")], ids=["nested", "siblings"])
def test_flow_keeps_folder_files_with_workbook_invoice__xi_p1_b1(tmp_path: Path, folders: tuple[str, str]) -> None:
    # Given: two workbook rows and files whose full-path sorting favors the child.
    inputdata = _project(tmp_path, folders)
    legacy_groups, _ = ExcelInvoiceChecker(tmp_path / "legacy-temp").parse(inputdata)
    observed: list[tuple[str, str]] = []

    def record(paths: InputPaths, invoice: InvoiceData) -> None:
        observed.append((paths.rawfiles[0].name, invoice.raw["basic"]["dataName"]))

    # When: the strict Runner groups the archive and invokes the flow for each row.
    report = Runner(root=tmp_path, inputdata_path=inputdata, unpacked_dir_path=tmp_path / "data/temp").run(record)
    # Then: the parent row is paired with its own file, matching legacy grouping.
    assert report.status == "success", report.error
    assert [[path.name for path in group] for group in legacy_groups] == [["zz.txt"], ["aa.txt"]]
    assert observed == [("zz.txt", "parent invoice"), ("aa.txt", "child invoice")]


def test_folder_count_mismatch_remains_catalogued__xi_n1(tmp_path: Path) -> None:
    # Given: three populated folders and only two workbook registration rows.
    inputdata = _project(tmp_path, ("parent", "parent/child"))
    _generate.rewrite_excelinvoice_archive(tmp_path, {"parent/zz.txt": b"parent", "parent/child/aa.txt": b"child", "other/third.txt": b"extra"})
    # When: read-only discovery verifies workbook and folder cardinality.
    with pytest.raises(RdeValidationError) as caught:
        discover_input_snapshot(ModeKind.excelinvoice, inputdata, RdeConfig())
    # Then: the mismatch retains the catalogued error rather than dropping a group.
    assert caught.value.code == 4006
    assert not (tmp_path / "data/temp").exists()


def test_unreadable_workbook_remains_catalogued__xi_n2(tmp_path: Path) -> None:
    # Given: an indicated workbook whose payload cannot be read.
    (tmp_path / "bad_excel_invoice.xlsx").write_bytes(b"not a workbook")
    # When: read-only discovery tries to build registration groups.
    with pytest.raises(RdeValidationError) as caught:
        discover_input_snapshot(ModeKind.excelinvoice, tmp_path, RdeConfig())
    # Then: the malformed input keeps its catalogued validation error.
    assert caught.value.code == 4006
