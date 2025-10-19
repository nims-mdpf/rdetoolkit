from __future__ import annotations

import pandas as pd

from rdetoolkit.graph.exceptions import PlotConfigError
from rdetoolkit.graph.models import PlotConfig


class DualAxisStrategy:
    """Dual-axis plotting strategy (EXPERIMENTAL - DISABLED).

    From review.md:
        - IndexError in default mode (legends mismatch)
        - Disabled at CLI level
        - Raises PlotConfigError at API level

    Future work:
        - Fix legend generation for auto-split y1_cols/y2_cols
        - Enable after proper column inference logic
    """

    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[None]:
        """Raise PlotConfigError for dual_axis mode.

        Args:
            df: DataFrame (unused)
            config: Plot configuration (unused)

        Raises:
            PlotConfigError: Always raised (feature disabled)
        """
        msg = (
            "dual_axis mode is experimental and currently disabled due to "
            "IndexError in legend generation. Use mode='combined' or 'individual' instead."
        )
        raise PlotConfigError(msg)
