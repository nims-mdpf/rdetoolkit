"""Strict interpolation and phase-aware diagnostics at the GA boundary.

EP/BV table (written before implementation):
G01 schema rejects substituted value -> 4007, artifact_publish, no value leak.
G02 read/write cause contains private text -> typed 4006/4007, no cause leak.
G03 malformed validate-only template -> 4005, pre_validate, no flow call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.domain.magic import MagicOptions
from rdetoolkit.domain.magic_service import apply_interpolation
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.report.failure import failure_diagnostic
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import OutputContext
from tests.v2.domain.test_magic_service import _bundle
from tests.v2.runner.test_magic_integration import _seed


def test_schema_failure_sidecar_redacts_value(tmp_path: Path) -> None:
    """G01: Schema exception causes cannot disclose resolved values."""
    # Given: a template accepted by the schema, whose resolved value is rejected
    root = _seed(tmp_path, "${metadata:constant:name}")
    schema_path = root / "data/tasksupport/invoice.schema.json"
    schema = readf_json(schema_path)
    basic = schema.setdefault("properties", {}).setdefault("basic", {"type": "object"})
    basic.setdefault("properties", {})["dataName"] = {"type": "string", "pattern": r"^\$\{"}
    writef_json(schema_path, schema)
    private_value = "PRIVATE-INTERPOLATED-VALUE-704"

    def emit(out: OutputContext) -> None:
        writef_json(out.meta / "metadata.json", {"constant": {"name": {"value": private_value}}})

    before = (root / "data/invoice/invoice.json").read_bytes()
    # When: publishing the substituted invoice in a real flow
    report = Runner(root=root).run(emit)
    document = readf_json(root / "data/logs" / f"diagnostics_{report.run_id}.json")
    # Then: failure attribution remains precise and every diagnostic is value-free
    assert report.status == "failed"
    assert report.iterations[0]["error"]["code"] == 4007
    assert document["diagnostics"][0]["phase"] == "artifact_publish"
    assert document["diagnostics"][0]["code"] == 4007
    assert private_value not in json.dumps(document)
    assert (root / "data/invoice/invoice.json").read_bytes() == before


@pytest.mark.parametrize("operation,code", [("read", 4006), ("write", 4007)])
@pytest.mark.parametrize("error_type", [OSError, StructuredError])
def test_io_diagnostics_hide_private_causes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, code: int, error_type: type[Exception],
) -> None:
    """G02: External I/O exception messages do not bypass strict redaction."""
    # Given: a resolver source or destination operation with a sensitive cause
    paths, snapshot = _bundle(tmp_path, "${invoice:basic:dataOwnerId}")
    private_value = "PRIVATE-IO-DETAIL-704"

    def fail(*args: Any, **kwargs: Any) -> None:
        raise error_type(private_value)

    function = "readf_json" if operation == "read" else "writef_json"
    monkeypatch.setattr(f"rdetoolkit.domain.magic_service.{function}", fail)
    # When: the strict boundary converts the operation to a catalogued failure
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    diagnostic = failure_diagnostic(caught.value, phase="artifact_publish").to_dict()
    # Then: both type/code and source-value privacy survive diagnostic serialization
    assert caught.value.code == code
    assert diagnostic["code"] == code
    assert private_value not in json.dumps(diagnostic)


@pytest.mark.parametrize("template", ["${}", "${filename:extra}"])
def test_validate_only_failure_phase(tmp_path: Path, template: str) -> None:
    """G03: Validate-only syntax failures retain their pre-validation phase."""
    # Given: an invalid template and a flow that must not be called
    root = _seed(tmp_path, template)
    calls: list[bool] = []
    request = RunRequest(root=root, target=FlowTarget(function=lambda: calls.append(True)), validate_only=True)
    # When: running static validation through the ordinary lifecycle
    report = Runner(root=root).run(request)
    document = readf_json(root / "data/logs" / f"diagnostics_{report.run_id}.json")
    # Then: failure remains static, catalogued, and independent of user processing
    assert calls == []
    assert report.status == "failed"
    assert report.error["code"] == 4005
    assert document["diagnostics"][0]["phase"] == "pre_validate"
    assert document["diagnostics"][0]["code"] == 4005
