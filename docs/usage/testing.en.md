# Testing Structured Processing

rdetoolkit ships a pytest plugin (registered through the `pytest11` entry
point, so it loads automatically once rdetoolkit and pytest are installed).
It offers three levels of testing; pick the smallest one that covers what you
want to check.

| Level | Tool | Runs the Runner | Typical use |
|-------|------|-----------------|-------------|
| Unit | call the `@node` / `@flow` function directly, `rde_paths`, `rde_out`, `rde_config`, `rde_invoice` fixtures | no | one node's logic |
| Integration | `rde_runner` fixture → `RdeTestResult` | yes, on a staged copy | a real project with its invoice and tasksupport |
| Declarative | `rde_case` marker + `rde_run` fixture | yes, on a staged copy | one scenario per instrument or data shape |

`rdetoolkit.testing.run_flow` remains available unchanged.

## Isolated runs with `rde_runner`

```python
from pathlib import Path

from modules.processing import main  # your flow

PROJECT = Path(__file__).parent / "cases" / "sample"


def test_process(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    run.assert_success()
    assert (run.data_root / "structured" / "result.csv").exists()
```

`rde_runner.run(flow=..., project=..., config=None)`:

- copies `project` into a new directory below the test's `tmp_path`
  (`<tmp_path>/rde_runner/run-NNN/<project name>`). The source fixture is
  never written, and every call stages its own copy, so tests do not depend
  on each other or on execution order. Symlinks are copied by content.
- accepts both layouts: a project directory holding `data/`
  (`data/inputdata`, `data/invoice`, `data/tasksupport`) and an alias-flat
  data root (`inputdata/`, `invoice/`, `tasksupport/` directly inside). The
  data root is resolved with the same rule as production.
- runs the flow through the real Runner, exactly like
  `workflows.run(flow=..., config=...)`, with the staged project as working
  directory. The caller's working directory is restored afterwards.
- `config` is an `RdeConfig` or an override mapping
  (e.g. `{"system": {"extended_mode": "MultiDataTile"}}`), so every mode can
  be tested.
- `flow` is a flow callable or a concrete `ProcessingTemplate` subclass.
- A relative `project` is resolved against the current working directory.

A failed run is **returned, not raised**. Exceptions that escape the Runner
itself (for example `KeyboardInterrupt`, or a `TypeError` for a non-callable
flow) propagate unchanged; the staged copy stays for inspection.

### `RdeTestResult`

| Attribute | Meaning |
|-----------|---------|
| `report` | the `RunReport` |
| `status` | `"success"`, `"partial"` or `"failed"` |
| `project_root` | the staged project copy |
| `data_root` | the staged data root |
| `iterations` | one `RdeIterationSummary` per tile (`index`, `datatile_id`, `status`, `error_code`, `error_name`, `error_message`) |
| `report_path` | `logs/run_report_<run_id>.json`, or `None` |
| `events_path` | `logs/events_<run_id>.jsonl`, or `None` |
| `diagnostics_path` | `logs/diagnostics_<run_id>.json`, or `None` when the run wrote no diagnostics sidecar |
| `job_failed_path` | `job.failed`, or `None` |
| `artifact_path(name)` | `data_root / name`; absolute names and names containing `..` raise `ValueError` |
| `assert_success()` | raises `AssertionError` unless the run succeeded |

`assert_success()` names the status, the run error and every failed tile
(catalog code, name, message and recorded stack trace), and points at the
data root, `job.failed`, the run report and the diagnostics sidecar.

`RdeTestRunner(base_dir)` is the same runner without pytest; the fixture is
`RdeTestRunner(tmp_path / "rde_runner")`.

## Declarative cases with `rde_case`

```python
from rdetoolkit.testing import rde_case

from modules.processing import main


@rde_case(
    flow=main,
    project="tests/cases/valid_measurement",
    expect_status="success",
    expect_files=("structured/result.csv",),
)
def test_valid_measurement(rde_run):
    assert "time" in rde_run.artifact_path("structured/result.csv").read_text(encoding="utf-8")
```

`rde_case(...)` returns an ordinary pytest mark (`pytest.mark.rde_case`).
It runs nothing when the test module is imported or collected:
`pytest --collect-only` and editor test discovery never execute flows, copy
data or write files.

The `rde_run` fixture reads the closest `rde_case` marker at fixture setup,
runs the case through `rde_runner`, and returns the `RdeTestResult`. Before
the test body runs, the declared expectations are checked; a violated
expectation makes the test **fail** with an explanation.

| Parameter | Meaning |
|-----------|---------|
| `flow` | flow callable or concrete `ProcessingTemplate` subclass (required) |
| `project` | project directory or alias-flat data root (required); a relative path is resolved against pytest's rootdir |
| `expect_status` | `"success"` (default), `"partial"` or `"failed"` |
| `expect_files` | artifacts that must exist, relative to the isolated data root |
| `expect_error_code` | catalog code the run or one of its tiles must record (non-success cases only) |
| `expect_phase` | phase the diagnostics sidecar must record (non-success cases only) |
| `config` | `RdeConfig` or override mapping |

Misconfiguration is reported at fixture setup as a test error with a message
naming the parameter, before any data is copied: positional arguments,
unknown parameters, a missing or non-directory project, an unknown status,
`expect_files` given as a single string, an absolute or `..` expected path,
and an error code or phase on a success case. A test marked with `rde_case`
that does not request `rde_run` is also an error, because its case would
never run.

### Several data cases

Give each parameter its own case with `pytest.param(..., marks=...)`; the
`id` becomes the readable test ID.

```python
import pytest


@pytest.mark.parametrize(
    "label",
    [
        pytest.param("valid", marks=rde_case(flow=main, project="tests/cases/valid"), id="valid-measurement"),
        pytest.param(
            "broken",
            marks=rde_case(flow=main, project="tests/cases/broken", expect_status="failed", expect_error_code=3001),
            id="broken-reader",
        ),
    ],
)
def test_measurements(rde_run, label):
    ...
```

Ordinary `pytest.mark.parametrize` arguments combine with a decorated case as
usual; each item runs the case on its own copy.

## From a repro archive

A failure captured with `rdetoolkit repro export` can become a regression
test. `rdetoolkit repro to-pytest` writes the `rde_case` for you (see the
[CLI reference](cli.en.md#repro-to-pytest-turn-an-archived-run-into-a-regression-test)):

```shell
rdetoolkit repro import failure.zip tests/cases/failure      # or let to-pytest stage it
rdetoolkit repro to-pytest failure.zip --ref modules.processing:main \
    -o tests/test_regression_failure.py --project tests/cases/failure
```

The generated module looks like this (abridged):

```python
from pathlib import Path

from rdetoolkit.testing import RdeTestResult, rde_case

from modules.processing import main as flow_under_test

PROJECT = Path(__file__).parent / "cases/failure"


@rde_case(
    flow=flow_under_test,
    project=PROJECT,
    # The behaviour expected after the fix, not the archived outcome: the
    # archived run ended 'failed' (error code 3001).
    expect_status="success",
    expect_files=[],
)
def test_regression_9f3c2a7e(rde_run: RdeTestResult) -> None:  # named after the run id
    assert rde_run.status == "success"
    # Add expectations derived independently of the implementation under test ...
```

Work through it in this order:

1. Run it before fixing anything: it **fails**, because it expects `success`
   while the defect is still there. The archived failure is never accepted
   as the expected result; pass `--expect-status failed` only when you have
   confirmed that failing is the correct behaviour.
2. Fix the flow and run it again until it passes.
3. Record what the fixed flow must produce: list the artifacts in
   `expect_files` and replace the assertion template with expectations you
   derived independently, such as values checked by hand or a reviewed
   golden file. Never copy the current output of the implementation under
   test into the test; such a test only proves that the code does what it
   does. When a later change alters an expected artifact, update it the same
   way: verify the new value independently, then edit the expectation.
4. Commit the test. If you used `--stage-inputs`, the directory holds the
   archived raw inputs: commit it only if that data may be stored with your
   tests.

## Without pytest

Importing `rdetoolkit.testing` never imports pytest, and `RdeTestRunner`
works in plain scripts. Only `rde_case(...)` requires pytest and raises
`ImportError` with an explanation when it is missing.
