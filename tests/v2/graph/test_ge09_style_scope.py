"""GE-09 (#715): scoped Matplotlib style and safe ownership of internally created figures.

Intentional behaviour change IC-5 (versioned tests end in ``_v2_0``): ``csv2graph``,
``plot_from_dataframe`` and ``render_graph`` no longer leave the house style
(``font.size=20`` and friends) in the process-global ``matplotlib.rcParams``; every
figure the facade creates only to save it is closed after saving, also when the
writer fails; ``return_fig=True`` figures stay open and have a frozen layout so they
look the same when the caller saves them later. ``apply_matplotlib_config()`` keeps
its global effect (ruling C-08) and a direct ``MatplotlibRenderer.render_*`` call
keeps applying the style globally (ruling C-07, open item O-5).

Ownership (design §2.10): engine figures are ``Figure`` + ``FigureCanvasAgg`` and are
never registered with pyplot; the legacy facade closes its save-only figures in a
``finally``; ``return_fig`` figures belong to the caller; ``render_overlay`` /
``render_individual`` close the figure they created when they raise.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| style_scope | rc None / rc mapping | rcParams restored after the block; mapping applied inside | TC-GE09-EP-001 |
| new_figure | size given / None | pyplot-free Agg figure of that size / rcParams figsize | TC-GE09-EP-002 |
| new_figure | same drawing as plt.subplots | byte-identical PNG | TC-GE09-EP-003 |
| detach_figure + export_figure | export outside the scope | byte-identical to the export inside it | TC-GE09-EP-004 |
| detach_figure | tick params not set explicitly / set explicitly | pinned to the scoped rcParams / kept | TC-GE09-EP-014 |
| export_figure | png / svg / bbox None | format magic, no pyplot figure | TC-GE09-EP-005 |
| plot_from_dataframe | save-only | rcParams unchanged, no new figure, files written | TC-GE09-EP-006 |
| csv2graph | save-only | rcParams unchanged, no new figure | TC-GE09-EP-007 |
| plot_from_dataframe | return_fig=True | rcParams unchanged, figures open + drawable, caller can close | TC-GE09-EP-008 |
| plot_from_dataframe | return_fig figure saved outside the scope at dpi 300 | byte-identical to the legacy global-style PNG | TC-GE09-EP-009 |
| plot_from_dataframe | html=True save-only (Plotly figure is foreign) | HTML written, Matplotlib figures closed | TC-GE09-EP-010 |
| render_graph | output=None / output given | figures pyplot-free, rcParams unchanged | TC-GE09-EP-011 |
| MatplotlibRenderer direct call | legacy | global style still applied (C-07/O-5) | TC-GE09-EP-012 |
| all entry points | backend switching forbidden | mpl.use / switch_backend never called, backend unchanged | TC-GE09-EP-013 |

Negative / failure table:

| API | Failure | Expected | Test ID |
| --- | --- | --- | --- |
| style_scope | exception in the block | propagates, rcParams restored | TC-GE09-NEG-001 |
| plot_from_dataframe | FileWriter.save_figure raises OSError on the 2nd file | OSError, no figure left, rcParams restored | TC-GE09-NEG-002 |
| plot_from_dataframe | rendering fails after the overlay figure exists | error propagates, no figure left, rcParams restored | TC-GE09-NEG-003 |
| plot_from_dataframe | return_fig and detaching fails | error propagates, no figure left | TC-GE09-NEG-004 |
| plot_from_dataframe | collections carry a foreign (non-Matplotlib) figure | not closed, no AttributeError | TC-GE09-NEG-005 |
| render_overlay | failure after the figure was created | figure closed, error re-raised | TC-GE09-NEG-006 |
| render_individual | y_cols None (fails after the figure was created) | ValueError, figure closed | TC-GE09-NEG-007 |
| render_graph | rendering raises, with and without output | error propagates, rcParams restored, nothing pyplot-registered | TC-GE09-NEG-008 |
| export_figure | unsupported format | ValueError from Matplotlib | TC-GE09-NEG-009 |
| (no detach) | figure built in the scope, exported outside | export differs (why detach exists, T-4) | TC-GE09-NEG-011 |
| csv2graph | writer failure | OSError, no figure left, rcParams restored | TC-GE09-NEG-010 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| plot_from_dataframe | 300 series x 200 rows save-only | 301 saves of open figures, plt.get_fignums() unchanged | TC-GE09-BV-001 |
| plot_from_dataframe | 20 repeated save-only runs (real writer) | plt.get_fignums() unchanged after every run | TC-GE09-BV-002 |
| detach_figure | dpi 300 (default) / 150 | export at that dpi identical to the in-scope export; figure dpi restored | TC-GE09-EP-004 / TC-GE09-BV-003 |
"""

from __future__ import annotations

import importlib
import shutil
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.layout_engine import TightLayoutEngine

from rdetoolkit.graph import engine
from rdetoolkit.graph.api.csv2graph import csv2graph, plot_from_dataframe
from rdetoolkit.graph.config import DEFAULT_PLOT_PARAMS
from rdetoolkit.graph.io.file_writer import FileWriter
from rdetoolkit.graph.models import MatplotlibArtifact, PlotConfig, PlotMode, RenderCollections, RenderResult
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.renderers import mpl_runtime
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.mpl_runtime import detach_figure, export_figure, new_figure, style_scope
from rdetoolkit.graph.spec import GraphSpec, OutputSpec

FIXTURES = Path(__file__).parent / "fixtures"
# ``rdetoolkit.graph.api.csv2graph`` the attribute is the function; the seams live on the module.
csv2graph_module = importlib.import_module("rdetoolkit.graph.api.csv2graph")


def _multi_y() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "multi_unit.csv")


def _wide(series: int, rows: int) -> pd.DataFrame:
    """A deterministic wide table built from integer arithmetic (no random seed)."""
    data: dict[str, list[int]] = {"t (s)": list(range(rows))}
    for index in range(series):
        data[f"s{index:03d} (V)"] = [(row * (index + 1)) % 97 for row in range(rows)]
    return pd.DataFrame(data)


def _rc() -> dict[str, Any]:
    return dict(mpl.rcParams)


def _png(fig: Any) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
    return buffer.getvalue()


@pytest.fixture
def ambient() -> Iterator[dict[str, Any]]:
    """A non-default ambient style the caller owns; it must survive every call untouched."""
    with mpl.rc_context({"font.size": 7.0, "lines.linewidth": 3.0}):
        yield _rc()


# --- mpl_runtime -----------------------------------------------------------------


def test_style_scope_restores_rcparams__tc_ge09_ep_001(ambient: dict[str, Any]) -> None:
    """TC-GE09-EP-001: a mapping applies inside the scope only; None changes nothing."""
    # Given: the caller's ambient style
    # When: entering a scope with rc params and mutating rcParams inside it
    with style_scope({"font.size": 13.0}):
        inside = mpl.rcParams["font.size"]
        mpl.rcParams["axes.xmargin"] = 0.3
    # Then: the mapping was visible inside, and everything is restored after
    assert inside == 13.0
    assert _rc() == ambient
    with style_scope():
        assert _rc() == ambient
    assert _rc() == ambient


def test_style_scope_restores_rcparams_on_error__tc_ge09_neg_001(ambient: dict[str, Any]) -> None:
    """TC-GE09-NEG-001: the scope restores the style when the block raises."""
    # Given/When: a block that changes the style and fails
    with pytest.raises(RuntimeError, match="boom"), style_scope(dict(DEFAULT_PLOT_PARAMS)):
        mpl.rcParams["lines.linewidth"] = 9.0
        msg = "boom"
        raise RuntimeError(msg)
    # Then
    assert _rc() == ambient


@pytest.mark.parametrize(("size", "expected"), [((4.0, 3.0), (4.0, 3.0)), (None, (6.4, 4.8))])
def test_new_figure_is_pyplot_free__tc_ge09_ep_002(size: tuple[float, float] | None, expected: tuple[float, float]) -> None:
    """TC-GE09-EP-002: an Agg figure that pyplot does not know about."""
    # Given: no open pyplot figure
    before = plt.get_fignums()
    # When
    fig, ax = new_figure(size)
    # Then: a real Figure/Axes pair, never registered with pyplot
    assert isinstance(fig, Figure) and isinstance(ax, Axes) and ax.figure is fig
    assert isinstance(fig.canvas, FigureCanvasAgg)
    assert tuple(fig.get_size_inches()) == pytest.approx(expected)
    assert plt.get_fignums() == before
    # And: closing it through pyplot (what legacy callers do) is harmless
    plt.close(fig)


def test_new_figure_png_equals_plt_subplots__tc_ge09_ep_003() -> None:
    """TC-GE09-EP-003: the pyplot-free figure renders byte-identically to plt.subplots."""
    # Given: the same drawing on both kinds of figure, under the house style
    with style_scope(dict(DEFAULT_PLOT_PARAMS)):
        fig_a, ax_a = new_figure((8.85, 8))
        fig_b, ax_b = plt.subplots(figsize=(8.85, 8), tight_layout=True)
        for ax in (ax_a, ax_b):
            ax.plot([0, 1, 2], [3.0, 1.0, 2.0], label="v")
            ax.set_title("t")
            ax.legend()
        # When/Then
        assert export_figure(fig_a, "png", dpi=100) == export_figure(fig_b, "png", dpi=100)
    plt.close(fig_b)


def _house_figure(size: tuple[float, float]) -> Figure:
    """A small drawing whose layout depends on the (late-bound) house font size."""
    fig, ax = new_figure(size)
    ax.plot([0, 1, 2], [3.0, 1.0, 2.0], label="v")
    ax.set_title("t")
    ax.set_xlabel("time (s)")
    ax.legend()
    return fig


@pytest.mark.parametrize("size", [(8.85, 8.0), (4.0, 3.0)])
def test_detached_figure_exports_identically_outside_the_scope__tc_ge09_ep_004(size: tuple[float, float]) -> None:
    """TC-GE09-EP-004: after detach_figure, late-bound font sizes and layout are frozen."""
    # Given: two identical fresh figures under the house style; one is exported in the scope
    with style_scope(dict(DEFAULT_PLOT_PARAMS)):
        inside = export_figure(_house_figure(size), "png", dpi=300)
        fig = _house_figure(size)
        detach_figure(fig)
    # When: the caller exports the detached one later, with default rcParams
    outside = export_figure(fig, "png", dpi=300)
    # Then: identical bytes, no tight layout left and the figure dpi is untouched
    assert outside == inside
    assert not isinstance(fig.get_layout_engine(), TightLayoutEngine)
    assert fig.dpi == 100


def test_detach_pins_tick_style_but_keeps_explicit_choices__tc_ge09_ep_014() -> None:
    """TC-GE09-EP-014: ticks created later keep the scoped style; explicit tick params win."""
    # Given: the house style (inward ticks, 20 pt labels) and an explicit y tick choice
    with style_scope(dict(DEFAULT_PLOT_PARAMS)):
        fig = _house_figure((4.0, 3.0))
        fig.axes[0].tick_params(axis="y", direction="out", labelsize=7)
        detach_figure(fig)
    # When: read back outside the scope (default rcParams: outward ticks, "medium" labels)
    x_major = fig.axes[0].xaxis.get_tick_params(which="major")
    y_major = fig.axes[0].yaxis.get_tick_params(which="major")
    x_minor = fig.axes[0].xaxis.get_tick_params(which="minor")
    # Then: x took the scoped rcParams, y kept the explicit values
    assert (x_major["direction"], x_major["labelsize"]) == ("in", 20.0)
    assert x_minor["direction"] == "in"
    assert (y_major["direction"], y_major["labelsize"]) == ("out", 7)


def test_undetached_figure_changes_outside_the_scope__tc_ge09_neg_011() -> None:
    """TC-GE09-NEG-011: why detaching is needed (trap T-4): without it the export differs."""
    # Given: two identical figures, only one exported inside the scope
    with style_scope(dict(DEFAULT_PLOT_PARAMS)):
        inside = export_figure(_house_figure((8.85, 8.0)), "png", dpi=300)
        fig = _house_figure((8.85, 8.0))
    # When/Then: the late-bound title font size resolves against the default font.size
    assert export_figure(fig, "png", dpi=300) != inside


def test_detach_figure_at_another_dpi__tc_ge09_bv_003() -> None:
    """TC-GE09-BV-003: the layout is frozen at the dpi given; an export at that dpi matches."""
    # Given: a reference export at 150 dpi inside the scope
    with style_scope(dict(DEFAULT_PLOT_PARAMS)):
        inside = export_figure(_house_figure((4.0, 3.0)), "png", dpi=150)
        fig = _house_figure((4.0, 3.0))
        # When: detaching for 150 dpi
        detach_figure(fig, dpi=150)
    # Then
    assert export_figure(fig, "png", dpi=150) == inside
    assert fig.dpi == 100


@pytest.mark.parametrize(("fmt", "magic", "bbox"), [("png", b"\x89PNG", "tight"), ("svg", b"<?xml", "tight"), ("png", b"\x89PNG", None)])
def test_export_figure_formats__tc_ge09_ep_005(fmt: str, magic: bytes, bbox: str | None) -> None:
    """TC-GE09-EP-005: bytes of the requested format; nothing is pyplot-registered."""
    # Given
    fig, ax = new_figure((2.0, 2.0))
    ax.plot([0, 1], [0, 1])
    # When
    data = export_figure(fig, fmt, dpi=50, bbox_inches=bbox)
    # Then
    assert data.startswith(magic)
    assert plt.get_fignums() == []


def test_export_figure_rejects_an_unknown_format__tc_ge09_neg_009() -> None:
    """TC-GE09-NEG-009: Matplotlib's ValueError surfaces unchanged."""
    # Given
    fig, _ = new_figure((2.0, 2.0))
    # When/Then
    with pytest.raises(ValueError, match="not supported"):
        export_figure(fig, "nope", dpi=50)


# --- legacy facade -----------------------------------------------------------------


def test_plot_from_dataframe_save_only_leaks_nothing_v2_0__tc_ge09_ep_006(tmp_path: Path, ambient: dict[str, Any]) -> None:
    """TC-GE09-EP-006 (IC-5): no rcParams change and no open figure after a save-only run."""
    # Given: the caller's style and figure list
    before = plt.get_fignums()
    # When
    result = plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", title="cell")
    # Then: three files, nothing left behind
    assert result is None
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["cell.png", "cell_current_(a).png", "cell_voltage_(v).png"]
    assert plt.get_fignums() == before
    assert _rc() == ambient


def test_csv2graph_save_only_leaks_nothing_v2_0__tc_ge09_ep_007(tmp_path: Path, ambient: dict[str, Any]) -> None:
    """TC-GE09-EP-007 (IC-5): the CSV entry point is scoped too."""
    # Given: a fixture copied into tmp_path (repository-delta guard)
    csv_path = tmp_path / "multi_unit.csv"
    shutil.copy(FIXTURES / "multi_unit.csv", csv_path)
    before = plt.get_fignums()
    # When
    csv2graph(csv_path, output_dir=tmp_path / "out")
    # Then
    assert len(list((tmp_path / "out").iterdir())) == 3
    assert plt.get_fignums() == before
    assert _rc() == ambient


def test_plot_from_dataframe_return_fig_is_caller_owned_v2_0__tc_ge09_ep_008(tmp_path: Path, ambient: dict[str, Any]) -> None:
    """TC-GE09-EP-008 (IC-5): returned figures stay open and drawable; the style does not leak."""
    # Given
    before = set(plt.get_fignums())
    # When
    artifacts = plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", title="cell", return_fig=True)
    # Then: one open figure per artifact, frozen layout, nothing written, no leak
    assert artifacts is not None and len(artifacts) == 3
    assert all(isinstance(a, MatplotlibArtifact) and isinstance(a.figure, Figure) for a in artifacts)
    assert set(plt.get_fignums()) - before == {a.figure.number for a in artifacts}
    assert all(not isinstance(a.figure.get_layout_engine(), TightLayoutEngine) for a in artifacts)
    assert not (tmp_path / "out").exists()
    assert _rc() == ambient
    # And: the house style was baked in at draw time (frozen font size)
    assert artifacts[0].figure.axes[0].title.get_fontsize() == pytest.approx(20 * 1.2)
    artifacts[0].figure.canvas.draw()
    # And: the caller closes them the usual way
    for artifact in artifacts:
        plt.close(artifact.figure)
    assert set(plt.get_fignums()) == before


def test_return_fig_png_equals_the_legacy_global_style_png_v2_0__tc_ge09_ep_009(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE09-EP-009: a returned figure saved later matches the pre-GE-09 legacy output."""
    # Given: the exact request the facade builds, captured from its collect call
    captured: list[tuple[pd.DataFrame, PlotConfig, PlotMode]] = []
    original = csv2graph_module.collect_render_results

    def spy(df: pd.DataFrame, config: PlotConfig, mode: PlotMode) -> RenderCollections:
        captured.append((df, config, mode))
        return original(df, config, mode)

    monkeypatch.setattr(csv2graph_module, "collect_render_results", spy)
    artifacts = plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", title="cell", return_fig=True)
    assert artifacts is not None
    # When: the caller saves outside any scope, with default rcParams
    returned = [_png(a.figure) for a in artifacts]
    # Then: identical to the legacy behaviour (global style left in place, saved afterwards)
    df, config, mode = captured[0]
    with mpl.rc_context():
        legacy = original(df, config, mode)
        reference = [_png(r.figure) for r in legacy.all_results()]
        for result in legacy.all_results():
            plt.close(result.figure)
    assert returned == reference


def test_html_save_only_closes_matplotlib_figures__tc_ge09_ep_010(tmp_path: Path, ambient: dict[str, Any]) -> None:
    """TC-GE09-EP-010: Plotly figures are foreign and skipped; Matplotlib ones are closed."""
    # Given: Plotly is available
    pytest.importorskip("plotly")
    before = plt.get_fignums()
    # When
    plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", html=True, title="cell")
    # Then: the HTML and the PNGs exist, nothing is left open
    names = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert "cell.html" in names and "cell.png" in names
    assert plt.get_fignums() == before
    assert _rc() == ambient


def test_writer_failure_closes_every_figure_v2_0__tc_ge09_neg_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ambient: dict[str, Any]) -> None:
    """TC-GE09-NEG-002: a failing writer leaves no figure and no style behind."""
    # Given: a writer that fails on the second file
    calls = {"n": 0}
    original = FileWriter.save_figure

    def flaky(self: FileWriter, figure: Any, output_dir: Path, filename: str, format_type: str = "png", **kwargs: Any) -> Path:
        calls["n"] += 1
        if calls["n"] == 2:
            msg = "disk full"
            raise OSError(msg)
        return original(self, figure, output_dir, filename, format_type, **kwargs)

    monkeypatch.setattr(FileWriter, "save_figure", flaky)
    before = plt.get_fignums()
    # When/Then: the error propagates with the first file written only
    with pytest.raises(OSError, match="disk full"):
        plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", title="cell")
    assert calls["n"] == 2
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["cell.png"]
    assert plt.get_fignums() == before
    assert _rc() == ambient


def test_csv2graph_writer_failure_cleans_up_v2_0__tc_ge09_neg_010(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ambient: dict[str, Any]) -> None:
    """TC-GE09-NEG-010: the CSV entry point cleans up the same way."""
    # Given
    csv_path = tmp_path / "multi_unit.csv"
    shutil.copy(FIXTURES / "multi_unit.csv", csv_path)

    def broken(self: FileWriter, *args: Any, **kwargs: Any) -> Path:
        msg = "read-only"
        raise OSError(msg)

    monkeypatch.setattr(FileWriter, "save_figure", broken)
    before = plt.get_fignums()
    # When/Then
    with pytest.raises(OSError, match="read-only"):
        csv2graph(csv_path, output_dir=tmp_path / "out")
    assert plt.get_fignums() == before
    assert _rc() == ambient


@pytest.mark.parametrize("return_fig", [False, True])
def test_render_failure_after_first_figure_cleans_up__tc_ge09_neg_003(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ambient: dict[str, Any], return_fig: bool,
) -> None:
    """TC-GE09-NEG-003: figures rendered before a failing one are closed too."""
    # Given: the first individual figure fails after the overlay figure was created
    original = MatplotlibRenderer.render_individual

    def failing(self: MatplotlibRenderer, *args: Any, **kwargs: Any) -> Figure:
        msg = "render failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(MatplotlibRenderer, "render_individual", failing)
    assert original is not failing
    before = plt.get_fignums()
    # When/Then
    with pytest.raises(RuntimeError, match="render failed"):
        plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", return_fig=return_fig)
    assert plt.get_fignums() == before
    assert _rc() == ambient
    assert not (tmp_path / "out").exists()


def test_return_fig_detach_failure_cleans_up__tc_ge09_neg_004(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ambient: dict[str, Any]) -> None:
    """TC-GE09-NEG-004: handles the caller never receives are closed."""
    # Given: detaching fails on the second figure
    calls = {"n": 0}
    original = csv2graph_module.detach_figure

    def flaky(fig: Figure) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            msg = "boom"
            raise RuntimeError(msg)
        original(fig)

    monkeypatch.setattr(csv2graph_module, "detach_figure", flaky)
    before = plt.get_fignums()
    # When/Then
    with pytest.raises(RuntimeError, match="boom"):
        plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", return_fig=True)
    assert plt.get_fignums() == before
    assert _rc() == ambient


def test_foreign_figures_are_not_closed__tc_ge09_neg_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE09-NEG-005 (C-04): a non-Matplotlib figure is saved and never closed."""
    # Given: collections with a stub figure that only knows write_html, plus one real figure
    written: list[Path] = []

    class StubFigure:
        def write_html(self, path: Path, **kwargs: Any) -> None:
            written.append(Path(path))
            Path(path).write_text("<html></html>", encoding="utf-8")

    real, _ = plt.subplots()
    collections = RenderCollections(
        overlay=[RenderResult(StubFigure(), "stub.html", "html"), RenderResult(real, "real.png", "png")],
        individual=[],
    )
    monkeypatch.setattr(csv2graph_module, "collect_render_results", lambda df, config, mode: collections)
    # When
    plot_from_dataframe(_multi_y(), output_dir=tmp_path / "out", html_output_dir=tmp_path / "html", html=True)
    # Then: the stub was used, the real figure closed, no AttributeError on the stub
    assert written == [tmp_path / "html" / "stub.html"]
    assert (tmp_path / "out" / "real.png").exists()
    assert not plt.fignum_exists(real.number)


# --- MatplotlibRenderer direct calls -----------------------------------------------------


def test_direct_render_overlay_keeps_the_legacy_global_style__tc_ge09_ep_012() -> None:
    """TC-GE09-EP-012 (C-07/O-5): the low-level class API still applies the style globally."""
    # Given: default rcParams
    config = PlotConfig(mode=PlotMode.OVERLAY, x_col=0, y_cols=[1])
    # When
    fig = MatplotlibRenderer().render_overlay(_multi_y(), config)
    # Then: documented legacy leak, and the figure is a pyplot figure owned by the caller
    assert mpl.rcParams["font.size"] == 20
    assert plt.fignum_exists(fig.number)


def test_render_overlay_closes_its_figure_on_failure__tc_ge09_neg_006(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE09-NEG-006: a failure after the figure exists closes it and re-raises."""
    # Given: axis configuration fails
    def broken(self: MatplotlibRenderer, *args: Any, **kwargs: Any) -> None:
        msg = "axes failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(MatplotlibRenderer, "_configure_axes", broken)
    config = PlotConfig(mode=PlotMode.OVERLAY, x_col=0, y_cols=[1])
    # When/Then
    with pytest.raises(RuntimeError, match="axes failed"):
        MatplotlibRenderer().render_overlay(_multi_y(), config)
    assert plt.get_fignums() == []


def test_render_individual_closes_its_figure_on_failure__tc_ge09_neg_007() -> None:
    """TC-GE09-NEG-007: the y_cols check runs after the figure exists; the figure is closed."""
    # Given: a config without y columns
    config = PlotConfig(mode=PlotMode.INDIVIDUAL, x_col=0, y_cols=None)
    # When/Then
    with pytest.raises(ValueError, match="y_cols must be specified"):
        MatplotlibRenderer().render_individual(_multi_y(), config, 1)
    assert plt.get_fignums() == []


# --- render_graph --------------------------------------------------------------------


def test_render_graph_figures_are_pyplot_free__tc_ge09_ep_011(tmp_path: Path, ambient: dict[str, Any]) -> None:
    """TC-GE09-EP-011: engine figures are never pyplot-registered; no style leak."""
    # Given
    before = plt.get_fignums()
    # When: in memory
    result = engine.render_graph(_multi_y(), GraphSpec(title="cell"))
    # Then: valid caller-owned figures that pyplot does not track
    assert len(result.artifacts) == 3
    assert all(isinstance(a.figure, Figure) and isinstance(a.figure.canvas, FigureCanvasAgg) for a in result.artifacts)
    assert plt.get_fignums() == before
    assert _rc() == ambient
    assert result.artifacts[0].figure.axes[0].title.get_fontsize() == pytest.approx(20 * 1.2)
    assert _png(result.artifacts[0].figure).startswith(b"\x89PNG")
    # When: written
    written = engine.render_graph(_multi_y(), GraphSpec(title="cell"), output=OutputSpec(DirectorySink(tmp_path / "out")))
    # Then
    assert len([a for a in written.artifacts if a.path]) == 3
    assert plt.get_fignums() == before
    assert _rc() == ambient


@pytest.mark.parametrize("to_disk", [False, True])
def test_render_graph_failure_restores_style__tc_ge09_neg_008(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ambient: dict[str, Any], to_disk: bool,
) -> None:
    """TC-GE09-NEG-008: a rendering failure leaks neither style nor figures."""
    # Given: the second figure fails while drawing (after the house style was applied)
    calls = {"n": 0}
    original = MatplotlibRenderer._configure_axes

    def flaky(self: MatplotlibRenderer, *args: Any, **kwargs: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            msg = "draw failed"
            raise RuntimeError(msg)
        original(self, *args, **kwargs)

    monkeypatch.setattr(MatplotlibRenderer, "_configure_axes", flaky)
    output = OutputSpec(DirectorySink(tmp_path / "out")) if to_disk else None
    # When/Then
    with pytest.raises(RuntimeError, match="draw failed"):
        engine.render_graph(_multi_y(), output=output)
    assert plt.get_fignums() == []
    assert _rc() == ambient
    assert not (tmp_path / "out").exists()


def test_no_entry_point_switches_the_backend__tc_ge09_ep_013(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE09-EP-013: rendering never calls mpl.use or plt.switch_backend."""
    # Given: backend switching is a hard error
    backend = mpl.get_backend()

    def forbidden(*args: Any, **kwargs: Any) -> None:
        msg = "backend switch attempted"
        raise AssertionError(msg)

    monkeypatch.setattr(mpl, "use", forbidden)
    monkeypatch.setattr(plt, "switch_backend", forbidden)
    # When: every entry point renders
    engine.render_graph(_multi_y())
    engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path / "engine")))
    plot_from_dataframe(_multi_y(), output_dir=tmp_path / "facade")
    plot_from_dataframe(_multi_y(), output_dir=tmp_path / "facade", return_fig=True)
    # Then
    assert mpl.get_backend() == backend


# --- volume ----------------------------------------------------------------------------


def test_hundreds_of_series_leave_no_figure__tc_ge09_bv_001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ambient: dict[str, Any]) -> None:
    """TC-GE09-BV-001: 300 synthetic series x 200 rows, save-only, leave no figure handle."""
    # Given: a wide deterministic table and a writer that records instead of encoding 301
    # PNGs at 300 dpi (the figure lifecycle under test is unchanged, only the I/O is skipped)
    df = _wide(300, 200)
    saved: list[tuple[str, bool]] = []

    def record(self: FileWriter, figure: Any, output_dir: Path, filename: str, format_type: str = "png", **kwargs: Any) -> Path:
        saved.append((filename, plt.fignum_exists(figure.number)))
        return Path(output_dir) / filename

    monkeypatch.setattr(FileWriter, "save_figure", record)
    before = plt.get_fignums()
    # When
    plot_from_dataframe(df, output_dir=tmp_path / "out", title="wide")
    # Then: one overlay + one figure per series, each still open while saved, none left after
    assert len(saved) == 301 and len({name for name, _ in saved}) == 301
    assert all(open_while_saved for _, open_while_saved in saved)
    assert plt.get_fignums() == before
    assert _rc() == ambient


def test_repeated_save_only_runs_keep_fignums_flat__tc_ge09_bv_002(tmp_path: Path, ambient: dict[str, Any]) -> None:
    """TC-GE09-BV-002: the figure count does not grow across repeated runs."""
    # Given
    before = plt.get_fignums()
    df = _wide(2, 5)
    # When/Then: every run leaves the figure list as it was
    for run in range(20):
        plot_from_dataframe(df, output_dir=tmp_path / f"run{run:02d}", no_individual=True)
        assert plt.get_fignums() == before
    assert len(list(tmp_path.glob("run*/plot.png"))) == 20
    assert _rc() == ambient


def test_mpl_runtime_exports_its_public_surface() -> None:
    """The runtime module exposes exactly the functions design section 2.10 names for GE-09."""
    # Given/When/Then
    assert {"style_scope", "new_figure", "detach_figure", "export_figure"} <= set(mpl_runtime.__all__)
