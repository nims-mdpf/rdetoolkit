"""``run --validate-only --explain`` previews graph inputs read-only and value-free (#735)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from tests.v2.contract.fixtures import _generate

_ARGS = ["run", "must_not_import:pipeline", "--validate-only", "--explain"]
_PRIVATE_COLUMN = "private_column_name"


def _schema() -> dict[str, Any]:
    return json.loads((Path(__file__).parents[3] / "src/rdetoolkit/static/registration-explain.schema.json").read_text())


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, files: dict[str, str]) -> Path:
    _generate.materialize_case(_generate.oracle_case(f"v1/{mode}/ok"), tmp_path)
    (tmp_path / "rdeconfig.yaml").write_text(f"system:\n  extended_mode: {mode}\n")
    (tmp_path / "must_not_import.py").write_text("raise RuntimeError('user module imported')\n")
    inputdata = tmp_path / "data" / "inputdata"
    for name, text in files.items():
        (inputdata / name).write_text(text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _explain_json(root: Path) -> dict[str, Any]:
    before = _tree(root)
    result = CliRunner().invoke(app, [*_ARGS, "--format", "json"])
    assert result.exit_code == 0, result.output
    assert _tree(root) == before
    payload: dict[str, Any] = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    return payload


def _files_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for tile in payload["graph_preview"]["tiles"] for item in tile["files"]}


def test_header_csv_is_detected_without_values__graph_p1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: an invoice-mode tile with a headed CSV next to a non-tabular raw file.
    root = _project(tmp_path, monkeypatch, "invoice", {"spectrum.csv": f"{_PRIVATE_COLUMN},y\n1,2\n3,4\n"})
    # When: explaining as JSON.
    payload = _explain_json(root)
    # Then: the standard reader is selected with its shape, and no header text leaks.
    graph = payload["graph_preview"]
    assert (graph["status"], graph["reason"]) == ("previewed", "pre_flow_snapshot")
    item = _files_by_name(payload)["spectrum.csv"]
    assert (item["status"], item["reader"], item["column_count"], item["data_rows"]) == ("detected", "standard", 2, 2)
    assert item["candidates"][0]["reader_id"] == "standard"
    assert "invoice_input.txt" not in _files_by_name(payload)
    assert _PRIVATE_COLUMN not in json.dumps(payload)


def test_mixed_inputs_are_previewed_per_tile__graph_p2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: MultiDataTile inputs mixing detectable, ambiguous, empty, TSV and non-tabular files.
    files = {
        "a_header.csv": "x,y\n1,2\n",
        "b_numeric.csv": "1,2\n3,4\n",
        "c_empty.csv": "",
        "d_tabs.tsv": "x\ty\n1\t2\n",
        "e_notes.txt": "x,y\n1,2\n",
    }
    root = _project(tmp_path, monkeypatch, "multidatatile", files)
    # When: explaining as JSON.
    payload = _explain_json(root)
    # Then: every tile is listed in tile order and each tabular file has its own outcome.
    tiles = payload["graph_preview"]["tiles"]
    assert [tile["index"] for tile in tiles] == list(range(payload["tile_count"]))
    by_name = _files_by_name(payload)
    assert set(by_name) == {"a_header.csv", "b_numeric.csv", "c_empty.csv", "d_tabs.tsv"}
    assert (by_name["a_header.csv"]["status"], by_name["a_header.csv"]["reader"]) == ("detected", "standard")
    ambiguous = by_name["b_numeric.csv"]
    assert (ambiguous["status"], ambiguous["reason"], ambiguous["reader"]) == ("ambiguous", "no_confident_candidate", None)
    assert {c["reader_id"] for c in ambiguous["candidates"]} == {"standard", "noheader"}
    assert (by_name["c_empty.csv"]["status"], by_name["c_empty.csv"]["reason"]) == ("unreadable", "empty_oversized_or_unreadable")
    assert (by_name["d_tabs.tsv"]["delimiter"], by_name["d_tabs.tsv"]["reader"]) == ("\t", "standard")


def test_archive_members_are_deferred__graph_p3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: RDEFormat, whose only CSV is a member of the unextracted input archive.
    root = _project(tmp_path, monkeypatch, "rdeformat", {})
    # When: explaining as JSON.
    payload = _explain_json(root)
    # Then: the CSV is listed but not sampled, and the preview says so.
    graph = payload["graph_preview"]
    assert (graph["status"], graph["reason"]) == ("deferred", "tabular_inputs_inside_archives")
    assert {item["status"] for item in _files_by_name(payload).values()} == {"skipped"}


@pytest.mark.parametrize("mode", ["invoice", "multidatatile", "smarttable", "excelinvoice"])
def test_no_tabular_inputs__graph_p4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    # Given: the stock fixtures, which carry no top-level CSV or TSV input.
    root = _project(tmp_path, monkeypatch, mode, {})
    # When: explaining as JSON.
    payload = _explain_json(root)
    # Then: the preview reports that there is nothing to detect.
    graph = payload["graph_preview"]
    assert (graph["status"], graph["reason"], graph["tiles"]) == ("no_tabular_inputs", "no_csv_or_tsv_inputs", [])


def test_graph_preview_is_deterministic__graph_p5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: several tabular tiles.
    _project(tmp_path, monkeypatch, "multidatatile", {"a.csv": "x,y\n1,2\n", "b.csv": "1,2\n3,4\n"})
    # When: explaining twice.
    first = CliRunner().invoke(app, [*_ARGS, "--format", "json"])
    second = CliRunner().invoke(app, [*_ARGS, "--format", "json"])
    # Then: the bytes are identical and keys are emitted in sorted order.
    assert first.exit_code == 0, first.output
    assert first.stdout == second.stdout
    assert first.stdout == json.dumps(json.loads(first.stdout), sort_keys=True, ensure_ascii=False) + "\n"


def test_text_output_names_reader_and_remedy__graph_p6(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: one detectable and one ambiguous CSV.
    root = _project(tmp_path, monkeypatch, "multidatatile", {"a.csv": "x,y\n1,2\n", "b.csv": "1,2\n3,4\n"})
    before = _tree(root)
    # When: explaining as text.
    result = CliRunner().invoke(app, _ARGS)
    # Then: the graph section shows the reader, the ambiguity, and how to resolve it.
    assert result.exit_code == 0, result.output
    assert "Graph preview: previewed (pre_flow_snapshot)" in result.stdout
    assert "a.csv: detected -> standard (confident_builtin_reader, 2 column(s))" in result.stdout
    assert "b.csv: ambiguous (no_confident_candidate)" in result.stdout
    assert "Remedy: name the reader with csv_format=<id> or --csv-format <id>." in result.stdout
    assert _tree(root) == before


def test_invalid_config_with_tabular_inputs_fails_before_detection__graph_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: tabular inputs, but an invalid mode setting.
    root = _project(tmp_path, monkeypatch, "invoice", {"a.csv": "x,y\n1,2\n"})
    (root / "rdeconfig.yaml").write_text("system:\n  extended_mode: typo\n")
    # When: explaining as JSON.
    result = CliRunner().invoke(app, [*_ARGS, "--format", "json"])
    # Then: one schema-valid failure envelope is printed, with no graph section.
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema())
    assert payload["status"] == "failed"
    assert "graph_preview" not in payload
