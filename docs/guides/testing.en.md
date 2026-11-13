# Testing Guide

v2 nodes and flows are ordinary Python functions, so you can test them with pytest as they are.
`rdetoolkit.testing` provides fixtures and helpers that save you the work of preparing
reserved-type values and the RDE directory layout.

## Four levels of testing

| Level | Target | How |
|-------|--------|-----|
| 1 | A single node or slot | Call it directly as a function or method |
| 2 | A single flow | Call it directly with reserved-type values built by fixtures |
| 3 | Integration with the Runner | Run it through the real Runner with `run_flow()` |
| 4 | The output tree | Compare the directory layout with `assert_output_tree()` |

Most tests can be written at levels 1 and 2. Use level 3 when you want to check behavior that
includes mode determination, the invoice and `job.failed`.

## What is provided

Installing rdetoolkit registers a pytest plugin automatically. Without writing a `conftest.py`,
you can use the following fixtures just by naming them as test arguments.

| Fixture | Type | Content |
|---------|------|---------|
| `rde_paths` | `InputPaths` | A minimal input tree in a temporary directory |
| `rde_out` | `OutputContext` | An output destination with every output directory already created |
| `rde_config` | `RdeConfig` | The default configuration |
| `rde_invoice` | `InvoiceData` | A minimal invoice |

| Helper | Content |
|--------|---------|
| `make_input_paths(tmp_path, files=...)` | Creates an input tree, creates each of `files` as an empty file in `inputdata/` and lists them in `rawfiles` |
| `make_output_context(tmp_path)` | Returns an `OutputContext` with the full set of output directories created |
| `make_invoice(overrides=...)` | Builds an invoice. Keys other than sections such as `basic` go into `custom` |
| `run_flow(flow, fixture_dir)` | Runs the Runner on a temporary RDE tree whose inputs are the files in `fixture_dir`, and returns the RunReport |
| `run_flow(flow, data_root=root)` | Runs an existing RDE tree in place, leaving the outputs and `job.failed` behind |
| `assert_output_tree(out, golden_dir)` | Checks that the directory layout of the output destination matches `golden_dir` |

## Example: writing tests for a project

We test the following `modules/processing.py`. It contains a node that finds the maximum value
in a CSV, a flow that uses it, and a class that writes the same processing as a template slot.

<!-- test: testing-source -->
```python
from typing import final

import pandas as pd

from rdetoolkit import flow, node
from rdetoolkit.nodes import read_csv_with_header, save_csv
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths, OutputContext


@node(id="example.find_peak")
def find_peak(df: pd.DataFrame) -> float:
    """Return the largest intensity."""
    return float(df["intensity"].max())


@flow(id="example.pipeline")
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    for csv_path in paths.rawfiles:
        peak = find_peak(read_csv_with_header(csv_path))
        save_csv(pd.DataFrame({"peak": [peak]}), out, f"{csv_path.stem}_peak.csv")


class PeakTemplate(ProcessingTemplate):
    @slot
    def peak(self, df: pd.DataFrame) -> float: ...

    @final
    def __flow__(self, paths: InputPaths, out: OutputContext) -> None:
        for csv_path in paths.rawfiles:
            peak = self.peak(read_csv_with_header(csv_path))
            save_csv(pd.DataFrame({"peak": [peak]}), out, f"{csv_path.stem}_peak.csv")


class CsvPeak(PeakTemplate):
    def peak(self, df: pd.DataFrame) -> float:
        return float(df["intensity"].max())
```

The tests go in `tests/test_processing.py`.

<!-- test: testing-tests -->
```python
import pandas as pd

from rdetoolkit.testing import make_input_paths, run_flow

from modules.processing import CsvPeak, find_peak, pipeline

CSV = "time,intensity\n0,1.0\n1,3.0\n2,2.0\n"


def test_find_peak():
    # Level 1: a node is a plain function.
    assert find_peak(pd.DataFrame({"intensity": [1.0, 3.0, 2.0]})) == 3.0


def test_slot():
    # Level 1: a template slot is a plain method.
    assert CsvPeak().peak(pd.DataFrame({"intensity": [1.0, 3.0]})) == 3.0


def test_pipeline_direct(tmp_path, rde_out):
    # Level 2: call the flow with fixture-built reserved values.
    paths = make_input_paths(tmp_path / "input", files=["sample.csv"])
    paths.rawfiles[0].write_text(CSV, encoding="utf-8")
    pipeline(paths, rde_out)
    assert (rde_out.struct / "sample_peak.csv").read_text(encoding="utf-8").splitlines() == ["peak", "3.0"]


def test_pipeline_through_runner(tmp_path):
    # Level 3: run the real Runner on a temporary RDE tree.
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "sample.csv").write_text(CSV, encoding="utf-8")
    report = run_flow(pipeline, fixture_dir)
    assert report.status == "success"
    calls = [call["node_id"] for call in report.iterations[0]["node_calls"]]
    assert "example.find_peak" in calls


def test_template_through_runner(tmp_path):
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "sample.csv").write_text(CSV, encoding="utf-8")
    assert run_flow(CsvPeak, fixture_dir).status == "success"
```

Run them in the project directory. `python -m pytest` adds the current directory to the
import path, so the `modules` package can be imported as it is.

<!-- test: testing-run -->
```bash
$ python -m pytest tests
```

## Two ways to use `run_flow`

- `run_flow(flow, fixture_dir)` runs on a temporary tree in which the files of `fixture_dir` are
  copied into `inputdata/` (with a synthesized invoice and an empty schema), and deletes the tree
  afterwards. It suits checking the RunReport status and the call log.
- `run_flow(flow, data_root=root)` runs, in place, an RDE tree that has real `invoice.json`,
  `invoice.schema.json` and `metadata-def.json` files (or a project that has such a tree under
  `data/`). The artifacts and `job.failed` remain, so you can inspect their content after the run.

In both cases the current directory is restored after the run.

## Comparing output trees

`assert_output_tree(out, golden_dir)` compares the output directory layout of `out` (the set of
directories) with the layout under `golden_dir`, and fails with `missing` / `extra` if anything
is missing or extra. Do not write the expected tree by hand; create it from the result of a run
that worked correctly.

## Checking in CI

Node and template registrations can be checked without running anything. Running `nodes lint`
in CI in addition to pytest detects missing type annotations, unstable node IDs and misuse of
templates.

<!-- test: testing-lint -->
```bash
$ python -m rdetoolkit nodes lint --module modules.processing
```

## Related pages

- [Flows](../concepts/flow.md) — reserved types and dependency injection
- [v2 Tutorial](../tutorial_v2.md) — level 3, using `run_flow`
- [API reference: rdetoolkit.testing](../rdetoolkit/v2/testing.md)
