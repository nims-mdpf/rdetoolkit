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
| `assert_*`, `read_*`, `iter_csv` | artifact assertions and bounded readers, see [Artifact assertions](#artifact-assertions) |
| `assert_checks(*checks)` | runs reusable checks explicitly, see [Reusable checks](#reusable-checks) |

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
| `checks` | reusable output checks run after the run, see [Reusable checks](#reusable-checks) |

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

## Artifact assertions

`RdeTestResult` has small, composable assertions on the artifacts of the
isolated run. Every name is relative to the data root (absolute and `..`
names raise `ValueError`), and every failure message names the artifact, the
exact difference and where the retained run is (data root and run report).

```python
def test_process(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    run.assert_status("success")
    run.assert_artifact("structured/result.csv")
    run.assert_artifact("job.failed", exists=False)
    run.assert_csv_columns("structured/result.csv", {"time", "value"})
    run.assert_json_subset("invoice/invoice.json", {"custom": {"temperature": 300}})
    run.assert_metadata_valid()
```

| Method | Checks | Failure shows |
|--------|--------|---------------|
| `assert_status(status)` | run status | status, run and tile errors, artifact paths |
| `assert_error_code(code)` | catalog code on the run or a tile | the recorded codes |
| `assert_artifact(name, exists=True)` | presence or absence | the path and the files next to it |
| `assert_tree(files, root=None, ignore=())` | exact file set below the data root or `root` | missing and unexpected files |
| `assert_json_subset(name, expected)` | `expected` is contained in the JSON | one line per JSON pointer |
| `assert_json_equal(name, expected)` | exact JSON content | missing, changed and unexpected pointers |
| `assert_csv_columns(name, columns, exact=False)` | CSV header | missing (and with `exact`, unexpected) columns |
| `assert_csv_rows(name, rows)` | every data row, cell by cell (cells as strings) | row count, row number and column of each change |
| `assert_metadata_valid(name="meta/metadata.json", definition="tasksupport/metadata-def.json")` | metadata structure, and every key defined in the definition (`definition=None` skips that) | validator error or undefined keys |
| `assert_invoice_valid(name="invoice/invoice.json", schema="tasksupport/invoice.schema.json")` | invoice against its schema | validator error |
| `assert_snapshot(artifact, golden, ...)` | artifact matches an approved golden copy | see [Golden snapshots](#golden-snapshots) |

JSON values are compared strictly: `1`, `1.0` and `true` are different, and
`null` is not the same as an absent key. `ignore=` of `assert_tree` takes
`fnmatch` patterns such as `"logs/*"`; nothing is ignored unless listed.

The read helpers `read_bytes`, `read_text`, `read_json` and `read_csv`
(rows as `{column: cell}` with string cells) refuse files above 16 MiB by
default (`max_bytes=None` lifts the limit); `iter_csv` streams large CSV
files. The same functions exist as
`rdetoolkit.testing.assertions.<name>(run, ...)`.

## Golden snapshots

`assert_snapshot` compares an artifact file or directory with golden files
you reviewed and committed. Expected values are never derived from
production code while the test runs.

```python
GOLDEN = Path(__file__).parent / "golden"


def test_structured_output(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    run.assert_snapshot(
        "structured",
        GOLDEN / "structured",
        ignore_fields=("/run_id",),     # JSON pointers; '*' matches any key or index
        ignore_columns=("timestamp",),  # CSV columns
        ignore_files=("*.log",),        # files left out of a directory snapshot
    )
```

- `.json` files are compared by JSON pointer, `.csv` files cell by cell,
  other text files (`.txt`, `.md`, `.yaml`, ...) as a line diff, and
  everything else (images, binary formats) by size and sha256 -- binary data
  is never decoded.
- Only what you list is normalized. An ignored field or column keeps its key
  or header (removing it is still a difference); its value is replaced by
  `<rde-snapshot:ignored>` on both sides.
- Missing and unexpected files, changed cells and values, `null` versus
  absent, `1` versus `1.0` and line-ending changes are all reported. A
  relative `golden` path is resolved against the current directory; prefer
  `Path(__file__).parent / ...`.

**Approving changes.** A snapshot that does not match (or does not exist
yet) fails and lists exactly which files would change. To approve, review
the change and run locally:

```bash
pytest --rde-update-snapshots
```

The golden files are rewritten (files no longer produced are removed) and
the terminal summary lists every file under `rdetoolkit: snapshot updates`.
The option is **refused when the `CI` environment variable is set** to a
true value, and `update=True` is refused there as well, so CI can never
approve a change.

**Privacy.** Golden files are usually committed and published with the
repository. Snapshots of `inputdata/`, `raw/` and `nonshared_raw/` are
refused unless you pass `allow_raw=True`; ignored fields are written as the
placeholder, so run IDs and timestamps do not reach the golden copy;
symlinked artifacts are refused; files above `max_bytes` (16 MiB by default)
are refused on either side. Snapshot only what may be shared.

## Reusable checks

A check is a function that takes the `RdeTestResult` and fails by raising
(normally `assert`). `rde_check(id=...)` only gives it a stable rule ID for
failure messages and returns the same function; plain functions and lambdas
work too.

```python
from rdetoolkit.testing import rde_case, rde_check


@rde_check(id="xrd.positive-intensity")
def positive_intensity(run):
    rows = run.read_csv("structured/peaks.csv")
    assert all(float(row["intensity"]) >= 0 for row in rows)


@rde_check(id="invoice.temperature")
def physical_temperature(run):
    assert run.read_json("invoice/invoice.json")["custom"]["temperature"] >= 0


@rde_case(flow=main, project="tests/cases/xrd", checks=(positive_intensity, physical_temperature))
def test_xrd(rde_run):
    pass


def test_xrd_without_the_decorator(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    positive_intensity(run)  # a plain call
    run.assert_checks(positive_intensity, physical_temperature)
```

- Checks run after the real Runner has finished and only where a test lists
  them; nothing is registered, and production runs never call them.
- With `rde_case`, checks run once `expect_status` holds, and every failing
  check is reported. If the processing outcome is not the expected one, the
  case reports that instead and says the checks were not run.
- A failure reads `output contract failed: rde_check '<id>'` and names the
  dataset, every artifact the check read through the result helpers with
  its tile (`divided/0001/...` is tile 1) and datatile, the assertion and
  its line.
- A failing check fails the pytest test only: the run's `RunReport.status`
  and `job.failed` are unchanged.
- A check that returns a value (for example `return all(...)`) fails:
  checks must raise, so a forgotten `assert` cannot pass silently.

A negative case pairs a known-bad dataset with the check and expects the
failure explicitly:

```python
def test_negative_intensity_is_caught(rde_runner):
    run = rde_runner.run(flow=main, project="tests/cases/xrd_negative")
    with pytest.raises(AssertionError, match="xrd.positive-intensity"):
        run.assert_checks(positive_intensity)
```

## `rdetoolkit test`

`rdetoolkit test [PATH] [PYTEST_ARGS]...` runs `python -m pytest` with the
same interpreter, in the current directory, with every argument forwarded
unchanged, and exits with pytest's exit code. It is a convenience for first
steps; `pytest` itself is fully equivalent and remains the recommended
command in CI, where you control plugins and options directly.

```bash
pip install "rdetoolkit[testing]"   # pytest is not installed with rdetoolkit
rdetoolkit test
rdetoolkit test tests/ -k xrd -x
rdetoolkit test -- --help           # options after '--' always go to pytest
```

Without pytest the command prints the installation hint and exits 2.
Under either command, a failing test that used `rde_runner` or `rde_run`
shows an `rdetoolkit: retained runs` section after pytest's own failure output, with
each run's data root, run report, diagnostics sidecar and `job.failed`.

## Without pytest

Importing `rdetoolkit.testing` never imports pytest, and `RdeTestRunner`
works in plain scripts. Only `rde_case(...)` requires pytest and raises
`ImportError` with an explanation when it is missing.
