# Text flow

Save this block as `processing.py` in the project root. Inputs are local UTF-8
text files in `data/inputdata/`, an invoice at `data/invoice/invoice.json`, and
valid `data/tasksupport/invoice.schema.json` and `metadata-def.json`. Use the
rdetoolkit-testing recipe to create a synthetic complete tree; empty raw input
is also supported in invoice mode. CI executes this exact block through the
real Runner and checks each normalized output plus the finalized invoice.

<!-- example: authoring-flow -->
```python
from rdetoolkit import flow, node
from rdetoolkit.nodes import read_text, save_text
from rdetoolkit.types import InputPaths, OutputContext


@node
def normalize_text(text: str) -> str:
    """Normalize a local text measurement."""
    return text.strip() + "\n"


@flow
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    """Write one structured text artifact for every raw input."""
    for index, source in enumerate(paths.rawfiles):
        save_text(normalize_text(read_text(source)), out, f"structured-{index}.txt")
```

Inspect `report.status`, `report.exit_code` and `report.iterations` after
`workflows.run(flow=pipeline)`. Exit codes are 0 success, 1 failed, 2 partial;
the CLI reserves 3 for usage errors. A successful invoice-mode run writes
`data/structured/structured-0.txt` for the first input. Other processing modes
may split artifacts under `data/divided/`; verify their actual output trees.

After saving the block as `processing.py`, check the project from its root.
Doctor imports `processing` but never calls `pipeline`, and writes nothing.
Expect `"status": "passed"` and `"mode": "invoice"`; each finding names its
check, path and remediation.

<!-- example: authoring-doctor -->
```console
python -m rdetoolkit doctor --format json --ref processing:pipeline
```

Then execute the installed CLI from the project root. CI runs both exact
commands in an independent Python process.

<!-- example: authoring-run -->
```console
python -m rdetoolkit run processing:pipeline
```
