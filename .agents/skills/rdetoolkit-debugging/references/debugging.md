# Failure, repair, rerun

Use a complete local invoice-mode fixture, with one text file under
`data/inputdata/`. Set that file to `invalid`, empty text, or `-2` to reproduce.
Save this block as `processing.py`, then call `workflows.run(flow=pipeline)`.
The user validation error has code 1 and names the expected positive value.
Inspect the failed iteration's recorded `positive_measurement` call and
`data/job.failed`. Repair the input to `2.5` and rerun the same callable; expect
success and `data/structured/measurement.txt` containing `2.5\n`. The Runner
does not clear an existing `job.failed` on success. Preserve it with the failed
report, then archive it explicitly before rerunning; its presence alone is not
proof that the new run failed. CI performs this exact failure/repair sequence.

<!-- example: debugging-flow -->
```python
from math import isfinite

from rdetoolkit import flow, node
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes import read_text, save_text
from rdetoolkit.types import InputPaths, OutputContext


@node
def positive_measurement(text: str) -> float:
    """Validate a positive local measurement with an actionable message."""
    try:
        value = float(text)
    except ValueError as error:
        raise StructuredError("Expected a positive measurement; repair the input.", ecode=1) from error
    if not isfinite(value) or value <= 0:
        raise StructuredError("Expected a positive measurement; repair the input.", ecode=1)
    return value


@flow
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    """Validate the first measurement and write the repaired result."""
    value = positive_measurement(read_text(paths.rawfiles[0]))
    save_text(f"{value}\n", out, "measurement.txt")
```

Use `report.exit_code` for library callers; production scripts can request
`exit_on_failure=True`. For partial multi-tile runs the exit code is 2 and each
failed iteration needs independent inspection. An ordinary direct node call
outside a run propagates the original exception; Runner execution records it.

After inspecting the failing report, execute this repair block in the same
namespace as `pipeline`. For this synthetic one-file fixture only, it repairs
the input and preserves the previous failure marker. For real scientific data,
repair the source with domain knowledge instead of replacing measurements.

<!-- example: debugging-repair -->
```python
from pathlib import Path

from rdetoolkit import workflows

marker = Path("data/job.failed")
archive = Path("data/job.failed.previous")
if archive.exists():
    raise FileExistsError("Preserve the previous failure evidence before rerunning.")
marker.rename(archive)
source = sorted(Path("data/inputdata").glob("*.txt"))[0]
source.write_text("2.5", encoding="utf-8")
report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
assert report.status == "success", report.error
```

To inspect the specific failed report in the CLI, copy the report whose `run_id`
you just verified to `failure-report.json`, then run the exact command below.
CI checks that it identifies the same run and failed node. Keep this copy local.

<!-- example: debugging-report -->
```console
python -m rdetoolkit report show failure-report.json
```

The same failure as structured data follows. In the copy, `evidence` reports
the iteration detail and event log as `missing`, because they stay beside the
original under `data/logs/`; diagnose the original to check that they belong
to this run. CI checks that both identify the failed `positive_measurement` call.

<!-- example: debugging-diagnose -->
```console
python -m rdetoolkit report diagnose failure-report.json --json
```
