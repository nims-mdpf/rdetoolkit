"""GE-01 (#707): reject invalid plot modes and contradictory options.

Intentional behaviour changes (design IC-1 / IC-2, versioned tests end in ``_v2_0``):
an unsupported ``mode`` no longer falls back to individual plots, and
``mode="individual"`` combined with ``no_individual=True`` no longer silently
produces nothing. Both fail with ``PlotRequestError`` (a ``PlotConfigError`` that is
also a ``ValueError``) before any directory or file is created. The CLI rejects the
same two conditions with exit code 2.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| validate_plot_request | mode in {overlay, individual}, compatible switch | returns None | TC-GE01-EP-001 |
| validate_plot_request | mode outside the supported set (typo, empty, dual_axis, case, whitespace, non-str) | PlotRequestError(reason="invalid_mode") | TC-GE01-EP-002 |
| validate_plot_request | individual + no_individual=True | PlotRequestError(reason="contradictory_switches") | TC-GE01-EP-003 |
| _resolve_plot_mode | supported mode | matching PlotMode | TC-GE01-EP-004 |
| _resolve_plot_mode | "invalid" (mutation check: old code fell back to INDIVIDUAL) | PlotRequestError(reason="invalid_mode") | TC-GE01-EP-005 |
| plot_from_dataframe | invalid mode, save and return_fig | raises, output dir absent, no figure left open | TC-GE01-EP-006 |
| plot_from_dataframe | individual + no_individual=True, save and return_fig | raises, output dir absent | TC-GE01-EP-007 |
| plot_from_dataframe | invalid mode + unknown y column | request error wins (validated before columns) | TC-GE01-EP-008 |
| collect_render_results | INDIVIDUAL + config.output.no_individual | PlotRequestError(reason="no_figures") | TC-GE01-EP-009 |
| csv2graph | invalid mode / contradictory switches | raises, nothing written next to the CSV | TC-GE01-EP-010 |
| CLI plot | --mode invalid / --mode individual --no-individual | exit 2, no file written | TC-GE01-EP-011 |
| CLI plot | compatible switch combinations | exit 0, intended file set | TC-GE01-EP-012 |
| PlotRequestError | class contract | PlotConfigError + ValueError, exported, carries reason | TC-GE01-EP-013 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| plot_from_dataframe | zero columns | ColumnNotFoundError (legacy type), output dir absent | TC-GE01-BV-001 |
| plot_from_dataframe | zero y series (x column only) | ValueError "at least one y column", output dir absent | TC-GE01-BV-002 |
| plot_from_dataframe | one series x no_individual in {None, False, True} x mode | exact artifact names | TC-GE01-BV-003 |
| plot_from_dataframe | two series x no_individual in {None, False, True} x mode | exact artifact names | TC-GE01-BV-004 |
| plot_from_dataframe | return_fig with every compatible combination | same artifact names in memory, nothing written | TC-GE01-BV-005 |
| collect_render_results | low-level empty RenderCollections saved | documented no-op, nothing created | TC-GE01-BV-006 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from typer.testing import CliRunner

import rdetoolkit.graph as graph_pkg
from rdetoolkit.cli.app import app
from rdetoolkit.graph.api.csv2graph import (
    _resolve_plot_mode,
    _save_render_results,
    csv2graph,
    plot_from_dataframe,
)
from rdetoolkit.graph.exceptions import (
    ColumnNotFoundError,
    GraphPlottingError,
    GraphUserWarning,
    PlotConfigError,
    PlotRequestError,
)
from rdetoolkit.graph.models import OutputConfig, PlotConfig, PlotMode, RenderCollections
from rdetoolkit.graph.strategies.render_coordinator import collect_render_results
from rdetoolkit.graph.validation import validate_plot_request

INVALID_MODES: tuple[Any, ...] = ("invalid", "", "dual_axis", "OVERLAY", "Individual", " overlay", None, 1)


def _one_series() -> pd.DataFrame:
    return pd.DataFrame({"x": [0.0, 1.0, 2.0], "a": [1.0, 2.0, 3.0]})


def _two_series() -> pd.DataFrame:
    return pd.DataFrame({"x": [0.0, 1.0, 2.0], "a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]})


def _files(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


# --- validate_plot_request ------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "no_individual"),
    [
        ("overlay", None),
        ("overlay", False),
        ("overlay", True),
        ("individual", None),
        ("individual", False),
    ],
)
def test_validate_plot_request_accepts_compatible_requests__tc_ge01_ep_001(
    mode: str, no_individual: bool | None,
) -> None:
    # Given: a supported mode with a switch that does not contradict it
    # When: validating the request
    result = validate_plot_request(mode=mode, no_individual=no_individual)
    # Then: validation passes silently
    assert result is None


@pytest.mark.parametrize("mode", INVALID_MODES)
@pytest.mark.parametrize("no_individual", [None, False, True])
def test_validate_plot_request_rejects_unsupported_mode__tc_ge01_ep_002(
    mode: Any, no_individual: bool | None,
) -> None:
    # Given: a mode value outside {"overlay", "individual"}
    # When: validating the request
    with pytest.raises(PlotRequestError) as excinfo:
        validate_plot_request(mode=mode, no_individual=no_individual)
    # Then: the typed error names the mode problem and the supported values
    assert excinfo.value.reason == "invalid_mode"
    assert "Invalid mode" in str(excinfo.value)
    assert "'overlay'" in str(excinfo.value)
    assert "'individual'" in str(excinfo.value)


def test_validate_plot_request_rejects_individual_without_individual_plots__tc_ge01_ep_003() -> None:
    # Given: individual mode while individual plots are switched off
    # When: validating the request
    with pytest.raises(PlotRequestError) as excinfo:
        validate_plot_request(mode="individual", no_individual=True)
    # Then: the contradiction is reported, naming both options
    assert excinfo.value.reason == "contradictory_switches"
    assert "no_individual" in str(excinfo.value)
    assert "individual" in str(excinfo.value)


# --- _resolve_plot_mode (mutation check) --------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("overlay", PlotMode.OVERLAY), ("individual", PlotMode.INDIVIDUAL)],
)
def test_resolve_plot_mode_maps_supported_modes__tc_ge01_ep_004(mode: str, expected: PlotMode) -> None:
    # Given/When: a supported mode is resolved
    # Then: the matching enum member is returned
    assert _resolve_plot_mode(mode) is expected  # type: ignore[arg-type]


@pytest.mark.parametrize("mode", INVALID_MODES)
def test_resolve_plot_mode_raises_instead_of_falling_back_v2_0__tc_ge01_ep_005(mode: Any) -> None:
    # Given: an unsupported mode (the v1 code mapped every non-"overlay" value to INDIVIDUAL)
    # When: resolving it
    with pytest.raises(PlotRequestError) as excinfo:
        _resolve_plot_mode(mode)
    # Then: it fails instead of silently falling back
    assert excinfo.value.reason == "invalid_mode"


# --- plot_from_dataframe ---------------------------------------------------------------


@pytest.mark.parametrize("mode", INVALID_MODES)
@pytest.mark.parametrize("return_fig", [False, True])
def test_plot_from_dataframe_rejects_invalid_mode_before_output_v2_0__tc_ge01_ep_006(
    tmp_path: Path, mode: Any, return_fig: bool,
) -> None:
    # Given: a plottable two-series frame and an unsupported mode
    out = tmp_path / "out"
    main = tmp_path / "main"
    figures_before = set(plt.get_fignums())
    # When: plotting
    with pytest.raises(PlotRequestError) as excinfo:
        plot_from_dataframe(_two_series(), out, main_image_dir=main, mode=mode, return_fig=return_fig)
    # Then: nothing was created and no figure was rendered
    assert excinfo.value.reason == "invalid_mode"
    assert not out.exists()
    assert not main.exists()
    assert set(plt.get_fignums()) == figures_before


@pytest.mark.parametrize("return_fig", [False, True])
@pytest.mark.parametrize("frame", [_one_series, _two_series])
def test_plot_from_dataframe_rejects_individual_with_no_individual_v2_0__tc_ge01_ep_007(
    tmp_path: Path, return_fig: bool, frame: Any,
) -> None:
    # Given: individual mode with individual plots switched off
    out = tmp_path / "out"
    figures_before = set(plt.get_fignums())
    # When: plotting
    with pytest.raises(PlotRequestError) as excinfo:
        plot_from_dataframe(frame(), out, mode="individual", no_individual=True, return_fig=return_fig)
    # Then: it fails before any directory or figure exists (v1 returned None / [] silently)
    assert excinfo.value.reason == "contradictory_switches"
    assert isinstance(excinfo.value, ValueError)
    assert not out.exists()
    assert set(plt.get_fignums()) == figures_before


def test_plot_from_dataframe_validates_request_before_columns__tc_ge01_ep_008(tmp_path: Path) -> None:
    # Given: both an unsupported mode and an unknown y column
    # When: plotting
    with pytest.raises(PlotRequestError) as excinfo:
        plot_from_dataframe(_two_series(), tmp_path / "out", mode="invalid", y_cols="missing")
    # Then: the request error is reported first, not the column error
    assert excinfo.value.reason == "invalid_mode"
    assert not isinstance(excinfo.value, ColumnNotFoundError)


def test_plot_from_dataframe_keeps_type_error_for_non_bool_switch(tmp_path: Path) -> None:
    # Given: a non-bool no_individual together with individual mode
    # When: plotting
    with pytest.raises(TypeError, match="no_individual must be True, False, or None"):
        plot_from_dataframe(
            _two_series(), tmp_path / "out", mode="individual", no_individual="yes",  # type: ignore[arg-type]
        )
    # Then: the legacy type check still runs first and nothing is created
    assert not (tmp_path / "out").exists()


def test_plot_from_dataframe_zero_columns_keeps_legacy_type__tc_ge01_bv_001(tmp_path: Path) -> None:
    # Given: a frame without any column
    out = tmp_path / "out"
    # When: plotting with a valid request
    with pytest.raises(ColumnNotFoundError):
        plot_from_dataframe(pd.DataFrame(), out)
    # Then: the legacy error type is kept and nothing is created
    assert not out.exists()


@pytest.mark.parametrize("mode", ["overlay", "individual"])
def test_plot_from_dataframe_zero_y_series_keeps_legacy_type__tc_ge01_bv_002(tmp_path: Path, mode: str) -> None:
    # Given: a frame with an x column only
    out = tmp_path / "out"
    # When: plotting
    with pytest.raises(ValueError, match="at least one y column") as excinfo:
        plot_from_dataframe(pd.DataFrame({"x": [1.0, 2.0]}), out, mode=mode)  # type: ignore[arg-type]
    # Then: the legacy ValueError (not a request error) is raised before any directory exists
    assert not isinstance(excinfo.value, PlotRequestError)
    assert not out.exists()


ONE_SERIES_CASES = [
    ("overlay", None, ["p.png"], []),
    ("overlay", False, ["p.png"], ["p_a.png"]),
    ("overlay", True, ["p.png"], []),
    ("individual", None, [], ["p_a.png"]),
    ("individual", False, [], ["p_a.png"]),
]
TWO_SERIES_CASES = [
    ("overlay", None, ["p.png"], ["p_a.png", "p_b.png"]),
    ("overlay", False, ["p.png"], ["p_a.png", "p_b.png"]),
    ("overlay", True, ["p.png"], []),
    ("individual", None, [], ["p_a.png", "p_b.png"]),
    ("individual", False, [], ["p_a.png", "p_b.png"]),
]


@pytest.mark.parametrize(("mode", "no_individual", "main_files", "individual_files"), ONE_SERIES_CASES)
def test_plot_from_dataframe_one_series_output_counts__tc_ge01_bv_003(
    tmp_path: Path, mode: str, no_individual: bool | None, main_files: list[str], individual_files: list[str],
) -> None:
    # Given: a single-series frame and a compatible request
    out, main = tmp_path / "out", tmp_path / "main"
    # When: saving the plots
    result = plot_from_dataframe(
        _one_series(), out, main_image_dir=main, mode=mode, name="p", no_individual=no_individual,  # type: ignore[arg-type]
    )
    # Then: exactly the intended files are written
    assert result is None
    assert _files(main) == main_files
    assert _files(out) == individual_files


@pytest.mark.parametrize(("mode", "no_individual", "main_files", "individual_files"), TWO_SERIES_CASES)
def test_plot_from_dataframe_two_series_output_counts__tc_ge01_bv_004(
    tmp_path: Path, mode: str, no_individual: bool | None, main_files: list[str], individual_files: list[str],
) -> None:
    # Given: a two-series frame and a compatible request
    out, main = tmp_path / "out", tmp_path / "main"
    # When: saving the plots
    plot_from_dataframe(
        _two_series(), out, main_image_dir=main, mode=mode, name="p", no_individual=no_individual,  # type: ignore[arg-type]
    )
    # Then: exactly the intended files are written
    assert _files(main) == main_files
    assert _files(out) == individual_files


@pytest.mark.parametrize(
    ("frame", "mode", "no_individual", "main_files", "individual_files"),
    [(_one_series, *case) for case in ONE_SERIES_CASES] + [(_two_series, *case) for case in TWO_SERIES_CASES],
)
def test_plot_from_dataframe_return_fig_counts__tc_ge01_bv_005(
    tmp_path: Path,
    frame: Any,
    mode: str,
    no_individual: bool | None,
    main_files: list[str],
    individual_files: list[str],
) -> None:
    # Given: a compatible request returning in-memory figures
    out = tmp_path / "out"
    # When: plotting with return_fig=True
    artifacts = plot_from_dataframe(
        frame(), out, mode=mode, name="p", no_individual=no_individual, return_fig=True,  # type: ignore[arg-type]
    )
    # Then: the same artifact names come back in order and nothing is written
    assert artifacts is not None
    assert [a.filename for a in artifacts] == main_files + individual_files
    assert not out.exists()


# --- collect_render_results ------------------------------------------------------------


def test_collect_render_results_rejects_individual_without_figures__tc_ge01_ep_009() -> None:
    # Given: a low-level config asking for individual plots only, with individual plots disabled
    config = PlotConfig(mode=PlotMode.INDIVIDUAL, x_col=0, y_cols=[1, 2], output=OutputConfig(no_individual=True))
    figures_before = set(plt.get_fignums())
    # When: collecting render results
    with pytest.raises(PlotRequestError) as excinfo:
        collect_render_results(_two_series(), config, PlotMode.INDIVIDUAL)
    # Then: zero figures is an explicit error, not an empty collection
    assert excinfo.value.reason == "no_figures"
    assert set(plt.get_fignums()) == figures_before


def test_collect_render_results_overlay_without_individual_still_renders() -> None:
    # Given: overlay mode with individual plots disabled
    config = PlotConfig(mode=PlotMode.OVERLAY, x_col=0, y_cols=[1, 2], output=OutputConfig(no_individual=True))
    # When: collecting render results
    collections = collect_render_results(_two_series(), config, PlotMode.OVERLAY)
    # Then: exactly one overlay figure and no individual figure
    assert len(collections.overlay) == 1
    assert collections.individual == []


def test_save_render_results_empty_collection_is_documented_noop__tc_ge01_bv_006(tmp_path: Path) -> None:
    # Given: an empty collection (the documented low-level no-op case)
    out = tmp_path / "out"
    # When: saving it
    _save_render_results(RenderCollections(overlay=[], individual=[]), out, None)
    # Then: nothing is created
    assert not out.exists()


# --- csv2graph -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"mode": "invalid"}, "invalid_mode"),
        ({"mode": "dual_axis"}, "invalid_mode"),
        ({"mode": "individual", "no_individual": True}, "contradictory_switches"),
    ],
)
def test_csv2graph_rejects_bad_request_without_writing_v2_0__tc_ge01_ep_010(
    tmp_path: Path, kwargs: dict[str, Any], reason: str,
) -> None:
    # Given: a CSV in an otherwise empty directory
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("x,a,b\n0,1,3\n1,2,2\n", encoding="utf-8")
    # When: calling the file-level API with a bad request
    with pytest.raises(PlotRequestError) as excinfo:
        csv2graph(csv_path, **kwargs)
    # Then: it fails and only the CSV remains next to it
    assert excinfo.value.reason == reason
    assert _files(tmp_path) == ["data.csv"]


# --- CLI -------------------------------------------------------------------------------


def _write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("x,a,b\n0,1,3\n1,2,2\n", encoding="utf-8")
    return csv_path


@pytest.mark.parametrize(
    ("args", "hint"),
    [
        (["--mode", "invalid"], "--mode"),
        (["--mode", "dual_axis"], "--mode"),
        (["--mode", "OVERLAY"], "--mode"),
        (["--mode", "individual", "--no-individual"], "--no-individual"),
    ],
)
def test_cli_plot_rejects_bad_request_with_exit_2__tc_ge01_ep_011(
    tmp_path: Path, args: list[str], hint: str,
) -> None:
    # Given: a CSV and an output directory
    csv_path = _write_csv(tmp_path)
    out = tmp_path / "out"
    # When: invoking the plot command with an invalid request
    result = CliRunner().invoke(app, ["plot", str(csv_path), "--output-dir", str(out), *args])
    # Then: usage error (exit 2) naming the offending option; nothing is written
    assert result.exit_code == 2, result.output
    assert hint in result.output
    assert not out.exists()
    assert _files(tmp_path) == ["data.csv"]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--mode", "overlay", "--no-individual"], ["data.png"]),
        (["--mode", "overlay"], ["data.png", "data_a.png", "data_b.png"]),
        (["--mode", "individual"], ["data_a.png", "data_b.png"]),
        (["--mode", "individual", "--individual"], ["data_a.png", "data_b.png"]),
    ],
)
def test_cli_plot_compatible_switches_keep_output__tc_ge01_ep_012(
    tmp_path: Path, args: list[str], expected: list[str],
) -> None:
    # Given: a two-series CSV and an output directory
    csv_path = _write_csv(tmp_path)
    out = tmp_path / "out"
    # When: invoking the plot command with a compatible request
    result = CliRunner().invoke(app, ["plot", str(csv_path), "--output-dir", str(out), *args])
    # Then: success with exactly the intended files
    assert result.exit_code == 0, result.output
    assert _files(out) == expected


# --- exception contract ----------------------------------------------------------------


def test_plot_request_error_contract__tc_ge01_ep_013() -> None:
    # Given/When: constructing the typed error
    error = PlotRequestError("bad request", reason="invalid_mode")
    # Then: it is a PlotConfigError and a ValueError, keeps its message and reason, and is exported
    assert isinstance(error, PlotConfigError)
    assert isinstance(error, GraphPlottingError)
    assert isinstance(error, ValueError)
    assert error.reason == "invalid_mode"
    assert str(error) == "bad request"
    assert graph_pkg.PlotRequestError is PlotRequestError
    assert graph_pkg.GraphUserWarning is GraphUserWarning
    assert issubclass(GraphUserWarning, UserWarning)
    assert {"PlotRequestError", "GraphUserWarning"} <= set(graph_pkg.__all__)
