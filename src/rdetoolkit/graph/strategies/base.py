"""Base protocol for plot strategies.

This module defines the PlotStrategy protocol that all strategy classes implement.
Strategy pattern allows different plot modes (combined, individual, dual_axis)
to be implemented independently without affecting each other.
"""

from __future__ import annotations

from typing import Any, Protocol

import pandas as pd

from rdetoolkit.graph.models import PlotConfig


class PlotStrategy(Protocol):
    """Protocol for plot strategy classes.

    All plot strategies (Combined, Individual, DualAxis) implement this protocol.

    Design pattern (from refactor_plan.md):
        - **Strategy layer**: Decides WHAT to render (workflow orchestration)
        - **Renderer layer**: Decides HOW to render (actual drawing logic)
        - **I/O layer**: Decides WHERE to save (file operations)

    This separation enables:
        - Adding new plot modes without modifying existing strategies
        - Swapping rendering engines (matplotlib ↔ plotly)
        - Testing strategies with mock renderers

    Note:
        Implementation classes should accept a Renderer in their __init__:
        ```
        def __init__(self, renderer: BaseRenderer):
            self.renderer = renderer
        ```
    """

    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[Any]:
        """Execute plotting strategy and return results.

        Args:
            df: DataFrame containing plot data
            config: Plot configuration from PlotConfigBuilder

        Returns:
            List of render results. Actual type determined in Phase 6:
                - Phase 5 (current): list[Any] (placeholder)
                - Phase 6 (planned): list[RenderResult]

            Behavior depends on config.output.return_fig:
                - If return_fig=True: Returns list of Figure objects
                - If return_fig=False: Saves to disk and returns None

        Workflow (typical implementation):
            1. Validate column specifications using normalizers.validate_column_specs()
            2. Apply matplotlib configuration using config.apply_matplotlib_config()
            3. Delegate actual rendering to Renderer (Phase 6)
            4. Handle output based on config.output settings

        """
        ...
