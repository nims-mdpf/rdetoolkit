"""Focused unit tests for the public csv2graph API.

Equivalence Partitioning

| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `graph.plot_from_dataframe` | Single-series, `no_individual=None` | Auto detection should skip per-series artifacts | One overlay artifact only | `TC-EP-API-001` |
| `graph.plot_from_dataframe` | Single-series, `no_individual=False` | Explicit opt-in must restore per-series artifacts | Overlay + individual artifact | `TC-EP-API-002` |
| `graph.plot_from_dataframe` | Multi-series, `no_individual=None` | Default multi-series output should include individuals | Overlay + N individual artifacts | `TC-EP-API-003` |
| `graph.plot_from_dataframe` | Multi-series, `no_individual=True` | Explicit skip should suppress individuals | Overlay artifact only | `TC-EP-API-004` |
| `graph.plot_from_dataframe` | Invalid `no_individual` type | Ensure type-safety on the new tri-state parameter | Raise `TypeError` with clear message | `TC-EP-API-005` |

Boundary Value

| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `graph.plot_from_dataframe` | `len(y_cols)=1` vs `len(y_cols)=2` | Auto suppression triggers only at the single-series boundary | Transition from overlay-only to overlay+individual | `TC-BV-API-001` |
| `graph.plot_from_dataframe` | `mode="overlay"` vs `mode="individual"` | Individual mode must ignore overlay auto-detection | Only per-series artifacts are produced | `TC-BV-API-002` |
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd
import pytest
from matplotlib import pyplot as plt

# Do not run in CI / GitHub Actions
if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
    pytest.skip("Skipping csv2graph unit tests on CI.", allow_module_level=True)

# Ensure plotting uses a headless backend inside tests
matplotlib.use("Agg")  # pragma: no cover - configuration

from matplotlib.ticker import ScalarFormatter

from rdetoolkit.graph.api.csv2graph import _build_plot_config, plot_from_dataframe
from rdetoolkit.graph.exceptions import ColumnNotFoundError
from rdetoolkit.graph.models import DirectionConfig, NormalizedColumns, PlotMode
from rdetoolkit.graph.normalizers import ColumnNormalizer
from rdetoolkit.graph.parsers import CSVParser
from rdetoolkit.graph.textutils import parse_header


def write_csv(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def _close_artifacts(artifacts: list[Any] | None) -> None:
    """Close matplotlib figures attached to artifacts."""
    if not artifacts:
        return
    for artifact in artifacts:
        plt.close(artifact.figure)


def test_csv_parser_single_header_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "single_header.csv",
        """
        time (s),current (mA)
        0,1
        1,2
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    assert metadata["mode"] == CSVParser.DEFAULT_MODE
    assert metadata["title"] == "single_header"
    assert metadata["xaxis_label"] == "time (s)"
    assert metadata["yaxis_label"] == "current (mA)"
    assert metadata["legends"] == ["current"]
    assert list(df.columns) == ["time (s)", "current (mA)"]


def test_csv_parser_no_header_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "no_header.csv",
        """
        1,10,0.5
        2,20,0.6
        3,30,0.7
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    assert metadata["mode"] == CSVParser.DEFAULT_MODE
    assert metadata["title"] == "no_header"
    assert metadata["xaxis_label"] == "x (arb.unit)"
    assert metadata["yaxis_label"] == "y (arb.unit)"
    assert metadata["legends"] == ["y1", "y2"]
    assert list(df.columns) == ["x (arb.unit)", "y1 (arb.unit)", "y2 (arb.unit)"]


def test_csv_parser_meta_block_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "meta_block.csv",
        """
        #title,Meta Block Example
        #dimension,x,y
        #x,Time,s
        #y,Current,mA
        #legend,Series A,Series B
        0,10,12
        1,11,13
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    assert metadata["mode"] == CSVParser.DEFAULT_MODE
    assert metadata["title"] == "Meta Block Example"
    assert metadata["xaxis_label"] == "Time (s)"
    assert metadata["yaxis_label"] == "Current (mA)"
    assert metadata["legends"] == ["Series A", "Series B"]
    assert list(df.columns) == ["Time (s)", "Series A (mA)", "Series B (mA)"]


def test_csv_parser_meta_block_header_mismatch(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "meta_mismatch.csv",
        """
        #title,Meta Block Example
        #dimension,x,y
        #x,Time,s
        #y,Current,mA
        #legend,Series A,Series B
        0,10
        1,11
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    # Missing data columns are safely trimmed
    assert metadata["legends"] == ["Series A"]
    assert list(df.columns) == ["Time (s)", "Series A (mA)"]


def test_parse_header_humanizes_and_extracts_unit() -> None:
    assert parse_header("series_one: cycle_number (mAh)") == ("Series One", "Cycle Number", "mAh")
    assert parse_header("Voltage (V)") == (None, "Voltage", "V")
    assert parse_header("temperature") == (None, "Temperature", None)


def test_column_normalizer_to_index_variants() -> None:
    df = pd.DataFrame([[0, 1]], columns=["time", "current"])
    normalizer = ColumnNormalizer(df)

    assert normalizer.to_index(1) == 1
    assert normalizer.to_index("current") == 1

    with pytest.raises(ColumnNotFoundError, match="'voltage'"):
        normalizer.to_index("voltage")

    with pytest.raises(TypeError, match="int or str"):
        normalizer.to_index(0.5)  # type: ignore[arg-type]


def test_plot_from_dataframe_raises_on_mismatched_columns(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "time (s)": [0, 1, 2],
            "series_one: current (mA)": [1, 2, 3],
            "series_two: voltage (V)": [4, 5, 6],
        }
    )

    with pytest.raises(ValueError, match="must be equal"):
        plot_from_dataframe(
            df=df,
            output_dir=tmp_path,
            name="example",
            logy=False,
            html=False,
            x_col=[0, 1],
            y_cols=[2],
            return_fig=True,
        )


def test_plot_from_dataframe_respects_direction_filter(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "time": [0, 1, 2, 3],
            "value": [1.0, 2.0, 3.0, 4.0],
            "direction": ["Charge", "Discharge", "Charge", "Discharge"],
        }
    )

    filtered_artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="direction_case",
        title="Direction Case",
        x_label="Time",
        y_label="Value",
        logy=False,
        x_col=0,
        y_cols=[1],
        logx=False,
        html=False,
        direction_cols=[2],
        direction_filter=["Charge"],
        no_individual=True,
        return_fig=True,
    )

    assert filtered_artifacts is not None
    filtered_overlay = filtered_artifacts[0]
    assert len(filtered_overlay.figure.axes[0].lines) == 1
    plt.close(filtered_overlay.figure)

    all_artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="direction_case",
        title="Direction Case",
        x_label="Time",
        y_label="Value",
        logy=False,
        x_col=0,
        y_cols=[1],
        logx=False,
        html=False,
        direction_cols=[2],
        no_individual=True,
        return_fig=True,
    )

    assert all_artifacts is not None
    overlay = all_artifacts[0]
    assert len(overlay.figure.axes[0].lines) == 2
    plt.close(overlay.figure)


def test_plot_from_dataframe_creates_directories(tmp_path: Path) -> None:
    df = pd.DataFrame({"time": [0, 1], "value": [1, 2]})

    output_dir = tmp_path / "missing"
    main_dir = tmp_path / "main_missing"

    plot_from_dataframe(
        df=df,
        output_dir=output_dir,
        main_image_dir=main_dir,
        name="dir_case",
        title="Dir Case",
        x_label="Time",
        y_label="Value",
        logy=False,
        x_col=0,
        y_cols=[1],
        no_individual=False,
        return_fig=False,
    )

    assert output_dir.is_dir()
    assert main_dir.is_dir()
    assert any(main_dir.glob("dir_case.png"))
    assert list(output_dir.glob("dir_case_*.png"))


def test_plot_from_dataframe_auto_skips_single_series__tc_ep_api_001(tmp_path: Path) -> None:
    """Auto detection skips individual artifacts for single-series overlays."""
    df = pd.DataFrame({"time": [0, 1, 2], "value": [1, 2, 3]})

    # Given: a single-series DataFrame with auto detection (no_individual=None)
    # When: plotting with return_fig=True
    artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="auto_single",
        x_col="time",
        y_cols=["value"],
        no_individual=None,
        return_fig=True,
    )

    # Then: only the overlay artifact is produced
    assert artifacts is not None
    assert len(artifacts) == 1
    _close_artifacts(artifacts)


def test_plot_from_dataframe_explicit_false_enables_individual__tc_ep_api_002(tmp_path: Path) -> None:
    """Explicit False should create per-series artifacts even for single-series inputs."""
    df = pd.DataFrame({"time": [0, 1, 2], "value": [3, 2, 1]})

    # Given: a single-series DataFrame with no_individual=False
    # When: plotting with return_fig=True
    artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="explicit_false",
        x_col="time",
        y_cols=["value"],
        no_individual=False,
        return_fig=True,
    )

    # Then: overlay and per-series artifacts are returned
    assert artifacts is not None
    assert len(artifacts) == 2
    _close_artifacts(artifacts)


def test_plot_from_dataframe_multi_series_generates_individuals__tc_ep_api_003(tmp_path: Path) -> None:
    """Multi-series DataFrames should emit overlay plus individual artifacts."""
    df = pd.DataFrame(
        {
            "time": [0, 1, 2],
            "value_a": [1, 2, 3],
            "value_b": [3, 2, 1],
        },
    )

    # Given: a multi-series DataFrame with default no_individual=None
    # When: plotting with return_fig=True
    artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="multi_series",
        x_col="time",
        y_cols=["value_a", "value_b"],
        no_individual=None,
        return_fig=True,
    )

    # Then: overlay + per-series artifacts (total 3) are returned
    assert artifacts is not None
    assert len(artifacts) == 3
    _close_artifacts(artifacts)


def test_plot_from_dataframe_explicit_true_skips_multi_series__tc_ep_api_004(tmp_path: Path) -> None:
    """Explicit True suppresses per-series artifacts even with multiple columns."""
    df = pd.DataFrame(
        {
            "time": [0, 1, 2],
            "value_a": [1, 2, 3],
            "value_b": [3, 2, 1],
        },
    )

    # Given: a multi-series DataFrame with no_individual=True
    # When: plotting with return_fig=True
    artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="multi_skip",
        x_col="time",
        y_cols=["value_a", "value_b"],
        no_individual=True,
        return_fig=True,
    )

    # Then: only the overlay artifact remains
    assert artifacts is not None
    assert len(artifacts) == 1
    _close_artifacts(artifacts)


def test_plot_from_dataframe_rejects_non_bool_no_individual__tc_ep_api_005(tmp_path: Path) -> None:
    """Invalid no_individual values should raise TypeError."""
    df = pd.DataFrame({"time": [0, 1], "value": [1, 2]})

    # Given: an invalid no_individual value
    # When: plotting with a non-bool/non-None flag
    # Then: the API surfaces a descriptive TypeError
    with pytest.raises(TypeError, match="True, False, or None"):
        plot_from_dataframe(
            df=df,
            output_dir=tmp_path,
            name="invalid_flag",
            x_col="time",
            y_cols=["value"],
            no_individual="sometimes",  # type: ignore[arg-type]
            return_fig=True,
        )


def test_plot_from_dataframe_series_count_boundary__tc_bv_api_001(tmp_path: Path) -> None:
    """Validate the boundary where auto suppression toggles."""
    single_df = pd.DataFrame({"time": [0, 1], "value": [1, 2]})
    multi_df = pd.DataFrame({"time": [0, 1], "value_a": [1, 2], "value_b": [2, 1]})

    # Given: a single-series DataFrame
    # When: plotting with auto detection
    single_artifacts = plot_from_dataframe(
        df=single_df,
        output_dir=tmp_path,
        name="boundary_single",
        x_col="time",
        y_cols=["value"],
        no_individual=None,
        return_fig=True,
    )

    # Then: only the overlay artifact exists
    assert single_artifacts is not None
    assert len(single_artifacts) == 1
    _close_artifacts(single_artifacts)

    # Given: a multi-series DataFrame
    # When: plotting with auto detection
    multi_artifacts = plot_from_dataframe(
        df=multi_df,
        output_dir=tmp_path,
        name="boundary_multi",
        x_col="time",
        y_cols=["value_a", "value_b"],
        no_individual=None,
        return_fig=True,
    )

    # Then: overlay + two per-series artifacts exist
    assert multi_artifacts is not None
    assert len(multi_artifacts) == 3
    _close_artifacts(multi_artifacts)


def test_plot_from_dataframe_mode_boundary__tc_bv_api_002(tmp_path: Path) -> None:
    """Individual mode should ignore overlay auto-detection."""
    df = pd.DataFrame({"time": [0, 1], "value_a": [1, 2], "value_b": [2, 1]})

    # Given: overlay mode
    # When: plotting with auto detection for a multi-series DataFrame
    overlay_artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="mode_boundary",
        x_col="time",
        y_cols=["value_a", "value_b"],
        mode="overlay",
        no_individual=None,
        return_fig=True,
    )

    # Then: overlay + per-series artifacts exist
    assert overlay_artifacts is not None
    assert len(overlay_artifacts) == 3
    _close_artifacts(overlay_artifacts)

    # Given: individual mode on the same DataFrame
    # When: plotting with auto detection
    individual_artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="mode_boundary",
        x_col="time",
        y_cols=["value_a", "value_b"],
        mode="individual",
        no_individual=None,
        return_fig=True,
    )

    # Then: only per-series artifacts exist and overlay filename is absent
    assert individual_artifacts is not None
    assert len(individual_artifacts) == 2
    assert all(artifact.filename != "mode_boundary.png" for artifact in individual_artifacts)
    _close_artifacts(individual_artifacts)


def test_plot_from_dataframe_applies_y_tick_format_sci__tc_ep_api_006(tmp_path: Path) -> None:
    """y_tick_format='sci' propagates through to the rendered Axes' y-axis formatter.

    Issue #483 Task 04: verifies that the x_tick_format/y_tick_format
    parameters added to plot_from_dataframe() reach the matplotlib renderer
    (Task 03's _apply_tick_formatting()) end-to-end.
    """
    df = pd.DataFrame({"time": [0, 1, 2, 3], "value": [1_000, 2_000, 3_000, 4_000]})

    # Given: a DataFrame plotted with explicit y_tick_format="sci"
    # When: plotting with return_fig=True
    artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="tick_format_sci",
        x_col="time",
        y_cols=["value"],
        y_tick_format="sci",
        return_fig=True,
    )

    # Then: the figure is returned without error and the y-axis formatter is a
    # ScalarFormatter configured for scientific notation (powerlimits (0, 0))
    assert artifacts is not None
    assert len(artifacts) == 1
    figure = artifacts[0].figure
    ax = figure.axes[0]
    formatter = ax.yaxis.get_major_formatter()
    assert isinstance(formatter, ScalarFormatter)
    assert formatter.get_useMathText() is True
    assert formatter._scientific is True
    assert formatter._powerlimits == (0, 0)
    _close_artifacts(artifacts)


def test_plot_from_dataframe_positional_return_fig_backward_compat__tc_ep_api_007(tmp_path: Path) -> None:
    """Legacy positional return_fig calls keep working after new parameters were added.

    Issue #483 review follow-up: x_tick_format/y_tick_format must not shift the
    position of return_fig, otherwise pre-existing callers passing return_fig
    positionally (v1.6.5 argument order) would bind True to x_tick_format.
    """
    df = pd.DataFrame({"time": [0, 1, 2, 3], "value": [1.0, 2.0, 3.0, 4.0]})

    # Given: a fully positional call in the v1.6.5 argument order, where the
    # 27th argument is return_fig=True
    artifacts = plot_from_dataframe(
        df,          # df
        tmp_path,    # output_dir
        None,        # main_image_dir
        None,        # html_output_dir
        False,       # logy
        False,       # logx
        False,       # html
        "overlay",   # mode
        0,           # x_col
        [1],         # y_cols
        None,        # direction_cols
        None,        # direction_filter
        None,        # direction_colors
        "Legacy",    # title
        "legacy",    # name
        None,        # x_label
        None,        # y_label
        None,        # legend_info
        None,        # legend_loc
        None,        # xlim
        None,        # ylim
        False,       # grid
        False,       # invert_x
        False,       # invert_y
        True,        # no_individual
        None,        # max_legend_items
        True,        # return_fig
    )

    # Then: the call succeeds and returns figure artifacts (return_fig=True)
    assert artifacts is not None
    assert len(artifacts) == 1
    _close_artifacts(artifacts)


def test_build_plot_config_wires_legend_policy_fields() -> None:
    """_build_plot_config() must forward legend_policy/outside_threshold/ncol into LegendConfig."""
    normalized = NormalizedColumns(
        x_col=0,
        y_cols=[1, 2],
        direction_cols=[None, None],
        derived_x_label="X",
        derived_y_label="Y",
    )

    # Given: explicit non-default legend policy parameters
    # When: building the PlotConfig via _build_plot_config()
    config = _build_plot_config(
        plot_mode=PlotMode.OVERLAY,
        normalized=normalized,
        direction_config=DirectionConfig(),
        display_title=None,
        x_label=None,
        y_label=None,
        logx=False,
        logy=False,
        xlim=None,
        ylim=None,
        grid=False,
        invert_x=False,
        invert_y=False,
        legend_info=None,
        legend_loc=None,
        max_legend_items=None,
        legend_policy="outside_bottom",
        legend_outside_threshold=5,
        legend_bottom_threshold=25,
        legend_ncol=4,
        formats=["png"],
        no_individual=True,
        return_fig=False,
        base_filename="plot",
        main_image_dir_path=None,
    )

    # Then: LegendConfig carries the requested policy fields
    assert config.legend.policy == "outside_bottom"
    assert config.legend.outside_threshold == 5
    assert config.legend.bottom_threshold == 25
    assert config.legend.ncol == 4


def test_build_plot_config_defaults_legend_policy_to_legacy() -> None:
    """_build_plot_config() default legend policy values preserve backward compatibility."""
    normalized = NormalizedColumns(
        x_col=0,
        y_cols=[1],
        direction_cols=[None],
        derived_x_label="X",
        derived_y_label="Y",
    )

    # Given: legend policy parameters matching the public API defaults
    # When: building the PlotConfig via _build_plot_config()
    config = _build_plot_config(
        plot_mode=PlotMode.OVERLAY,
        normalized=normalized,
        direction_config=DirectionConfig(),
        display_title=None,
        x_label=None,
        y_label=None,
        logx=False,
        logy=False,
        xlim=None,
        ylim=None,
        grid=False,
        invert_x=False,
        invert_y=False,
        legend_info=None,
        legend_loc=None,
        max_legend_items=None,
        legend_policy="legacy",
        legend_outside_threshold=8,
        legend_bottom_threshold=21,
        legend_ncol=None,
        formats=["png"],
        no_individual=True,
        return_fig=False,
        base_filename="plot",
        main_image_dir_path=None,
    )

    # Then: LegendConfig matches LegendConfig()'s own defaults
    assert config.legend.policy == "legacy"
    assert config.legend.outside_threshold == 8
    assert config.legend.bottom_threshold == 21
    assert config.legend.ncol is None


def test_csv2graph_legend_policy_outside_right_end_to_end(tmp_path: Path) -> None:
    """legend_policy="outside_right" reaches the renderer through the public API."""
    df = pd.DataFrame({
        "x": [0, 1, 2],
        **{f"y{i}": [i, i + 1, i + 2] for i in range(10)},
    })

    # Given: a DataFrame with enough series to trigger an outside-right legend
    # When: plotting via the public plot_from_dataframe() API with legend_policy="outside_right"
    figs = plot_from_dataframe(
        df,
        output_dir=tmp_path,
        x_col="x",
        y_cols=[f"y{i}" for i in range(10)],
        legend_policy="outside_right",
        no_individual=True,
        return_fig=True,
    )

    # Then: the rendered figure carries a legend
    assert figs is not None
    fig = figs[0].figure if hasattr(figs[0], "figure") else figs[0]
    ax = fig.axes[0]
    assert ax.get_legend() is not None
    _close_artifacts(figs)


def test_csv2graph_legend_policy_hide_suppresses_legend_end_to_end(tmp_path: Path) -> None:
    """legend_policy="hide" suppresses the legend through the public API."""
    df = pd.DataFrame({"x": [0, 1, 2], "y1": [1, 2, 3], "y2": [3, 2, 1]})

    # Given: a small multi-series DataFrame
    # When: plotting via the public plot_from_dataframe() API with legend_policy="hide"
    figs = plot_from_dataframe(
        df,
        output_dir=tmp_path,
        x_col="x",
        y_cols=["y1", "y2"],
        legend_policy="hide",
        no_individual=True,
        return_fig=True,
    )

    # Then: no legend is attached to the rendered figure
    assert figs is not None
    fig = figs[0].figure if hasattr(figs[0], "figure") else figs[0]
    ax = fig.axes[0]
    assert ax.get_legend() is None
    _close_artifacts(figs)


def test_csv2graph_legend_policy_hide_applies_to_html_output(tmp_path: Path) -> None:
    """Regression: legend_policy="hide" must also disable the legend in Plotly HTML."""
    pytest.importorskip("plotly")
    from rdetoolkit.graph import csv2graph

    df = pd.DataFrame({"x": [0, 1, 2], "y1": [1, 2, 3], "y2": [3, 2, 1]})
    csv_path = tmp_path / "data.csv"
    df.to_csv(csv_path, index=False)

    # Given: a multi-series CSV rendered with html=True and legend_policy="hide"
    # When: generating outputs via the public csv2graph() API
    csv2graph(
        csv_path,
        output_dir=tmp_path,
        html_output_dir=tmp_path,
        x_col="x",
        y_cols=["y1", "y2"],
        legend_policy="hide",
        html=True,
        no_individual=True,
    )

    # Then: the generated HTML disables the Plotly legend
    html_files = list(tmp_path.glob("*.html"))
    assert html_files, "HTML output was not generated"
    html_content = html_files[0].read_text(encoding="utf-8").replace(" ", "")
    assert '"showlegend":false' in html_content


def test_plot_from_dataframe_rejects_invalid_legend_policy(tmp_path: Path) -> None:
    """The public API rejects an invalid legend_policy with ValueError."""
    df = pd.DataFrame({"x": [0, 1, 2], "y1": [1, 2, 3]})

    # Given/When: calling the public API with an unsupported legend_policy value
    # Then: a ValueError is raised before any rendering happens
    with pytest.raises(ValueError, match="Invalid legend policy"):
        plot_from_dataframe(
            df,
            output_dir=tmp_path,
            x_col="x",
            y_cols=["y1"],
            legend_policy="typo",  # type: ignore[arg-type]
            no_individual=True,
        )


def test_csv2graph_default_legend_policy_is_legacy(tmp_path: Path) -> None:
    """Default legend_policy="legacy" preserves pre-#497 output."""
    df = pd.DataFrame({"x": [0, 1, 2], "y1": [1, 2, 3], "y2": [3, 2, 1]})

    # Given: no legend_policy override
    # When: plotting via the public plot_from_dataframe() API
    figs = plot_from_dataframe(
        df,
        output_dir=tmp_path,
        x_col="x",
        y_cols=["y1", "y2"],
        no_individual=True,
        return_fig=True,
    )

    # Then: rendering succeeds and produces a legend as before
    assert figs is not None
    fig = figs[0].figure if hasattr(figs[0], "figure") else figs[0]
    ax = fig.axes[0]
    assert ax.get_legend() is not None
    _close_artifacts(figs)
