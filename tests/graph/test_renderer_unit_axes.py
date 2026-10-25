"""Default tick formatting must not override Matplotlib's categorical/date axes.

Regression for the 1.7.0 default axis formatting (#483): ``tick_format="auto"``
replaced the formatter/locator Matplotlib installs for string (categorical) and
datetime columns with ``ScalarFormatter`` + ``MaxNLocator``, so sample names
and timestamps were drawn as ``0.0, 0.4, ...`` floats.

Equivalence Partitioning Table
| API                     | Input/State Partition                                    | Rationale                                              | Expected Outcome                                         | Test ID   |
| ----------------------- | -------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------- | --------- |
| plot_from_dataframe     | string x column, tick_format="auto" (overlay)            | Categorical axis owns its ticks                        | x tick labels == category names                          | TC-EP-001 |
| plot_from_dataframe     | string x column, tick_format="auto" (individual)         | render_individual shares _configure_axes               | x tick labels == category names                          | TC-EP-002 |
| plot_from_dataframe     | pd.date_range x column, tick_format="auto"               | Date axis owns its ticks                               | date formatter kept, labels are date strings, no offset  | TC-EP-003 |
| plot_from_dataframe     | string y column, tick_format="auto"                      | Detection applies to the y axis as well                | y tick labels == category names                          | TC-EP-004 |
| csv2graph               | CSV with a string x column                               | CLI/API entry from a file keeps sample names           | x tick labels == category names                          | TC-EP-005 |
| plot_from_dataframe     | numeric x column, tick_format="auto"                     | Numeric behavior of #483 is unchanged                  | ScalarFormatter + MaxNLocator on x                       | TC-EP-006 |
| MatplotlibRenderer      | Decimal x values (numeric unit converter), "auto"        | Only categorical/date converters are exempted          | ScalarFormatter + MaxNLocator on x                       | TC-EP-007 |
| plot_from_dataframe     | string x column, explicit x_tick_format="sci"            | Explicit format is user intent and is always applied   | ScalarFormatter applied (category labels replaced)       | TC-EP-008 |
| plot_from_dataframe     | date x column, explicit x_tick_format="plain"            | Explicit format is user intent and is always applied   | ScalarFormatter applied                                  | TC-EP-009 |
| _uses_non_numeric_units | axis without get_converter (Matplotlib < 3.10)           | Fallback to the ``converter`` attribute                | category -> True, None -> False                          | TC-EP-010 |

Pytest Execution Commands:
- Direct: PYTHONPATH=src pytest -q tests/graph/test_renderer_unit_axes.py
- Via tox: tox -e py312-module
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.category import StrCategoryConverter
from matplotlib.ticker import MaxNLocator, ScalarFormatter

from rdetoolkit.graph.api.csv2graph import csv2graph, plot_from_dataframe
from rdetoolkit.graph.models import AxisConfig, DirectionConfig, LegendConfig, OutputConfig, PlotConfig, PlotMode
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer

SAMPLES = ["sample-a", "sample-b", "sample-c"]
_NUMERIC_LABEL = re.compile(r"^[\s$\\a-z{]*[-−]?\d+(\.\d+)?[}$\s]*$")


def _first_figure(artifacts: list[Any] | None) -> Any:
    assert artifacts, "plot API returned no figures"
    return artifacts[0].figure


def _drawn_labels(fig: Any, axis_name: str) -> list[str]:
    fig.canvas.draw()
    ax = fig.axes[0]
    labels = ax.get_xticklabels() if axis_name == "x" else ax.get_yticklabels()
    return [label.get_text() for label in labels if label.get_text()]


@pytest.fixture(autouse=True)
def _close_figures() -> Any:
    yield
    plt.close("all")


def test_string_x_column_keeps_category_labels_overlay__tc_ep_001(tmp_path: Path) -> None:
    # Given: a DataFrame whose x column holds sample names (strings)
    df = pd.DataFrame({"x": SAMPLES, "y": [1.0, 2.0, 3.0]})

    # When: plotting with the default tick format and drawing the figure
    fig = _first_figure(plot_from_dataframe(df, tmp_path, x_col="x", y_cols=["y"], return_fig=True, no_individual=True))

    # Then: the rendered x tick labels are the sample names, not 0.0, 0.4, ...
    assert _drawn_labels(fig, "x") == SAMPLES


def test_string_x_column_keeps_category_labels_individual__tc_ep_002(tmp_path: Path) -> None:
    # Given: a string x column and two y series, rendered in individual mode
    df = pd.DataFrame({"x": SAMPLES, "y1": [1.0, 2.0, 3.0], "y2": [3.0, 2.0, 1.0]})

    # When: plotting individual figures with the default tick format
    artifacts = plot_from_dataframe(df, tmp_path, mode="individual", x_col="x", y_cols=["y1", "y2"], return_fig=True)

    # Then: every rendered figure keeps the sample names on the x axis
    assert artifacts
    for artifact in artifacts:
        assert _drawn_labels(artifact.figure, "x") == SAMPLES


def test_date_x_column_keeps_date_labels__tc_ep_003(tmp_path: Path) -> None:
    # Given: a DataFrame whose x column is a pd.date_range
    df = pd.DataFrame({"x": pd.date_range("2024-01-01", periods=3, freq="D"), "y": [1.0, 2.0, 3.0]})

    # When: plotting with the default tick format and drawing the figure
    fig = _first_figure(plot_from_dataframe(df, tmp_path, x_col="x", y_cols=["y"], return_fig=True, no_individual=True))
    labels = _drawn_labels(fig, "x")
    ax = fig.axes[0]

    # Then: Matplotlib's date formatter is kept and labels are dates, not floats with an offset
    assert not isinstance(ax.xaxis.get_major_formatter(), ScalarFormatter)
    assert type(ax.xaxis.get_major_formatter()).__module__ == mdates.__name__
    assert labels
    assert not any(_NUMERIC_LABEL.match(label) for label in labels), labels
    assert all("01" in label for label in labels), labels
    assert ax.xaxis.get_offset_text().get_text() == ""


def test_string_y_column_keeps_category_labels__tc_ep_004(tmp_path: Path) -> None:
    # Given: numeric x and a categorical (string) y column
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": SAMPLES})

    # When: plotting with the default tick format
    fig = _first_figure(plot_from_dataframe(df, tmp_path, x_col="x", y_cols=["y"], return_fig=True, no_individual=True))

    # Then: y keeps the category names while numeric x still gets ScalarFormatter
    assert _drawn_labels(fig, "y") == SAMPLES
    assert isinstance(fig.axes[0].xaxis.get_major_formatter(), ScalarFormatter)


def test_csv2graph_string_x_column_keeps_category_labels__tc_ep_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a CSV file whose first column holds sample names, and a spy that
    # keeps the overlay figure (csv2graph writes files and returns nothing)
    csv_path = tmp_path / "samples.csv"
    csv_path.write_text("sample,intensity (a.u.)\nsample-a,1.0\nsample-b,2.0\nsample-c,3.0\n", encoding="utf-8")
    rendered: list[Any] = []
    original_render_overlay = MatplotlibRenderer.render_overlay

    def _spy(self: MatplotlibRenderer, df: pd.DataFrame, config: PlotConfig) -> Any:
        figure = original_render_overlay(self, df, config)
        rendered.append(figure)
        return figure

    monkeypatch.setattr(MatplotlibRenderer, "render_overlay", _spy)

    # When: plotting through the csv2graph entry point
    csv2graph(csv_path, output_dir=tmp_path / "out", x_col=0, y_cols=[1], no_individual=True)
    assert len(rendered) == 1
    fig = rendered[0]

    # Then: the sample names are rendered as x tick labels
    assert _drawn_labels(fig, "x") == SAMPLES


def test_numeric_x_column_keeps_scalar_formatting__tc_ep_006(tmp_path: Path) -> None:
    # Given: an ordinary numeric x column
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]})

    # When: plotting with the default tick format
    fig = _first_figure(plot_from_dataframe(df, tmp_path, x_col="x", y_cols=["y"], return_fig=True, no_individual=True))
    labels = _drawn_labels(fig, "x")
    ax = fig.axes[0]

    # Then: the #483 numeric formatting (ScalarFormatter + MaxNLocator) still applies
    assert isinstance(ax.xaxis.get_major_formatter(), ScalarFormatter)
    assert isinstance(ax.xaxis.get_major_locator(), MaxNLocator)
    assert labels
    assert all(_NUMERIC_LABEL.match(label) for label in labels), labels


def test_decimal_unit_converter_is_treated_as_numeric__tc_ep_007() -> None:
    # Given: Decimal x values, for which Matplotlib installs a numeric unit converter
    df = pd.DataFrame({"x": [Decimal("1.0"), Decimal("2.0"), Decimal("3.0")], "y": [1.0, 2.0, 3.0]})
    config = PlotConfig(
        mode=PlotMode.OVERLAY,
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X", scale="linear"),
        y_axis=AxisConfig(label="Y", scale="linear"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    # When: rendering with the default tick format
    fig = MatplotlibRenderer().render_overlay(df, config)
    fig.canvas.draw()
    ax = fig.axes[0]

    # Then: only categorical/date converters are exempted; numeric converters keep ScalarFormatter
    assert isinstance(ax.xaxis.get_major_formatter(), ScalarFormatter)
    assert isinstance(ax.xaxis.get_major_locator(), MaxNLocator)


def test_explicit_sci_on_string_column_is_applied__tc_ep_008(tmp_path: Path) -> None:
    # Given: a string x column with an explicit x_tick_format="sci"
    df = pd.DataFrame({"x": SAMPLES, "y": [1.0, 2.0, 3.0]})

    # When: plotting
    fig = _first_figure(
        plot_from_dataframe(df, tmp_path, x_col="x", y_cols=["y"], return_fig=True, no_individual=True, x_tick_format="sci"),
    )
    labels = _drawn_labels(fig, "x")

    # Then: the explicit format is user intent and is applied as before (labels become numeric)
    assert isinstance(fig.axes[0].xaxis.get_major_formatter(), ScalarFormatter)
    assert labels != SAMPLES


def test_explicit_plain_on_date_column_is_applied__tc_ep_009(tmp_path: Path) -> None:
    # Given: a date x column with an explicit x_tick_format="plain"
    df = pd.DataFrame({"x": pd.date_range("2024-01-01", periods=3, freq="D"), "y": [1.0, 2.0, 3.0]})

    # When: plotting
    fig = _first_figure(
        plot_from_dataframe(df, tmp_path, x_col="x", y_cols=["y"], return_fig=True, no_individual=True, x_tick_format="plain"),
    )
    fig.canvas.draw()

    # Then: the explicit format replaces the date formatter
    assert isinstance(fig.axes[0].xaxis.get_major_formatter(), ScalarFormatter)


@pytest.mark.parametrize(
    ("converter", "expected"),
    [
        (StrCategoryConverter(), True),
        (mdates.DateConverter(), True),
        (None, False),
    ],
)
def test_converter_attribute_fallback__tc_ep_010(converter: Any, expected: bool) -> None:
    # Given: an axis object without get_converter (Matplotlib < 3.10 exposes only .converter)
    axis = SimpleNamespace(converter=converter)

    # When / Then: the helper reads the attribute and classifies the converter
    assert MatplotlibRenderer._uses_non_numeric_units(axis) is expected
