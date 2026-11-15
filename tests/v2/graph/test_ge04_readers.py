"""GE-04 (#710): a TableReader registry and an instrument-format extension seam.

A third-party reader implements the small ``TableReader`` protocol (``reader_id``,
``extensions``, ``read(path) -> TableData``) and is used through a caller-owned
``ReaderRegistry`` or through the ``rdetoolkit.graph.readers`` entry-point group,
without editing ``ParserFactory``. Selection is deterministic (caller registry, then
builtin ids, then entry points; ``auto`` = the one reader claiming the suffix) and
inspectable through the returned ``DetectionDecision``. Registries are values created
on demand: importing the package registers nothing.

The fake plugin lives in ``tests/v2/graph/fixtures/reader_plugin_pkg``; entry points
are simulated by patching ``registry.metadata.entry_points`` (no distribution is
installed).

EP table
========

| API | Partition | Expected | Test ID |
|---|---|---|---|
| render_graph | path + reader id + caller registry | instrument frame plotted, PNG written, decision forced | TC-GE04-EP-001 |
| render_graph | path + reader id from an entry point (instance target) | plotted without a caller registry | TC-GE04-EP-002 |
| discover_readers | entry point = zero-arg factory | factory called once, reader usable | TC-GE04-EP-003 |
| render_graph / read_table | auto + suffix claimed (caller registry, entry point, upper-case suffix) | claimant selected, decision not forced | TC-GE04-EP-004 |
| builtin_readers | two calls | same sorted ids, distinct instances, registering into one leaves the other | TC-GE04-EP-005 |
| builtin readers | standard / transpose / noheader / meta_block | frames equal the parser classes; provenance per column | TC-GE04-EP-006 |
| csv2graph | csv_format = entry-point id | PNGs written next to the input | TC-GE04-EP-007 |
| rdetoolkit plot | --csv-format builtin / auto / discovered id | exit 0, PNG written | TC-GE04-EP-008 |
| resolve_reader | caller registry shadows a builtin id | caller reader wins, evidence names the caller registry | TC-GE04-EP-009 |
| ReaderRegistry | register(replace=True), ids(), for_extension | replaced, sorted, suffix lookup sorted by id | TC-GE04-EP-010 |
| import rdetoolkit.graph.readers | fresh interpreter, entry points disabled | no entry-point access, no registry instance at module level | TC-GE04-EP-011 |
| DetectionDecision.explain | forced / auto | names the selection and its evidence | TC-GE04-EP-012 |
| TableData | mapping metadata | frozen copy, caller mutation does not leak | TC-GE04-EP-013 |
| csv2graph | default and upper-case legacy id | reads exactly like StandardParser | TC-GE04-EP-014 |
| read_table | auto, no claimant (str path) | content sniffing selects "standard" (header row over numbers) | TC-GE04-EP-015 |
| public surface | rdetoolkit.graph exports | GE-04 names exported and in the stub | TC-GE04-EP-016 |

Negative table
==============

| API | Partition | Expected | Test ID |
|---|---|---|---|
| ReaderRegistry | two readers with one id | DuplicateReaderError naming both targets | TC-GE04-NEG-001 |
| discover_readers | two entry points with one name | DuplicateReaderError naming both targets | TC-GE04-NEG-002 |
| discover_readers | entry point named like a builtin id | DuplicateReaderError naming plugin and builtin | TC-GE04-NEG-003 |
| discover_readers / register | id "auto" | DuplicateReaderError (reserved selector) | TC-GE04-NEG-004 |
| resolve_reader | unknown id | UnknownReaderError (InvalidCSVFormatError, ValueError) listing every id | TC-GE04-NEG-005 |
| ReaderRegistry.get / origin | unknown id | UnknownReaderError listing the registry ids | TC-GE04-NEG-006 |
| discovery | plugin import fails | discovery succeeds; ReaderPluginError only when requested; others usable | TC-GE04-NEG-007 |
| discovery | factory raises / target not a reader / id mismatch | ReaderPluginError with cause and both names | TC-GE04-NEG-008 |
| auto | two claimants | AmbiguousFormatError, .decision with both candidates, remedy, nothing written | TC-GE04-NEG-009 |
| auto | broken plugin + one healthy claimant | GraphUserWarning, healthy claimant selected | TC-GE04-NEG-010 |
| read_table | reader returns a non-TableData | TypeError naming the reader | TC-GE04-NEG-011 |
| ReaderRegistry.register | non-reader / reader class / empty id | TypeError / TypeError / ValueError | TC-GE04-NEG-012 |
| render_graph | DataFrame or TableData source + reader options | PlotRequestError(reason="contradictory_switches") | TC-GE04-NEG-013 |
| rdetoolkit plot | unknown id / conflicting entry points | exit 2, message lists ids / names both targets, nothing written | TC-GE04-NEG-014 |
| csv2graph | unknown csv_format | UnknownReaderError with the legacy prefix, nothing written | TC-GE04-NEG-015 |
| resolve_reader / read_table | reader neither str nor instance; path not str/Path | TypeError | TC-GE04-NEG-016 |
| TableData | provenance count differs from the frame width; empty id | ValueError | TC-GE04-NEG-017 |
| render_graph | missing input file | FileNotFoundError, nothing written | TC-GE04-NEG-018 |
| discover_readers | entry points change between calls | no module-level cache: second call sees the change | TC-GE04-NEG-019 |
| legacy ParserFactory | create("vendor.instrument") | still ValueError: ParserFactory keeps its three ids | TC-GE04-NEG-020 |

BV table
========

| API | Boundary | Expected | Test ID |
|---|---|---|---|
| discover_readers | zero entry points | empty registry | TC-GE04-BV-001 |
| auto | file without a suffix | no claimant -> default reader | TC-GE04-BV-002 |
| auto | caller registry and entry point claim with the same id | one candidate (caller wins), no ambiguity | TC-GE04-BV-003 |

Typing table (mypy --strict against the installed stubs)
========================================================

| Consumer | Partition | Expected | Test ID |
|---|---|---|---|
| vendor plugin + render_graph/read_table/resolve usage | valid | clean | TC-GE04-TYPE-EP-001 |
| render_graph | reader=3 | [arg-type] | TC-GE04-TYPE-NEG-001 |
| ReaderRegistry.register | object() | [arg-type] | TC-GE04-TYPE-NEG-002 |
| ColumnProvenance | source="bogus" | [arg-type] | TC-GE04-TYPE-NEG-003 |
| render_graph | readers=[reader] (not a registry) | [arg-type] | TC-GE04-TYPE-NEG-004 |
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
import warnings
from collections.abc import Iterator
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

import rdetoolkit.graph as graph_pkg
from rdetoolkit.graph import (
    AmbiguousFormatError,
    ColumnProvenance,
    DetectionDecision,
    DuplicateReaderError,
    FormatCandidate,
    GraphSpec,
    GraphUserWarning,
    InvalidCSVFormatError,
    OutputSpec,
    PlotRequestError,
    ReaderPluginError,
    ReaderRegistry,
    TableData,
    TableReader,
    UnknownReaderError,
    builtin_readers,
    discover_readers,
    read_table,
    render_graph,
)
from rdetoolkit.graph.api.csv2graph import csv2graph
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.parsers import CSVParser, NoHeaderParser, ParserFactory, StandardParser, TransposeParser
from rdetoolkit.graph.readers import READER_ENTRY_POINT_GROUP, registry, resolve_reader
from tests.v2.graph.fixtures.reader_plugin_pkg.vendor import InstrumentReader, ReturnsNoTableData

FIXTURES = Path(__file__).parent / "fixtures"
VENDOR = "tests.v2.graph.fixtures.reader_plugin_pkg.vendor"
BROKEN = "tests.v2.graph.fixtures.reader_plugin_pkg.broken"
INSTRUMENT_COLUMNS = ["time (s)", "signal (mV)"]


def _copy_fixture(name: str, directory: Path) -> Path:
    target = directory / name
    shutil.copyfile(FIXTURES / name, target)
    return target


def _ep(name: str, value: str) -> EntryPoint:
    return EntryPoint(name=name, value=value, group=READER_ENTRY_POINT_GROUP)


def _patch_entries(monkeypatch: pytest.MonkeyPatch, *entries: EntryPoint) -> list[str]:
    """Replace the installed reader entry points; return the list of requested groups."""
    calls: list[str] = []

    def fake_entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        calls.append(group)
        return entries if group == READER_ENTRY_POINT_GROUP else ()

    monkeypatch.setattr(registry.metadata, "entry_points", fake_entry_points)
    return calls


@pytest.fixture
def instrument(tmp_path: Path) -> Path:
    return _copy_fixture("sample.instrument", tmp_path)


@pytest.fixture
def no_entry_points(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    yield _patch_entries(monkeypatch)


def _written(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


# --- positive: the extension seam ---------------------------------------------------------


def test_custom_reader_through_a_caller_registry__tc_ge04_ep_001(instrument: Path, tmp_path: Path, no_entry_points: list[str]) -> None:
    """TC-GE04-EP-001: a third-party reader works through render_graph without editing ParserFactory."""
    # Given: a caller-owned registry holding the vendor reader
    readers = ReaderRegistry([InstrumentReader()])
    out = tmp_path / "out"
    # When: rendering the instrument file by reader id
    result = render_graph(instrument, GraphSpec(), output=OutputSpec(DirectorySink(out), base_name="run"),
                          reader="vendor.instrument", readers=readers)
    # Then: the vendor frame was planned, one PNG was written and the selection is recorded
    assert [series.label for series in result.plan.series] == ["Signal"]
    assert _written(out) == ["run.png"]
    assert (out / "run.png").read_bytes().startswith(b"\x89PNG")
    decision = result.detection
    assert isinstance(decision, DetectionDecision)
    assert (decision.selected, decision.forced) == ("vendor.instrument", True)
    assert "caller registry" in " ".join(decision.candidates[0].evidence)
    # And: a named id found in the caller registry never consults entry points
    assert no_entry_points == []


@pytest.mark.parametrize("target", [f"{VENDOR}:READER", f"{VENDOR}:make_reader"])
def test_entry_point_reader_is_used_by_id__tc_ge04_ep_002(target: str, instrument: Path, tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-EP-002: an installed entry point (instance or factory target) is selectable by id."""
    # Given: the vendor reader published as an entry point
    _patch_entries(monkeypatch, _ep("vendor.instrument", target))
    # When: rendering by id without any caller registry
    result = render_graph(instrument, output=OutputSpec(DirectorySink(tmp_path / "out")), reader="vendor.instrument")
    # Then: the entry-point reader produced the frame, and the evidence names the entry point
    assert _written(tmp_path / "out") == ["plot.png"]
    assert result.detection.selected == "vendor.instrument"  # type: ignore[union-attr]
    assert f"entry point 'vendor.instrument' = {target}" in result.detection.explain()  # type: ignore[union-attr]


def test_entry_point_factory_is_called_once_per_registry__tc_ge04_ep_003(instrument: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-EP-003: entry points load lazily, once per registry value."""
    # Given: a factory entry point that counts its calls
    calls: list[int] = []
    vendor = importlib.import_module(VENDOR)

    def counting_factory() -> InstrumentReader:
        calls.append(1)
        return vendor.InstrumentReader()

    monkeypatch.setattr(vendor, "make_reader", counting_factory)
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:make_reader"))
    # When: discovering, then asking twice
    readers = discover_readers()
    assert calls == []
    first = readers.get("vendor.instrument")
    second = readers.get("vendor.instrument")
    # Then: loaded once on first request, and it reads the file
    assert calls == [1]
    assert first is second
    assert list(first.read(instrument).frame.columns) == INSTRUMENT_COLUMNS


def test_auto_selects_the_reader_claiming_the_suffix__tc_ge04_ep_004(instrument: Path, tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-EP-004: under "auto" the one reader claiming the suffix is selected (caller or entry point)."""
    # Given/When: a caller registry claims ".instrument" (no entry points)
    _patch_entries(monkeypatch)
    by_caller, decision = resolve_reader("auto", instrument, readers=ReaderRegistry([InstrumentReader()]))
    # Then: selected without being forced
    assert (by_caller.reader_id, decision.selected, decision.forced) == ("vendor.instrument", "vendor.instrument", False)
    assert decision.candidates == (FormatCandidate("vendor.instrument", 1.0, decision.candidates[0].evidence),)
    assert "'.instrument'" in decision.candidates[0].evidence[0]
    # Given/When: only an entry point claims it, and the suffix is upper-case
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    upper = tmp_path / "RUN.INSTRUMENT"
    shutil.copyfile(instrument, upper)
    result = render_graph(upper)
    # Then: the entry point reader was chosen by suffix and the frame is the vendor frame
    assert result.detection.selected == "vendor.instrument"  # type: ignore[union-attr]
    assert result.detection.forced is False  # type: ignore[union-attr]
    assert [series.label for series in result.plan.series] == ["Signal"]
    assert read_table(instrument).reader_id == "vendor.instrument"


def test_builtin_readers_are_fresh_values__tc_ge04_ep_005() -> None:
    """TC-GE04-EP-005: builtin_readers() returns a new, independent registry per call."""
    # Given/When: two builtin registries
    first, second = builtin_readers(), builtin_readers()
    # Then: equal ids, no shared instances, and mutating one leaves the other alone
    assert first.ids() == second.ids() == ("meta_block", "noheader", "standard", "transpose")
    assert all(first.get(rid) is not second.get(rid) for rid in first.ids())
    first.register(InstrumentReader())
    assert "vendor.instrument" in first.ids()
    assert "vendor.instrument" not in second.ids()
    assert "vendor.instrument" not in builtin_readers().ids()
    # And: builtins claim no suffix (they are chosen by id or by content)
    assert all(first.get(rid).extensions == () for rid in second.ids())


@pytest.mark.parametrize(("reader_id", "parser", "content", "sources"), [
    ("standard", StandardParser, "time (s),voltage (V)\n0,0.0\n1,0.5\n", ["header", "header"]),
    ("standard", StandardParser, "x,,y\n0,1,2\n", ["header", "generated", "header"]),
    ("transpose", TransposeParser, "label,a,b\nx,0,1\ny,2,3\n", ["header", "header", "header"]),
    ("transpose", TransposeParser, ",a,b\nx,0,1\n", ["generated", "header"]),
    ("noheader", NoHeaderParser, "0,1,2\n1,3,4\n", ["generated", "generated", "generated"]),
])
def test_legacy_formats_read_like_the_parser_classes__tc_ge04_ep_006(
    reader_id: str, parser: type[Any], content: str, sources: list[str], tmp_path: Path,
) -> None:
    """TC-GE04-EP-006: builtin readers are thin adapters; frames equal the legacy parser output."""
    # Given: a file in the legacy format
    path = tmp_path / "table.csv"
    path.write_text(content, encoding="utf-8")
    # When: reading through the builtin reader
    data = read_table(path, reader=reader_id)
    # Then: the frame equals the parser class result, with one provenance entry per column
    pd.testing.assert_frame_equal(data.frame, parser().parse(path))
    assert data.reader_id == reader_id
    assert [entry.source for entry in data.columns] == sources
    assert [entry.name for entry in data.columns] == [str(name) for name in data.frame.columns]
    assert [entry.source_index for entry in data.columns] == list(range(len(sources)))


def test_meta_block_reader_carries_the_metadata__tc_ge04_ep_006b(tmp_path: Path) -> None:
    """TC-GE04-EP-006: the meta_block reader adapts CSVParser.parse and keeps its metadata."""
    # Given: a legacy metadata-block CSV
    path = tmp_path / "meta.csv"
    path.write_text("#title,Run 7\n#dimension,x,y\n#x,Time,s\n#y,Signal,V\n#legend,A\n0,1\n1,2\n", encoding="utf-8")
    # When
    data = read_table(path, reader="meta_block")
    # Then
    expected_frame, expected_meta = CSVParser.parse(path)
    pd.testing.assert_frame_equal(data.frame, expected_frame)
    assert dict(data.metadata) == expected_meta
    assert data.metadata["title"] == "Run 7"
    assert [(entry.name, entry.source) for entry in data.columns] == [("Time (s)", "metadata"), ("A (V)", "metadata")]


def test_csv2graph_reads_an_entry_point_format__tc_ge04_ep_007(instrument: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-EP-007: the legacy facade accepts a discovered reader id as csv_format."""
    # Given: the vendor entry point
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    # When: csv2graph with the vendor id
    csv2graph(instrument, csv_format="vendor.instrument")
    # Then: the overlay PNG is written next to the input (single series: no individual PNGs)
    assert _written(instrument.parent) == ["sample.instrument", "sample.png"]


@pytest.mark.parametrize(("fmt", "fixture", "expected"), [
    ("standard", "simple.csv", ["simple.csv", "simple.png"]),
    ("auto", "simple.csv", ["simple.csv", "simple.png"]),
    ("vendor.instrument", "sample.instrument", ["sample.instrument", "sample.png"]),
])
def test_cli_accepts_builtin_auto_and_discovered_ids__tc_ge04_ep_008(fmt: str, fixture: str, expected: list[str], tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-EP-008: --csv-format takes builtin ids, auto and entry-point ids."""
    # Given: the vendor entry point and a copied input
    from rdetoolkit.cli.app import app

    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    path = _copy_fixture(fixture, tmp_path)
    # When
    outcome = CliRunner().invoke(app, ["plot", str(path), "--csv-format", fmt])
    # Then
    assert outcome.exit_code == 0, outcome.output
    assert _written(tmp_path) == expected


class _ShadowStandard(InstrumentReader):
    def __init__(self) -> None:
        super().__init__(reader_id="standard", extensions=())


def test_caller_registry_takes_precedence_over_builtins__tc_ge04_ep_009(instrument: Path, no_entry_points: list[str]) -> None:
    """TC-GE04-EP-009: explicit precedence — caller registry, then builtin ids, then entry points."""
    # Given: a caller reader registered under a builtin id
    readers = ReaderRegistry([_ShadowStandard()])
    # When
    selected, decision = resolve_reader("standard", instrument, readers=readers)
    builtin, builtin_decision = resolve_reader("standard", instrument)
    # Then: the caller's reader wins and the decision says where it came from
    assert isinstance(selected, _ShadowStandard)
    assert decision.candidates[0].evidence[0].startswith("caller registry: ")
    assert not isinstance(builtin, _ShadowStandard)
    assert builtin_decision.candidates[0].evidence[0].startswith("builtin: ")
    assert no_entry_points == []


def test_registry_replace_ids_and_suffix_lookup__tc_ge04_ep_010() -> None:
    """TC-GE04-EP-010: replace=True swaps a reader; ids() and for_extension() are sorted."""
    # Given
    readers = ReaderRegistry([InstrumentReader(reader_id="zeta", extensions=(".instrument",)),
                              InstrumentReader(reader_id="alpha", extensions=(".instrument", ".inst"))])
    replacement = InstrumentReader(reader_id="zeta", extensions=(".zeta",))
    # When
    readers.register(replacement, replace=True)
    # Then
    assert readers.ids() == ("alpha", "zeta")
    assert readers.get("zeta") is replacement
    assert [reader.reader_id for reader in readers.for_extension(".INSTRUMENT")] == ["alpha"]
    assert [reader.reader_id for reader in readers.for_extension(".zeta")] == ["zeta"]
    assert readers.for_extension(".csv") == ()
    assert "zeta" in readers
    assert "missing" not in readers


_NO_IMPORT_TIME_REGISTRATION = """
import importlib, importlib.metadata as metadata, sys

def forbidden(*args, **kwargs):
    raise SystemExit("entry points were read at import time")

metadata.entry_points = forbidden
import rdetoolkit.graph as graph
from rdetoolkit.graph.readers import ReaderRegistry, TableReader
assert graph.ReaderRegistry is ReaderRegistry
names = [name for name in sorted(sys.modules) if name.startswith("rdetoolkit.graph.readers")]
assert names == ["rdetoolkit.graph.readers", "rdetoolkit.graph.readers.base", "rdetoolkit.graph.readers.builtin",
                 "rdetoolkit.graph.readers.detection", "rdetoolkit.graph.readers.registry"], names
for name in names:
    held = [key for key, value in vars(sys.modules[name]).items()
            if not isinstance(value, type) and isinstance(value, (ReaderRegistry, TableReader))]
    assert not held, (name, held)
print("clean")
"""


def test_import_performs_no_registration__tc_ge04_ep_011() -> None:
    """TC-GE04-EP-011: importing the readers package touches no entry point and holds no registry."""
    # Given: a fresh interpreter whose entry-point API fails if anything reads it
    # When: importing rdetoolkit.graph and the readers package
    completed = subprocess.run([sys.executable, "-c", _NO_IMPORT_TIME_REGISTRATION], capture_output=True, text=True, check=False)
    # Then: nothing read entry points and no module holds a registry or reader instance
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "clean"
    # And: two fresh registries are equal and unshared
    first, second = ReaderRegistry(), ReaderRegistry()
    assert first.ids() == second.ids() == ()
    first.register(InstrumentReader())
    assert second.ids() == ()


def test_decision_explain_names_selection_and_evidence__tc_ge04_ep_012(instrument: Path, no_entry_points: list[str]) -> None:
    """TC-GE04-EP-012: the decision is inspectable as text."""
    # Given/When
    _, forced = resolve_reader("noheader", instrument)
    _, auto = resolve_reader("auto", instrument, readers=ReaderRegistry([InstrumentReader()]))
    # Then
    assert "selected: noheader (forced)" in forced.explain()
    assert "builtin: " in forced.explain()
    assert "selected: vendor.instrument (auto)" in auto.explain()
    assert "claims the suffix '.instrument'" in auto.explain()


def test_table_data_metadata_is_a_frozen_copy__tc_ge04_ep_013() -> None:
    """TC-GE04-EP-013: TableData freezes metadata and columns."""
    # Given
    source = {"title": "run"}
    data = TableData(pd.DataFrame({"x": [1]}), "custom", [ColumnProvenance("x", "header", 0)], source)  # type: ignore[arg-type]
    # When
    source["title"] = "changed"
    # Then
    assert data.metadata["title"] == "run"
    assert isinstance(data.columns, tuple)
    with pytest.raises(TypeError):
        data.metadata["title"] = "x"  # type: ignore[index]
    assert isinstance(InstrumentReader(), TableReader)


@pytest.mark.parametrize("fmt", ["standard", "STANDARD"])
def test_csv2graph_legacy_ids_read_like_standard_parser__tc_ge04_ep_014(fmt: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-EP-014: csv2graph defaults and legacy (case-insensitive) ids read exactly as before."""
    # Given: entry-point access is forbidden — the legacy ids must not depend on plugins
    def forbidden(*, group: str) -> tuple[EntryPoint, ...]:
        raise AssertionError(group)

    monkeypatch.setattr(registry.metadata, "entry_points", forbidden)
    path = _copy_fixture("simple.csv", tmp_path)
    # When
    csv2graph(path, csv_format=fmt)  # type: ignore[arg-type]
    csv2graph(path)
    # Then
    assert _written(tmp_path) == ["simple.csv", "simple.png"]


def test_auto_without_claimant_reads_standard__tc_ge04_ep_015(tmp_path: Path, no_entry_points: list[str]) -> None:
    """TC-GE04-EP-015: "auto" with no suffix claimant detects the format from the content.

    No reader claims ``.csv``, so ``detect_table_format`` sniffs the sample: a text
    header row over numeric rows selects ``standard`` (not a fixed default reader).
    """
    # Given
    path = _copy_fixture("simple.csv", tmp_path)
    # When
    data = read_table(str(path))
    _, decision = resolve_reader("auto", path)
    # Then
    pd.testing.assert_frame_equal(data.frame, StandardParser().parse(path))
    assert (data.reader_id, decision.selected, decision.forced) == ("standard", "standard", False)
    # And: the selection comes from the content, not from a fallback
    assert decision.candidates[0].evidence[0] == "row 1 is all text and later rows contain numbers: a header row"
    assert no_entry_points == [READER_ENTRY_POINT_GROUP, READER_ENTRY_POINT_GROUP]


GE04_EXPORTS = ("TableReader", "TableData", "ColumnProvenance", "ReaderRegistry", "builtin_readers", "discover_readers",
                "read_table", "DetectionDecision", "FormatCandidate", "UnknownReaderError", "AmbiguousFormatError",
                "DuplicateReaderError", "ReaderPluginError")


def test_public_surface_exports_ge04_names__tc_ge04_ep_016() -> None:
    """TC-GE04-EP-016: the reader contract is public through rdetoolkit.graph and its stub."""
    # Given/When
    exported = set(graph_pkg.__all__)
    stub = Path(graph_pkg.__file__).with_suffix(".pyi").read_text(encoding="utf-8")
    # Then
    assert set(GE04_EXPORTS) <= exported
    assert all(f"{name} as {name}" in stub for name in GE04_EXPORTS)
    assert graph_pkg.ReaderRegistry is registry.ReaderRegistry
    assert "resolve_reader" not in exported


# --- negative -------------------------------------------------------------------------------


def test_conflicting_registrations_fail_naming_both__tc_ge04_neg_001() -> None:
    """TC-GE04-NEG-001: two readers with one id are rejected, naming both targets."""
    # Given/When/Then: at construction
    with pytest.raises(DuplicateReaderError) as caught:
        ReaderRegistry([InstrumentReader(), ReturnsNoTableData()])
    message = str(caught.value)
    assert "'vendor.instrument'" in message
    assert f"{VENDOR}.InstrumentReader" in message
    assert f"{VENDOR}.ReturnsNoTableData" in message
    # And: through register() the first registration is kept
    readers = ReaderRegistry([InstrumentReader()])
    with pytest.raises(DuplicateReaderError):
        readers.register(ReturnsNoTableData())
    assert type(readers.get("vendor.instrument")) is InstrumentReader


def test_two_entry_points_with_one_name_fail_closed__tc_ge04_neg_002(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-002: conflicting entry points fail discovery, naming both targets."""
    # Given
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"), _ep("vendor.instrument", f"{VENDOR}:make_reader"))
    # When/Then
    with pytest.raises(DuplicateReaderError) as caught:
        discover_readers()
    assert f"{VENDOR}:READER" in str(caught.value)
    assert f"{VENDOR}:make_reader" in str(caught.value)
    assert isinstance(caught.value, ValueError)


def test_entry_point_shadowing_a_builtin_fails__tc_ge04_neg_003(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """TC-GE04-NEG-003: an entry point may not take a builtin id."""
    # Given
    _patch_entries(monkeypatch, _ep("standard", f"{VENDOR}:READER"))
    # When/Then: discovery, and auto (which consults entry points) both fail closed
    with pytest.raises(DuplicateReaderError) as caught:
        discover_readers()
    assert f"{VENDOR}:READER" in str(caught.value)
    assert "rdetoolkit.graph.readers.builtin.StandardReader" in str(caught.value)
    with pytest.raises(DuplicateReaderError):
        resolve_reader("auto", tmp_path / "x.csv")


def test_auto_is_a_reserved_id__tc_ge04_neg_004(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-004: "auto" is the selector and can never be a reader id."""
    # Given/When/Then
    with pytest.raises(DuplicateReaderError, match="reserved"):
        ReaderRegistry([InstrumentReader(reader_id="auto")])
    _patch_entries(monkeypatch, _ep("auto", f"{VENDOR}:READER"))
    with pytest.raises(DuplicateReaderError, match="reserved"):
        discover_readers()


def test_unknown_id_lists_every_available_id__tc_ge04_neg_005(instrument: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-005: a missing reader fails clearly and lists caller, builtin and entry-point ids."""
    # Given
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    # When/Then
    with pytest.raises(UnknownReaderError) as caught:
        resolve_reader("nope", instrument, readers=ReaderRegistry([InstrumentReader(reader_id="mine")]))
    message = str(caught.value)
    assert message.startswith("Unsupported CSV format: 'nope'")
    assert "['auto', 'meta_block', 'mine', 'noheader', 'standard', 'transpose', 'vendor.instrument']" in message
    assert isinstance(caught.value, InvalidCSVFormatError)
    assert isinstance(caught.value, ValueError)


def test_registry_get_unknown_lists_its_ids__tc_ge04_neg_006() -> None:
    """TC-GE04-NEG-006: ReaderRegistry.get names the ids it has."""
    # Given/When/Then
    with pytest.raises(UnknownReaderError, match=r"^Unsupported CSV format: 'x'\. Available readers: \['meta_block', 'noheader', 'standard', 'transpose'\]$"):
        builtin_readers().get("x")
    with pytest.raises(UnknownReaderError, match=r"Available readers: \[\]"):
        ReaderRegistry().get("x")
    with pytest.raises(UnknownReaderError, match=r"^Unsupported CSV format: 'x'"):
        ReaderRegistry().origin("x")
    assert builtin_readers().origin("standard") == "rdetoolkit.graph.readers.builtin.StandardReader"


def test_broken_plugin_fails_only_when_requested__tc_ge04_neg_007(instrument: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-007: a plugin whose import fails is listed, and fails only when its id is requested."""
    # Given: one broken and one healthy entry point
    _patch_entries(monkeypatch, _ep("broken.reader", f"{BROKEN}:READER"), _ep("vendor.instrument", f"{VENDOR}:READER"))
    # When: discovering and using the healthy one
    readers = discover_readers()
    healthy, _ = resolve_reader("vendor.instrument", instrument)
    # Then: discovery succeeded, the healthy reader works, the broken one raises on request
    assert readers.ids() == ("broken.reader", "vendor.instrument")
    assert healthy.reader_id == "vendor.instrument"
    with pytest.raises(ReaderPluginError) as caught:
        readers.get("broken.reader")
    assert "'broken.reader'" in str(caught.value)
    assert f"{BROKEN}:READER" in str(caught.value)
    assert isinstance(caught.value.__cause__, ModuleNotFoundError)
    with pytest.raises(ReaderPluginError):
        read_table(instrument, reader="broken.reader")


@pytest.mark.parametrize(("name", "target", "fragment", "cause"), [
    ("vendor.instrument", f"{VENDOR}:make_failing_reader", "vendor licence file missing", RuntimeError),
    ("vendor.instrument", f"{VENDOR}:NOT_A_READER", "is not a TableReader", None),
    ("vendor.instrument", f"{VENDOR}:InstrumentReader.missing", "failed to load", AttributeError),
    ("vendor.instrument", f"{VENDOR}:make_mismatched_reader", "'not.the.entry.point.name'", None),
])
def test_invalid_plugin_targets_raise_reader_plugin_error__tc_ge04_neg_008(
    name: str, target: str, fragment: str, cause: type[BaseException] | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GE04-NEG-008: factory failures, non-readers and id mismatches are ReaderPluginError on request."""
    # Given
    _patch_entries(monkeypatch, _ep(name, target))
    readers = discover_readers()
    # When/Then
    with pytest.raises(ReaderPluginError) as caught:
        readers.get(name)
    assert fragment in str(caught.value)
    assert target in str(caught.value)
    assert (type(caught.value.__cause__) if cause else None) is cause


def test_two_suffix_claimants_are_ambiguous__tc_ge04_neg_009(instrument: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-009: two readers claiming the suffix under auto fail with the decision and a remedy."""
    # Given: one claimant in the caller registry and another as an entry point
    _patch_entries(monkeypatch, _ep("other.instrument", f"{VENDOR}:make_other_reader"))
    out = tmp_path / "out"
    # When/Then
    with pytest.raises(AmbiguousFormatError) as caught:
        render_graph(instrument, output=OutputSpec(DirectorySink(out)), readers=ReaderRegistry([InstrumentReader()]))
    decision = caught.value.decision
    assert isinstance(decision, DetectionDecision)
    assert decision.selected is None
    assert [candidate.reader_id for candidate in decision.candidates] == ["other.instrument", "vendor.instrument"]
    message = str(caught.value)
    assert "other.instrument" in message and "vendor.instrument" in message
    assert "--csv-format" in message and "reader=" in message
    assert isinstance(caught.value, InvalidCSVFormatError)
    assert not out.exists()


def test_broken_plugin_is_skipped_with_a_warning_under_auto__tc_ge04_neg_010(instrument: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-010: under auto a plugin that cannot load is skipped visibly, never silently."""
    # Given
    _patch_entries(monkeypatch, _ep("broken.reader", f"{BROKEN}:READER"), _ep("vendor.instrument", f"{VENDOR}:READER"))
    # When
    with pytest.warns(GraphUserWarning, match="broken.reader") as caught:
        selected, decision = resolve_reader("auto", instrument)
    # Then
    assert selected.reader_id == decision.selected == "vendor.instrument"
    assert len(caught) == 1


def test_reader_returning_a_non_table_fails__tc_ge04_neg_011(instrument: Path) -> None:
    """TC-GE04-NEG-011: the contract is checked at the seam."""
    # Given/When/Then
    with pytest.raises(TypeError, match=r"vendor\.instrument.*DataFrame"):
        read_table(instrument, reader=ReturnsNoTableData())


@pytest.mark.parametrize(("candidate", "error", "fragment"), [
    (object(), TypeError, "TableReader"),
    (InstrumentReader, TypeError, "instance"),
    (InstrumentReader(reader_id=""), ValueError, "non-empty"),
])
def test_register_rejects_non_readers__tc_ge04_neg_012(candidate: Any, error: type[Exception], fragment: str) -> None:
    """TC-GE04-NEG-012: only TableReader instances with a non-empty id can be registered."""
    # Given/When/Then
    with pytest.raises(error, match=fragment):
        ReaderRegistry().register(candidate)


@pytest.mark.parametrize("kwargs", [{"reader": "standard"}, {"readers": ReaderRegistry()}])
def test_reader_options_need_a_path_source__tc_ge04_neg_013(kwargs: dict[str, Any], tmp_path: Path) -> None:
    """TC-GE04-NEG-013: reader options on an in-memory source contradict it."""
    # Given
    frame = pd.DataFrame({"x": [0, 1], "y": [1, 2]})
    table = TableData(frame, "custom", (ColumnProvenance("x", "header", 0), ColumnProvenance("y", "header", 1)))
    for source in (frame, table):
        # When/Then
        with pytest.raises(PlotRequestError) as caught:
            render_graph(source, output=OutputSpec(DirectorySink(tmp_path / "out")), **kwargs)
        assert caught.value.reason == "contradictory_switches"
    assert not (tmp_path / "out").exists()
    # And: a TableData source without reader options renders
    assert render_graph(table).detection is None


def test_cli_rejects_unknown_and_conflicting_formats__tc_ge04_neg_014(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-014: --csv-format failures are usage errors that name the remedy."""
    from rdetoolkit.cli.app import app

    # Given
    path = _copy_fixture("simple.csv", tmp_path)
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    # When: an unknown id
    unknown = CliRunner().invoke(app, ["plot", str(path), "--csv-format", "bogus"])
    # Then
    assert unknown.exit_code == 2
    assert "bogus" in unknown.output
    assert "vendor.instrument" in unknown.output
    # When: the installed entry points conflict
    _patch_entries(monkeypatch, _ep("standard", f"{VENDOR}:READER"))
    conflict = CliRunner().invoke(app, ["plot", str(path), "--csv-format", "bogus"])
    # Then
    assert conflict.exit_code == 2
    assert "StandardReader" in conflict.output
    assert _written(tmp_path) == ["simple.csv"]


def test_csv2graph_unknown_format_keeps_the_legacy_prefix__tc_ge04_neg_015(tmp_path: Path, no_entry_points: list[str]) -> None:
    """TC-GE04-NEG-015: csv2graph's unknown format is still a ValueError with the legacy prefix."""
    # Given
    path = _copy_fixture("simple.csv", tmp_path)
    # When/Then
    with pytest.raises(UnknownReaderError, match=r"^Unsupported CSV format: 'bogus'"):
        csv2graph(path, csv_format="bogus")
    assert _written(tmp_path) == ["simple.csv"]


def test_invalid_reader_arguments_are_type_errors__tc_ge04_neg_016(instrument: Path) -> None:
    """TC-GE04-NEG-016: reader must be an id or a reader instance; path must be str or Path."""
    # Given/When/Then
    with pytest.raises(TypeError, match="reader"):
        resolve_reader(3, instrument)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reader"):
        resolve_reader(InstrumentReader, instrument)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="path"):
        read_table(b"x.csv")  # type: ignore[arg-type]


@pytest.mark.parametrize(("reader_id", "columns"), [
    ("custom", ()),
    ("", (ColumnProvenance("x", "header", 0),)),
])
def test_table_data_rejects_inconsistent_values__tc_ge04_neg_017(reader_id: str, columns: tuple[ColumnProvenance, ...]) -> None:
    """TC-GE04-NEG-017: provenance must describe every column; the reader id is required."""
    # Given/When/Then
    with pytest.raises(ValueError, match="column|reader_id"):
        TableData(pd.DataFrame({"x": [1]}), reader_id, columns)


def test_missing_input_file_writes_nothing__tc_ge04_neg_018(tmp_path: Path, no_entry_points: list[str]) -> None:
    """TC-GE04-NEG-018: a missing input fails before any artifact exists."""
    # Given/When/Then
    with pytest.raises(FileNotFoundError):
        render_graph(tmp_path / "missing.csv", output=OutputSpec(DirectorySink(tmp_path / "out")))
    assert not (tmp_path / "out").exists()


def test_discovery_has_no_module_level_cache__tc_ge04_neg_019(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-019: each discover_readers() call reflects the installed entry points."""
    # Given/When
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    before = discover_readers().ids()
    _patch_entries(monkeypatch)
    after = discover_readers().ids()
    # Then
    assert (before, after) == (("vendor.instrument",), ())


def test_parser_factory_keeps_its_three_ids__tc_ge04_neg_020(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-NEG-020: the extension seam is the reader registry; ParserFactory is unchanged."""
    # Given
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    # When/Then
    with pytest.raises(ValueError, match="Supported formats: 'standard', 'transpose', 'noheader'"):
        ParserFactory.create("vendor.instrument")


# --- boundaries ---------------------------------------------------------------------------


def test_zero_entry_points_give_an_empty_registry__tc_ge04_bv_001(no_entry_points: list[str]) -> None:
    """TC-GE04-BV-001."""
    # Given/When
    readers = discover_readers()
    # Then
    assert readers.ids() == ()
    assert no_entry_points == [READER_ENTRY_POINT_GROUP]


def test_file_without_suffix_falls_back__tc_ge04_bv_002(tmp_path: Path, no_entry_points: list[str]) -> None:
    """TC-GE04-BV-002: an empty suffix is never claimed."""
    # Given
    path = tmp_path / "table"
    shutil.copyfile(FIXTURES / "simple.csv", path)
    # When
    _, decision = resolve_reader("auto", path, readers=ReaderRegistry([InstrumentReader(extensions=("",))]))
    # Then
    assert decision.selected == "standard"


def test_same_id_from_caller_and_entry_point_is_one_candidate__tc_ge04_bv_003(instrument: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE04-BV-003: a caller reader overrides an entry point of the same id; no ambiguity."""
    # Given
    _patch_entries(monkeypatch, _ep("vendor.instrument", f"{VENDOR}:READER"))
    mine = InstrumentReader()
    # When
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        selected, decision = resolve_reader("auto", instrument, readers=ReaderRegistry([mine]))
    # Then
    assert selected is mine
    assert len(decision.candidates) == 1
    assert decision.candidates[0].evidence[1].startswith("caller registry: ")


# --- typing of the public reader contract -----------------------------------------------

TYPED_CONSUMER = (FIXTURES / "reader_plugin_pkg" / "vendor.py").read_text(encoding="utf-8") + '''

from rdetoolkit.graph import DetectionDecision, GraphResult, ReaderRegistry, TableReader, read_table, render_graph


def use(path: Path) -> GraphResult:
    reader: TableReader = InstrumentReader()
    registry = ReaderRegistry([reader])
    registry.register(make_reader(), replace=True)
    ids: tuple[str, ...] = registry.ids()
    table: TableData = read_table(path, reader="vendor.instrument", readers=registry)
    first: ColumnProvenance = table.columns[0]
    result = render_graph(path, reader=reader)
    decision = result.detection
    assert ids and first.name and isinstance(decision, DetectionDecision)
    return render_graph(str(path), readers=registry)
'''


def _mypy(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )


def test_reader_contract_is_typed_for_plugin_authors__tc_ge04_type_ep_001(tmp_path: Path) -> None:
    """TC-GE04-TYPE-EP-001: a plugin written against the public names passes mypy --strict."""
    # Given/When
    result = _mypy(tmp_path, TYPED_CONSUMER)
    # Then
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("source", [
    "from pathlib import Path\nfrom rdetoolkit.graph import render_graph\nrender_graph(Path('a.csv'), reader=3)\n",
    "from rdetoolkit.graph import ReaderRegistry\nReaderRegistry().register(object())\n",
    "from rdetoolkit.graph import ColumnProvenance\nColumnProvenance('x', 'bogus', 0)\n",
    "from pathlib import Path\nfrom rdetoolkit.graph import builtin_readers, render_graph\n"
    "render_graph(Path('a.csv'), readers=[builtin_readers().get('standard')])\n",
])
def test_reader_contract_misuse_is_rejected__tc_ge04_type_neg(tmp_path: Path, source: str) -> None:
    """TC-GE04-TYPE-NEG-001..004: the stubs constrain reader, registry and provenance arguments."""
    # Given/When
    result = _mypy(tmp_path, source)
    # Then
    assert result.returncode == 1, result.stdout + result.stderr
    assert "[arg-type]" in result.stdout, result.stdout
