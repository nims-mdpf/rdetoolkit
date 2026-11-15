"""Compatibility placeholder for the unsupported dual-axis mode (GE-12).

Dual-axis plotting is not part of the rdetoolkit 2.0 API. ``DualAxisStrategy`` stays
importable from ``rdetoolkit.graph.strategies.dual_axis`` (and, for compatibility, as
an attribute of ``rdetoolkit.graph.strategies``) but is no longer exported in
``__all__``; rendering with it always raises.
"""

from __future__ import annotations

import pandas as pd

from rdetoolkit.graph import compat
from rdetoolkit.graph.models import PlotConfig


class DualAxisStrategy:
    """Dual-axis plotting strategy: NOT SUPPORTED, kept for import compatibility.

    The prototype failed with an ``IndexError`` while building the legend of
    auto-split y1/y2 series, so the mode was never usable. Every call raises the same
    typed error as the other legacy entry points, naming the alternatives
    (``unit_policy='split'``, ``mode='individual'``, Matplotlib ``twinx`` with the
    ``save_figure`` node).
    """

    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[None]:
        """Refuse to render; dual-axis plotting is not supported.

        Args:
            df: DataFrame (unused)
            config: Plot configuration (unused)

        Raises:
            PlotRequestError: Always, with ``reason="dual_axis_unsupported"``; it is
                a ``PlotConfigError`` (and a ``ValueError``) like before.
        """
        raise compat.dual_axis_unsupported_error()
