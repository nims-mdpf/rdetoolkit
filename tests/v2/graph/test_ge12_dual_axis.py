"""GE-12 (#718): dual-axis plotting is not part of the v2.0 GA surface.

Release decision (design §3.3, orchestrator ruling O-3): dual-axis is EXCLUDED. The
legacy names stay importable and constructible because v1 tests pin them
(``PlotMode.DUAL_AXIS``, ``PlotConfigBuilder.set_y2_axis``, ``PlotConfig.y2_axis``,
``DualAxisStrategy``, ``DualAxisError``), but rendering a configuration that asks for
a secondary y axis raises ``PlotRequestError(reason="dual_axis_unsupported")`` on
every rendering entry point, before a figure or a file exists. It never falls back
silently to individual or overlay figures. The spec API (``GraphSpec``) has no
dual-axis field at all; the facade and the CLI reject ``mode="dual_axis"`` as an
invalid mode.

Intentional behaviour change IC-7 (versioned tests end in ``_v2_0``):
``collect_render_results(..., PlotMode.DUAL_AXIS)`` used to return individual
figures and a ``y2_axis`` was silently ignored; both now raise.

The "previously documented legend mismatch" is the ``IndexError`` in the legend of the
old dual-axis prototype (two series with two units auto-split into y1/y2 columns).
Its regression asserts that the same configuration ends in the typed error, not in an
``IndexError`` and not in a fallback.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| collect_render_results | two-unit two-series DUAL_AXIS config (legend mismatch) | dual_axis_unsupported, no figure, no file | TC-GE12-EP-001 |
| collect_render_results | plot_mode DUAL_AXIS, config.mode OVERLAY | dual_axis_unsupported (no individual fallback) | TC-GE12-EP-002 |
| collect_render_results | y2_axis set, plot_mode OVERLAY / INDIVIDUAL | dual_axis_unsupported | TC-GE12-EP-003 |
| collect_render_results | DUAL_AXIS + no_individual=True | dual_axis_unsupported wins over no_figures | TC-GE12-EP-004 |
| MatplotlibRenderer.render_overlay / render_individual | DUAL_AXIS or y2_axis | dual_axis_unsupported, no open figure | TC-GE12-EP-005 |
| PlotlyRenderer.render_html | DUAL_AXIS or y2_axis | dual_axis_unsupported | TC-GE12-EP-006 |
| OverlayStrategy / IndividualStrategy.render | DUAL_AXIS config | dual_axis_unsupported | TC-GE12-EP-007 |
| DualAxisStrategy.render | any config | dual_axis_unsupported (a PlotConfigError) | TC-GE12-EP-008 |
| error message | any rejection | names the alternatives | TC-GE12-EP-009 |
| plot_from_dataframe / csv2graph | mode "dual_axis" / PlotMode.DUAL_AXIS | invalid_mode, no directory | TC-GE12-EP-010 |
| rdetoolkit plot | --mode dual_axis | exit 2; help says not supported | TC-GE12-EP-011 |
| GraphSpec / SeriesSpec | dual-axis fields, layout "dual_axis" | no such field; invalid_spec | TC-GE12-EP-012 |
| legacy names | enum, builder, field, strategy, error | importable and constructible; strategy not in __all__ | TC-GE12-EP-013 |
| collect_render_results | y2_axis None, OVERLAY (control) | figures rendered as before | TC-GE12-EP-014 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| collect_render_results | y2_axis = ``AxisConfig(label="")`` | counts as set: raises | TC-GE12-BV-001 |
| collect_render_results | builder set_y2_axis(...) then set_y2_axis(None) | not set: renders | TC-GE12-BV-002 |
| collect_render_results | config.mode given as the plain string "dual_axis" | raises | TC-GE12-BV-003 |
| render_graph | spec without any dual-axis notion, mixed units, split | renders (the documented alternative) | TC-GE12-BV-004 |
"""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from typer.testing import CliRunner

import rdetoolkit.graph as graph_pkg
import rdetoolkit.graph.strategies as strategies_pkg
from rdetoolkit.cli.app import app
from rdetoolkit.graph.api.csv2graph import csv2graph, plot_from_dataframe
from rdetoolkit.graph.config import PlotConfigBuilder
from rdetoolkit.graph.engine import render_graph
from rdetoolkit.graph.exceptions import (
    DualAxisError,
    GraphPlottingError,
    GraphUserWarning,
    PlotConfigError,
    PlotRequestError,
)
from rdetoolkit.graph.models import AxisConfig, OutputConfig, PlotConfig, PlotMode
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.spec import GraphSpec, OutputSpec, SeriesSpec
from rdetoolkit.graph.strategies.all_graphs import OverlayStrategy
from rdetoolkit.graph.strategies.dual_axis import DualAxisStrategy
from rdetoolkit.graph.strategies.individual import IndividualStrategy
from rdetoolkit.graph.strategies.render_coordinator import collect_render_results

REASON = "dual_axis_unsupported"
# The submodule (``rdetoolkit.graph.api.csv2graph`` the attribute is the function).
csv2graph_module = importlib.import_module("rdetoolkit.graph.api.csv2graph")
ALTERNATIVES = ("unit_policy='split'", "mode='individual'", "twinx", "save_figure")


def _two_units() -> pd.DataFrame:
    """Two series with two units: the shape that hit the old legend IndexError."""
    return pd.DataFrame(
        {
            "time (s)": [0.0, 1.0, 2.0],
            "voltage (V)": [3.0, 3.5, 4.0],
            "current (A)": [0.1, 0.2, 0.3],
        },
    )


def _config(**changes: object) -> PlotConfig:
    base = PlotConfig(x_col=0, y_cols=[1, 2], output=OutputConfig(formats=["png"], base_name="cell"))
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


def _assert_rejected(caught: pytest.ExceptionInfo[PlotRequestError]) -> None:
    error = caught.value
    assert type(error) is PlotRequestError
    assert error.reason == REASON
    assert isinstance(error, PlotConfigError)
    assert isinstance(error, ValueError)


def _files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


# --------------------------------------------------------------------------- legend mismatch regression


def test_two_unit_dual_axis_config_raises_typed_error_not_index_error_v2_0__tc_ge12_ep_001(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GE12-EP-001: the documented legend mismatch ends in the typed error, not a fallback."""
    # Given: two series with two units configured for the dual-axis mode with a y2 axis
    config = (
        PlotConfigBuilder()
        .set_mode(PlotMode.DUAL_AXIS)
        .set_y_axis(AxisConfig(label="Voltage (V)"))
        .set_y2_axis(AxisConfig(label="Current (A)"))
        .build()
    )
    config = dataclasses.replace(config, x_col=0, y_cols=[1, 2])
    before = plt.get_fignums()
    # When: rendering through the legacy coordinator
    with pytest.raises(PlotRequestError) as caught:
        collect_render_results(_two_units(), config, PlotMode.DUAL_AXIS)
    # Then: typed error (never IndexError) and no figure was created
    _assert_rejected(caught)
    assert not isinstance(caught.value, IndexError)
    assert plt.get_fignums() == before
    # And: through csv2graph, which writes under tmp_path, the same dual-axis config
    # (injected where the facade builds its config) writes nothing next to the CSV
    csv_path = tmp_path / "cell.csv"
    _two_units().to_csv(csv_path, index=False)
    original = csv2graph_module._build_plot_config

    def dual_axis_config(**kwargs: object) -> PlotConfig:
        built = original(**kwargs)  # type: ignore[arg-type]
        return dataclasses.replace(built, mode=PlotMode.DUAL_AXIS, y2_axis=AxisConfig(label="Current (A)"))

    monkeypatch.setattr(csv2graph_module, "_build_plot_config", dual_axis_config)
    with pytest.raises(PlotRequestError) as through_facade:
        csv2graph(csv_path, output_dir=tmp_path / "out", html=True)
    _assert_rejected(through_facade)
    assert plt.get_fignums() == before
    assert _files(tmp_path) == ["cell.csv"]


def test_dual_axis_plot_mode_no_longer_falls_back_to_individual_v2_0__tc_ge12_ep_002() -> None:
    """TC-GE12-EP-002: plot_mode DUAL_AXIS used to return 0 overlay + 2 individual figures."""
    # Given: a plain overlay config, but the dual-axis plot mode
    config = _config()
    # When/Then: rendering raises instead of producing individual figures
    with pytest.raises(PlotRequestError) as caught:
        collect_render_results(_two_units(), config, PlotMode.DUAL_AXIS)
    _assert_rejected(caught)
    assert plt.get_fignums() == []


@pytest.mark.parametrize("plot_mode", [PlotMode.OVERLAY, PlotMode.INDIVIDUAL])
def test_y2_axis_is_no_longer_silently_ignored_v2_0__tc_ge12_ep_003(plot_mode: PlotMode) -> None:
    """TC-GE12-EP-003: a y2 axis on an overlay / individual config raises."""
    # Given: a config with a secondary y axis
    config = _config(y2_axis=AxisConfig(label="Current (A)"))
    # When/Then: rendering raises; no figure is left open
    with pytest.raises(PlotRequestError) as caught:
        collect_render_results(_two_units(), config, plot_mode)
    _assert_rejected(caught)
    assert plt.get_fignums() == []


def test_dual_axis_rejection_precedes_no_figures__tc_ge12_ep_004() -> None:
    """TC-GE12-EP-004: the unsupported mode is reported, not the empty-result symptom."""
    # Given: dual-axis plot mode with individual plots disabled
    config = _config(output=OutputConfig(formats=["png"], no_individual=True))
    # When/Then: the dual-axis reason wins over "no_figures"
    with pytest.raises(PlotRequestError) as caught:
        collect_render_results(_two_units(), config, PlotMode.DUAL_AXIS)
    _assert_rejected(caught)


def test_empty_y2_axis_counts_as_set__tc_ge12_bv_001() -> None:
    """TC-GE12-BV-001: any AxisConfig in y2_axis requests a secondary axis."""
    # Given: an empty AxisConfig as y2 axis / When/Then: rejected
    with pytest.raises(PlotRequestError) as caught:
        collect_render_results(_two_units(), _config(y2_axis=AxisConfig(label="")), PlotMode.OVERLAY)
    _assert_rejected(caught)


def test_plain_string_dual_axis_mode_is_rejected__tc_ge12_bv_003() -> None:
    """TC-GE12-BV-003: a str mode equal to the enum value is treated like the enum."""
    # Given: config.mode set to the plain string (dataclasses do not coerce)
    config = _config(mode="dual_axis")
    # When/Then: rejected even with an overlay plot mode
    with pytest.raises(PlotRequestError) as caught:
        collect_render_results(_two_units(), config, PlotMode.OVERLAY)
    _assert_rejected(caught)


# --------------------------------------------------------------------------- legacy renderers / strategies


@pytest.mark.parametrize(
    "changes",
    [{"mode": PlotMode.DUAL_AXIS}, {"y2_axis": AxisConfig(label="Current (A)")}],
    ids=["mode", "y2_axis"],
)
def test_matplotlib_legacy_adapters_reject_dual_axis__tc_ge12_ep_005(changes: dict[str, object]) -> None:
    """TC-GE12-EP-005: direct render_overlay / render_individual calls raise before drawing."""
    # Given: a dual-axis config and the Matplotlib renderer
    renderer = MatplotlibRenderer()
    config = _config(**changes)
    # When/Then: both legacy adapters raise and no figure is created
    with pytest.raises(PlotRequestError) as overlay:
        renderer.render_overlay(_two_units(), config)
    _assert_rejected(overlay)
    with pytest.raises(PlotRequestError) as individual:
        renderer.render_individual(_two_units(), config, 1, 0)
    _assert_rejected(individual)
    assert plt.get_fignums() == []


@pytest.mark.parametrize(
    "changes",
    [{"mode": PlotMode.DUAL_AXIS}, {"y2_axis": AxisConfig(label="Current (A)")}],
    ids=["mode", "y2_axis"],
)
def test_plotly_legacy_adapter_rejects_dual_axis__tc_ge12_ep_006(changes: dict[str, object]) -> None:
    """TC-GE12-EP-006: render_html raises instead of drawing a single-axis HTML figure."""
    pytest.importorskip("plotly")
    # Given/When/Then: the HTML adapter rejects the dual-axis config
    with pytest.raises(PlotRequestError) as caught:
        PlotlyRenderer().render_html(_two_units(), _config(**changes))
    _assert_rejected(caught)


@pytest.mark.parametrize("strategy_type", [OverlayStrategy, IndividualStrategy])
def test_legacy_strategies_reject_dual_axis_config__tc_ge12_ep_007(
    strategy_type: type[OverlayStrategy | IndividualStrategy],
) -> None:
    """TC-GE12-EP-007: the overlay / individual strategies never draw a dual-axis config."""
    # Given: a strategy with the Matplotlib renderer
    strategy = strategy_type(MatplotlibRenderer())
    # When/Then: rendering a dual-axis config raises
    with pytest.raises(PlotRequestError) as caught:
        strategy.render(_two_units(), _config(mode=PlotMode.DUAL_AXIS))
    _assert_rejected(caught)
    assert plt.get_fignums() == []


@pytest.mark.parametrize("config", [PlotConfig(), _config(mode=PlotMode.DUAL_AXIS)], ids=["default", "dual"])
def test_dual_axis_strategy_raises_the_same_typed_error__tc_ge12_ep_008(config: PlotConfig) -> None:
    """TC-GE12-EP-008: DualAxisStrategy.render always raises the typed error."""
    # Given/When/Then: whatever the config, the strategy refuses
    with pytest.raises(PlotRequestError) as caught:
        DualAxisStrategy().render(_two_units(), config)
    _assert_rejected(caught)
    assert isinstance(caught.value, GraphPlottingError)


@pytest.mark.parametrize(
    "call",
    [
        lambda: collect_render_results(_two_units(), _config(), PlotMode.DUAL_AXIS),
        lambda: MatplotlibRenderer().render_overlay(_two_units(), _config(y2_axis=AxisConfig(label=""))),
        lambda: DualAxisStrategy().render(_two_units(), PlotConfig()),
    ],
    ids=["coordinator", "renderer", "strategy"],
)
def test_rejection_message_names_the_alternatives__tc_ge12_ep_009(call: object) -> None:
    """TC-GE12-EP-009: the message says it is unsupported and how to plot instead."""
    # Given/When: any rejecting entry point
    with pytest.raises(PlotRequestError) as caught:
        call()  # type: ignore[operator]
    # Then: the unambiguous statement plus every documented alternative
    text = str(caught.value)
    assert "not supported" in text
    assert "experimental" not in text
    for fragment in ALTERNATIVES:
        assert fragment in text


# --------------------------------------------------------------------------- facade and CLI


@pytest.mark.parametrize("mode", ["dual_axis", PlotMode.DUAL_AXIS, "DUAL_AXIS"])
def test_facade_rejects_dual_axis_mode_as_invalid_mode__tc_ge12_ep_010(tmp_path: Path, mode: object) -> None:
    """TC-GE12-EP-010: plot_from_dataframe never offers the dual-axis mode."""
    # Given: an output directory that does not exist yet
    out = tmp_path / "out"
    # When/Then: invalid_mode, nothing created
    with pytest.raises(PlotRequestError) as caught:
        plot_from_dataframe(_two_units(), output_dir=out, mode=mode)  # type: ignore[arg-type]
    assert caught.value.reason == "invalid_mode"
    assert not out.exists()
    assert plt.get_fignums() == []


def test_csv2graph_rejects_dual_axis_mode_as_invalid_mode__tc_ge12_ep_010(tmp_path: Path) -> None:
    """TC-GE12-EP-010: csv2graph rejects the mode before reading output paths."""
    # Given: a two-unit CSV copied into tmp_path
    csv_path = tmp_path / "cell.csv"
    _two_units().to_csv(csv_path, index=False)
    out = tmp_path / "out"
    # When/Then: invalid_mode and only the input file exists
    with pytest.raises(PlotRequestError) as caught:
        csv2graph(csv_path, output_dir=out, mode="dual_axis")  # type: ignore[arg-type]
    assert caught.value.reason == "invalid_mode"
    assert _files(tmp_path) == ["cell.csv"]


def test_cli_plot_rejects_dual_axis_and_help_says_unsupported__tc_ge12_ep_011(tmp_path: Path) -> None:
    """TC-GE12-EP-011: the CLI rejects --mode dual_axis and documents it as not supported."""
    # Given: a two-unit CSV
    csv_path = tmp_path / "cell.csv"
    _two_units().to_csv(csv_path, index=False)
    out = tmp_path / "out"
    runner = CliRunner()
    # When: requesting the dual-axis mode
    result = runner.invoke(app, ["plot", str(csv_path), "--output-dir", str(out), "--mode", "dual_axis"])
    # Then: usage error, nothing written
    assert result.exit_code == 2, result.output
    assert "--mode" in result.output
    assert not out.exists()
    # And: the help names the two modes and says dual-axis is not supported
    help_result = runner.invoke(app, ["plot", "--help"], env={"NO_COLOR": "1", "COLUMNS": "250"})
    assert help_result.exit_code == 0
    help_text = " ".join(help_result.output.split())
    assert "overlay or individual" in help_text
    assert "dual-axis is not supported" in help_text


# --------------------------------------------------------------------------- spec API


def test_graph_spec_has_no_dual_axis_notion__tc_ge12_ep_012() -> None:
    """TC-GE12-EP-012: GraphSpec / SeriesSpec carry no secondary-axis field."""
    # Given: the spec dataclasses
    spec_fields = {field.name for field in dataclasses.fields(GraphSpec)}
    series_fields = {field.name for field in dataclasses.fields(SeriesSpec)}
    # Then: no y2 / secondary / dual field and no per-series axis selector
    for name in spec_fields | series_fields:
        lowered = name.lower()
        assert "y2" not in lowered
        assert "dual" not in lowered
        assert "secondary" not in lowered
    assert "axis" not in series_fields
    # And: a y2 keyword is a TypeError, a dual-axis layout an invalid spec
    with pytest.raises(TypeError):
        GraphSpec(y2_axis=None)  # type: ignore[call-arg]
    with pytest.raises(PlotRequestError) as caught:
        GraphSpec(layout="dual_axis")  # type: ignore[arg-type]
    assert caught.value.reason == "invalid_spec"


def test_render_graph_split_is_the_documented_alternative__tc_ge12_bv_004(tmp_path: Path) -> None:
    """TC-GE12-BV-004: two units via the spec API: split overlays, one per unit."""
    # Given: the two-unit frame and the split unit policy
    spec = GraphSpec(unit_policy="split", layout="overlay")
    # When: rendering to a directory
    result = render_graph(_two_units(), spec, output=OutputSpec(sink=DirectorySink(tmp_path), base_name="cell"))
    # Then: two overlay images, one per unit, and nothing else
    assert [(artifact.figure_id, artifact.role) for artifact in result.artifacts] == [
        ("overlay_g0", "main_image"),
        ("overlay_g1", "main_image"),
    ]
    assert _files(tmp_path) == ["cell_a.png", "cell_v.png"]


# --------------------------------------------------------------------------- compat surface


def test_legacy_dual_axis_names_stay_importable_and_constructible__tc_ge12_ep_013() -> None:
    """TC-GE12-EP-013: compat names exist (C-11) but are not advertised as strategies."""
    # Given/When: building a config with every legacy dual-axis setter
    config = PlotConfigBuilder().set_mode(PlotMode.DUAL_AXIS).set_y2_axis(AxisConfig(label="Y2")).build()
    # Then: construction is unchanged
    assert PlotMode.DUAL_AXIS.value == "dual_axis"
    assert config.mode is PlotMode.DUAL_AXIS
    assert config.y2_axis == AxisConfig(label="Y2")
    assert PlotConfig().y2_axis is None
    # And: the strategy and the error stay importable, the strategy is no longer exported
    assert strategies_pkg.DualAxisStrategy is DualAxisStrategy
    assert "DualAxisStrategy" not in strategies_pkg.__all__
    assert graph_pkg.DualAxisError is DualAxisError
    assert issubclass(DualAxisError, GraphPlottingError)


def test_overlay_without_y2_axis_still_renders__tc_ge12_ep_014() -> None:
    """TC-GE12-EP-014 (control): the guard does not touch ordinary overlays."""
    # Given: a two-series overlay config without a secondary axis
    # When: rendering (the legacy path warns about the mixed-unit overlay, IC-6)
    with pytest.warns(GraphUserWarning, match="different units"):
        collections = collect_render_results(_two_units(), _config(), PlotMode.OVERLAY)
    # Then: one overlay and two individual figures as before
    assert [result.filename for result in collections.overlay] == ["cell.png"]
    assert len(collections.individual) == 2


def test_y2_axis_reset_to_none_renders__tc_ge12_bv_002() -> None:
    """TC-GE12-BV-002: set_y2_axis(None) removes the request again."""
    # Given: a builder whose y2 axis was set and then cleared
    config = PlotConfigBuilder().set_y2_axis(AxisConfig(label="Y2")).set_y2_axis(None).build()
    config = dataclasses.replace(config, x_col=0, y_cols=[1, 2])
    # When: rendering the overlay
    with pytest.warns(GraphUserWarning, match="different units"):
        collections = collect_render_results(_two_units(), config, PlotMode.OVERLAY)
    # Then: rendered normally
    assert len(collections.overlay) == 1
    assert len(collections.individual) == 2
