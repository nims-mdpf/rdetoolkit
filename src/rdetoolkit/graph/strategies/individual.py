from __future__ import annotations

import warnings

import pandas as pd

from rdetoolkit.graph.models import PlotConfig, RenderResult
from rdetoolkit.graph.renderers.base import BaseRenderer
from rdetoolkit.graph.exceptions import GraphUserWarning
from rdetoolkit.graph.naming import reserve_stems, series_stem
from rdetoolkit.graph.textutils import parse_header


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
        2. Resolve every y column and reserve all file names (naming.py) before
           the first figure is rendered
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

        positions = [self._resolve_column_index(df, spec) for spec in config.y_cols]
        filenames = self._reserve_filenames(df, config, positions)

        results = []
        for position, (col_idx, filename) in enumerate(zip(positions, filenames, strict=True)):
            figure = self.renderer.render_individual(df, config, col_idx, position)
            results.append(RenderResult(
                figure=figure,
                filename=filename,
                format="png",
            ))

        return results

    @staticmethod
    def _resolve_column_index(df: pd.DataFrame, spec: int | str) -> int:
        """Resolve one y column spec to its integer position."""
        if not isinstance(spec, str):
            return spec
        col_idx = df.columns.get_loc(spec)
        if not isinstance(col_idx, int):
            msg = f"Column '{spec}' resolved to non-integer index"
            raise ValueError(msg)
        return col_idx

    @staticmethod
    def _reserve_filenames(df: pd.DataFrame, config: PlotConfig, positions: list[int]) -> list[str]:
        """Reserve one unique PNG file name per series, in series order.

        Names are decided for all series up front so that two series can never
        overwrite each other and a bad name fails before anything is rendered.
        Each resolved collision is reported as a ``GraphUserWarning``.
        """
        base_name = str(config.output.base_name or config.title or "plot")
        candidates = []
        for position, col_idx in enumerate(positions):
            header = str(df.columns[col_idx])
            header_series, _, _ = parse_header(header)
            candidates.append((f"s{position:03d}", series_stem(base_name, header_series, header)))
        stems, diagnostics = reserve_stems(candidates)
        for diagnostic in diagnostics:
            warnings.warn(f"{diagnostic.code}: {diagnostic.message}", GraphUserWarning, stacklevel=2)
        return [f"{stem}.png" for stem in stems]
