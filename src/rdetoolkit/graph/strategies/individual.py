from __future__ import annotations

import pandas as pd

from rdetoolkit.graph.models import PlotConfig, RenderResult
from rdetoolkit.graph.renderers.base import BaseRenderer
from rdetoolkit.graph.textutils import parse_header, sanitize_filename, to_snake_case


class IndividualStrategy:
    """Strategy for plotting each data series individually.

    Equivalent to Legacy plot_individual_graphs().

    Features:
        - One PNG per series
        - Direction-based line splitting within each graph
        - Series name in title: "{title} - {series_name}"
        - Skippable via config.output.no_individual

    Design:
        - Loops over y_cols and generates separate figures
        - Rendering logic delegated to Renderer

    Workflow:
        1. Check config.output.no_individual flag (early return if True)
        2. Loop over y_cols
        3. For each series, delegate to renderer.render_individual()
        4. Return list of RenderResult objects
    """

    def __init__(self, renderer: BaseRenderer) -> None:
        """Initialize strategy with renderer.

        Args:
            renderer: Renderer instance (e.g., MatplotlibRenderer)
        """
        self.renderer = renderer

    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[RenderResult] | None:
        """Plot each series individually.

        Args:
            df: DataFrame with plot data
            config: Plot configuration

        Returns:
            - If no_individual=True: None (early return)
            - Otherwise: list[RenderResult] (one per series)
        """
        if config.output.no_individual:
            return None

        if config.y_cols is None:
            msg = "y_cols must be specified in PlotConfig"
            raise ValueError(msg)

        results = []

        for position, y_col_spec in enumerate(config.y_cols):
            if isinstance(y_col_spec, str):
                col_idx = df.columns.get_loc(y_col_spec)
                if not isinstance(col_idx, int):
                    msg = f"Column '{y_col_spec}' resolved to non-integer index"
                    raise ValueError(msg)
            else:
                col_idx = y_col_spec

            series_name = str(df.columns[col_idx])
            parsed_series, _, _ = parse_header(series_name)
            name_for_file = parsed_series if parsed_series else series_name
            series_name_snake = to_snake_case(name_for_file)

            figure = self.renderer.render_individual(df, config, col_idx, position)
            base_name_raw = config.output.base_name or config.title or "plot"
            base_name = sanitize_filename(str(base_name_raw)) or "plot"
            filename = f"{base_name}_{series_name_snake}.png"

            results.append(RenderResult(
                figure=figure,
                filename=filename,
                format="png",
            ))

        return results
