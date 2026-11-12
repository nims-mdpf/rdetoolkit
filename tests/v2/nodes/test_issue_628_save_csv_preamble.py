"""Issue 628 EP/BV: ``save_csv`` writes a ``#`` header block before the table.

EP table
| Partition | Expected | Test ID |
|---|---|---|
| preamble=None (default) | bytes identical to the pre-#628 ``df.to_csv`` output | I628-EP-001 |
| rows of different lengths | each row written with the table's csv dialect, then the table | I628-EP-002 |
| rows needing quoting (comma, quote) | quoted like ``to_csv`` quotes table cells | I628-EP-003 |
| str preamble | written verbatim, then the table | I628-EP-004 |
| blank_line_after_preamble=True | one empty line between the block and the table | I628-EP-005 |
| table options with a preamble | float_format / header / index still apply to the table | I628-EP-006 |
| AES template layout (v1 csv.writer) | same text the v1 template wrote | I628-EP-007 |
| written file | ``rdetoolkit.graph`` parses the header block and the table | I628-EP-008 |
| a row given as a str | TypeError, no file written | I628-NEG-001 |

BV table
| Boundary | Expected | Test ID |
|---|---|---|
| empty row sequence | no preamble text | I628-BV-001 |
| empty str preamble | no preamble text | I628-BV-001 |
| one-field row / empty row | one field / one empty line | I628-BV-002 |
| blank line with no preamble | ignored: bytes identical to the default | I628-BV-003 |
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.nodes import save_csv
from rdetoolkit.testing import make_output_context

NL = os.linesep


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"Kinetic Energy": [100.0, 101.5], "Intensity": [1234, 1300]})


def test_default_keeps_previous_bytes__i628_ep_001(tmp_path: Path) -> None:
    """I628-EP-001: without a preamble the file is exactly ``df.to_csv``."""
    frame = _frame()
    path = save_csv(frame, make_output_context(tmp_path), "data.csv")
    assert path.read_bytes() == frame.to_csv(index=False).encode("utf-8")


def test_rows_use_table_dialect__i628_ep_002(tmp_path: Path) -> None:
    """I628-EP-002: ragged rows precede the table, same delimiter and line ending."""
    frame = _frame()
    rows = [["#title", "AES"], ["#dimension", "x", "y"], ["##comment", "AES(JEOL)spectrum"]]
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", preamble=rows)
    expected = f"#title,AES{NL}#dimension,x,y{NL}##comment,AES(JEOL)spectrum{NL}" + frame.to_csv(index=False)
    assert path.read_text(encoding="utf-8") == expected


def test_rows_are_quoted_like_table__i628_ep_003(tmp_path: Path) -> None:
    """I628-EP-003: fields with a comma or quote are quoted as ``to_csv`` would."""
    rows: list[list[object]] = [["#title", 'a,"b"'], ["#n", 3, 1.5, None]]
    path = save_csv(_frame(), make_output_context(tmp_path), "data.csv", preamble=rows)
    first_two = path.read_text(encoding="utf-8").split(NL)[:2]
    assert first_two == ['#title,"a,""b"""', "#n,3,1.5,"]


def test_str_preamble_is_verbatim__i628_ep_004(tmp_path: Path) -> None:
    """I628-EP-004: a str preamble is written as given."""
    frame = _frame()
    text = "#title,raw text\n#x,a;b\n"
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", preamble=text)
    assert path.read_text(encoding="utf-8") == text + frame.to_csv(index=False)


@pytest.mark.parametrize("preamble", [[["#title", "AES"]], f"#title,AES{NL}"])
def test_blank_line_after_preamble__i628_ep_005(tmp_path: Path, preamble: Sequence[Sequence[object]] | str) -> None:
    """I628-EP-005: one empty line separates the block from the table."""
    frame = _frame()
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", preamble=preamble, blank_line_after_preamble=True)
    assert path.read_text(encoding="utf-8") == f"#title,AES{NL}{NL}" + frame.to_csv(index=False)


def test_table_options_still_apply__i628_ep_006(tmp_path: Path) -> None:
    """I628-EP-006: float_format / header / index apply to the table part."""
    frame = _frame()
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", float_format="%.2f", header=["E", "I"], index=True, preamble=[["#title", "AES"]])
    assert path.read_text(encoding="utf-8") == f"#title,AES{NL}" + frame.to_csv(float_format="%.2f", header=["E", "I"], index=True)


def test_matches_v1_aes_template__i628_ep_007(tmp_path: Path) -> None:
    """I628-EP-007: writes the v1 AES template layout quoted in #628.

    The expected text is a literal, not rebuilt with ``csv.writer``; only the
    line ending follows this platform (the v1 template's fixed LF is a
    #599 ``lineterminator=`` concern).
    """
    frame = _frame()
    header = [
        ["#title", "Survey"],
        ["#dimension", "x", "y"],
        ["#x", "Kinetic Energy", "eV"],
        ["#y", "Intensity", "counts"],
        ["#legend", "Survey"],
        ["#acq_date", "2023/07/19 10:11:12"],
        ["##comment", "AES(JEOL)spectrum"],
    ]
    expected = [
        "#title,Survey",
        "#dimension,x,y",
        "#x,Kinetic Energy,eV",
        "#y,Intensity,counts",
        "#legend,Survey",
        "#acq_date,2023/07/19 10:11:12",
        "##comment,AES(JEOL)spectrum",
        "",
        "Kinetic Energy,Intensity",
        "100.0,1234",
        "101.5,1300",
        "",
    ]
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", preamble=header, blank_line_after_preamble=True)
    assert path.read_bytes() == NL.join(expected).encode("utf-8")


def test_graph_parser_reads_written_file__i628_ep_008(tmp_path: Path) -> None:
    """I628-EP-008: the metadata-header parser in ``rdetoolkit.graph`` reads the output."""
    from rdetoolkit.graph.parsers.base import CSVParser

    header = [["#title", "Survey"], ["#dimension", "x", "y"], ["#x", "Kinetic Energy", "eV"], ["#y", "Intensity", "counts"], ["#legend", "Survey"]]
    path = save_csv(_frame(), make_output_context(tmp_path), "data.csv", preamble=header)
    parsed, metadata = CSVParser().parse(path)
    assert metadata["title"] == "Survey"
    assert list(parsed[parsed.columns[1]]) == [1234, 1300]


def test_str_row_is_rejected__i628_neg_001(tmp_path: Path) -> None:
    """I628-NEG-001: a row given as one string is rejected rather than split into characters."""
    out = make_output_context(tmp_path)
    with pytest.raises(TypeError, match="preamble"):
        save_csv(_frame(), out, "data.csv", preamble=["#title,AES"])  # str is a Sequence, so only the runtime check rejects it
    assert not (out.struct / "data.csv").exists()


@pytest.mark.parametrize("preamble", [[], ""])
def test_empty_preamble_writes_nothing__i628_bv_001(tmp_path: Path, preamble: Sequence[Sequence[object]] | str) -> None:
    """I628-BV-001: an empty preamble adds no text."""
    frame = _frame()
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", preamble=preamble)
    assert path.read_text(encoding="utf-8") == frame.to_csv(index=False)


def test_one_field_and_empty_rows__i628_bv_002(tmp_path: Path) -> None:
    """I628-BV-002: a one-field row and an empty row each take one line."""
    frame = _frame()
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", preamble=[["#only"], []])
    assert path.read_text(encoding="utf-8") == f"#only{NL}{NL}" + frame.to_csv(index=False)


def test_blank_line_without_preamble_is_ignored__i628_bv_003(tmp_path: Path) -> None:
    """I628-BV-003: blank_line_after_preamble alone does not change the bytes."""
    frame = _frame()
    path = save_csv(frame, make_output_context(tmp_path), "data.csv", blank_line_after_preamble=True)
    assert path.read_bytes() == frame.to_csv(index=False).encode("utf-8")
