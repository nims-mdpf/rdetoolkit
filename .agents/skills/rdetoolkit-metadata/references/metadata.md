# Typed values and repeated rows

Use the same complete invoice-mode tree as the flow-authoring recipe. This
synthetic example defines its schema inline for reproducibility; production
code normally passes `paths.tasksupport / "metadata-def.json"`. It requires
pandas/matplotlib already installed as runtime dependencies. CI checks numeric
values, units, both variable rows, and the PNG signature after real execution.

<!-- example: metadata-flow -->
```python
import pandas as pd

from rdetoolkit import flow
from rdetoolkit.nodes import build_meta, plot_lines, save_meta
from rdetoolkit.types import OutputContext


@flow
def pipeline(out: OutputContext) -> None:
    """Save definition-driven metadata and a local measurement plot."""
    definitions = {
        "temperature": {"schema": {"type": "number"}, "unit": "K"},
        "position": {"schema": {"type": "number"}, "variable": 1, "unit": "nm"},
    }
    metadata = build_meta(
        {"temperature": "300"}, definitions,
        repeated={"position": ["1.5", "2.5"]},
    )
    save_meta(metadata, out)
    frame = pd.DataFrame({"index": [0, 1], "position": [1.5, 2.5]})
    plot_lines(frame, out, "positions.png", x="index", y="position", kind="other_image")
```

Expected metadata contains constant temperature `300` with unit `K` and two
variable position cells, `1.5` and `2.5`, each with unit `nm`. The plot is written
under `other_image`. Inspect the actual JSON instead of treating a successful
import or process exit as proof of a correct scientific result.
