from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from rdetoolkit.graph.readers.base import TableData, TableReader
from rdetoolkit.graph.readers.registry import ReaderRegistry
from rdetoolkit.graph.renderers.registry import RendererRegistry
from rdetoolkit.graph.result import GraphResult
from rdetoolkit.graph.spec import GraphSpec, OutputSpec

def render_graph(
    source: pd.DataFrame | Sequence[pd.DataFrame] | TableData | str | Path,
    spec: GraphSpec | None = None,
    *,
    output: OutputSpec | None = None,
    reader: str | TableReader = "auto",
    readers: ReaderRegistry | None = None,
    renderers: RendererRegistry | None = None,
) -> GraphResult: ...
