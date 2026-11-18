from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import Any, cast

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
from rdetoolkit.graph.spec import StyleSpec


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

    The builder keeps the full Matplotlib settings (``fig_size``,
    ``matplotlib_params``: house defaults plus overrides) for inspection. Only the
    explicitly set parts reach ``PlotConfig.style`` (a ``StyleSpec``), so the
    renderers apply them over the house defaults; without a style setter the
    legacy appearance is unchanged. The setters never validate: an invalid size or
    rcParam is rejected when the figure is planned (``PlotRequestError``).

    Example:
        >>> builder = PlotConfigBuilder()
        >>> config = (builder
        ...     .set_mode(PlotMode.OVERLAY)
        ...     .set_title("Test Plot")
        ...     .set_figure_size(10, 6)
        ...     .set_matplotlib_params(font_size=18)
        ...     .build())
        >>> config.style
        StyleSpec(figure_size=(10, 6), rc_params=mappingproxy({'font.size': 18}))
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
        # Only what a setter stated becomes PlotConfig.style; the defaults stay implicit.
        self._figure_size_set = False
        self._rc_overrides: dict[str, Any] = {}
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
            mode: Plot mode (OVERLAY or INDIVIDUAL). ``DUAL_AXIS`` is accepted
                here for compatibility, but rendering the built config raises
                ``PlotRequestError(reason="dual_axis_unsupported")``.

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
        self._figure_size_set = True
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
            self._rc_overrides[mpl_key] = value
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
        """Set secondary Y-axis configuration (dual-axis plots are NOT supported).

        Kept for compatibility: the value is stored on ``PlotConfig.y2_axis``, but
        rendering a config whose ``y2_axis`` is not ``None`` raises
        ``PlotRequestError(reason="dual_axis_unsupported")``. Plot the series per unit
        instead (``GraphSpec(unit_policy="split")`` or ``mode="individual"``).

        Args:
            axis_config: Y2-axis configuration (None to clear it)

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
            ``PlotConfig.style`` carries only what ``set_figure_size`` /
            ``set_matplotlib_params`` stated (``None`` when neither was called);
            there are no ``fig_size`` / ``matplotlib_params`` attributes on
            PlotConfig. The full settings stay readable via ``builder.fig_size``
            and ``builder.matplotlib_params``.

        Example:
            >>> config = builder.set_figure_size(10, 8).build()
            >>> config.style.figure_size
            (10, 8)
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
            style=self._style(),
        )

    def _style(self) -> StyleSpec | None:
        """The explicitly requested style, or ``None`` for the legacy appearance."""
        if not (self._figure_size_set or self._rc_overrides):
            return None
        return StyleSpec(
            figure_size=self._fig_size if self._figure_size_set else None,
            rc_params=dict(self._rc_overrides),
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
    cast(MutableMapping[str, Any], plt.rcParams).update(params)


def determine_titles(
    *, title: str | None, name: str | None,
) -> tuple[str | None, str]:
    """Resolve display title and base filename for outputs.

    Determines the title shown in plots and the base filename for saved outputs
    based on user-provided title and name parameters. The function follows
    a specific precedence: title takes precedence for display, name for filename.

    Args:
        title: Desired plot title (also used for filename if name is None)
        name: Desired base filename (takes precedence over title for filename)

    Returns:
        A tuple containing:
            - display_title: Title to show in plot (title if provided, else name)
            - base_filename: Base name for output files (name if provided,
                            else title, else "plot")

    Example:
        >>> determine_titles(title="My Plot", name="output")
        ('My Plot', 'output')
        >>> determine_titles(title="My Plot", name=None)
        ('My Plot', 'My Plot')
        >>> determine_titles(title=None, name="output")
        ('output', 'output')
        >>> determine_titles(title=None, name=None)
        (None, 'plot')
    """
    display_title = title if title is not None else name
    base_filename = name or title or "plot"
    return display_title, base_filename


def determine_formats(html: bool, return_fig: bool) -> list[str]:
    """Compute output formats based on execution mode.

    Determines which file formats to generate based on whether HTML output
    is requested and whether the function will return figure objects directly.

    Args:
        html: If True, request HTML (Plotly) output in addition to PNG
        return_fig: If True, figures will be returned in memory (not saved to disk)

    Returns:
        List of format strings to generate. Always includes "png".
        Adds "html" only when html=True and return_fig=False.

    Note:
        When return_fig=True, HTML format is excluded because figures are
        returned as Matplotlib objects (not compatible with HTML/Plotly).

    Example:
        >>> determine_formats(html=False, return_fig=False)
        ['png']
        >>> determine_formats(html=True, return_fig=False)
        ['png', 'html']
        >>> determine_formats(html=True, return_fig=True)
        ['png']
    """
    formats = ["png"]
    if html and not return_fig:
        formats.append("html")
    return formats


def normalize_axis_limits(
    limits: tuple[float | None, float | None] | None,
) -> tuple[float, float] | None:
    """Return axis limits only when both bounds are specified.

    Validates and normalizes axis limit specifications. Returns None unless
    both start and end bounds are explicitly provided as non-None values.

    Args:
        limits: Axis limit specification as (start, end) tuple,
                where each bound can be None to indicate auto-scaling

    Returns:
        Tuple of (start, end) floats if both are specified, otherwise None

    Note:
        Matplotlib requires both bounds to be specified for manual limits.
        Partial specifications (e.g., (0, None) or (None, 10)) are treated
        as auto-scaling and return None.

    Example:
        >>> normalize_axis_limits((0.0, 10.0))
        (0.0, 10.0)
        >>> normalize_axis_limits((None, 10.0))
        None
        >>> normalize_axis_limits((0.0, None))
        None
        >>> normalize_axis_limits(None)
        None
    """
    if not limits:
        return None
    start, end = limits
    if start is None or end is None:
        return None
    return (start, end)
