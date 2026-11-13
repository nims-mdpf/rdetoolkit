# Complete local integration fixture

Run this recipe in an empty temporary working directory, with rdetoolkit v2
installed. It creates a `scratch/data/` tree using only synthetic values. It
leaves artifacts on disk for inspection and asserts the actual structured
text and finalized invoice. No network, external LLM or private dataset is used.

<!-- example: testing-roundtrip -->
```python
import json
from pathlib import Path

from rdetoolkit import flow
from rdetoolkit.nodes import read_text, save_text
from rdetoolkit.testing import make_input_paths, make_invoice, run_flow
from rdetoolkit.types import InputPaths, OutputContext

project = Path("scratch").resolve()
paths = make_input_paths(project / "data", files=["measurement.txt"])
paths.rawfiles[0].write_text("test\n", encoding="utf-8")
invoice = make_invoice({
    "datasetId": "synthetic-test",
    "basic": {"dataName": "test", "dateSubmitted": "2026-11-12", "dataOwnerId": "0" * 56},
})
(paths.invoice / "invoice.json").write_text(json.dumps(invoice.raw), encoding="utf-8")
(paths.tasksupport / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
(paths.tasksupport / "metadata-def.json").write_text("{}", encoding="utf-8")


@flow
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    """Write a structured artifact from one synthetic text input."""
    save_text(read_text(paths.rawfiles[0]), out, "result.txt")


report = run_flow(pipeline, data_root=project)
assert report.status == "success", report.error
assert report.exit_code == 0
assert (project / "data/structured/result.txt").read_text(encoding="utf-8") == "test\n"
assert json.loads((project / "data/invoice/invoice.json").read_text(encoding="utf-8"))["basic"]["dataName"] == "test"
assert not (project / "data/job.failed").exists()
```

For direct node tests use `make_output_context(tmp_path)` and compare actual
serialized bytes or parsed values. For a failure test use the debugging Skill's
validation example and assert its original error code and failed node. Preserve
the failed report and explicitly archive its `job.failed` marker before repairing
the synthetic input and rerunning. The Runner does not automatically clear an
existing marker on success; verify the new report and artifact instead.
