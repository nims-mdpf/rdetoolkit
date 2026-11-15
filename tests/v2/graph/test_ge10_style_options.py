"""GE-10 (#716): figure size and style options actually affect the rendered figure.

Intentional behaviour change IC-10 (versioned tests end in ``_v2_0``): the
``PlotConfigBuilder`` setters ``set_figure_size`` / ``set_matplotlib_params`` now
reach the renderer through ``PlotConfig.style`` (a ``StyleSpec``, ruling C-09: never
attributes named ``fig_size`` / ``matplotlib_params``), and ``GraphSpec.style`` drives
``render_graph``. Precedence, applied once per figure: ambient rcParams < engine
defaults (``DEFAULT_PLOT_PARAMS``, ``DEFAULT_FIG_SIZE``) < the explicit style. The
explicit rcParams apply to that call's figures only; a figure drawn with them is
detached so it keeps them when saved later. Without a style setter the output is
byte-identical to the legacy output. Validation happens when the plan is built, never
in the builder setters (ruling C-10).

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| builder -> render_overlay / render_individual | set_figure_size(4, 3) | Figure.get_size_inches() == (4, 3) | TC-GE10-EP-001 |
| builder -> collect_render_results | set_figure_size(5, 4) | every overlay and individual figure is 5 x 4 | TC-GE10-EP-001 |
| builder.build | no style setter / size only / params only | style None / size only / explicit overrides only; no fig_size attr | TC-GE10-EP-002 |
| render_graph(GraphSpec.style) | figure_size given, in memory and written | figure 5 x 4; PNG pixel size differs from the default | TC-GE10-EP-003 |
| render_graph(GraphSpec.style) | rc font.size=9 | figure texts 9 pt, rcParams unchanged afterwards | TC-GE10-EP-004 |
| builder -> render_overlay (direct) | rc font.size=9 | figure texts 9 pt; afterwards rcParams equal those of a style-less call | TC-GE10-EP-005 |
| precedence | explicit key over a default key | font.size 9 wins, other house defaults (inward ticks) stay | TC-GE10-EP-006 |
| default appearance | no style / explicit StyleSpec() | byte-identical to the legacy PNG | TC-GE10-EP-007 |
| explicit defaults | builder setters given the default values | byte-identical to the style-less legacy PNG | TC-GE10-EP-008 |
| Plotly render_html | explicit size / default | layout width/height = inches x 100 / not set | TC-GE10-EP-009 |
| detach + rc font.family | ticks created after leaving the scope | keep the scoped family | TC-GE10-EP-010 |
| validate_style | int sizes, valid keys | floats returned, mapping kept | TC-GE10-EP-011 |
| plan | explicit style | plan.style merged over defaults, origins explicit | TC-GE10-EP-012 |

Negative table:

| API | Failure | Expected | Test ID |
| --- | --- | --- | --- |
| validate_style | width/height 0, negative, NaN, inf, bool, str | PlotRequestError reason="invalid_figure_size" | TC-GE10-NEG-001 |
| validate_style | unknown key (with suggestion), non-str key | PlotRequestError reason="invalid_rc_param" | TC-GE10-NEG-002 |
| validate_style | denied key backend / backend_fallback / interactive / toolbar | PlotRequestError reason="invalid_rc_param" | TC-GE10-NEG-003 |
| validate_style | value the rcParam rejects (font.size="huge") | PlotRequestError reason="invalid_rc_param" | TC-GE10-NEG-004 |
| render_graph | invalid size with an output | raises before writing; no file, no pyplot figure, rcParams unchanged | TC-GE10-NEG-005 |
| builder -> render_overlay | (0, 0) size / unknown key accepted by setters (C-10) | build() succeeds; rendering raises before a figure exists | TC-GE10-NEG-006 |
| build_plot_plan | invalid style | raises at plan time | TC-GE10-NEG-007 |
| builder -> render_overlay | drawing fails inside the explicit style scope | figure closed, rcParams restored to the legacy global style | TC-GE10-NEG-008 |
| builder -> render_individual | freezing (detach) the styled figure fails | figure closed, error re-raised, rcParams restored | TC-GE10-NEG-009 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| validate_style | smallest positive sizes (1e-6), large (1000) | accepted | TC-GE10-BV-001 |
| validate_style | empty rc mapping | accepted, origin default | TC-GE10-BV-002 |
"""

from __future__ import annotations

import hashlib
import math
import struct
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.figure import Figure
from matplotlib.text import Text

from rdetoolkit.graph import engine
from rdetoolkit.graph.api.csv2graph import plot_from_dataframe
from rdetoolkit.graph.config import DEFAULT_FIG_SIZE, DEFAULT_PLOT_PARAMS, PlotConfigBuilder
from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.models import PlotConfig, PlotMode
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.plan import build_plot_plan
from rdetoolkit.graph.renderers import matplotlib_renderer
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.spec import GraphSpec, OutputSpec, StyleSpec
from rdetoolkit.graph.strategies.render_coordinator import collect_render_results
from rdetoolkit.graph.validation import validate_style

FIXTURES = Path(__file__).parent / "fixtures"


def _multi_y() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "multi_unit.csv")


def _builder() -> PlotConfigBuilder:
    return PlotConfigBuilder().set_columns(x_col=0, y_cols=[1, 2]).set_title("cell")


def _png(fig: Any) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
    return buffer.getvalue()


def _png_size(data: bytes) -> tuple[int, int]:
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _font_sizes(fig: Figure) -> set[float]:
    """Font sizes of every non-empty text the renderer drew."""
    return {text.get_fontsize() for text in fig.findobj(Text) if text.get_text()}


def _size(fig: Figure) -> tuple[float, float]:
    width, height = fig.get_size_inches()
    return float(width), float(height)


# --- builder path ---------------------------------------------------------------


def test_builder_figure_size_reaches_render_overlay_and_individual_v2_0__tc_ge10_ep_001() -> None:
    """TC-GE10-EP-001: set_figure_size changes the actual Figure dimensions."""
    # Given: a builder with a figure size
    config = _builder().set_figure_size(4, 3).build()
    renderer = MatplotlibRenderer()
    # When: rendering the overlay and one individual figure directly
    overlay = renderer.render_overlay(_multi_y(), config)
    individual = renderer.render_individual(_multi_y(), config, 2, 1)
    # Then: both have the requested size, not the legacy (8.85, 8)
    assert _size(overlay) == (4.0, 3.0)
    assert _size(individual) == (4.0, 3.0)


def test_builder_figure_size_reaches_every_strategy_figure_v2_0__tc_ge10_ep_001() -> None:
    """TC-GE10-EP-001: the strategy entry point renders every figure at the builder size."""
    # Given: a builder config with a size
    config = _builder().set_figure_size(5, 4).build()
    # When: rendering overlay plus individual figures through the coordinator
    collections = collect_render_results(_multi_y(), config, PlotMode.OVERLAY)
    figures = [result.figure for result in collections.all_results()]
    # Then: three figures (overlay + 2 individual), all 5 x 4
    assert len(figures) == 3
    assert [_size(fig) for fig in figures] == [(5.0, 4.0)] * 3


def test_builder_emits_style_only_when_a_setter_was_called__tc_ge10_ep_002() -> None:
    """TC-GE10-EP-002: build() carries a StyleSpec only for explicit style; no fig_size attribute (C-09)."""
    # Given/When: three builders
    plain = _builder().build()
    sized = _builder().set_figure_size(6, 5).build()
    styled = _builder().set_matplotlib_params(font_size=9, grid_alpha=0.5).build()
    # Then: no setter -> None; size only -> size and no rc; params only -> the overrides only
    assert plain.style is None
    assert sized.style == StyleSpec(figure_size=(6, 5))
    assert styled.style is not None
    assert styled.style.figure_size is None
    assert dict(styled.style.rc_params) == {"font.size": 9, "grid.alpha": 0.5}
    for config in (plain, sized, styled):
        assert not hasattr(config, "fig_size")
        assert not hasattr(config, "matplotlib_params")


# --- spec path ------------------------------------------------------------------


def test_graphspec_figure_size_changes_in_memory_and_written_figures__tc_ge10_ep_003(tmp_path: Path) -> None:
    """TC-GE10-EP-003: GraphSpec.style.figure_size drives render_graph, in memory and on disk."""
    # Given: a spec with a size
    spec = GraphSpec(unit_policy="allow", layout="overlay", style=StyleSpec(figure_size=(5, 4)))
    # When: rendering in memory and to files (default and sized)
    in_memory = engine.render_graph(_multi_y(), spec)
    engine.render_graph(_multi_y(), spec, output=OutputSpec(DirectorySink(tmp_path / "sized")))
    engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"), output=OutputSpec(DirectorySink(tmp_path / "default")))
    # Then: the figure is 5 x 4 and the written PNG is smaller than the 8.85 x 8 default
    assert len(in_memory.artifacts) == 1
    assert _size(in_memory.artifacts[0].figure) == (5.0, 4.0)
    sized = _png_size((tmp_path / "sized" / "plot.png").read_bytes())
    default = _png_size((tmp_path / "default" / "plot.png").read_bytes())
    assert sized[0] < default[0]
    assert sized[1] < default[1]
    assert in_memory.plan.origins["style.figure_size"] == "explicit"


def test_graphspec_font_rc_changes_only_that_call__tc_ge10_ep_004() -> None:
    """TC-GE10-EP-004: an rc font size changes the figure, not rcParams afterwards."""
    # Given: the caller's ambient style
    before = dict(mpl.rcParams)
    # When: rendering with font.size 9 and without
    styled = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay", style=StyleSpec(rc_params={"font.size": 9, "xtick.labelsize": 9, "ytick.labelsize": 9})))
    plain = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay"))
    # Then: the styled figure uses 9 pt everywhere, the plain one the house 20 pt, rcParams untouched
    assert _font_sizes(styled.artifacts[0].figure) == {9.0}
    assert 20.0 in _font_sizes(plain.artifacts[0].figure)
    assert 9.0 not in _font_sizes(plain.artifacts[0].figure)
    assert dict(mpl.rcParams) == before


def test_builder_font_rc_on_a_direct_call_is_scoped_to_that_call_v2_0__tc_ge10_ep_005() -> None:
    """TC-GE10-EP-005: on the direct legacy call, explicit rc params do not outlive the call."""
    # Given: a style-less reference call (applies the legacy global style, C-07)
    renderer = MatplotlibRenderer()
    renderer.render_overlay(_multi_y(), _builder().build())
    after_plain = dict(mpl.rcParams)
    # When: the same call with builder rc params
    config = _builder().set_matplotlib_params(font_size=9, xtick_labelsize=9, ytick_labelsize=9, axes_titlesize=9).build()
    fig = renderer.render_overlay(_multi_y(), config)
    # Then: the figure got 9 pt texts, saved later it keeps them, and rcParams equal the style-less ones
    assert _font_sizes(fig) == {9.0}
    assert dict(mpl.rcParams) == after_plain
    assert mpl.rcParams["font.size"] == 20
    assert plt.fignum_exists(fig.number)
    fig.canvas.draw()
    assert _font_sizes(fig) == {9.0}


def test_direct_call_figure_saved_later_keeps_the_explicit_style_v2_0__tc_ge10_ep_005() -> None:
    """TC-GE10-EP-005: the returned figure, saved after the call, equals an in-style export."""
    # Given: builder rc params that change the late-bound layout (font.size drives the tight-layout pad)
    config = _builder().set_matplotlib_params(font_size=9).build()
    renderer = MatplotlibRenderer()
    # When: one figure is saved while the same style is active, another after the call returned
    with mpl.rc_context():
        reference = renderer.render_overlay(_multi_y(), config)
        # The call re-applies the house style globally (C-07); restore the explicit style to save.
        mpl.rcParams.update({**DEFAULT_PLOT_PARAMS, "font.size": 9})
        in_style = _png(reference)
    returned = renderer.render_overlay(_multi_y(), config)
    assert mpl.rcParams["font.size"] == 20
    # Then: the figure kept its style although rcParams moved back to the house font size
    assert _png(returned) == in_style


def test_explicit_rc_overrides_one_default_and_keeps_the_others__tc_ge10_ep_006() -> None:
    """TC-GE10-EP-006: explicit style wins key by key over the house defaults."""
    # Given: an explicit font size only
    result = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay", style=StyleSpec(rc_params={"font.size": 9})))
    fig = result.artifacts[0].figure
    ax = fig.axes[0]
    # Then: font.size is 9 (axis label), the house tick defaults (20 pt, inward) stay
    assert ax.xaxis.label.get_fontsize() == 9.0
    major = ax.xaxis.get_tick_params(which="major")
    assert (major["direction"], major["labelsize"]) == ("in", 20.0)
    assert result.plan.style.rc_params["font.size"] == 9
    assert result.plan.style.rc_params["xtick.direction"] == "in"


def test_default_appearance_is_unchanged__tc_ge10_ep_007(tmp_path: Path) -> None:
    """TC-GE10-EP-007: no style (or StyleSpec()) renders exactly the legacy PNG."""
    # Given: the legacy facade output as the reference
    frame = _multi_y()
    plot_from_dataframe(frame, tmp_path / "legacy", title="cell")
    # When: rendering through the spec API with no style and an explicit empty StyleSpec
    engine.render_graph(frame, GraphSpec(title="cell", unit_policy="allow"), output=OutputSpec(DirectorySink(tmp_path / "none"), base_name="cell"))
    engine.render_graph(frame, GraphSpec(title="cell", unit_policy="allow", style=StyleSpec()), output=OutputSpec(DirectorySink(tmp_path / "empty"), base_name="cell"))
    # Then: the overlay PNGs are byte-identical
    digests = {hashlib.sha256((tmp_path / name / "cell.png").read_bytes()).hexdigest() for name in ("legacy", "none", "empty")}
    assert len(digests) == 1


def test_builder_given_the_default_values_matches_the_style_less_png__tc_ge10_ep_008() -> None:
    """TC-GE10-EP-008: explicitly restating the defaults changes nothing in the image."""
    # Given: a style-less config and one restating every default
    plain = _builder().build()
    restated = _builder().set_figure_size(*DEFAULT_FIG_SIZE).set_matplotlib_params(**{key.replace(".", "_"): value for key, value in DEFAULT_PLOT_PARAMS.items()}).build()
    assert restated.style is not None and dict(restated.style.rc_params) == DEFAULT_PLOT_PARAMS
    renderer = MatplotlibRenderer()
    # When: both are rendered and saved at 300 dpi
    reference = _png(renderer.render_overlay(_multi_y(), plain))
    restated_png = _png(renderer.render_overlay(_multi_y(), restated))
    # Then: identical bytes
    assert restated_png == reference


def test_plotly_size_only_for_an_explicit_figure_size__tc_ge10_ep_009() -> None:
    """TC-GE10-EP-009: HTML gets width/height (inches x 100) only for an explicit size (C-13)."""
    # Given/When: a sized and a default legacy HTML render
    sized = PlotlyRenderer().render_html(_multi_y(), _builder().set_figure_size(5, 4).build())
    default = PlotlyRenderer().render_html(_multi_y(), _builder().set_matplotlib_params(font_size=9).build())
    # Then: only the sized one carries a layout size
    assert (sized.layout.width, sized.layout.height) == (500, 400)
    assert (default.layout.width, default.layout.height) == (None, None)


def test_scoped_font_family_survives_ticks_created_later__tc_ge10_ep_010() -> None:
    """TC-GE10-EP-010: tick labels created after detaching keep the scoped font family."""
    # Given: an in-memory figure drawn with a monospace font
    result = engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", layout="overlay", style=StyleSpec(rc_params={"font.family": ["monospace"]})))
    fig = result.artifacts[0].figure
    ax = fig.axes[0]
    assert mpl.rcParams["font.family"] != ["monospace"]
    # When: the caller widens the limits outside the scope, so new ticks are created, and draws
    ax.set_xlim(-100, 100)
    ax.set_xticks(range(-100, 101, 10))
    fig.canvas.draw()
    # Then: every tick label (old and new) uses the scoped family
    families = {tuple(label.get_fontfamily()) for label in ax.get_xticklabels() + ax.get_yticklabels()}
    assert families == {("monospace",)}
    assert len(ax.get_xticklabels()) == 21


def test_validate_style_normalizes_valid_input__tc_ge10_ep_011() -> None:
    """TC-GE10-EP-011: integer sizes become floats; valid rc keys pass unchanged."""
    # Given/When
    style = validate_style(StyleSpec(figure_size=(4, 3), rc_params={"font.size": 9, "lines.linewidth": 2}))
    # Then
    assert style.figure_size == (4.0, 3.0)
    assert all(isinstance(value, float) for value in style.figure_size)
    assert dict(style.rc_params) == {"font.size": 9, "lines.linewidth": 2}
    assert validate_style(StyleSpec()) == StyleSpec()


def test_plan_records_the_resolved_style__tc_ge10_ep_012() -> None:
    """TC-GE10-EP-012: the plan carries the resolved style and its origins."""
    # Given/When
    plan = build_plot_plan(_multi_y(), GraphSpec(unit_policy="allow", style=StyleSpec(figure_size=(4, 3), rc_params={"font.size": 9})))
    default = build_plot_plan(_multi_y(), GraphSpec(unit_policy="allow"))
    # Then
    assert plan.style.figure_size == (4.0, 3.0)
    assert dict(plan.style.rc_params) == {**DEFAULT_PLOT_PARAMS, "font.size": 9}
    assert (plan.origins["style.figure_size"], plan.origins["style.rc_params"]) == ("explicit", "explicit")
    assert default.style.figure_size == DEFAULT_FIG_SIZE
    assert (default.origins["style.figure_size"], default.origins["style.rc_params"]) == ("default", "default")


# --- validation -----------------------------------------------------------------


@pytest.mark.parametrize("size", [
    (0, 3), (4, 0), (0, 0), (-1, 3), (4, -0.5), (math.nan, 3), (4, math.inf), (-math.inf, 3), (True, 3), ("4", 3), (None, 3),
])
def test_invalid_figure_sizes_are_rejected__tc_ge10_neg_001(size: tuple[Any, Any]) -> None:
    """TC-GE10-NEG-001: each size component must be a finite real number > 0."""
    # Given: a style with an invalid size component
    style = StyleSpec(figure_size=size)
    # When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        validate_style(style)
    assert excinfo.value.reason == "invalid_figure_size"
    assert isinstance(excinfo.value, ValueError)


def test_unknown_rc_key_is_rejected_with_a_suggestion__tc_ge10_neg_002() -> None:
    """TC-GE10-NEG-002: an unknown key names the closest rcParams."""
    # Given/When/Then: a typo
    with pytest.raises(PlotRequestError) as excinfo:
        validate_style(StyleSpec(rc_params={"font.sise": 9}))
    assert excinfo.value.reason == "invalid_rc_param"
    assert "font.sise" in str(excinfo.value)
    assert "font.size" in str(excinfo.value)
    # And: a key that resembles nothing, and a non-string key
    for params in ({"no_such_param": 1}, {1: 2}):
        with pytest.raises(PlotRequestError) as other:
            validate_style(StyleSpec(rc_params=params))
        assert other.value.reason == "invalid_rc_param"


@pytest.mark.parametrize("key", ["backend", "backend_fallback", "interactive", "toolbar"])
def test_denied_rc_keys_are_rejected__tc_ge10_neg_003(key: str) -> None:
    """TC-GE10-NEG-003: keys that would switch the backend or the UI are never applied."""
    # Given: a real rcParams key on the deny list
    assert key in mpl.rcParams
    # When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        validate_style(StyleSpec(rc_params={key: mpl.rcParams[key]}))
    assert excinfo.value.reason == "invalid_rc_param"
    assert key in str(excinfo.value)


@pytest.mark.parametrize(("key", "value"), [("font.size", "huge"), ("lines.linewidth", "thick"), ("xtick.direction", "sideways")])
def test_rc_values_matplotlib_rejects_are_rejected__tc_ge10_neg_004(key: str, value: Any) -> None:
    """TC-GE10-NEG-004: a value the rcParam validator rejects fails at plan time."""
    # Given/When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        validate_style(StyleSpec(rc_params={key: value}))
    assert excinfo.value.reason == "invalid_rc_param"
    assert key in str(excinfo.value)


def test_render_graph_rejects_an_invalid_style_before_writing__tc_ge10_neg_005(tmp_path: Path) -> None:
    """TC-GE10-NEG-005: nothing is written or opened, rcParams unchanged."""
    # Given: the caller's state
    before_rc = dict(mpl.rcParams)
    before_figs = plt.get_fignums()
    # When/Then
    for style, reason in ((StyleSpec(figure_size=(0, 4)), "invalid_figure_size"), (StyleSpec(rc_params={"backend": "agg"}), "invalid_rc_param")):
        with pytest.raises(PlotRequestError) as excinfo:
            engine.render_graph(_multi_y(), GraphSpec(unit_policy="allow", style=style), output=OutputSpec(DirectorySink(tmp_path / "out")))
        assert excinfo.value.reason == reason
    assert not (tmp_path / "out").exists()
    assert plt.get_fignums() == before_figs
    assert dict(mpl.rcParams) == before_rc


@pytest.mark.parametrize(("configure", "reason"), [
    (lambda b: b.set_figure_size(0, 0), "invalid_figure_size"),
    (lambda b: b.set_figure_size(-3, 2), "invalid_figure_size"),
    (lambda b: b.set_matplotlib_params(not_a_param=1), "invalid_rc_param"),
])
def test_builder_accepts_invalid_style_but_rendering_rejects_it_v2_0__tc_ge10_neg_006(configure: Any, reason: str) -> None:
    """TC-GE10-NEG-006: the setters never validate (C-10); rendering fails before a figure exists."""
    # Given: an invalid style accepted by the builder
    config = configure(_builder()).build()
    assert isinstance(config, PlotConfig)
    before = plt.get_fignums()
    # When/Then: direct render and the strategy entry point
    with pytest.raises(PlotRequestError) as excinfo:
        MatplotlibRenderer().render_overlay(_multi_y(), config)
    assert excinfo.value.reason == reason
    with pytest.raises(PlotRequestError):
        collect_render_results(_multi_y(), config, PlotMode.OVERLAY)
    assert plt.get_fignums() == before


def test_build_plot_plan_rejects_invalid_style__tc_ge10_neg_007() -> None:
    """TC-GE10-NEG-007: style validation is part of planning."""
    # Given/When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        build_plot_plan(_multi_y(), GraphSpec(unit_policy="allow", style=StyleSpec(figure_size=(math.nan, 1))))
    assert excinfo.value.reason == "invalid_figure_size"


def test_failure_inside_the_explicit_scope_closes_the_figure__tc_ge10_neg_008(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE10-NEG-008: a draw failure under an explicit style leaves no figure and no override behind."""
    # Given: drawing that fails after the figure was created
    def boom(*_: Any, **__: Any) -> None:
        msg = "draw failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(MatplotlibRenderer, "_configure_axes", boom)
    before = plt.get_fignums()
    config = _builder().set_matplotlib_params(font_size=9).build()
    # When/Then
    with pytest.raises(RuntimeError, match="draw failed"):
        MatplotlibRenderer().render_overlay(_multi_y(), config)
    assert plt.get_fignums() == before
    assert mpl.rcParams["font.size"] == 20


def test_detach_failure_under_an_explicit_style_closes_the_figure__tc_ge10_neg_009(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE10-NEG-009: if freezing the styled figure fails, the caller gets no leaked figure."""
    # Given: detaching fails after the figure was drawn
    def boom(*_: Any, **__: Any) -> None:
        msg = "detach failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(matplotlib_renderer, "detach_figure", boom)
    before = plt.get_fignums()
    config = _builder().set_matplotlib_params(font_size=9).build()
    # When/Then
    with pytest.raises(RuntimeError, match="detach failed"):
        MatplotlibRenderer().render_individual(_multi_y(), config, 1, 0)
    assert plt.get_fignums() == before
    assert mpl.rcParams["font.size"] == 20


@pytest.mark.parametrize("size", [(1e-6, 1e-6), (1000, 1000), (0.1, 0.1)])
def test_extreme_positive_sizes_are_accepted__tc_ge10_bv_001(size: tuple[float, float]) -> None:
    """TC-GE10-BV-001: any finite positive size passes validation."""
    # Given/When/Then
    assert validate_style(StyleSpec(figure_size=size)).figure_size == (float(size[0]), float(size[1]))


def test_empty_rc_mapping_is_the_default__tc_ge10_bv_002() -> None:
    """TC-GE10-BV-002: an empty rc mapping is valid and counts as not given."""
    # Given/When
    plan = build_plot_plan(_multi_y(), GraphSpec(unit_policy="allow", style=StyleSpec(rc_params={})))
    # Then
    assert plan.origins["style.rc_params"] == "default"
    assert dict(plan.style.rc_params) == DEFAULT_PLOT_PARAMS
