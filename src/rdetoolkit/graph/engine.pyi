from collections.abc import Sequence
from typing import Final

import pandas as pd

from rdetoolkit.graph.result import GraphResult
from rdetoolkit.graph.spec import GraphSpec, OutputSpec

RENDERER_ID: Final[str]
IMAGE_FORMATS: Final[tuple[str, ...]]

def render_graph(
    source: pd.DataFrame | Sequence[pd.DataFrame],
    spec: GraphSpec | None = None,
    *,
    output: OutputSpec | None = None,
) -> GraphResult: ...
