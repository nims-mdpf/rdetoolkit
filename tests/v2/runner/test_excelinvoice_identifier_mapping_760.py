"""ExcelInvoice workbook-identifier to folder-group association (#760).

Each folder group gets the index of the first workbook row whose column-A value
equals one of the archive-relative path components of the group's first file.
Groups without a match get the terminal index. A stable sort then orders the
groups, and the sorted groups are paired with workbook rows by position.

| ID | Partition | Row identifiers | Expected (file, row invoice) |
|----|-----------|-----------------|------------------------------|
| XM-P1 | unique, workbook order | parent, child | zz-row1, aa-row2 |
| XM-P2 | unique, reversed workbook order | child, parent | aa-row1, zz-row2 |
| XM-P3 | no identifier matches | missing-a, missing-b | folder order: zz-row1, aa-row2 |
| XM-P4 | duplicate ancestor identifier | parent, parent | folder order: zz-row1, aa-row2 |
| XM-P5 | duplicate descendant identifier | child, child | aa-row1, zz-row2 |
| XM-P6 | unmatched row before an ancestor match | missing, parent | folder order: zz-row1, aa-row2 |
| XM-P7 | sibling folders, unique, reversed | b, a | b-row1, a-row2 |
| XM-B1 | sibling folders, unmatched row first | missing, a | a-row1, b-row2 (positional) |
| XM-B2 | identifier names a directory outside the archive | extraction dir, b | v2 ignores it: b-row1, a-row2 |
"""

from pathlib import Path

import pytest
from openpyxl import load_workbook

from rdetoolkit.impl.input_controller import ExcelInvoiceChecker
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.preview import preview_registration
from rdetoolkit.types import InputPaths, InvoiceData
from tests.v2.contract.fixtures import _generate

_NESTED = {"parent/zz.txt": b"parent", "parent/child/aa.txt": b"child"}
_SIBLINGS = {"a/a.txt": b"a", "b/b.txt": b"b"}


def _project(root: Path, identifiers: tuple[str, str], members: dict[str, bytes]) -> Path:
    _generate.materialize_case(_generate.oracle_case("v1/excelinvoice/ok"), root)
    inputdata = root / "data/inputdata"
    workbook_path = next(inputdata.glob("*.xlsx"))
    workbook = load_workbook(workbook_path)
    sheet = workbook["invoice_form"]
    sheet["A5"], sheet["A6"] = identifiers
    sheet["B5"], sheet["B6"] = "row1", "row2"
    workbook.save(workbook_path)
    workbook.close()
    _generate.rewrite_excelinvoice_archive(root, members)
    (root / "rdeconfig.yaml").write_text("system:\n  extended_mode: excelinvoice\n", encoding="utf-8")
    return inputdata


def _execute(root: Path, inputdata: Path) -> list[tuple[str, str]]:
    observed: list[tuple[str, str]] = []

    def record(paths: InputPaths, invoice: InvoiceData) -> None:
        observed.append((paths.rawfiles[0].name, invoice.raw["basic"]["dataName"]))

    report = Runner(root=root, inputdata_path=inputdata, unpacked_dir_path=root / "data/temp").run(record)
    assert report.status == "success", report.error
    return observed


def _preview(root: Path) -> list[tuple[str, int | None]]:
    return [(Path(tile.input_names[0]).name, tile.source_row) for tile in preview_registration(root).tiles]


def _legacy(root: Path, inputdata: Path) -> list[str]:
    groups, _ = ExcelInvoiceChecker(root / "legacy-temp").parse(inputdata)
    return [group[0].name for group in groups]


@pytest.mark.parametrize(
    ("identifiers", "members", "expected"),
    [
        (("parent", "child"), _NESTED, ["zz.txt", "aa.txt"]),
        (("child", "parent"), _NESTED, ["aa.txt", "zz.txt"]),
        (("missing-a", "missing-b"), _NESTED, ["zz.txt", "aa.txt"]),
        (("parent", "parent"), _NESTED, ["zz.txt", "aa.txt"]),
        (("child", "child"), _NESTED, ["aa.txt", "zz.txt"]),
        (("missing", "parent"), _NESTED, ["zz.txt", "aa.txt"]),
        (("b", "a"), _SIBLINGS, ["b.txt", "a.txt"]),
        (("missing", "a"), _SIBLINGS, ["a.txt", "b.txt"]),
    ],
    ids=["xm_p1_unique", "xm_p2_reversed", "xm_p3_no_match", "xm_p4_duplicate_ancestor", "xm_p5_duplicate_descendant", "xm_p6_unmatched_then_ancestor", "xm_p7_siblings_reversed", "xm_b1_positional_fallback"],
)
def test_row_identifier_association_matches_legacy__xm(tmp_path: Path, identifiers: tuple[str, str], members: dict[str, bytes], expected: list[str]) -> None:
    # Given: two workbook rows whose identifiers exercise one matching partition.
    inputdata = _project(tmp_path, identifiers, members)
    pairs = list(zip(expected, ["row1", "row2"], strict=True))
    # When: the legacy checker, the read-only preview, and the Runner each group the archive.
    legacy = _legacy(tmp_path, inputdata)
    preview = _preview(tmp_path)
    observed = _execute(tmp_path, inputdata)
    # Then: all three pair the same file with the same workbook row.
    assert legacy == expected
    assert preview == [(name, row) for row, name in enumerate(expected, start=1)]
    assert observed == pairs


def test_identifier_outside_archive_is_ignored__xm_b2(tmp_path: Path) -> None:
    # Given: row 1 names the directory the legacy checker extracts into, not an archive folder.
    inputdata = _project(tmp_path, ("legacy-temp", "b"), _SIBLINGS)
    # When: grouping with the legacy checker and with the v2 Runner.
    legacy = _legacy(tmp_path, inputdata)
    observed = _execute(tmp_path, inputdata)
    # Then: legacy matched the extraction path for every group; v2 matches archive members only.
    assert legacy == ["a.txt", "b.txt"]
    assert observed == [("b.txt", "row1"), ("a.txt", "row2")]
    assert _preview(tmp_path) == [("b.txt", 1), ("a.txt", 2)]
