"""Draw graphs with a custom ``GraphRenderer``.

The renderer below writes a minimal SVG (one polyline per series) without Matplotlib.
It implements the four members of the ``GraphRenderer`` protocol
(``capabilities``, ``render``, ``export`` and ``close``) and is injected through a
caller-owned ``RendererRegistry``: ``render_graph`` sends every artifact to the first
registered renderer whose capabilities declare its format and figure kind. rdetoolkit
itself is not modified, and only the public ``rdetoolkit.graph`` API is imported.

Run it with ``python custom_renderer.py <output directory>``.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd

from rdetoolkit.graph import (
    DirectorySink,
    FigurePlan,
    GraphResult,
    GraphSpec,
    OutputSpec,
    PlotData,
    PlotPlan,
    RendererCapabilities,
    RendererRegistry,
    render_graph,
)

WIDTH = 400
HEIGHT = 300


def _points(x_values: Any, y_values: Any, bounds: tuple[float, float, float, float]) -> str:
    """Scale one series into the SVG viewport (y grows downwards in SVG)."""
    x_min, x_max, y_min, y_max = bounds
    x_span = (x_max - x_min) or 1.0
    y_span = (y_max - y_min) or 1.0
    pairs = zip(x_values, y_values, strict=True)
    return " ".join(
        f"{(x - x_min) / x_span * WIDTH:.1f},{HEIGHT - (y - y_min) / y_span * HEIGHT:.1f}" for x, y in pairs
    )


class SvgSketchRenderer:
    """A dependency-free renderer producing one small SVG per figure."""

    @property
    def capabilities(self) -> RendererCapabilities:
        """Declare the formats and figure kinds this renderer can draw."""
        return RendererCapabilities(
            renderer_id="svg-sketch",
            formats=frozenset({"svg"}),
            figure_kinds=frozenset({"overlay", "individual"}),
        )

    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> dict[str, Any]:
        """Collect the series of one figure from the resolved plan.

        Args:
            plan: The resolved plot plan (labels, columns, axes).
            figure: The figure to draw; ``figure.series_ids`` selects its series.
            data: The frames the plan was built from.

        Returns:
            A handle with the title and ``(label, x, y)`` per series.
        """
        series = []
        for entry in plan.series:
            if entry.series_id in figure.series_ids:
                for _direction, x_values, y_values in data.segments(entry):
                    series.append((entry.label, list(x_values), list(y_values)))
        return {"title": figure.title or figure.figure_id, "series": series}

    def export(self, handle: dict[str, Any], fmt: str, *, dpi: int) -> bytes:
        """Serialize the handle as SVG bytes (``dpi`` does not apply to SVG text)."""
        del fmt, dpi
        xs = [x for _label, x_values, _y in handle["series"] for x in x_values]
        ys = [y for _label, _x, y_values in handle["series"] for y in y_values]
        bounds = (min(xs), max(xs), min(ys), max(ys))
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}">',
            f"<title>{escape(handle['title'])}</title>",
        ]
        for label, x_values, y_values in handle["series"]:
            points = _points(x_values, y_values, bounds)
            lines.append(f'<polyline fill="none" stroke="black" points="{points}"><title>{escape(label)}</title></polyline>')
        lines.append("</svg>")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def close(self, handle: dict[str, Any]) -> None:
        """Release the handle; a plain dict holds no resources."""
        handle.clear()


def main(output_dir: Path) -> GraphResult:
    """Plot two series as one overlay and two individual SVGs.

    Args:
        output_dir: Directory receiving the SVG files.

    Returns:
        The graph result; its manifest lists every written file.
    """
    frame = pd.DataFrame({"time (s)": [0, 1, 2, 3], "signal (mV)": [1.0, 2.5, 2.0, 4.0], "noise (mV)": [0.5, 0.25, 0.75, 0.5]})
    return render_graph(
        frame,
        GraphSpec(title="Sketch", layout="both"),
        output=OutputSpec(sink=DirectorySink(output_dir), formats=("svg",), base_name="sketch"),
        renderers=RendererRegistry([SvgSketchRenderer()]),
    )


if __name__ == "__main__":
    result = main(Path(sys.argv[1] if len(sys.argv) > 1 else "graph_engine_output"))
    print(result.manifest_json())  # noqa: T201 - command-line demo output
