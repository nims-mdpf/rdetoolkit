"""Publication failure followed by a corrected same-root rerun (#759).

A flow completes, then the final interpolation validation rejects the expanded
``basic.dataName`` (4007, phase ``artifact_publish``). Publication is atomic
for ``invoice.json`` only; the flow's own outputs and the artifacts of earlier
Invoice-mode stages stay on disk. The user corrects either the generated
metadata or the destination schema and reruns on the same data root without
removing anything by hand.

General rerun/state isolation across all modes and entries is covered by
``tests/v2/ga/test_state_isolation.py`` (#698); the mode-specific stage order
on failure by ``test_artifact_stage_order_i_review_a.py``. This module adds
only the interpolation-publication scenario.

EP table:
| TC | Correction | Expected |
|----|------------|----------|
| TC-PFR-001 | none (first run) | failed tile, 4007 in ``artifact_publish``, invoice bytes unchanged, flow outputs and pre-magic ``structured/invoice.json`` retained, ``job.failed`` = 4007 |
| TC-PFR-002 | metadata | rerun succeeds; current invoice/flow outputs; new run_id; no stale diagnostics; old run logs and ``job.failed`` kept |
| TC-PFR-003 | schema | same as TC-PFR-002 with the original metadata value |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import OutputContext
from tests.v2.ga._harness import GaRun
from tests.v2.runner.test_magic_integration import _seed

_TEMPLATE = "${metadata:constant:sample}"
_PATTERN = "^OK-"


class _SampleFlow:
    """Deterministic flow that overwrites every output it owns on each call."""

    def __init__(self, sample: str) -> None:
        self.sample = sample

    def __call__(self, out: OutputContext) -> None:
        writef_json(out.meta / "metadata.json", {"constant": {"sample": {"value": self.sample}}, "variable": []})
        (out.struct / "result.csv").write_text(f"sample\n{self.sample}\n", encoding="utf-8")


def _set_data_name_schema(root: Path, constraint: dict[str, str]) -> None:
    schema_path = root / "data/tasksupport/invoice.schema.json"
    schema = readf_json(schema_path)
    properties = schema.setdefault("properties", {}).setdefault("basic", {"type": "object"}).setdefault("properties", {})
    properties["dataName"] = {"type": "string", **constraint}
    writef_json(schema_path, schema)


def _run(root: Path, flow: _SampleFlow) -> GaRun:
    request = RunRequest(
        root=root,
        target=FlowTarget(function=flow),
        config_source={"system": {"save_invoice_to_structured": True}},
    )
    return GaRun(root, Runner(root=root).run(request))


@pytest.mark.parametrize("correction", ["metadata", "schema"])
def test_rerun_after_publication_failure_overwrites_retained_outputs(tmp_path: Path, correction: str) -> None:
    """TC-PFR-001/002/003: retained artifacts are documented and a corrected rerun replaces them."""
    # Given: an Invoice-mode root whose dataName expands from flow metadata under a strict pattern
    root = _seed(tmp_path, _TEMPLATE)
    _set_data_name_schema(root, {"pattern": _PATTERN})
    data = root / "data"
    invoice_path = data / "invoice/invoice.json"
    original_invoice = invoice_path.read_bytes()
    flow = _SampleFlow("bad")

    # When: the flow completes but its metadata expands to a value the schema rejects
    failed = _run(root, flow)

    # Then: the tile fails at final publication and the invoice is not replaced
    assert failed.report.status == "failed"
    assert [iteration["status"] for iteration in failed.report.iterations] == ["failed"]
    assert failed.report.iterations[0]["error"]["code"] == 4007
    diagnostics = failed.diagnostics()
    assert [(item["phase"], item["code"], item["iteration_index"]) for item in diagnostics] == [("artifact_publish", 4007, 0)]
    assert invoice_path.read_bytes() == original_invoice
    first_job_failed = (data / "job.failed").read_text(encoding="utf-8")
    assert first_job_failed.splitlines()[0] == "ErrorCode=4007"

    # And: the flow's outputs and the pre-magic structured export are retained (Invoice stage order)
    assert readf_json(data / "meta/metadata.json")["constant"]["sample"]["value"] == "bad"
    assert (data / "structured/result.csv").read_text(encoding="utf-8") == "sample\nbad\n"
    assert readf_json(data / "structured/invoice.json")["basic"]["dataName"] == _TEMPLATE
    assert readf_json(failed.logs / "iterations/iteration_0.json")["status"] == "failed"

    # When: the user corrects the generated metadata or the schema and reruns on the same root
    if correction == "metadata":
        flow.sample = "OK-1"
    else:
        _set_data_name_schema(root, {})
    rerun = _run(root, flow)

    # Then: the rerun succeeds and publishes the current value over the retained outputs
    assert rerun.report.status == "success"
    assert rerun.report.error is None
    assert rerun.report.warnings == []
    assert rerun.report.run_id != failed.report.run_id
    assert [iteration["status"] for iteration in rerun.report.iterations] == ["completed"]
    assert readf_json(invoice_path)["basic"]["dataName"] == flow.sample
    assert readf_json(data / "meta/metadata.json")["constant"]["sample"]["value"] == flow.sample
    assert (data / "structured/result.csv").read_text(encoding="utf-8") == f"sample\n{flow.sample}\n"
    assert readf_json(data / "structured/invoice.json")["basic"]["dataName"] == _TEMPLATE
    assert readf_json(rerun.logs / "iterations/iteration_0.json")["status"] == "completed"

    # And: no diagnostics are attributed to the rerun, while the failed run's logs stay addressable
    assert rerun.sidecar() is None
    assert failed.sidecar_path.exists()
    assert failed.report_path.exists()
    explanation = rerun.explain()
    assert (explanation["run_id"], explanation["run_status"], explanation["explanations"]) == (
        rerun.report.run_id,
        "success",
        [],
    )
    assert failed.explain()["run_status"] == "failed"

    # And: job.failed is left in place, as v1 left it (TC-K3-HYG-002)
    assert (data / "job.failed").read_text(encoding="utf-8") == first_job_failed
