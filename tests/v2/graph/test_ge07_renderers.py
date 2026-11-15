"""GE-07 (#713): renderer selection is injectable and extensible.

A ``GraphRenderer`` declares what it can produce (``RendererCapabilities``: formats,
figure kinds, optional modules, install hint). ``render_graph(renderers=...)`` takes an
explicit ``RendererRegistry``; without one, ``builtin_renderers()`` builds a fresh
registry (Matplotlib, then Plotly) for that call only, so renderer instances are scoped
to one graph operation and importing the package registers nothing. Each artifact is
routed to the first registered renderer whose capabilities cover its
``(format, figure kind)``; a format or kind nobody covers, and a missing optional
module, fail with a typed error during artifact planning, before any file or directory
exists. The legacy facade obtains its renderers from the same builtin registry and
still draws the overlay image through ``MatplotlibRenderer.render_overlay`` (C-06).

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| GraphRenderer | MatplotlibRenderer / PlotlyRenderer / test fake | isinstance True; declared capabilities exact | TC-GE07-EP-001 |
| builtin_renderers | two calls | ids (matplotlib, plotly); fresh registry and instances each call | TC-GE07-EP-002 |
| render_graph(renderers=) | fake renderer for "txt" | receives the executed plan, each figure and the data; bytes written; closed | TC-GE07-EP-003 |
| render_graph default | formats png + html, overlay | png by matplotlib in main_image, html by plotly in html_dir | TC-GE07-EP-004 |
| RendererRegistry.for_format | fake before / after matplotlib for png | first registered match wins | TC-GE07-EP-005 |
| render_graph output=None | default / fake registered first | matplotlib Figure / fake handle, renderer id recorded | TC-GE07-EP-006 |
| collect_render_results(renderers=) | recording MatplotlibRenderer subclass | its render_overlay called once, its render_individual per series | TC-GE07-EP-007 |
| OverlayStrategy(html_renderer=) | injected html adapter | used instead of the builtin Plotly renderer | TC-GE07-EP-008 |
| OverlayStrategy() | html requested, nothing injected | builtin Plotly figure for html, Matplotlib for png | TC-GE07-EP-008b |
| html artifact diagnostics | explicit rc_params / implicit | style_ignored info on the html artifact only / none | TC-GE07-EP-009 |
| RendererRegistry.register | replace=True | replaced in place, order kept | TC-GE07-EP-010 |
| import rdetoolkit.graph | fresh interpreter | plotly not imported, no registry or renderer held by any module | TC-GE07-EP-011 |
| default PNG | builtin registry injected explicitly vs default | byte-identical PNG | TC-GE07-EP-012 |
| PlotlyRenderer.export | html | the figure's HTML document as UTF-8 bytes | TC-GE07-EP-013 |

Boundary table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| RendererCapabilities | upper-case format names | normalized to lower case | TC-GE07-BV-001 |
| render_graph | layout="overlay" with html only | exactly one artifact (html) | TC-GE07-BV-002 |

Negative table:

| API | Failure | Expected | Test ID |
| --- | --- | --- | --- |
| render_graph | unknown format jpg / bmp | UnsupportedFormatError naming supported formats; no directory; nothing rendered | TC-GE07-NEG-001 |
| render_graph | html for individual figures | UnsupportedFormatError naming the kind; no directory | TC-GE07-NEG-002 |
| render_graph | plotly hidden (sys.modules entry None) | RendererUnavailableError (ImportError) with install hint; no directory, no png | TC-GE07-NEG-003 |
| plot_from_dataframe(html=True) | plotly hidden | RendererUnavailableError before rendering; no directory, no figure | TC-GE07-NEG-004 |
| collect_render_results | plotly hidden, html format | RendererUnavailableError before render_overlay runs | TC-GE07-NEG-005 |
| OverlayStrategy() | plotly hidden, html format | RendererUnavailableError before render_overlay runs | TC-GE07-NEG-005b |
| render_graph | fake requires a missing module | RendererUnavailableError carrying the fake's hint | TC-GE07-NEG-006 |
| check_requirements | dotted name under a missing package / imported module without spec | unavailable (no hint text without a hint) / available | TC-GE07-NEG-006b |
| RendererRegistry | non-renderer object / class | TypeError | TC-GE07-NEG-007 |
| RendererRegistry.register | duplicate id | ValueError mentioning replace=True | TC-GE07-NEG-008 |
| RendererCapabilities | empty id / no formats / unknown kind / non-str requires | ValueError | TC-GE07-NEG-009 |
| RendererRegistry.for_format | empty registry | UnsupportedFormatError | TC-GE07-NEG-010 |
| render_graph | renderers= not a RendererRegistry | TypeError | TC-GE07-NEG-011 |
| render_graph | export fails on the second figure | nothing written; every rendered handle closed | TC-GE07-NEG-012 |
| collect_render_results | selected renderer lacks render_overlay | TypeError before anything renders | TC-GE07-NEG-013 |
| render_graph output=None | no renderer covers individual | UnsupportedFormatError | TC-GE07-NEG-014 |
| render_graph output=None | render fails on the second figure | first handle closed through the renderer | TC-GE07-NEG-015 |
| PlotlyRenderer.render_html | go is None (C-14) | RendererUnavailableError, an ImportError, with install hint | TC-GE07-NEG-016 |
| PlotlyRenderer.export / MatplotlibRenderer.export | format outside capabilities | UnsupportedFormatError | TC-GE07-NEG-017 |
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.figure import Figure

import rdetoolkit.graph as graph_pkg
from rdetoolkit.graph import engine
from rdetoolkit.graph.api.csv2graph import plot_from_dataframe
from rdetoolkit.graph.exceptions import RendererError, RendererUnavailableError, UnsupportedFormatError
from rdetoolkit.graph.models import OutputConfig, PlotConfig, PlotMode, RenderResult
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan
from rdetoolkit.graph.renderers import plotly_renderer
from rdetoolkit.graph.renderers.base import GraphRenderer, RendererCapabilities
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.renderers.registry import RendererRegistry, builtin_renderers
from rdetoolkit.graph.spec import GraphSpec, OutputSpec, StyleSpec
from rdetoolkit.graph.strategies.all_graphs import OverlayStrategy
from rdetoolkit.graph.strategies.render_coordinator import collect_render_results

FIXTURES = Path(__file__).parent / "fixtures"
PLOTLY_HINT = 'pip install "rdetoolkit[plotly]"'


def _multi_y() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "multi_unit.csv")


@dataclass
class TextRenderer:
    """A third-party renderer written against the public protocol only (no rdetoolkit internals)."""

    renderer_id: str = "text"
    formats: frozenset[str] = frozenset({"txt"})
    kinds: frozenset[str] = frozenset({"overlay", "individual"})
    requires: tuple[str, ...] = ()
    install_hint: str = ""
    fail_export_on: int | None = None
    fail_render_on: int | None = None
    rendered: list[tuple[PlotPlan, FigurePlan, PlotData]] = field(default_factory=list)
    exported: list[tuple[str, str, int]] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)

    @property
    def capabilities(self) -> RendererCapabilities:
        return RendererCapabilities(
            renderer_id=self.renderer_id,
            formats=self.formats,
            figure_kinds=self.kinds,
            requires=self.requires,
            install_hint=self.install_hint,
        )

    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> dict[str, Any]:
        if self.fail_render_on is not None and len(self.rendered) + 1 == self.fail_render_on:
            msg = "render failed"
            raise RuntimeError(msg)
        self.rendered.append((plan, figure, data))
        labels = [entry.label for entry in plan.series if entry.series_id in figure.series_ids]
        return {"figure_id": figure.figure_id, "labels": labels}

    def export(self, handle: dict[str, Any], fmt: str, *, dpi: int) -> bytes:
        if self.fail_export_on is not None and len(self.exported) + 1 == self.fail_export_on:
            msg = "disk full"
            raise OSError(msg)
        self.exported.append((handle["figure_id"], fmt, dpi))
        return f"{handle['figure_id']}|{fmt}|{dpi}|{','.join(handle['labels'])}".encode()

    def close(self, handle: dict[str, Any]) -> None:
        self.closed.append(handle["figure_id"])


class RecordingMatplotlib(MatplotlibRenderer):
    """A MatplotlibRenderer subclass counting the legacy adapter calls (injected, not patched)."""

    def __init__(self) -> None:
        super().__init__()
        self.overlay_calls = 0
        self.individual_calls = 0

    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Figure:
        self.overlay_calls += 1
        return super().render_overlay(df, config)

    def render_individual(self, df: pd.DataFrame, config: PlotConfig, y_col_index: int, series_position: int | None = None) -> Figure:
        self.individual_calls += 1
        return super().render_individual(df, config, y_col_index, series_position)


def _legacy_config(formats: list[str], *, no_individual: bool = False) -> PlotConfig:
    return PlotConfig(
        mode=PlotMode.OVERLAY,
        x_col=0,
        y_cols=[1, 2],
        output=OutputConfig(base_name="cell", formats=formats, no_individual=no_individual),
    )


def _tree(path: Path) -> list[str]:
    return sorted(str(p.relative_to(path)) for p in path.rglob("*"))


def _hide_plotly(monkeypatch: pytest.MonkeyPatch) -> None:
    # A None entry makes both ``import plotly`` and ``importlib.util.find_spec("plotly")``
    # behave as if the optional extra were not installed, without uninstalling it.
    monkeypatch.setitem(sys.modules, "plotly", None)


# --------------------------------------------------------------------------- positive


@pytest.mark.parametrize(
    ("renderer", "expected"),
    [
        (MatplotlibRenderer(), RendererCapabilities("matplotlib", frozenset({"png", "svg", "pdf"}), frozenset({"overlay", "individual"}), applies_rc_params=True)),
        (PlotlyRenderer(), RendererCapabilities("plotly", frozenset({"html"}), frozenset({"overlay"}), requires=("plotly",), install_hint=PLOTLY_HINT)),
        (TextRenderer(), RendererCapabilities("text", frozenset({"txt"}), frozenset({"overlay", "individual"}))),
    ],
)
def test_renderers_conform_to_the_protocol__tc_ge07_ep_001(renderer: Any, expected: RendererCapabilities) -> None:
    """TC-GE07-EP-001: builtin and third-party renderers satisfy GraphRenderer and declare capabilities."""
    # Given/When: a renderer instance
    # Then: it is a GraphRenderer and declares exactly the expected capabilities
    assert isinstance(renderer, GraphRenderer)
    assert renderer.capabilities == expected


def test_builtin_renderers_are_fresh_per_call__tc_ge07_ep_002() -> None:
    """TC-GE07-EP-002: builtin registries are values; instances are scoped to one operation."""
    # Given/When: two builtin registries
    first, second = builtin_renderers(), builtin_renderers()
    # Then: same ids in a fixed order, but distinct registries and distinct renderer instances
    assert first.ids() == second.ids() == ("matplotlib", "plotly")
    assert first is not second
    assert first.for_format("png", "overlay") is not second.for_format("png", "overlay")
    assert type(first.for_format("png", "individual")) is MatplotlibRenderer
    assert type(first.for_format("html", "overlay")) is PlotlyRenderer
    # And: registering into one leaves the other untouched
    first.register(TextRenderer())
    assert first.ids() == ("matplotlib", "plotly", "text")
    assert second.ids() == ("matplotlib", "plotly")


def test_fake_renderer_is_injected_without_patching__tc_ge07_ep_003(tmp_path: Path) -> None:
    """TC-GE07-EP-003: a renderer written in the test receives the plan and produces the artifacts."""
    # Given: a registry holding only the fake renderer
    fake = TextRenderer()
    sink = DirectorySink(tmp_path / "out", main_image_dir=tmp_path / "main")
    # When: rendering overlay + individual figures as "txt"
    result = engine.render_graph(
        _multi_y(), GraphSpec(unit_policy="allow", title="cell"), output=OutputSpec(sink, formats=("txt",), base_name="cell", dpi=72),
        renderers=RendererRegistry([fake]),
    )
    # Then: the fake received the executed plan, every figure in plan order and the source data
    assert [figure for _, figure, _ in fake.rendered] == list(result.plan.figures)
    assert all(plan is result.plan for plan, _, _ in fake.rendered)
    assert all(list(data.frames[0].columns) == list(_multi_y().columns) for _, _, data in fake.rendered)
    assert fake.exported == [(f.figure_id, "txt", 72) for f in result.plan.figures]
    # And: every handle was closed after export, and the artifacts record the renderer
    assert fake.closed == [f.figure_id for f in result.plan.figures]
    assert [(a.renderer, a.role, a.format) for a in result.artifacts] == [
        ("text", "main_image", "txt"), ("text", "individual", "txt"), ("text", "individual", "txt"),
    ]
    assert _tree(tmp_path) == ["main", "main/cell.txt", "out", "out/cell_current_(a).txt", "out/cell_voltage_(v).txt"]
    overlay = result.plan.figures[0]
    assert (tmp_path / "main" / "cell.txt").read_bytes() == f"{overlay.figure_id}|txt|72|Voltage,Current".encode()


def test_png_and_html_route_by_capability__tc_ge07_ep_004(tmp_path: Path) -> None:
    """TC-GE07-EP-004: with the builtin registry PNG goes to Matplotlib and HTML to Plotly."""
    # Given: an overlay-only spec asking for png and html with separate directories
    sink = DirectorySink(tmp_path / "out", main_image_dir=tmp_path / "main", html_dir=tmp_path / "html")
    # When
    result = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), output=OutputSpec(sink, formats=("png", "html"), base_name="cell"))
    # Then: one artifact per format, each from the renderer declaring it, in its role directory
    assert [(a.renderer, a.role, a.format, a.path) for a in result.artifacts] == [
        ("matplotlib", "main_image", "png", (tmp_path / "main" / "cell.png").resolve()),
        ("plotly", "html", "html", (tmp_path / "html" / "cell.html").resolve()),
    ]
    assert (tmp_path / "main" / "cell.png").read_bytes().startswith(b"\x89PNG")
    html = (tmp_path / "html" / "cell.html").read_text(encoding="utf-8")
    assert html.lower().startswith("<!doctype html>") and "plotly" in html
    assert '"name":"Voltage"' in html and '"name":"Current"' in html
    assert _tree(tmp_path) == ["html", "html/cell.html", "main", "main/cell.png"]
    assert plt.get_fignums() == []


@pytest.mark.parametrize("fake_first", [True, False])
def test_first_registered_match_wins__tc_ge07_ep_005(fake_first: bool) -> None:
    """TC-GE07-EP-005: selection follows registration order among renderers covering the request."""
    # Given: a fake that also claims png, registered before or after Matplotlib
    fake = TextRenderer(renderer_id="fakepng", formats=frozenset({"png"}))
    mpl_renderer = MatplotlibRenderer()
    registry = RendererRegistry([fake, mpl_renderer] if fake_first else [mpl_renderer, fake])
    # When/Then
    assert registry.for_format("png", "overlay") is (fake if fake_first else mpl_renderer)
    assert registry.for_format("PNG", "individual") is (fake if fake_first else mpl_renderer)
    assert registry.ids() == (("fakepng", "matplotlib") if fake_first else ("matplotlib", "fakepng"))


def test_in_memory_uses_the_first_renderer_covering_the_kind__tc_ge07_ep_006() -> None:
    """TC-GE07-EP-006: output=None hands over handles from the selected renderer."""
    # Given/When: the default registry, and a registry with the fake first
    default = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"))
    fake = TextRenderer()
    injected = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), renderers=RendererRegistry([fake, MatplotlibRenderer()]))
    # Then: Matplotlib figures by default, the fake's handle when it is registered first
    assert [(a.renderer, a.format, isinstance(a.figure, Figure)) for a in default.artifacts] == [("matplotlib", "figure", True)]
    assert [(a.renderer, a.format, a.figure) for a in injected.artifacts] == [
        ("text", "figure", {"figure_id": "overlay", "labels": ["Voltage", "Current"]}),
    ]
    # And: caller-owned handles are not closed by the engine
    assert fake.closed == []
    assert plt.get_fignums() == []


def test_collect_render_results_uses_the_injected_registry__tc_ge07_ep_007() -> None:
    """TC-GE07-EP-007: the legacy coordinator draws through the registry's renderer (C-06 adapters)."""
    # Given: a registry whose image renderer counts the legacy adapter calls
    recording = RecordingMatplotlib()
    config = _legacy_config(["png"])
    # When
    collections = collect_render_results(_multi_y(), config, PlotMode.OVERLAY, renderers=RendererRegistry([recording]))
    # Then: one overlay call, one individual call per series, and the legacy file names
    assert (recording.overlay_calls, recording.individual_calls) == (1, 2)
    assert [r.filename for r in collections.all_results()] == ["cell.png", "cell_voltage_(v).png", "cell_current_(a).png"]
    for result in collections.all_results():
        plt.close(result.figure)


def test_overlay_strategy_uses_the_injected_html_renderer__tc_ge07_ep_008() -> None:
    """TC-GE07-EP-008: OverlayStrategy takes its HTML renderer by injection."""

    # Given: an html adapter that records the call
    @dataclass
    class HtmlAdapter:
        calls: list[tuple[pd.DataFrame, PlotConfig]] = field(default_factory=list)

        def render_html(self, df: pd.DataFrame, config: PlotConfig) -> str:
            self.calls.append((df, config))
            return "html-handle"

    adapter = HtmlAdapter()
    frame = _multi_y()
    config = _legacy_config(["html"])
    # When: only html is requested
    results = OverlayStrategy(MatplotlibRenderer(), html_renderer=adapter).render(frame, config)
    # Then: the injected adapter produced the html result; no Matplotlib figure was needed
    assert results == [RenderResult(figure="html-handle", filename="cell.html", format="html")]
    assert adapter.calls == [(frame, config)]
    assert plt.get_fignums() == []


def test_overlay_strategy_defaults_to_the_builtin_html_renderer__tc_ge07_ep_008b() -> None:
    """TC-GE07-EP-008b: without injection the HTML figure comes from a builtin Plotly renderer."""
    # Given/When: an OverlayStrategy without html_renderer asked for png + html
    results = OverlayStrategy(MatplotlibRenderer()).render(_multi_y(), _legacy_config(["png", "html"]))
    # Then: a Matplotlib figure for png and a Plotly figure for html, legacy file names
    assert [(r.filename, r.format, type(r.figure).__module__.split(".")[0]) for r in results] == [
        ("cell.png", "png", "matplotlib"), ("cell.html", "html", "plotly"),
    ]
    plt.close(results[0].figure)


def test_style_ignored_is_reported_for_html_only__tc_ge07_ep_009(tmp_path: Path) -> None:
    """TC-GE07-EP-009: explicit rcParams cannot reach Plotly; the HTML artifact says so."""
    # Given: explicit rcParams and an implicit style
    styled = GraphSpec(unit_policy="allow", layout="overlay", style=StyleSpec(rc_params={"font.size": 9}))
    # When
    with_rc = engine.render_graph(_multi_y(), styled, output=OutputSpec(DirectorySink(tmp_path / "a"), formats=("png", "html")))
    plain = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), output=OutputSpec(DirectorySink(tmp_path / "b"), formats=("png", "html")))
    # Then: only the html artifact of the styled request carries one style_ignored info diagnostic
    png, html = with_rc.artifacts
    assert png.diagnostics == ()
    assert [(d.code, d.severity) for d in html.diagnostics] == [("style_ignored", "info")]
    assert "plotly" in html.diagnostics[0].message and "rc_params" in html.diagnostics[0].message
    # GE-11: the deliberately shared V + A axis adds one plan-level unit diagnostic to both runs
    assert [(d.code, d.severity) for d in with_rc.diagnostics] == [("unit_mismatch", "info"), ("style_ignored", "info")]
    assert [a.diagnostics for a in plain.artifacts] == [(), ()]
    assert [(d.code, d.severity) for d in plain.diagnostics] == [("unit_mismatch", "info")]


def test_register_replace_keeps_the_position__tc_ge07_ep_010() -> None:
    """TC-GE07-EP-010: replace=True swaps the renderer with the same id in place."""
    # Given: a builtin registry
    registry = builtin_renderers()
    replacement = TextRenderer(renderer_id="matplotlib", formats=frozenset({"png"}))
    # When
    registry.register(replacement, replace=True)
    # Then: the id keeps its first position and now resolves to the replacement
    assert registry.ids() == ("matplotlib", "plotly")
    assert registry.for_format("png", "overlay") is replacement
    with pytest.raises(UnsupportedFormatError, match="svg"):
        registry.for_format("svg", "overlay")


_IMPORT_CHECK = """
import sys
import rdetoolkit.graph
assert "plotly" not in sys.modules, "plotly imported by rdetoolkit.graph"
assert "rdetoolkit.graph.renderers.registry" not in sys.modules
from rdetoolkit.graph.renderers.base import GraphRenderer
from rdetoolkit.graph.renderers.registry import RendererRegistry
held = [
    (name, key)
    for name, module in sorted(sys.modules.items())
    if name.startswith("rdetoolkit.graph") and module is not None
    for key, value in vars(module).items()
    if not isinstance(value, type) and isinstance(value, (RendererRegistry, GraphRenderer))
]
assert not held, held
print("clean")
"""


def test_import_has_no_side_effects__tc_ge07_ep_011() -> None:
    """TC-GE07-EP-011: importing the package neither imports Plotly nor creates renderers."""
    # Given/When: a fresh interpreter importing the package and the registry module
    completed = subprocess.run([sys.executable, "-c", _IMPORT_CHECK], capture_output=True, text=True, check=False)
    # Then
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "clean"


def test_explicit_builtin_registry_gives_identical_png__tc_ge07_ep_012(tmp_path: Path) -> None:
    """TC-GE07-EP-012: injecting the builtin registry changes nothing about the image."""
    # Given/When: the same request with the default and an explicit builtin registry
    engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", title="cell"), output=OutputSpec(DirectorySink(tmp_path / "default"), base_name="cell"))
    engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", title="cell"), output=OutputSpec(DirectorySink(tmp_path / "explicit"), base_name="cell"), renderers=builtin_renderers())
    # Then: every file is byte-identical
    names = _tree(tmp_path / "default")
    assert names == ["cell.png", "cell_current_(a).png", "cell_voltage_(v).png"] == _tree(tmp_path / "explicit")
    for name in names:
        assert (tmp_path / "default" / name).read_bytes() == (tmp_path / "explicit" / name).read_bytes()


def test_plotly_export_returns_the_html_document__tc_ge07_ep_013() -> None:
    """TC-GE07-EP-013: PlotlyRenderer.export is the same document write_html would write."""
    # Given: a rendered overlay
    frame = _multi_y()
    renderer = PlotlyRenderer()
    result = engine.render_graph(frame, GraphSpec(unit_policy="allow", layout="overlay"), renderers=RendererRegistry([renderer]))
    handle = result.artifacts[0].figure
    # When
    content = renderer.export(handle, "html", dpi=300)
    # Then: valid UTF-8 HTML of the same figure (Plotly assigns a random div id per call)
    text = content.decode("utf-8")
    assert text.lower().startswith("<!doctype html>") and text.rstrip().endswith("</html>")
    assert result.artifacts[0].renderer == "plotly"
    assert [trace.name for trace in handle.data] == ["Voltage", "Current"]
    renderer.close(handle)


def test_capability_formats_are_lower_cased__tc_ge07_bv_001() -> None:
    """TC-GE07-BV-001: declared formats are matched case-insensitively."""
    # Given/When
    caps = RendererCapabilities("upper", frozenset({"PNG", "Svg"}), frozenset({"overlay"}))
    # Then
    assert caps.formats == frozenset({"png", "svg"})
    assert caps.supports("SVG", "overlay") and not caps.supports("png", "individual")


def test_html_only_overlay_writes_one_artifact__tc_ge07_bv_002(tmp_path: Path) -> None:
    """TC-GE07-BV-002: html alone needs no Matplotlib figure."""
    # Given/When
    result = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), output=OutputSpec(DirectorySink(tmp_path), formats=("html",)))
    # Then
    assert [(a.renderer, a.format) for a in result.artifacts] == [("plotly", "html")]
    assert _tree(tmp_path) == ["plot.html"]


# --------------------------------------------------------------------------- negative


@pytest.mark.parametrize("fmt", ["jpg", "bmp"])
def test_unknown_format_fails_before_rendering__tc_ge07_neg_001(fmt: str, tmp_path: Path) -> None:
    """TC-GE07-NEG-001: a format no renderer declares is rejected at planning."""
    # Given: a registry with a recording fake and the builtins' formats
    fake = TextRenderer()
    registry = RendererRegistry([fake, MatplotlibRenderer(), PlotlyRenderer()])
    # When/Then
    with pytest.raises(UnsupportedFormatError) as excinfo:
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow"), output=OutputSpec(DirectorySink(tmp_path / "out"), formats=("txt", fmt)), renderers=registry)
    message = str(excinfo.value)
    assert fmt in message and "['html', 'pdf', 'png', 'svg', 'txt']" in message
    assert isinstance(excinfo.value, (RendererError, ValueError))
    assert not (tmp_path / "out").exists()
    assert fake.rendered == []


def test_html_for_individual_figures_is_rejected__tc_ge07_neg_002(tmp_path: Path) -> None:
    """TC-GE07-NEG-002: Plotly declares overlay figures only (format matrix §3.8)."""
    # Given/When/Then: layout "both" asks for html individual figures
    with pytest.raises(UnsupportedFormatError, match=r"'html'.*individual") as excinfo:
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="both"), output=OutputSpec(DirectorySink(tmp_path / "out"), formats=("png", "html")))
    assert "layout='overlay'" in str(excinfo.value)
    assert not (tmp_path / "out").exists()
    assert plt.get_fignums() == []


def test_missing_plotly_fails_before_any_file__tc_ge07_neg_003(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE07-NEG-003: a missing optional dependency is reported with the install hint, before writing."""
    # Given: Plotly hidden
    _hide_plotly(monkeypatch)
    # When/Then: png comes first, so a late check would already have written it
    with pytest.raises(RendererUnavailableError) as excinfo:
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), output=OutputSpec(DirectorySink(tmp_path / "out"), formats=("png", "html")))
    assert isinstance(excinfo.value, ImportError)
    assert PLOTLY_HINT in str(excinfo.value) and "'plotly'" in str(excinfo.value)
    assert not (tmp_path / "out").exists()
    assert plt.get_fignums() == []


def test_legacy_html_without_plotly_fails_before_rendering__tc_ge07_neg_004(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE07-NEG-004: plot_from_dataframe(html=True) checks Plotly before drawing or writing."""
    # Given: Plotly hidden
    _hide_plotly(monkeypatch)
    # When/Then
    with pytest.raises(RendererUnavailableError, match=r"rdetoolkit\[plotly\]"):
        plot_from_dataframe(_multi_y(), tmp_path / "out", name="cell", html=True, html_output_dir=tmp_path / "html")
    assert _tree(tmp_path) == []
    assert plt.get_fignums() == []


def test_coordinator_checks_plotly_before_the_overlay__tc_ge07_neg_005(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE07-NEG-005: the legacy coordinator rejects before render_overlay runs."""
    # Given: Plotly hidden and a recording image renderer next to the Plotly renderer
    _hide_plotly(monkeypatch)
    recording = RecordingMatplotlib()
    # When/Then
    with pytest.raises(RendererUnavailableError):
        collect_render_results(_multi_y(), _legacy_config(["png", "html"]), PlotMode.OVERLAY, renderers=RendererRegistry([recording, PlotlyRenderer()]))
    assert (recording.overlay_calls, recording.individual_calls) == (0, 0)
    assert plt.get_fignums() == []


def test_overlay_strategy_checks_plotly_before_drawing__tc_ge07_neg_005b(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE07-NEG-005b: the strategy's default HTML renderer is checked before render_overlay runs."""
    # Given: Plotly hidden
    _hide_plotly(monkeypatch)
    recording = RecordingMatplotlib()
    # When/Then
    with pytest.raises(RendererUnavailableError, match=r"rdetoolkit\[plotly\]"):
        OverlayStrategy(recording).render(_multi_y(), _legacy_config(["png", "html"]))
    assert recording.overlay_calls == 0
    assert plt.get_fignums() == []


def test_fake_with_missing_requirement__tc_ge07_neg_006(tmp_path: Path) -> None:
    """TC-GE07-NEG-006: declared requirements are checked for every renderer, with its own hint."""
    # Given: a fake needing a module that does not exist
    fake = TextRenderer(requires=("rdetoolkit_ge07_absent_module",), install_hint="pip install text-renderer")
    # When/Then
    with pytest.raises(RendererUnavailableError, match="pip install text-renderer") as excinfo:
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow"), output=OutputSpec(DirectorySink(tmp_path / "out"), formats=("txt",)), renderers=RendererRegistry([fake]))
    assert "rdetoolkit_ge07_absent_module" in str(excinfo.value)
    assert not (tmp_path / "out").exists()
    assert fake.rendered == []


def test_requirement_lookup_edge_cases__tc_ge07_neg_006b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE07-NEG-006b: a missing parent package is missing; an imported spec-less module is present."""
    # Given: a module that exists only in sys.modules (no spec), and a dotted name under a missing package
    spec_less = type(sys)("rdetoolkit_ge07_runtime_module")
    spec_less.__spec__ = None
    monkeypatch.setitem(sys.modules, "rdetoolkit_ge07_runtime_module", spec_less)
    present = TextRenderer(requires=("rdetoolkit_ge07_runtime_module",))
    absent = TextRenderer(requires=("rdetoolkit_ge07_absent_pkg.sub",))
    # When/Then: the spec-less module satisfies the requirement, the dotted one does not
    result = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), output=OutputSpec(DirectorySink(tmp_path), formats=("txt",)), renderers=RendererRegistry([present]))
    assert [a.renderer for a in result.artifacts] == ["text"]
    with pytest.raises(RendererUnavailableError, match="rdetoolkit_ge07_absent_pkg.sub") as excinfo:
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow"), renderers=RendererRegistry([absent]))
    assert "install it with" not in str(excinfo.value)
    assert absent.rendered == []


@pytest.mark.parametrize("item", [object(), TextRenderer, "matplotlib"])
def test_registry_rejects_non_renderers__tc_ge07_neg_007(item: Any) -> None:
    """TC-GE07-NEG-007: only GraphRenderer instances can be registered."""
    # Given/When/Then
    with pytest.raises(TypeError, match="GraphRenderer instance"):
        RendererRegistry([item])
    with pytest.raises(TypeError, match="GraphRenderer instance"):
        RendererRegistry().register(item)


def test_registry_rejects_duplicate_ids__tc_ge07_neg_008() -> None:
    """TC-GE07-NEG-008: a second renderer with the same id needs replace=True."""
    # Given
    registry = RendererRegistry([TextRenderer()])
    # When/Then
    with pytest.raises(ValueError, match=r"'text' is already registered.*replace=True"):
        registry.register(TextRenderer())
    with pytest.raises(ValueError, match="already registered"):
        RendererRegistry([MatplotlibRenderer(), MatplotlibRenderer()])
    assert registry.ids() == ("text",)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"renderer_id": ""}, "renderer_id"),
        ({"renderer_id": 3}, "renderer_id"),
        ({"formats": frozenset()}, "formats"),
        ({"formats": frozenset({""})}, "formats"),
        ({"figure_kinds": frozenset()}, "figure_kinds"),
        ({"figure_kinds": frozenset({"dual_axis"})}, "figure_kinds"),
        ({"requires": ("",)}, "requires"),
        ({"requires": "plotly"}, "requires"),
    ],
)
def test_capabilities_reject_invalid_declarations__tc_ge07_neg_009(kwargs: dict[str, Any], match: str) -> None:
    """TC-GE07-NEG-009: a renderer cannot declare an unusable capability set."""
    # Given
    values: dict[str, Any] = {"renderer_id": "x", "formats": frozenset({"png"}), "figure_kinds": frozenset({"overlay"})}
    values.update(kwargs)
    # When/Then
    with pytest.raises(ValueError, match=match):
        RendererCapabilities(**values)


def test_empty_registry_supports_nothing__tc_ge07_neg_010() -> None:
    """TC-GE07-NEG-010: an empty registry says that no renderer is registered."""
    # Given/When/Then
    with pytest.raises(UnsupportedFormatError, match="no renderer is registered"):
        RendererRegistry().for_format("png", "overlay")
    with pytest.raises(UnsupportedFormatError, match="no renderer is registered"):
        RendererRegistry().for_kind("overlay")


@pytest.mark.parametrize("renderers", [[MatplotlibRenderer()], MatplotlibRenderer(), "matplotlib"])
def test_renderers_argument_must_be_a_registry__tc_ge07_neg_011(renderers: Any, tmp_path: Path) -> None:
    """TC-GE07-NEG-011: render_graph takes a RendererRegistry, nothing looser."""
    # Given/When/Then
    with pytest.raises(TypeError, match="RendererRegistry"):
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow"), output=OutputSpec(DirectorySink(tmp_path / "out")), renderers=renderers)
    assert not (tmp_path / "out").exists()


def test_export_failure_writes_nothing_and_closes_handles__tc_ge07_neg_012(tmp_path: Path) -> None:
    """TC-GE07-NEG-012: every figure is exported before the first write; handles never leak."""
    # Given: a fake whose second export fails
    fake = TextRenderer(fail_export_on=2)
    # When/Then
    with pytest.raises(OSError, match="disk full"):
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow"), output=OutputSpec(DirectorySink(tmp_path / "out"), formats=("txt",)), renderers=RendererRegistry([fake]))
    assert not (tmp_path / "out").exists()
    assert fake.closed == [figure.figure_id for _, figure, _ in fake.rendered] == ["overlay", "s000"]


def test_legacy_path_needs_legacy_adapters__tc_ge07_neg_013() -> None:
    """TC-GE07-NEG-013: a registry renderer without render_overlay cannot serve the legacy facade."""
    # Given: a png-capable fake without the legacy adapter methods
    fake = TextRenderer(formats=frozenset({"png"}))
    # When/Then
    with pytest.raises(TypeError, match=r"'text'.*render_overlay.*render_graph"):
        collect_render_results(_multi_y(), _legacy_config(["png"]), PlotMode.OVERLAY, renderers=RendererRegistry([fake]))
    assert fake.rendered == []
    assert plt.get_fignums() == []


def test_in_memory_without_a_renderer_for_the_kind__tc_ge07_neg_014() -> None:
    """TC-GE07-NEG-014: individual figures need a renderer declaring them, also in memory."""
    # Given/When/Then: Plotly declares overlay only
    with pytest.raises(UnsupportedFormatError, match="individual"):
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="individual"), renderers=RendererRegistry([PlotlyRenderer()]))


def test_in_memory_render_failure_closes_previous_handles__tc_ge07_neg_015() -> None:
    """TC-GE07-NEG-015: handles the caller never receives are closed through their renderer."""
    # Given: a fake failing on the second figure
    fake = TextRenderer(fail_render_on=2)
    # When/Then
    with pytest.raises(RuntimeError, match="render failed"):
        engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow"), renderers=RendererRegistry([fake]))
    assert fake.closed == ["overlay"]


def test_plotly_render_path_keeps_its_own_check__tc_ge07_neg_016(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE07-NEG-016: C-14 — the Plotly render path raises a typed ImportError when go is missing."""
    # Given: the module global go missing, as without the extra
    monkeypatch.setattr(plotly_renderer, "go", None)
    # When/Then
    with pytest.raises(RendererUnavailableError, match=r"rdetoolkit\[plotly\]") as excinfo:
        PlotlyRenderer().render_html(_multi_y(), _legacy_config(["html"]))
    assert isinstance(excinfo.value, ImportError)


def test_export_rejects_undeclared_formats__tc_ge07_neg_017() -> None:
    """TC-GE07-NEG-017: export honours the declared formats."""
    # Given: one handle per builtin renderer
    mpl_handle = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay")).artifacts[0].figure
    plotly = PlotlyRenderer()
    plotly_handle = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), renderers=RendererRegistry([plotly])).artifacts[0].figure
    # When/Then
    with pytest.raises(UnsupportedFormatError, match="html"):
        MatplotlibRenderer().export(mpl_handle, "html", dpi=100)
    with pytest.raises(UnsupportedFormatError, match="png"):
        plotly.export(plotly_handle, "png", dpi=100)


def test_public_surface_exports_ge07_names__tc_ge07_ep_014() -> None:
    """TC-GE07-EP-014: the GE-07 names are public and resolve to their defining modules."""
    # Given/When
    names = ("GraphRenderer", "RendererCapabilities", "RendererRegistry", "builtin_renderers", "RendererUnavailableError", "UnsupportedFormatError")
    # Then
    assert set(names) <= set(graph_pkg.__all__)
    assert graph_pkg.RendererRegistry is RendererRegistry
    assert graph_pkg.GraphRenderer is GraphRenderer
    assert graph_pkg.UnsupportedFormatError is UnsupportedFormatError
    stub = Path(graph_pkg.__file__).with_suffix(".pyi").read_text(encoding="utf-8")
    assert all(f"{name} as {name}" in stub for name in names)
