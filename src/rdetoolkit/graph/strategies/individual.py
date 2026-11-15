from __future__ import annotations

import warnings
from typing import Final

import pandas as pd

from rdetoolkit.graph.models import PlotConfig, RenderResult
from rdetoolkit.graph.renderers.base import BaseRenderer
from rdetoolkit.graph.exceptions import GraphUserWarning
from rdetoolkit.graph.naming import reserve_stems, series_stem
from rdetoolkit.graph.textutils import parse_header

DEFAULT_IMAGE_FORMAT: Final = "png"


class IndividualStrategy:
    """Strategy for plotting each data series individually.

    Equivalent to Legacy plot_individual_graphs().

    Features:
        - One figure per series, written in every non-HTML format of
          ``config.output.formats`` (PNG when none is requested)
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
        stems = self._reserve_stems(df, config, positions)
        formats = _image_formats(config)

        results: list[RenderResult] = []
        for position, (col_idx, stem) in enumerate(zip(positions, stems, strict=True)):
            # One figure per series, written once per requested image format.
            figure = self.renderer.render_individual(df, config, col_idx, position)
            results.extend(RenderResult(figure=figure, filename=f"{stem}.{fmt}", format=fmt) for fmt in formats)

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
    def _reserve_stems(df: pd.DataFrame, config: PlotConfig, positions: list[int]) -> list[str]:
        """Reserve one unique file stem per series, in series order.

        Names are decided for all series up front so that two series can never
        overwrite each other and a bad name fails before anything is rendered.
        Unique stems stay unique in every format, since all formats share them.
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
        return list(stems)


def _image_formats(config: PlotConfig) -> list[str]:
    """The non-HTML formats of ``OutputConfig.formats``, lower-cased, first-seen order.

    HTML is an overlay-only artifact (format matrix), so it is skipped here. When no
    image format remains, individual figures fall back to PNG as they always did.
    """
    requested = dict.fromkeys(fmt.lower() for fmt in config.output.formats or [])
    return [fmt for fmt in requested if fmt != "html"] or [DEFAULT_IMAGE_FORMAT]
