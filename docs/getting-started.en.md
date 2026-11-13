# Getting Started with v2

This page walks you through your first rdetoolkit v2 structured processing
program: you create it, run it, and inspect what was recorded. The program is a
small flow that reads a CSV file, normalizes it, and saves a structured CSV and
a graph.

Existing programs written against v1's `run(custom_dataset_function=...)`
keep working unchanged in v2. To migrate one, see
[Migrating from v1 to v2](migration_v1_to_v2.md).

## Prerequisites

- Python 3.10 or later
- rdetoolkit 2.x

<!-- illustration: gs-install -->
```bash
$ pip install rdetoolkit
$ python -m rdetoolkit version
```

## 1. Create the project skeleton

Run `init` in an empty directory.

<!-- test: gs-init -->
```bash
$ python -m rdetoolkit init
```

The files an RDE structured program needs are created under `container/`
(this page does not use `input/` and `templates/`, which are created next to
`container/`).

<!-- illustration: gs-init-tree -->
```text
container/
├── Dockerfile
├── main.py
├── requirements.txt
├── modules/
└── data/
    ├── inputdata/
    ├── invoice/
    │   └── invoice.json
    └── tasksupport/
        ├── invoice.schema.json
        └── metadata-def.json
```

`data/` has the same layout as the directory tree on RDE: `inputdata/` holds
the input data, `invoice/` holds the invoice, and `tasksupport/` holds the
schema and the metadata definition.

## 2. Add input data

Create `container/data/inputdata/sample.csv` with this content:

<!-- test: gs-sample-csv -->
```csv
time,intensity
0,1.0
1,2.5
2,4.0
```

## 3. Write the flow

Put an empty `__init__.py` and the following `flow.py` in
`container/modules/`:

<!-- test: gs-flow -->
```python
import pandas as pd

from rdetoolkit import flow, node
from rdetoolkit.nodes import plot_lines, read_csv_with_header, save_csv
from rdetoolkit.types import InputPaths, OutputContext


@node(id="quickstart.normalize")
def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Scale the intensity column to its maximum."""
    df = df.copy()
    df["intensity"] = df["intensity"] / df["intensity"].max()
    return df


@flow(id="quickstart.pipeline")
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    for csv_path in paths.rawfiles:
        df = read_csv_with_header(csv_path)
        df = normalize(df)
        save_csv(df, out, csv_path.name)
        plot_lines(df, out, f"{csv_path.stem}.png", x="time", y="intensity")
```

Three things to note:

- `pipeline` runs as **plain Python**. The `for` loop and the f-string behave
  exactly as Python defines them.
- The Runner reads the type annotations `InputPaths` and `OutputContext` and
  passes the current data tile's input paths and output directories. The
  parameter names are up to you.
- `read_csv_with_header`, `save_csv` and `plot_lines` are rdetoolkit's
  **built-in nodes**. Like your own `normalize`, every call to them is recorded.

## 4. Write the entry point

Replace `container/main.py` with:

<!-- test: gs-main -->
```python
import rdetoolkit
from modules.flow import pipeline

report = rdetoolkit.workflows.run(flow=pipeline)
print(report.status)
```

`workflows.run(flow=...)` returns the outcome as a `RunReport`.

## 5. Run it

<!-- test: gs-run -->
```bash
$ cd container
$ python main.py
```

The run succeeded when it prints `success`. Outputs and the run record are
written under `container/data/`:

<!-- illustration: gs-run-tree -->
```text
data/
├── inputdata/sample.csv
├── structured/sample.csv          # normalized CSV
├── main_image/sample.png          # graph
├── nonshared_raw/sample.csv       # copy of the input file
└── logs/
    ├── run_report_<run_id>.json   # RunReport
    ├── events_<run_id>.jsonl      # event log
    └── iterations/iteration_0.json
```

When processing fails, the error code and message are written to
`data/job.failed`, as the RDE platform expects.

## 6. Inspect the run record

`report show` summarizes the RunReport, and `graph` shows the order in which
nodes were called (the Call Sequence).

<!-- test: gs-inspect -->
```bash
$ python -m rdetoolkit report show data/logs/run_report_<run_id>.json
$ python -m rdetoolkit graph data/logs/run_report_<run_id>.json --format mermaid
```

<!-- illustration: gs-inspect-output -->
```text
run_id: 550956f7318c414eb15a5f9175309f22
status: success
iterations: 1
```

`graph` records the **order in which nodes were called**. It is not a data
flow diagram reconstructed from how values were passed.

## 7. Run and check from the CLI

You can also run the flow directly from the CLI, without `main.py`. Use
`nodes lint` for static checks of the registered nodes.

<!-- test: gs-cli -->
```bash
$ python -m rdetoolkit run --flow modules.flow:pipeline
$ python -m rdetoolkit nodes lint --module modules.flow
```

`run --flow` writes the RunReport JSON to standard output and reports the
outcome in its exit code (0 = success, 1 = failed, 2 = partial, 3 = usage
error).

## Next steps

- [v2 Tutorial](tutorial_v2.md) — templates, flows and `run_flow` in three levels
- [Nodes](concepts/node.md), [Flows](concepts/flow.md) and [Runner](concepts/runner.md) — the core v2 concepts
- [Testing Guide](guides/testing.md) — writing tests with `rdetoolkit.testing`
- [CLI Reference](reference/cli.md) — every command and option
