from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import matplotlib.pyplot as plt

from rdetoolkit.graph.models import (
    AxisConfig,
    CSVFormat,
    DirectionConfig,
    LegendConfig,
    OutputConfig,
    PlotConfig,
    PlotMode,
)


DEFAULT_PLOT_PARAMS: dict[str, Any] = {
    "font.size": 20,
    "xtick.labelsize": 20,
    "ytick.labelsize": 20,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "axes.xmargin": 0,
}
DEFAULT_FIG_SIZE: tuple[float, float] = (8.85, 8)


class PlotConfigBuilder:
    """Builder for constructing PlotConfig objects.

    This class implements the Builder pattern to construct complex PlotConfig
    objects in a fluent, method-chaining style.

    The builder maintains Matplotlib-specific settings (fig_size, matplotlib_params)
    separately from PlotConfig, which focuses on plot semantics.

    Example:
        >>> builder = PlotConfigBuilder()
        >>> config = (builder
        ...     .set_mode(PlotMode.OVERLAY)
        ...     .set_title("Test Plot")
        ...     .set_figure_size(10, 6)
        ...     .set_matplotlib_params(font_size=18)
        ...     .build())
        >>> # Apply matplotlib settings separately
        >>> apply_matplotlib_config(builder.matplotlib_params)
        >>> # Use config for plotting
        >>> fig, ax = plt.subplots(figsize=builder.fig_size)
    """

    def __init__(self) -> None:
        self._mode = PlotMode.OVERLAY
        self._title: str | None = None
        self._x_axis = AxisConfig(label="X")
        self._y_axis = AxisConfig(label="Y")
        self._y2_axis: AxisConfig | None = None
        self._legend = LegendConfig()
        self._direction = DirectionConfig()
        self._output = OutputConfig()
        self._humanize = False
        self._csv_format = CSVFormat.META_BLOCK
        self._fig_size = DEFAULT_FIG_SIZE
        self._matplotlib_params = DEFAULT_PLOT_PARAMS.copy()
        self._x_col: int | str | list[int | str] | None = None
        self._y_cols: list[int | str] | None = None
        self._direction_cols: list[int | str | None] | None = None

    @property
    def fig_size(self) -> tuple[float, float]:
        """Get current figure size.

        Returns:
            Figure size as (width, height) in inches
        """
        return self._fig_size

    @property
    def matplotlib_params(self) -> dict[str, Any]:
        """Get current Matplotlib rcParams.

        Returns:
            Dictionary of Matplotlib rcParams
        """
        return self._matplotlib_params.copy()

    def set_mode(self, mode: PlotMode) -> PlotConfigBuilder:
        """Set plot mode.

        Args:
            mode: Plot mode (COMBINED, INDIVIDUAL, DUAL_AXIS)

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_mode(PlotMode.INDIVIDUAL)
        """
        self._mode = mode
        return self

    def set_title(self, title: str | None) -> PlotConfigBuilder:
        """Set plot title.

        Args:
            title: Plot title text (None for no title)

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_title("Battery Cycling Test")
        """
        self._title = title
        return self

    def set_figure_size(self, width: float, height: float) -> PlotConfigBuilder:
        """Set figure size.

        Args:
            width: Figure width in inches
            height: Figure height in inches

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_figure_size(10, 8)
        """
        self._fig_size = (width, height)
        return self

    def set_matplotlib_params(self, **params: Any) -> PlotConfigBuilder:
        """Set or update Matplotlib rcParams.

        Args:
            **params: Matplotlib rcParams to set or update.
                    Use underscores instead of dots (e.g., font_size=18).
                    Automatically converts to dot notation where possible.

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_matplotlib_params(
            ...     font_size=18,
            ...     xtick_labelsize=16,
            ...     grid_alpha=0.5
            ... )
        """
        def _resolve_mpl_key(raw_key: str) -> str:
            if "." in raw_key:
                return raw_key

            candidates: list[str] = []
            if "_" in raw_key:
                candidates.append(raw_key.replace("_", "."))
                candidates.append(raw_key.replace("_", ".", 1))
            candidates.append(raw_key)

            seen: set[str] = set()
            unique_candidates: list[str] = []
            for candidate in candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    unique_candidates.append(candidate)

            for candidate in unique_candidates:
                if candidate in plt.rcParams or candidate in plt.rcParamsDefault:
                    return candidate

            return unique_candidates[0]

        for key, value in params.items():
            mpl_key = _resolve_mpl_key(key)
            self._matplotlib_params[mpl_key] = value
        return self

    def set_x_axis(self, axis_config: AxisConfig) -> PlotConfigBuilder:
        """Set X-axis configuration.

        Args:
            axis_config: X-axis configuration

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_x_axis(AxisConfig(
            ...     label="Time (s)",
            ...     grid=True,
            ...     lim=(0, 100)
            ... ))
        """
        self._x_axis = axis_config
        return self

    def set_y_axis(self, axis_config: AxisConfig) -> PlotConfigBuilder:
        """Set Y-axis configuration.

        Args:
            axis_config: Y-axis configuration

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_y_axis(AxisConfig(
            ...     label="Voltage (V)",
            ...     grid=True,
            ...     invert=False
            ... ))
        """
        self._y_axis = axis_config
        return self

    def set_y2_axis(self, axis_config: AxisConfig | None) -> PlotConfigBuilder:
        """Set secondary Y-axis configuration (for dual_axis mode).

        Args:
            axis_config: Y2-axis configuration (None to disable)

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_y2_axis(AxisConfig(
            ...     label="Current (A)",
            ...     grid=False
            ... ))
        """
        self._y2_axis = axis_config
        return self

    def set_legend(self, legend_config: LegendConfig) -> PlotConfigBuilder:
        """Set legend configuration.

        Args:
            legend_config: Legend configuration

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_legend(LegendConfig(
            ...     max_items=10,
            ...     loc="upper right"
            ... ))
        """
        self._legend = legend_config
        return self

    def set_direction(self, direction_config: DirectionConfig) -> PlotConfigBuilder:
        """Set direction-based configuration.

        Args:
            direction_config: Direction configuration for charge/discharge coloring

        Returns:
            Self for method chaining

        Example:
            >>> from rdetoolkit.graph.models import Direction
            >>> builder.set_direction(DirectionConfig(
            ...     column="direction",
            ...     filters=[Direction.CHARGE, Direction.DISCHARGE]
            ... ))
        """
        self._direction = direction_config
        return self

    def set_output(self, output_config: OutputConfig) -> PlotConfigBuilder:
        """Set output configuration.

        Args:
            output_config: Output configuration

        Returns:
            Self for method chaining

        Example:
            >>> from pathlib import Path
            >>> builder.set_output(OutputConfig(
            ...     main_image_dir=Path("./output"),
            ...     formats=["png", "svg"]
            ... ))
        """
        self._output = output_config
        return self

    def set_humanize(self, humanize: bool) -> PlotConfigBuilder:
        """Set whether to humanize labels.

        Args:
            humanize: If True, apply humanization to snake_case labels

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_humanize(True)
        """
        self._humanize = humanize
        return self

    def set_csv_format(self, csv_format: CSVFormat) -> PlotConfigBuilder:
        """Set CSV format type.

        Args:
            csv_format: CSV format (META_BLOCK, SINGLE_HEADER, NO_HEADER)

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_csv_format(CSVFormat.SINGLE_HEADER)
        """
        self._csv_format = csv_format
        return self

    def set_columns(
        self,
        x_col: int | str | Sequence[int | str] | None = None,
        y_cols: Sequence[int | str] | None = None,
        direction_cols: Sequence[int | str | None] | None = None,
    ) -> PlotConfigBuilder:
        """Set column specifications for plotting.

        Args:
            x_col: X column specification (index, name, or list)
            y_cols: Y column specifications (indices or names)
            direction_cols: Direction column specifications
                            (for direction-based coloring)

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_columns(x_col=0, y_cols=[1, 2, 3])
            >>> builder.set_columns(x_col='time', y_cols=['voltage', 'current'])
        """
        if x_col is None or isinstance(x_col, (int, str)):
            self._x_col = x_col
        elif isinstance(x_col, Sequence):
            self._x_col = list(x_col)
        else:  # pragma: no cover - defensive guard for unexpected types
            msg = f"Unsupported x_col specification type: {type(x_col)!r}"
            raise TypeError(msg)

        self._y_cols = list(y_cols) if y_cols is not None else None
        self._direction_cols = list(direction_cols) if direction_cols is not None else None
        return self

    def build(self) -> PlotConfig:
        """Build the final PlotConfig object.

        Returns:
            Immutable PlotConfig instance

        Note:
            Matplotlib settings (fig_size, matplotlib_params) are not included
            in PlotConfig. Access them via builder.fig_size and
            builder.matplotlib_params properties.

        Example:
            >>> config = builder.build()
            >>> # Apply matplotlib settings
            >>> apply_matplotlib_config(builder.matplotlib_params)
            >>> # Create figure with configured size
            >>> fig, ax = plt.subplots(figsize=builder.fig_size)
        """
        return PlotConfig(
            mode=self._mode,
            title=self._title,
            x_axis=self._x_axis,
            y_axis=self._y_axis,
            y2_axis=self._y2_axis,
            legend=self._legend,
            direction=self._direction,
            output=self._output,
            humanize=self._humanize,
            csv_format=self._csv_format,
            x_col=self._x_col,
            y_cols=self._y_cols,
            direction_cols=self._direction_cols,
        )


def apply_matplotlib_config(
    matplotlib_params: dict[str, Any] | None = None,
) -> None:
    """Apply Matplotlib configuration globally.

    This function modifies plt.rcParams globally, similar to legacy
    configure_plot_params(). Use with caution as it affects all subsequent plots.

    Args:
        matplotlib_params: Matplotlib rcParams to apply.
                        If None, uses DEFAULT_PLOT_PARAMS.

    Example:
        >>> # Apply default settings
        >>> apply_matplotlib_config()
        >>>
        >>> # Apply custom settings
        >>> apply_matplotlib_config({"font.size": 16, "grid.alpha": 0.3})
        >>>
        >>> # Use with builder
        >>> builder = PlotConfigBuilder()
        >>> builder.set_matplotlib_params(font_size=18)
        >>> apply_matplotlib_config(builder.matplotlib_params)

    """
    params = DEFAULT_PLOT_PARAMS if matplotlib_params is None else matplotlib_params
    for key, value in params.items():
        plt.rcParams[key] = value
