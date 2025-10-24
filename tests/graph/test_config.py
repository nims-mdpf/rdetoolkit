from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pytest

from rdetoolkit.graph.config import (
    DEFAULT_FIG_SIZE,
    DEFAULT_PLOT_PARAMS,
    PlotConfigBuilder,
    apply_matplotlib_config,
)
from rdetoolkit.graph.models import (
    AxisConfig,
    CSVFormat,
    Direction,
    DirectionConfig,
    LegendConfig,
    OutputConfig,
    PlotConfig,
    PlotMode,
)


class TestPlotConfigBuilderInitialization:
    """Test PlotConfigBuilder initialization with defaults."""

    def test_default_mode_is_combined(self):
        """Builder initializes with COMBINED mode."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.mode == PlotMode.OVERLAY

    def test_default_title_is_none(self):
        """Builder initializes with no title."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.title is None

    def test_default_x_axis_label(self):
        """Builder initializes with default X-axis label."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.x_axis.label == "X"
        assert config.x_axis.grid is True

    def test_default_y_axis_label(self):
        """Builder initializes with default Y-axis label."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.y_axis.label == "Y"
        assert config.y_axis.grid is True

    def test_default_y2_axis_is_none(self):
        """Builder initializes with no secondary Y-axis."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.y2_axis is None

    def test_default_legend_config(self):
        """Builder initializes with default legend configuration."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.legend.max_items == 20
        assert config.legend.info is None
        assert config.legend.loc is None

    def test_default_direction_config(self):
        """Builder initializes with default direction configuration."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.direction.column is None
        assert config.direction.filters == []
        assert Direction.CHARGE in config.direction.colors

    def test_default_output_config(self):
        """Builder initializes with default output configuration."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.output.main_image_dir is None
        assert config.output.no_individual is False
        assert config.output.return_fig is False
        assert config.output.formats == ["png"]

    def test_default_humanize_is_false(self):
        """Builder initializes with humanize disabled."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.humanize is False

    def test_default_csv_format_is_meta_block(self):
        """Builder initializes with META_BLOCK CSV format."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert config.csv_format == CSVFormat.META_BLOCK

    def test_default_fig_size_from_legacy(self):
        """Builder initializes with Legacy FIG_SIZE."""
        builder = PlotConfigBuilder()
        assert builder.fig_size == DEFAULT_FIG_SIZE
        assert builder.fig_size == (8.85, 8)

    def test_default_matplotlib_params_from_legacy(self):
        """Builder initializes with Legacy PLOT_PARAMS."""
        builder = PlotConfigBuilder()
        params = builder.matplotlib_params
        assert params["font.size"] == 20
        assert params["xtick.labelsize"] == 20
        assert params["ytick.labelsize"] == 20
        assert params["xtick.direction"] == "in"
        assert params["ytick.direction"] == "in"
        assert params["axes.xmargin"] == 0


class TestPlotConfigBuilderSetters:
    """Test all PlotConfigBuilder setter methods."""

    def test_set_mode_returns_self(self):
        """set_mode() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_mode(PlotMode.INDIVIDUAL)
        assert result is builder

    def test_set_mode_updates_config(self):
        """set_mode() updates plot mode in final config."""
        builder = PlotConfigBuilder()
        config = builder.set_mode(PlotMode.INDIVIDUAL).build()
        assert config.mode == PlotMode.INDIVIDUAL

    def test_set_title_returns_self(self):
        """set_title() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_title("Test Plot")
        assert result is builder

    def test_set_title_updates_config(self):
        """set_title() updates title in final config."""
        builder = PlotConfigBuilder()
        config = builder.set_title("Battery Test").build()
        assert config.title == "Battery Test"

    def test_set_title_with_none(self):
        """set_title(None) clears title."""
        builder = PlotConfigBuilder()
        config = builder.set_title("Test").set_title(None).build()
        assert config.title is None

    def test_set_figure_size_returns_self(self):
        """set_figure_size() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_figure_size(10, 8)
        assert result is builder

    def test_set_figure_size_updates_property(self):
        """set_figure_size() updates fig_size property."""
        builder = PlotConfigBuilder()
        builder.set_figure_size(12, 9)
        assert builder.fig_size == (12, 9)

    def test_set_matplotlib_params_returns_self(self):
        """set_matplotlib_params() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_matplotlib_params(font_size=18)
        assert result is builder

    def test_set_matplotlib_params_updates_property(self):
        """set_matplotlib_params() updates matplotlib_params property."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(font_size=18, grid_alpha=0.5)
        params = builder.matplotlib_params
        assert params["font.size"] == 18
        assert params["grid.alpha"] == 0.5

    def test_set_matplotlib_params_converts_underscores_to_dots(self):
        """set_matplotlib_params() converts underscores to dots."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(
            xtick_labelsize=16,
            ytick_direction="out",
            axes_linewidth=2.0,
        )
        params = builder.matplotlib_params
        assert params["xtick.labelsize"] == 16
        assert params["ytick.direction"] == "out"
        assert params["axes.linewidth"] == 2.0

    def test_set_matplotlib_params_resolves_valid_rcparams(self):
        """set_matplotlib_params() resolves to valid rcParams keys."""
        builder = PlotConfigBuilder()
        # font_size should resolve to "font.size" (exists in rcParams)
        builder.set_matplotlib_params(font_size=18)
        params = builder.matplotlib_params
        assert "font.size" in params
        assert params["font.size"] == 18

    def test_set_x_axis_returns_self(self):
        """set_x_axis() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_x_axis(AxisConfig(label="Time"))
        assert result is builder

    def test_set_x_axis_updates_config(self):
        """set_x_axis() updates X-axis config."""
        builder = PlotConfigBuilder()
        axis = AxisConfig(label="Time (s)", grid=False, lim=(0, 100))
        config = builder.set_x_axis(axis).build()
        assert config.x_axis.label == "Time (s)"
        assert config.x_axis.grid is False
        assert config.x_axis.lim == (0, 100)

    def test_set_y_axis_returns_self(self):
        """set_y_axis() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_y_axis(AxisConfig(label="Voltage"))
        assert result is builder

    def test_set_y_axis_updates_config(self):
        """set_y_axis() updates Y-axis config."""
        builder = PlotConfigBuilder()
        axis = AxisConfig(label="Voltage (V)", invert=True)
        config = builder.set_y_axis(axis).build()
        assert config.y_axis.label == "Voltage (V)"
        assert config.y_axis.invert is True

    def test_set_y2_axis_returns_self(self):
        """set_y2_axis() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_y2_axis(AxisConfig(label="Current"))
        assert result is builder

    def test_set_y2_axis_updates_config(self):
        """set_y2_axis() updates secondary Y-axis config."""
        builder = PlotConfigBuilder()
        axis = AxisConfig(label="Current (A)")
        config = builder.set_y2_axis(axis).build()
        assert config.y2_axis is not None
        assert config.y2_axis.label == "Current (A)"

    def test_set_y2_axis_with_none(self):
        """set_y2_axis(None) disables secondary axis."""
        builder = PlotConfigBuilder()
        config = (
            builder.set_y2_axis(AxisConfig(label="Current"))
            .set_y2_axis(None)
            .build()
        )
        assert config.y2_axis is None

    def test_set_legend_returns_self(self):
        """set_legend() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_legend(LegendConfig(max_items=10))
        assert result is builder

    def test_set_legend_updates_config(self):
        """set_legend() updates legend config."""
        builder = PlotConfigBuilder()
        legend = LegendConfig(max_items=15, loc="upper right", info="Test Info")
        config = builder.set_legend(legend).build()
        assert config.legend.max_items == 15
        assert config.legend.loc == "upper right"
        assert config.legend.info == "Test Info"

    def test_set_direction_returns_self(self):
        """set_direction() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_direction(DirectionConfig(column="dir"))
        assert result is builder

    def test_set_direction_updates_config(self):
        """set_direction() updates direction config."""
        builder = PlotConfigBuilder()
        direction = DirectionConfig(
            column="direction",
            filters=[Direction.CHARGE, Direction.DISCHARGE],
        )
        config = builder.set_direction(direction).build()
        assert config.direction.column == "direction"
        assert len(config.direction.filters) == 2

    def test_set_output_returns_self(self):
        """set_output() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_output(OutputConfig(return_fig=True))
        assert result is builder

    def test_set_output_updates_config(self):
        """set_output() updates output config."""
        builder = PlotConfigBuilder()
        output = OutputConfig(
            main_image_dir=Path("/tmp/output"),
            formats=["png", "svg"],
            return_fig=True,
        )
        config = builder.set_output(output).build()
        assert config.output.main_image_dir == Path("/tmp/output")
        assert config.output.formats == ["png", "svg"]
        assert config.output.return_fig is True

    def test_set_humanize_returns_self(self):
        """set_humanize() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_humanize(True)
        assert result is builder

    def test_set_humanize_updates_config(self):
        """set_humanize() updates humanize flag."""
        builder = PlotConfigBuilder()
        config = builder.set_humanize(True).build()
        assert config.humanize is True

    def test_set_csv_format_returns_self(self):
        """set_csv_format() returns builder for chaining."""
        builder = PlotConfigBuilder()
        result = builder.set_csv_format(CSVFormat.SINGLE_HEADER)
        assert result is builder

    def test_set_csv_format_updates_config(self):
        """set_csv_format() updates CSV format."""
        builder = PlotConfigBuilder()
        config = builder.set_csv_format(CSVFormat.NO_HEADER).build()
        assert config.csv_format == CSVFormat.NO_HEADER


class TestPlotConfigBuilderMethodChaining:
    """Test fluent API method chaining."""

    def test_chaining_all_setters(self):
        """All setter methods can be chained."""
        builder = PlotConfigBuilder()
        config = (
            builder.set_mode(PlotMode.DUAL_AXIS)
            .set_title("Chained Test")
            .set_figure_size(10, 8)
            .set_matplotlib_params(font_size=18)
            .set_x_axis(AxisConfig(label="X-axis"))
            .set_y_axis(AxisConfig(label="Y-axis"))
            .set_y2_axis(AxisConfig(label="Y2-axis"))
            .set_legend(LegendConfig(max_items=10))
            .set_direction(DirectionConfig(column="dir"))
            .set_output(OutputConfig(return_fig=True))
            .set_humanize(True)
            .set_csv_format(CSVFormat.SINGLE_HEADER)
            .build()
        )

        assert config.mode == PlotMode.DUAL_AXIS
        assert config.title == "Chained Test"
        assert config.x_axis.label == "X-axis"
        assert config.y_axis.label == "Y-axis"
        assert config.y2_axis is not None
        assert config.y2_axis.label == "Y2-axis"
        assert config.legend.max_items == 10
        assert config.direction.column == "dir"
        assert config.output.return_fig is True
        assert config.humanize is True
        assert config.csv_format == CSVFormat.SINGLE_HEADER

    def test_chaining_partial_configuration(self):
        """Partial configuration with chaining uses remaining defaults."""
        builder = PlotConfigBuilder()
        config = (
            builder.set_mode(PlotMode.INDIVIDUAL)
            .set_title("Partial Config")
            .set_humanize(True)
            .build()
        )

        # Configured values
        assert config.mode == PlotMode.INDIVIDUAL
        assert config.title == "Partial Config"
        assert config.humanize is True

        # Default values
        assert config.x_axis.label == "X"
        assert config.y_axis.label == "Y"
        assert config.y2_axis is None
        assert config.csv_format == CSVFormat.META_BLOCK


class TestPlotConfigBuilderBuild:
    """Test PlotConfig generation from builder."""

    def test_build_creates_plot_config_instance(self):
        """build() creates PlotConfig instance."""
        builder = PlotConfigBuilder()
        config = builder.build()
        assert isinstance(config, PlotConfig)

    def test_build_preserves_all_configured_values(self):
        """build() preserves all setter-configured values."""
        builder = PlotConfigBuilder()
        builder.set_mode(PlotMode.INDIVIDUAL)
        builder.set_title("Test Title")
        builder.set_x_axis(AxisConfig(label="Custom X"))
        builder.set_humanize(True)

        config = builder.build()

        assert config.mode == PlotMode.INDIVIDUAL
        assert config.title == "Test Title"
        assert config.x_axis.label == "Custom X"
        assert config.humanize is True

    def test_build_can_be_called_multiple_times(self):
        """build() can be called multiple times."""
        builder = PlotConfigBuilder()
        builder.set_title("First Build")

        config1 = builder.build()
        config2 = builder.build()

        assert config1.title == "First Build"
        assert config2.title == "First Build"
        assert config1 is not config2  # Different instances

    def test_build_reflects_subsequent_changes(self):
        """Subsequent build() reflects new setter calls."""
        builder = PlotConfigBuilder()
        builder.set_title("First")
        config1 = builder.build()

        builder.set_title("Second")
        config2 = builder.build()

        assert config1.title == "First"
        assert config2.title == "Second"

    def test_build_does_not_include_matplotlib_settings(self):
        """build() does not include fig_size or matplotlib_params in PlotConfig."""
        builder = PlotConfigBuilder()
        builder.set_figure_size(12, 10)
        builder.set_matplotlib_params(font_size=22)

        config = builder.build()

        # PlotConfig should not have fig_size or matplotlib_params attributes
        assert not hasattr(config, "fig_size")
        assert not hasattr(config, "matplotlib_params")


class TestPlotConfigBuilderProperties:
    """Test builder properties (fig_size, matplotlib_params)."""

    def test_fig_size_property_returns_tuple(self):
        """fig_size property returns tuple."""
        builder = PlotConfigBuilder()
        assert isinstance(builder.fig_size, tuple)
        assert len(builder.fig_size) == 2

    def test_fig_size_property_is_readonly(self):
        """fig_size property cannot be directly assigned."""
        builder = PlotConfigBuilder()
        with pytest.raises(AttributeError):
            builder.fig_size = (10, 8)  # type: ignore[misc]

    def test_fig_size_updated_via_setter(self):
        """fig_size is updated via set_figure_size()."""
        builder = PlotConfigBuilder()
        original = builder.fig_size

        builder.set_figure_size(15, 12)
        updated = builder.fig_size

        assert original != updated
        assert updated == (15, 12)

    def test_matplotlib_params_property_returns_dict(self):
        """matplotlib_params property returns dictionary."""
        builder = PlotConfigBuilder()
        assert isinstance(builder.matplotlib_params, dict)

    def test_matplotlib_params_property_returns_copy(self):
        """matplotlib_params property returns copy, not reference."""
        builder = PlotConfigBuilder()
        params1 = builder.matplotlib_params
        params2 = builder.matplotlib_params

        assert params1 is not params2  # Different objects
        assert params1 == params2  # Same content

    def test_matplotlib_params_external_modification_does_not_affect_builder(self):
        """Modifying returned matplotlib_params dict does not affect builder."""
        builder = PlotConfigBuilder()
        params = builder.matplotlib_params
        params["font.size"] = 999  # External modification

        # Builder params should be unchanged
        assert builder.matplotlib_params["font.size"] == 20

    def test_matplotlib_params_updated_via_setter(self):
        """matplotlib_params is updated via set_matplotlib_params()."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(font_size=25, grid_alpha=0.7)

        params = builder.matplotlib_params
        assert params["font.size"] == 25
        assert params["grid.alpha"] == 0.7

    def test_matplotlib_params_preserves_previous_values(self):
        """set_matplotlib_params() preserves existing params."""
        builder = PlotConfigBuilder()
        original_xtick = builder.matplotlib_params["xtick.labelsize"]

        builder.set_matplotlib_params(font_size=18)

        params = builder.matplotlib_params
        assert params["font.size"] == 18  # Updated
        assert params["xtick.labelsize"] == original_xtick  # Preserved


class TestMatplotlibParamsResolution:
    """Test _resolve_mpl_key() logic in matplotlib params conversion."""

    def test_single_level_underscore_conversion(self):
        """Single level underscore (font_size) converts to dot (font.size)."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(font_size=16)
        params = builder.matplotlib_params
        # Should resolve to "font.size" (exists in rcParams)
        assert "font.size" in params
        assert params["font.size"] == 16

    def test_multi_level_underscore_conversion(self):
        """Multi-level underscores convert to dots."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(xtick_major_size=10)
        params = builder.matplotlib_params
        # Should check existence and use valid key
        assert any(key.startswith("xtick.major") for key in params)

    def test_already_dotted_param_name(self):
        """Params with dots pass through unchanged."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(**{"font.size": 18})
        params = builder.matplotlib_params
        assert params["font.size"] == 18

    def test_multiple_params_conversion(self):
        """Multiple parameters all get converted properly."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(
            font_size=18,
            xtick_labelsize=16,
            ytick_direction="out",
            axes_linewidth=2.0,
        )
        params = builder.matplotlib_params

        assert params["font.size"] == 18
        assert params["xtick.labelsize"] == 16
        assert params["ytick.direction"] == "out"
        assert params["axes.linewidth"] == 2.0

    def test_overwriting_existing_param(self):
        """Setting param multiple times uses latest value."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(font_size=18)
        builder.set_matplotlib_params(font_size=22)
        assert builder.matplotlib_params["font.size"] == 22

    def test_nonexistent_param_uses_first_candidate(self):
        """Non-existent params fall back to first candidate."""
        builder = PlotConfigBuilder()
        # Use a definitely non-existent param
        builder.set_matplotlib_params(nonexistent_param=999)
        params = builder.matplotlib_params
        # Should use first candidate (underscore → dot conversion)
        assert "nonexistent.param" in params
        assert params["nonexistent.param"] == 999


class TestApplyMatplotlibConfig:
    """Test apply_matplotlib_config() utility function."""

    def test_apply_default_params(self):
        """apply_matplotlib_config() applies DEFAULT_PLOT_PARAMS."""
        # Reset to known state
        plt.rcParams["font.size"] = 10  # Different from default

        apply_matplotlib_config()

        assert plt.rcParams["font.size"] == DEFAULT_PLOT_PARAMS["font.size"]
        assert plt.rcParams["xtick.labelsize"] == DEFAULT_PLOT_PARAMS["xtick.labelsize"]
        assert plt.rcParams["xtick.direction"] == DEFAULT_PLOT_PARAMS["xtick.direction"]

    def test_apply_custom_params(self):
        """apply_matplotlib_config() applies custom params."""
        custom_params = {
            "font.size": 25,
            "xtick.labelsize": 22,
            "grid.alpha": 0.8,
        }

        apply_matplotlib_config(custom_params)

        assert plt.rcParams["font.size"] == 25
        assert plt.rcParams["xtick.labelsize"] == 22
        assert plt.rcParams["grid.alpha"] == 0.8

    def test_apply_builder_params(self):
        """apply_matplotlib_config() works with builder.matplotlib_params."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(font_size=18, grid_alpha=0.5)

        apply_matplotlib_config(builder.matplotlib_params)

        assert plt.rcParams["font.size"] == 18
        assert plt.rcParams["grid.alpha"] == 0.5

    def test_apply_params_modifies_global_rcparams(self):
        """apply_matplotlib_config() modifies global plt.rcParams."""
        original_font_size = plt.rcParams["font.size"]

        apply_matplotlib_config({"font.size": 999})
        assert plt.rcParams["font.size"] == 999

        # Cleanup
        plt.rcParams["font.size"] = original_font_size

    def test_apply_none_uses_defaults(self):
        """apply_matplotlib_config(None) uses DEFAULT_PLOT_PARAMS."""
        apply_matplotlib_config(None)
        assert plt.rcParams["font.size"] == DEFAULT_PLOT_PARAMS["font.size"]


class TestPlotConfigBuilderEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_builder_produces_valid_config(self):
        """Builder with no setter calls produces valid config."""
        builder = PlotConfigBuilder()
        config = builder.build()

        assert isinstance(config, PlotConfig)
        assert config.mode == PlotMode.OVERLAY
        assert config.x_axis.label == "X"

    def test_setting_same_value_multiple_times(self):
        """Setting same value multiple times works correctly."""
        builder = PlotConfigBuilder()
        builder.set_title("Test")
        builder.set_title("Test")
        builder.set_title("Test")

        config = builder.build()
        assert config.title == "Test"

    def test_alternating_setter_calls(self):
        """Alternating setter calls uses last value."""
        builder = PlotConfigBuilder()
        builder.set_humanize(True)
        builder.set_humanize(False)
        builder.set_humanize(True)

        config = builder.build()
        assert config.humanize is True

    def test_very_large_figure_size(self):
        """Very large figure size is accepted."""
        builder = PlotConfigBuilder()
        builder.set_figure_size(1000, 1000)
        assert builder.fig_size == (1000, 1000)

    def test_very_small_figure_size(self):
        """Very small figure size is accepted."""
        builder = PlotConfigBuilder()
        builder.set_figure_size(0.1, 0.1)
        assert builder.fig_size == (0.1, 0.1)

    def test_zero_figure_size(self):
        """Zero figure size is technically valid (though not practical)."""
        builder = PlotConfigBuilder()
        builder.set_figure_size(0, 0)
        assert builder.fig_size == (0, 0)

    def test_many_matplotlib_params(self):
        """Setting many matplotlib params works."""
        builder = PlotConfigBuilder()
        many_params = {f"param_{i}": i for i in range(50)}
        builder.set_matplotlib_params(**many_params)

        params = builder.matplotlib_params
        # Check some samples
        assert params["param.25"] == 25
        assert params["param.49"] == 49


class TestPlotConfigBuilderLegacyCompatibility:
    """Test compatibility with Legacy csv2graph.py patterns."""

    def test_legacy_default_fig_size_preserved(self):
        """Legacy FIG_SIZE (8.85, 8) is preserved as default."""
        builder = PlotConfigBuilder()
        assert builder.fig_size == (8.85, 8)

    def test_legacy_default_plot_params_preserved(self):
        """Legacy PLOT_PARAMS values are preserved."""
        builder = PlotConfigBuilder()
        params = builder.matplotlib_params

        assert params["font.size"] == 20
        assert params["xtick.labelsize"] == 20
        assert params["ytick.labelsize"] == 20
        assert params["xtick.direction"] == "in"
        assert params["ytick.direction"] == "in"
        assert params["axes.xmargin"] == 0

    def test_legacy_configure_plot_params_equivalent(self):
        """apply_matplotlib_config() is equivalent to Legacy configure_plot_params()."""
        # Legacy pattern:
        # def configure_plot_params(PLOT_PARAMS):
        #     for key, value in PLOT_PARAMS.items():
        #         plt.rcParams[key] = value

        custom_params = {"font.size": 18, "grid.alpha": 0.7}
        apply_matplotlib_config(custom_params)

        assert plt.rcParams["font.size"] == 18
        assert plt.rcParams["grid.alpha"] == 0.7

    def test_legacy_workflow_pattern(self):
        """Legacy workflow: configure_plot_params() → plt.subplots() works."""
        builder = PlotConfigBuilder()
        builder.set_figure_size(10, 8)
        builder.set_matplotlib_params(font_size=16)

        # Apply config (equivalent to Legacy configure_plot_params())
        apply_matplotlib_config(builder.matplotlib_params)

        # Create figure (equivalent to Legacy plt.subplots(figsize=FIG_SIZE))
        fig, ax = plt.subplots(figsize=builder.fig_size)

        assert fig.get_figwidth() == 10
        assert fig.get_figheight() == 8
        assert plt.rcParams["font.size"] == 16

        # Cleanup
        plt.close(fig)


class TestPlotConfigBuilderDocstringExamples:
    """Test examples from docstrings work correctly."""

    def test_class_docstring_example(self):
        """Example from PlotConfigBuilder class docstring works."""
        builder = PlotConfigBuilder()
        config = (
            builder.set_mode(PlotMode.OVERLAY)
            .set_title("Test Plot")
            .set_figure_size(10, 6)
            .set_matplotlib_params(font_size=18)
            .build()
        )

        assert config.mode == PlotMode.OVERLAY
        assert config.title == "Test Plot"
        assert builder.fig_size == (10, 6)
        assert builder.matplotlib_params["font.size"] == 18

    def test_set_matplotlib_params_docstring_example(self):
        """Example from set_matplotlib_params() docstring works."""
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(
            font_size=18, xtick_labelsize=16, grid_alpha=0.5
        )

        params = builder.matplotlib_params
        assert params["font.size"] == 18
        assert params["xtick.labelsize"] == 16
        assert params["grid.alpha"] == 0.5

    def test_build_docstring_example(self):
        """Example from build() docstring works."""
        builder = PlotConfigBuilder()
        config = builder.build()

        # Apply matplotlib settings
        apply_matplotlib_config(builder.matplotlib_params)

        # Create figure with configured size
        fig, ax = plt.subplots(figsize=builder.fig_size)

        assert isinstance(config, PlotConfig)
        assert fig.get_figwidth() == DEFAULT_FIG_SIZE[0]
        assert fig.get_figheight() == DEFAULT_FIG_SIZE[1]

        # Cleanup
        plt.close(fig)

    def test_apply_matplotlib_config_docstring_examples(self):
        """Examples from apply_matplotlib_config() docstring work."""
        # Example 1: Apply default settings
        apply_matplotlib_config()
        assert plt.rcParams["font.size"] == DEFAULT_PLOT_PARAMS["font.size"]

        # Example 2: Apply custom settings
        apply_matplotlib_config({"font.size": 16, "grid.alpha": 0.3})
        assert plt.rcParams["font.size"] == 16
        assert plt.rcParams["grid.alpha"] == 0.3

        # Example 3: Use with builder
        builder = PlotConfigBuilder()
        builder.set_matplotlib_params(font_size=18)
        apply_matplotlib_config(builder.matplotlib_params)
        assert plt.rcParams["font.size"] == 18
