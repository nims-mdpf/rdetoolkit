"""Tests for rdetoolkit v2 builtin plot nodes (Session F1.6, TC-F1-PLOT-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f1.md
Conflict #2 (argument order), Conflict #3 (OutputKind guidance: both plot
nodes target ``main_image``, mirroring the retired ``save_graph`` ->
``self.main_image`` precedent), Known Trap 7 (matplotlib must run headless).

Pinned API shapes (binding contract for this file):

    plot_lines(df: pd.DataFrame, out: OutputContext, filename: str) -> Path
    plot_scatter(df: pd.DataFrame, out: OutputContext, filename: str, x: str, y: str) -> Path

``plot_lines`` plots every column against the DataFrame's index (no column
selection needed for a line plot); ``plot_scatter`` requires explicit ``x``/
``y`` column names since a scatter plot is inherently a paired-column
relationship. Exact dpi/font values are Codex's implementation choice
(Design §5.1's "scientific-plot 規約" leaves these undetermined) -- this file
never pins them, only: (a) a real, openable raster image is produced, and
(b) axis labels are set (non-empty) when column names are available, checked
mechanically via a ``matplotlib.axes.Axes.set_xlabel``/``set_ylabel`` capture
rather than OCR/pixel inspection of the rendered text.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # Known Trap 7: must run headless, before any pyplot import.

from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from PIL import Image  # noqa: E402

from rdetoolkit.types import OutputContext  # noqa: E402


def _capture_axis_labels(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Monkeypatch Axes.set_xlabel/set_ylabel to record what a plot node passes them."""
    recorded: dict[str, str] = {}
    original_set_xlabel = Axes.set_xlabel
    original_set_ylabel = Axes.set_ylabel

    def _record_xlabel(self: Axes, xlabel: str, *args: object, **kwargs: object) -> object:
        recorded["xlabel"] = xlabel
        return original_set_xlabel(self, xlabel, *args, **kwargs)

    def _record_ylabel(self: Axes, ylabel: str, *args: object, **kwargs: object) -> object:
        recorded["ylabel"] = ylabel
        return original_set_ylabel(self, ylabel, *args, **kwargs)

    monkeypatch.setattr(Axes, "set_xlabel", _record_xlabel)
    monkeypatch.setattr(Axes, "set_ylabel", _record_ylabel)
    return recorded


class TestPlotLines:
    """TC-F1-PLOT-LINES-*."""

    def test_produces_real_openable_raster_image_under_main_image(self, output_context: OutputContext) -> None:
        """EP: a small DataFrame produces an output file under out.main_image that PIL can open as a real raster image."""
        from rdetoolkit.nodes.plot import plot_lines

        df = pd.DataFrame({"time_s": [0.0, 1.0, 2.0, 3.0], "signal_intensity": [0.1, 0.5, 0.9, 0.3]})

        result_path = plot_lines(df, output_context, "lines.png")

        assert result_path.exists()
        assert result_path.parent == output_context.main_image
        with Image.open(result_path) as img:
            img.load()
            assert img.width > 10
            assert img.height > 10

    def test_sets_axis_labels_when_column_names_available(
        self,
        output_context: OutputContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """EP: axis labels are set (non-empty) when column names are available (Design §5.1 scientific-plot convention)."""
        recorded = _capture_axis_labels(monkeypatch)
        from rdetoolkit.nodes.plot import plot_lines

        df = pd.DataFrame({"time_s": [0.0, 1.0, 2.0], "signal_intensity": [0.1, 0.5, 0.9]})

        plot_lines(df, output_context, "lines_labeled.png")

        assert recorded.get("xlabel"), "plot_lines must call Axes.set_xlabel with a non-empty label"
        assert recorded.get("ylabel"), "plot_lines must call Axes.set_ylabel with a non-empty label"

    def test_empty_dataframe_raises(self, output_context: OutputContext) -> None:
        """BV: an empty (no columns) DataFrame raises rather than silently producing an empty plot."""
        from rdetoolkit.nodes.plot import plot_lines

        with pytest.raises(ValueError):
            plot_lines(pd.DataFrame(), output_context, "should_not_exist.png")

    def test_registered_as_builtin_node(self) -> None:
        """Registration: plot_lines appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("plot_lines") for node_id in ids), ids


class TestPlotScatter:
    """TC-F1-PLOT-SCATTER-*."""

    def test_produces_real_openable_raster_image_under_main_image(self, output_context: OutputContext) -> None:
        """EP: a small DataFrame with explicit x/y columns produces an output file under out.main_image."""
        from rdetoolkit.nodes.plot import plot_scatter

        df = pd.DataFrame({"temperature_c": [10.0, 20.0, 30.0], "resistance_ohm": [100.0, 110.0, 121.0]})

        result_path = plot_scatter(df, output_context, "scatter.png", x="temperature_c", y="resistance_ohm")

        assert result_path.exists()
        assert result_path.parent == output_context.main_image
        with Image.open(result_path) as img:
            img.load()
            assert img.width > 10
            assert img.height > 10

    def test_sets_axis_labels_from_x_y_column_names(
        self,
        output_context: OutputContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """EP: axis labels are set (non-empty) from the x/y column names."""
        recorded = _capture_axis_labels(monkeypatch)
        from rdetoolkit.nodes.plot import plot_scatter

        df = pd.DataFrame({"temperature_c": [10.0, 20.0, 30.0], "resistance_ohm": [100.0, 110.0, 121.0]})

        plot_scatter(df, output_context, "scatter_labeled.png", x="temperature_c", y="resistance_ohm")

        assert recorded.get("xlabel"), "plot_scatter must call Axes.set_xlabel with a non-empty label"
        assert recorded.get("ylabel"), "plot_scatter must call Axes.set_ylabel with a non-empty label"

    def test_missing_column_name_raises(self, output_context: OutputContext) -> None:
        """BV: a nonexistent x/y column name raises."""
        from rdetoolkit.nodes.plot import plot_scatter

        df = pd.DataFrame({"col_a": [1, 2, 3]})

        with pytest.raises((KeyError, ValueError)):
            plot_scatter(df, output_context, "should_not_exist.png", x="col_a", y="does_not_exist")

    def test_registered_as_builtin_node(self) -> None:
        """Registration: plot_scatter appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("plot_scatter") for node_id in ids), ids


class TestPlotModuleRunsHeadless:
    """Known Trap 7: nodes/plot.py must set the Agg backend itself, not rely
    on the importing process having already done so."""

    def test_backend_is_headless_after_importing_plot_module(self) -> None:
        """After importing rdetoolkit.nodes.plot, matplotlib's backend is a headless one (Agg)."""
        import matplotlib as mpl

        import rdetoolkit.nodes.plot  # noqa: F401

        assert mpl.get_backend().lower() == "agg"
