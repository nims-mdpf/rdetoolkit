"""Epic #703 (Graph Engine) acceptance check.

The epic acceptance criteria, exercised end to end through the public entry points
(``csv2graph`` and ``render_graph``) on the committed deterministic fixtures:

* the default ``csv2graph("simple.csv")`` works without options;
* an ambiguous input under ``auto`` fails with an explanation (candidates, evidence,
  remedy) and writes nothing;
* CSV/TSV, duplicate-label, multi-unit, transposed and large multi-series tables plot
  deterministically;
* PNG, SVG and HTML render, and HTML without Plotly fails typed before any file exists;
* every generated file is accounted for in the ``GraphResult`` manifest: nothing is
  omitted, and nothing is overwritten silently.

Fixtures are copied into ``tmp_path`` before plotting, because ``csv2graph`` writes
next to its CSV. The large multi-series table (300 series x 200 rows) is generated
from integer arithmetic and never committed.

EP table
========

| Entry point | Partition | Expected | Test ID |
|---|---|---|---|
| csv2graph | simple.csv, no options | exactly ``simple.png`` next to the CSV, a PNG | TC-GE-EPIC-EP-001 |
| csv2graph | simple.csv, ``csv_format="auto"`` | same single PNG as the default | TC-GE-EPIC-EP-002 |
| render_graph | tabs.tsv / simple.csv / duplicate_labels.csv / multi_unit.csv (split) / transposed.csv (split), auto reader | files on disk == manifest paths; detection recorded; second run gives the same manifest text | TC-GE-EPIC-EP-003 |
| render_graph | simple.csv, png + svg + html | PNG signature, SVG root, Plotly HTML; one artifact per format | TC-GE-EPIC-EP-004 |
| render_graph | 300 series x 200 rows, layout both | 301 artifacts, 300 unique individual names, files == manifest | TC-GE-EPIC-EP-005 |

BV table
========

| Entry point | Boundary | Expected | Test ID |
|---|---|---|---|
| render_graph | series names differing only by case (``Voltage`` / ``voltage``) | ``_s000`` / ``_s001`` suffixes, a ``filename_collision`` manifest diagnostic, both files listed | TC-GE-EPIC-BV-001 |
| render_graph | second run into the same directory, default ``on_existing`` | every artifact ``replaced_existing=True``, file set unchanged | TC-GE-EPIC-BV-002 |

Negative cases
==============

| Entry point | Partition | Expected | Test ID |
|---|---|---|---|
| csv2graph | numeric_header.csv, ``csv_format="auto"`` | ``AmbiguousFormatError`` (an ``InvalidCSVFormatError`` and a ``ValueError``) naming the candidates, evidence and remedy; no selection; only the CSV left | TC-GE-EPIC-NEG-001 |
| render_graph | numeric_header.csv, default ``reader="auto"`` | ``AmbiguousFormatError``; output directory never created | TC-GE-EPIC-NEG-002 |
| render_graph | empty.csv, auto | ``InvalidCSVFormatError``; nothing written | TC-GE-EPIC-NEG-003 |
| render_graph | Plotly hidden, png + html | ``RendererUnavailableError`` (an ``ImportError``) naming the install command; not even the PNG is written | TC-GE-EPIC-NEG-004 |
| csv2graph | Plotly hidden, ``html=True`` | ``ImportError`` before any figure file is written | TC-GE-EPIC-NEG-005 |
| render_graph | multi_unit.csv with the default ``unit_policy`` | ``PlotRequestError(reason="unit_mismatch")``; nothing written | TC-GE-EPIC-NEG-006 |
| render_graph | duplicate_labels.csv, html for individual figures | ``UnsupportedFormatError``; nothing written | TC-GE-EPIC-NEG-007 |
| render_graph | second run with ``on_existing="error"`` | ``ArtifactCollisionError``; the first run's bytes are unchanged | TC-GE-EPIC-NEG-008 |
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rdetoolkit.graph import (
    AmbiguousFormatError,
    ArtifactCollisionError,
    DirectorySink,
    FigurePlan,
    GraphResult,
    GraphSpec,
    InvalidCSVFormatError,
    OutputSpec,
    PlotData,
    PlotPlan,
    PlotRequestError,
    RendererCapabilities,
    RendererRegistry,
    RendererUnavailableError,
    UnsupportedFormatError,
    csv2graph,
    render_graph,
)
from rdetoolkit.graph.renderers import MatplotlibRenderer

FIXTURES = Path(__file__).parent / "fixtures"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PLOTLY_HINT = 'pip install "rdetoolkit[plotly]"'


def _copy(name: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy(FIXTURES / name, directory / name))


def _files(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def _manifest_files(result: GraphResult, root: Path) -> list[str]:
    paths = [artifact.path for artifact in result.artifacts]
    assert all(path is not None for path in paths)
    return sorted(path.relative_to(root).as_posix() for path in paths if path is not None)


def _hide_plotly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "plotly", None)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", None)


def _large_multiseries() -> pd.DataFrame:
    """300 series x 200 rows from integer arithmetic (deterministic, no random seed)."""
    columns: dict[str, list[int]] = {"index (s)": list(range(200))}
    for series in range(300):
        columns[f"channel {series:03d} (mV)"] = [(row * (series + 1)) % 97 for row in range(200)]
    return pd.DataFrame(columns)


class _TextIndividualRenderer:
    """A public-protocol renderer drawing individual figures as text (fast for 300 figures)."""

    @property
    def capabilities(self) -> RendererCapabilities:
        return RendererCapabilities(renderer_id="text", formats=frozenset({"png"}), figure_kinds=frozenset({"individual"}))

    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> dict[str, Any]:
        rows = [len(segment[2]) for entry in plan.series if entry.series_id in figure.series_ids for segment in data.segments(entry)]
        return {"figure_id": figure.figure_id, "rows": rows}

    def export(self, handle: dict[str, Any], fmt: str, *, dpi: int) -> bytes:
        return f"{handle['figure_id']}|{fmt}|{dpi}|{handle['rows']}".encode()

    def close(self, handle: dict[str, Any]) -> None:
        handle.clear()


# --- default csv2graph and auto -------------------------------------------------------------


def test_default_csv2graph_works_without_options__tc_ge_epic_ep_001(tmp_path: Path) -> None:
    """TC-GE-EPIC-EP-001: csv2graph("simple.csv") with no options writes its overlay PNG."""
    # Given: the simple fixture in an isolated directory
    csv_path = _copy("simple.csv", tmp_path)
    # When: plotting with every option at its default
    csv2graph(csv_path)
    # Then: exactly one PNG named after the CSV is written next to it
    assert _files(tmp_path) == ["simple.csv", "simple.png"]
    assert (tmp_path / "simple.png").read_bytes().startswith(PNG_SIGNATURE)


def test_csv2graph_auto_reads_an_unambiguous_file__tc_ge_epic_ep_002(tmp_path: Path) -> None:
    """TC-GE-EPIC-EP-002: csv_format="auto" on a clear file behaves like the default."""
    # Given: the simple fixture
    csv_path = _copy("simple.csv", tmp_path)
    # When: plotting with automatic format detection
    csv2graph(csv_path, csv_format="auto")
    # Then: the same single PNG is written
    assert _files(tmp_path) == ["simple.csv", "simple.png"]
    assert (tmp_path / "simple.png").read_bytes().startswith(PNG_SIGNATURE)


def test_csv2graph_auto_rejects_an_ambiguous_file_with_an_explanation__tc_ge_epic_neg_001(tmp_path: Path) -> None:
    """TC-GE-EPIC-NEG-001: an ambiguous input fails with candidates, evidence and remedy."""
    # Given: a fully numeric first row (header of numeric names, or first data row?)
    csv_path = _copy("numeric_header.csv", tmp_path)
    # When: plotting under auto
    with pytest.raises(AmbiguousFormatError) as excinfo:
        csv2graph(csv_path, csv_format="auto")
    # Then: the typed error explains the decision and nothing is written
    error = excinfo.value
    assert isinstance(error, InvalidCSVFormatError)
    assert isinstance(error, ValueError)
    message = str(error)
    assert "candidate noheader (0.50)" in message
    assert "candidate standard (0.50)" in message
    assert "every sampled row is numeric" in message
    assert "--csv-format" in message
    assert error.decision.selected is None
    assert sorted(candidate.reader_id for candidate in error.decision.candidates) == ["noheader", "standard"]
    assert _files(tmp_path) == ["numeric_header.csv"]


def test_render_graph_default_auto_rejects_an_ambiguous_file__tc_ge_epic_neg_002(tmp_path: Path) -> None:
    """TC-GE-EPIC-NEG-002: render_graph's default reader="auto" refuses to guess."""
    # Given: the ambiguous fixture and an output directory that does not exist yet
    csv_path = _copy("numeric_header.csv", tmp_path / "in")
    out = tmp_path / "out"
    # When: rendering with the default reader
    with pytest.raises(AmbiguousFormatError) as excinfo:
        render_graph(csv_path, output=OutputSpec(DirectorySink(out)))
    # Then: the decision says why, and the output directory was never created
    assert excinfo.value.decision.selected is None
    assert "Name the format" in str(excinfo.value)
    assert not out.exists()


def test_render_graph_auto_rejects_an_empty_file__tc_ge_epic_neg_003(tmp_path: Path) -> None:
    """TC-GE-EPIC-NEG-003: an empty file is an error, not an empty graph."""
    # Given: the empty fixture
    csv_path = _copy("empty.csv", tmp_path / "in")
    out = tmp_path / "out"
    # When: rendering under auto
    with pytest.raises(InvalidCSVFormatError) as excinfo:
        render_graph(csv_path, output=OutputSpec(DirectorySink(out)))
    # Then: it is not an ambiguity, and nothing is written
    assert not isinstance(excinfo.value, AmbiguousFormatError)
    assert not out.exists()


# --- deterministic fixtures and the manifest -------------------------------------------------


def _png_and_svg(*stems: str) -> list[str]:
    return sorted(f"{stem}.{fmt}" for stem in stems for fmt in ("png", "svg"))


SPLIT_STEMS = ("plot_v", "plot_a", "plot_voltage_(v)", "plot_current_(a)")


@pytest.mark.parametrize(("name", "spec", "selected", "expected"), [
    ("tabs.tsv", GraphSpec(), "standard", _png_and_svg("plot")),
    ("simple.csv", GraphSpec(), "standard", _png_and_svg("plot")),
    ("duplicate_labels.csv", GraphSpec(layout="both", unit_policy="allow"), "standard",
     _png_and_svg("plot", "plot_y", "plot_y.1", "plot_unnamed_s002", "plot_unnamed_s003")),
    ("multi_unit.csv", GraphSpec(unit_policy="split"), "standard", _png_and_svg(*SPLIT_STEMS)),
    ("transposed.csv", GraphSpec(unit_policy="split"), "transpose", _png_and_svg(*SPLIT_STEMS)),
], ids=["tsv", "csv", "duplicate-labels", "multi-unit", "transposed"])
def test_fixtures_render_deterministically_and_fully_accounted__tc_ge_epic_ep_003(
    tmp_path: Path, name: str, spec: GraphSpec, selected: str, expected: list[str],
) -> None:
    """TC-GE-EPIC-EP-003: every deterministic fixture plots, and files on disk == manifest."""
    # Given: the fixture, rendered twice into two separate directories
    csv_path = _copy(name, tmp_path / "in")
    results: list[GraphResult] = []
    for run in ("first", "second"):
        out = tmp_path / run
        # When: rendering PNG and SVG with the default auto reader
        results.append(render_graph(csv_path, spec, output=OutputSpec(DirectorySink(out), formats=("png", "svg"))))
    # Then: each run's files are exactly its manifest entries, and the runs agree
    for run, result in zip(("first", "second"), results, strict=True):
        assert _files(tmp_path / run) == expected
        assert _manifest_files(result, tmp_path / run) == expected
        assert all(not artifact.replaced_existing for artifact in result.artifacts)
    assert results[0].detection is not None
    assert results[0].detection.selected == selected
    assert results[0].manifest_json() == results[1].manifest_json()


def test_png_svg_and_html_render__tc_ge_epic_ep_004(tmp_path: Path) -> None:
    """TC-GE-EPIC-EP-004: static PNG, vector SVG and interactive HTML artifacts render."""
    # Given: the simple fixture
    csv_path = _copy("simple.csv", tmp_path / "in")
    out = tmp_path / "out"
    # When: rendering all three formats
    result = render_graph(csv_path, output=OutputSpec(DirectorySink(out), formats=("png", "svg", "html")))
    # Then: one artifact per format, by the expected renderer, with matching content
    assert [(a.format, a.renderer, a.role) for a in result.artifacts] == [
        ("png", "matplotlib", "main_image"), ("svg", "matplotlib", "main_image"), ("html", "plotly", "html"),
    ]
    assert _files(out) == ["plot.html", "plot.png", "plot.svg"] == _manifest_files(result, out)
    assert (out / "plot.png").read_bytes().startswith(PNG_SIGNATURE)
    assert b"<svg" in (out / "plot.svg").read_bytes()
    html = (out / "plot.html").read_bytes()
    assert b"plotly" in html
    assert b"<html" in html


def test_large_multiseries_is_fully_accounted__tc_ge_epic_ep_005(tmp_path: Path) -> None:
    """TC-GE-EPIC-EP-005: 300 series give 301 artifacts with unique names, all on disk."""
    # Given: the generated large table and a registry drawing individual figures as text
    frame = _large_multiseries()
    renderers = RendererRegistry([_TextIndividualRenderer(), MatplotlibRenderer()])
    out = tmp_path / "out"
    # When: rendering the overlay and every individual figure
    result = render_graph(
        frame, GraphSpec(layout="both"), output=OutputSpec(DirectorySink(out), formats=("png",), dpi=20), renderers=renderers,
    )
    # Then: one overlay + 300 individual artifacts, every name unique and every file listed
    individual = [a for a in result.artifacts if a.kind == "individual"]
    assert len(result.artifacts) == 301
    assert len(individual) == 300
    assert len({a.path for a in result.artifacts}) == 301
    assert _files(out) == _manifest_files(result, out)
    assert result.artifacts[0].renderer == "matplotlib"
    assert (out / "plot.png").read_bytes().startswith(PNG_SIGNATURE)
    assert {a.renderer for a in individual} == {"text"}
    assert (out / "plot_channel_000_(mv).png").read_bytes() == b"s000|png|20|[200]"
    assert (out / "plot_channel_299_(mv).png").read_bytes() == b"s299|png|20|[200]"


# --- no silent omission or overwrite ---------------------------------------------------------


def test_colliding_names_get_suffixes_and_are_listed__tc_ge_epic_bv_001(tmp_path: Path) -> None:
    """TC-GE-EPIC-BV-001: names differing only by case never overwrite each other."""
    # Given: two series whose individual file names collide case-insensitively
    frame = pd.DataFrame({"t": [0, 1, 2], "Voltage": [1, 2, 3], "voltage": [3, 2, 1]})
    out = tmp_path / "out"
    # When: rendering individual figures
    result = render_graph(frame, GraphSpec(layout="individual"), output=OutputSpec(DirectorySink(out)))
    # Then: both get their series id, both files exist and are listed, and the manifest says why
    expected = ["plot_voltage_s000.png", "plot_voltage_s001.png"]
    assert _files(out) == expected == _manifest_files(result, out)
    diagnostics = result.manifest()["diagnostics"]
    assert [(entry["code"], entry["severity"], entry["series_ids"]) for entry in diagnostics] == [
        ("filename_collision", "warning", ["s000", "s001"]),
    ]


def test_default_overwrite_is_recorded__tc_ge_epic_bv_002(tmp_path: Path) -> None:
    """TC-GE-EPIC-BV-002: a second run overwrites by default and says so per artifact."""
    # Given: a first run of the multi-unit fixture split per unit
    csv_path = _copy("multi_unit.csv", tmp_path / "in")
    out = tmp_path / "out"
    output = OutputSpec(DirectorySink(out))
    spec = GraphSpec(unit_policy="split")
    first = render_graph(csv_path, spec, output=output)
    # When: running the same request again into the same directory
    second = render_graph(csv_path, spec, output=output)
    # Then: the file set is unchanged and every replacement is recorded in the manifest
    expected = sorted(f"{stem}.png" for stem in SPLIT_STEMS)
    assert _files(out) == expected == _manifest_files(first, out) == _manifest_files(second, out)
    assert [a.replaced_existing for a in first.artifacts] == [False] * 4
    assert [a.replaced_existing for a in second.artifacts] == [True] * 4
    assert [entry["replaced_existing"] for entry in second.manifest()["artifacts"]] == [True] * 4


def test_on_existing_error_never_overwrites__tc_ge_epic_neg_008(tmp_path: Path) -> None:
    """TC-GE-EPIC-NEG-008: on_existing="error" refuses before rendering and keeps the bytes."""
    # Given: a first run of the simple fixture
    csv_path = _copy("simple.csv", tmp_path / "in")
    out = tmp_path / "out"
    render_graph(csv_path, output=OutputSpec(DirectorySink(out)))
    before = (out / "plot.png").read_bytes()
    # When: the same request is repeated with on_existing="error"
    with pytest.raises(ArtifactCollisionError) as excinfo:
        render_graph(csv_path, output=OutputSpec(DirectorySink(out), on_existing="error"))
    # Then: the error is a ValueError and the existing file is untouched
    assert isinstance(excinfo.value, ValueError)
    assert _files(out) == ["plot.png"]
    assert (out / "plot.png").read_bytes() == before


def test_mixed_units_default_policy_fails_before_writing__tc_ge_epic_neg_006(tmp_path: Path) -> None:
    """TC-GE-EPIC-NEG-006: a misleading mixed-unit overlay is refused, not drawn."""
    # Given: volts and amperes in one table
    csv_path = _copy("multi_unit.csv", tmp_path / "in")
    out = tmp_path / "out"
    # When: rendering with the default unit policy
    with pytest.raises(PlotRequestError) as excinfo:
        render_graph(csv_path, output=OutputSpec(DirectorySink(out)))
    # Then: the typed reason names the mismatch and nothing is written
    assert excinfo.value.reason == "unit_mismatch"
    assert "unit_policy='split'" in str(excinfo.value)
    assert not out.exists()


def test_html_for_individual_figures_is_refused__tc_ge_epic_neg_007(tmp_path: Path) -> None:
    """TC-GE-EPIC-NEG-007: an unsupported format/kind pair fails before any file exists."""
    # Given: the duplicate-label fixture with individual figures
    csv_path = _copy("duplicate_labels.csv", tmp_path / "in")
    out = tmp_path / "out"
    # When: requesting HTML for every figure
    with pytest.raises(UnsupportedFormatError) as excinfo:
        render_graph(
            csv_path, GraphSpec(layout="both", unit_policy="allow"), output=OutputSpec(DirectorySink(out), formats=("png", "html")),
        )
    # Then: the error names the alternative and nothing is written
    assert isinstance(excinfo.value, ValueError)
    assert "layout='overlay'" in str(excinfo.value)
    assert not out.exists()


# --- absent optional Plotly -------------------------------------------------------------------


def test_html_without_plotly_fails_before_any_file__tc_ge_epic_neg_004(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE-EPIC-NEG-004: HTML without Plotly is typed and actionable, and the PNG is not written."""
    # Given: Plotly is not importable
    _hide_plotly(monkeypatch)
    csv_path = _copy("simple.csv", tmp_path / "in")
    out = tmp_path / "out"
    # When: requesting PNG and HTML
    with pytest.raises(RendererUnavailableError) as excinfo:
        render_graph(csv_path, output=OutputSpec(DirectorySink(out), formats=("png", "html")))
    # Then: an ImportError naming the install command, and no output at all
    assert isinstance(excinfo.value, ImportError)
    assert PLOTLY_HINT in str(excinfo.value)
    assert not out.exists()


def test_csv2graph_html_without_plotly_fails_before_any_file__tc_ge_epic_neg_005(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GE-EPIC-NEG-005: csv2graph(html=True) without Plotly writes no figure."""
    # Given: Plotly is not importable
    _hide_plotly(monkeypatch)
    csv_path = _copy("simple.csv", tmp_path)
    # When: plotting with HTML
    with pytest.raises(ImportError) as excinfo:
        csv2graph(csv_path, html=True)
    # Then: the error names Plotly and only the CSV is in the directory
    assert "plotly" in str(excinfo.value).lower()
    assert _files(tmp_path) == ["simple.csv"]
