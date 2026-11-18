"""PR757 review regressions.

Contract IDs RF01-RF10 map to the verification matrix in PR757.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, resolve_invoice
from rdetoolkit.domain.magic_service import apply_interpolation
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.failure import failure_diagnostic
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import OutputContext, RdeConfig
from tests.v2.domain.test_magic_service import _bundle
from tests.v2.runner.test_magic_integration import _seed


@pytest.mark.parametrize("value", ["alpha__", "__alpha__", "_", "alpha___beta__"])
def test_omission_preserves_source_value(value: str) -> None:
    """RF01: Referenced underscores cannot be consumed as literal separators."""
    # Given: an absent expression directly after an opaque source value
    context = ResolutionContext.from_sources(
        original_invoice={"custom": {"id": value}},
        current_invoice={"basic": {"dataName": "${invoice:custom:id}${invoice:custom:absent}_post"}},
    )
    # When: explicitly omitting the absent reference
    result = resolve_invoice(context, options=MagicOptions(missing="omit"))
    # Then: the source value is preserved verbatim
    assert result["basic"]["dataName"] == value + "_post"


@pytest.mark.parametrize("field", ["dataName", "description"])
def test_runner_preserves_source_underscores(tmp_path: Path, field: str) -> None:
    """RF01: A real flow publishes the source text without separator corruption."""
    # Given: a tile using metadata next to an omitted source
    root = _seed(tmp_path, "plain")
    path = root / "data/invoice/invoice.json"
    invoice = readf_json(path)
    invoice["basic"][field] = "${metadata:constant:id}${metadata:constant:absent}_post"
    writef_json(path, invoice)

    def emit(out: OutputContext) -> None:
        writef_json(out.meta / "metadata.json", {"constant": {"id": {"value": "alpha__"}}, "variable": []})

    # When: publishing with the explicit omission policy
    report = Runner(root=root).run(emit, custom={"interpolation": {"missing": "omit"}})
    # Then: successful output retains every source underscore
    assert report.status == "success"
    assert readf_json(path)["basic"][field] == "alpha___post"


@pytest.mark.property
@given(st.text(alphabet="abc_", min_size=1, max_size=30))
def test_source_preservation_property(value: str) -> None:
    """RF02: Omission normalization never edits any referenced source text."""
    # Given: arbitrary source text surrounded by literal omission boundaries
    template = "pre__${invoice:custom:absent}__${invoice:custom:id}${invoice:custom:absent}_post"
    context = ResolutionContext.from_sources(original_invoice={"custom": {"id": value}}, current_invoice={"basic": {"dataName": template}})
    # When: resolving both omission boundaries
    result = resolve_invoice(context, options=MagicOptions(missing="omit"))
    # Then: only the two literal runs before the value collapse
    assert result["basic"]["dataName"] == "pre_" + value + "_post"


def test_limit_uses_final_normalized_length() -> None:
    """RF03: An oversized intermediate can normalize into an allowed result."""
    # Given: a long literal run that follows a resolved source and will collapse
    template = "${invoice:custom:value}" + "_" * 16000 + "${invoice:custom:absent}_"
    context = ResolutionContext.from_sources(original_invoice={"custom": {"value": "x" * 1000}}, current_invoice={"basic": {"dataName": "plain", "description": template}})
    # When: normalizing the entire template before enforcing output limits
    result = resolve_invoice(context, options=MagicOptions(missing="omit"))
    # Then: the final text, rather than its temporary representation, is bounded
    assert result["basic"]["description"] == "x" * 1000 + "_"


def test_multiple_literal_omission_boundaries() -> None:
    """RF02: Multiple literal omission boundaries normalize to completion."""
    # Given: two omitted values separated by a removable literal run
    context = ResolutionContext.from_sources(
        original_invoice={}, current_invoice={"basic": {"dataName": "a__${invoice:custom:absent}__${invoice:custom:absent}__b"}},
    )
    # When: resolving the complete omission sequence
    result = resolve_invoice(context, options=MagicOptions(missing="omit"))
    # Then: both literal boundaries collapse without retaining empty blockers
    assert result["basic"]["dataName"] == "a_b"


@pytest.mark.parametrize("size,code", [(16383, None), (16384, 4007), (16385, 4007)])
def test_final_description_limit(size: int, code: int | None) -> None:
    """RF04: The final normalized description obeys the exact output budget."""
    # Given: a value followed by one normalized literal underscore
    context = ResolutionContext.from_sources(
        original_invoice={"custom": {"value": "x" * size}},
        current_invoice={"basic": {"dataName": "plain", "description": "${invoice:custom:value}__${invoice:custom:absent}_"}},
    )
    # When: resolving the final normalized description
    if code is not None:
        with pytest.raises(RdeValidationError) as caught:
            resolve_invoice(context, options=MagicOptions(missing="omit"))
        # Then: over-budget output remains a catalogued failure
        assert caught.value.code == code
    else:
        result = resolve_invoice(context, options=MagicOptions(missing="omit"))
        # Then: output exactly at the declared budget is accepted
        assert result["basic"]["description"] == "x" * size + "_"


def _constrained_case(tmp_path: Path, constraint: dict[str, Any]) -> tuple[Path, str]:
    root = _seed(tmp_path, "${invoice:basic:dataOwnerId}")
    schema_path = root / "data/tasksupport/invoice.schema.json"
    schema = readf_json(schema_path)
    schema.setdefault("properties", {}).setdefault("basic", {"type": "object"}).setdefault("properties", {})["dataName"] = {"type": "string", **constraint}
    writef_json(schema_path, schema)
    return root, readf_json(root / "data/invoice/invoice.json")["basic"]["dataOwnerId"]


@pytest.mark.parametrize("kind", ["pattern", "minLength", "enum"])
def test_template_value_constraints_are_deferred(tmp_path: Path, kind: str) -> None:
    """RF05: Value constraints are applied to expanded data rather than syntax."""
    # Given: a placeholder rejected by the destination's final-value constraint
    constraint: dict[str, Any] = {"pattern": "^[0-9a-f-]+$"} if kind == "pattern" else {"minLength": 50}
    root, owner = _constrained_case(tmp_path, constraint)
    if kind == "enum":
        schema_path = root / "data/tasksupport/invoice.schema.json"
        schema = readf_json(schema_path)
        schema["properties"]["basic"]["properties"]["dataName"] = {"type": "string", "enum": [owner]}
        writef_json(schema_path, schema)
    calls: list[bool] = []
    # When: running an ordinary eager flow
    report = Runner(root=root).run(lambda: calls.append(True))
    # Then: the resolved destination passes the original schema
    assert report.status == "success"
    assert calls == [True]
    assert readf_json(root / "data/invoice/invoice.json")["basic"]["dataName"] == owner


@pytest.mark.parametrize("constraint", [{"pattern": "^never$"}, {"maxLength": 1}, {"enum": ["never"]}])
def test_invalid_resolved_value_fails_before_replacement(tmp_path: Path, constraint: dict[str, Any]) -> None:
    """RF06: Deferred constraints still reject invalid final values safely."""
    # Given: a destination whose resolved value will fail the original schema
    root, _ = _constrained_case(tmp_path, constraint)
    path = root / "data/invoice/invoice.json"
    before = path.read_bytes()
    calls: list[bool] = []
    # When: completing the user flow and validating its publication candidate
    report = Runner(root=root).run(lambda: calls.append(True))
    document = readf_json(root / "data/logs" / f"diagnostics_{report.run_id}.json")
    # Then: failure belongs to final publication and does not replace the invoice
    assert calls == [True]
    assert report.status == "failed"
    assert report.iterations[0]["error"]["code"] == 4007
    assert document["diagnostics"][0]["phase"] == "artifact_publish"
    assert path.read_bytes() == before


@pytest.mark.parametrize("invalid", ["owner", "required", "field_type", "disabled", "plain", "dataset"])
def test_preflight_retains_other_validation(tmp_path: Path, invalid: str) -> None:
    """RF07: Deferring interpolated values does not disable other preflight checks."""
    # Given: a template plus a constraint that must still be checked immediately
    root, _ = _constrained_case(tmp_path, {"pattern": "^[0-9a-f-]+$"})
    path = root / "data/invoice/invoice.json"
    invoice = readf_json(path)
    if invalid == "owner":
        invoice["basic"]["dataOwnerId"] = "bad-owner"
    elif invalid == "required":
        del invoice["basic"]["dataName"]
    elif invalid == "field_type":
        invoice["basic"]["dataName"] = ["${filename}"]
    elif invalid == "plain":
        invoice["basic"]["dataName"] = "plain"
    elif invalid == "dataset":
        del invoice["datasetId"]
    writef_json(path, invoice)
    calls: list[bool] = []
    system = {"magic_variable": False} if invalid == "disabled" else {}
    request = RunRequest(root=root, target=FlowTarget(function=lambda: calls.append(True)), config_source={"system": system})
    # When: validating the original request
    report = Runner(root=root).run(request)
    # Then: invalid nondeferred input is rejected before calling user code
    assert report.status == "failed"
    assert report.error["code"] == 4001
    assert calls == []


def test_validate_only_defers_value_constraints(tmp_path: Path) -> None:
    """RF08: Static validation accepts template shape without resolving values."""
    # Given: a syntactically valid template with a final-value pattern
    root, _ = _constrained_case(tmp_path, {"pattern": "^[0-9a-f-]+$"})
    path = root / "data/invoice/invoice.json"
    before = path.read_bytes()
    calls: list[bool] = []
    events = MemoryEventSink()
    request = RunRequest(root=root, target=FlowTarget(function=lambda: calls.append(True)), validate_only=True)
    # When: validating without runtime sources or user execution
    report = Runner(root=root, event_sink=events).run(request)
    # Then: syntax succeeds and the final-value check is explicitly deferred
    assert report.status == "success"
    assert calls == []
    assert path.read_bytes() == before
    assert any("deferred" in event.payload.get("message", "") for event in events.events)


@pytest.mark.parametrize("prior_run", ["none", "success", "failure"])
def test_direct_prevalidation_remains_strict(tmp_path: Path, prior_run: str) -> None:
    """RF07: Direct pre-validation never inherits a previous run's deferral."""
    # Given: an unresolved template and a Runner before or after an ordinary run
    root, owner = _constrained_case(tmp_path, {"pattern": "^[0-9a-f-]+$"})
    runner = Runner(root=root)
    path = root / "data/invoice/invoice.json"
    invoice = readf_json(path)
    if prior_run != "none":
        if prior_run == "failure":
            invoice["basic"]["dataOwnerId"] = "invalid"
            writef_json(path, invoice)
        report = runner.run(lambda: None)
        assert report.status == ("success" if prior_run == "success" else "failed")
        invoice["basic"]["dataOwnerId"] = owner
        writef_json(path, invoice)
    # When: using the public pre-validation seam directly
    with pytest.raises(RdeValidationError) as caught:
        runner.pre_validate(RdeConfig())
    # Then: the source value is strictly checked, even after a failed run
    assert caught.value.code == 4001


@pytest.mark.parametrize("failure", ["replace", "write"])
@pytest.mark.parametrize("error_type", [PermissionError, StructuredError])
def test_cleanup_failure_preserves_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, error_type: type[Exception],
) -> None:
    """RF09: Cleanup failure cannot replace a safe catalogued publication error."""
    # Given: a failed publication whose temporary file cannot be removed
    paths, snapshot = _bundle(tmp_path, "${invoice:basic:dataOwnerId}")
    path = paths.invoice / "invoice.json"
    before = path.read_bytes()
    private_path = str(tmp_path / "private-location")

    def fail(*args: Any, **kwargs: Any) -> None:
        raise error_type(private_path)

    def fail_cleanup(*args: Any, **kwargs: Any) -> None:
        raise PermissionError(private_path)

    operation = "os.replace" if failure == "replace" else "writef_json"
    monkeypatch.setattr(f"rdetoolkit.domain.magic_service.{operation}", fail)
    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    # When: both publication and cleanup fail
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    document = failure_diagnostic(caught.value, phase="artifact_publish").to_dict()
    # Then: cleanup does not change the original error or expose its internal path
    assert caught.value.code == 4007
    assert private_path not in json.dumps(document)
    assert path.read_bytes() == before


def test_successful_replace_releases_temporary_ownership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RF10: A consumed temporary name is not deleted again after commit."""
    # Given: a valid replacement and an unlink operation that refuses cleanup
    paths, snapshot = _bundle(tmp_path, "${invoice:basic:dataOwnerId}")

    def fail_cleanup(*args: Any, **kwargs: Any) -> None:
        message = "private consumed temporary path"
        raise PermissionError(message)

    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    # When: atomically replacing the destination succeeds
    apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    # Then: the valid published value remains a successful operation
    assert readf_json(paths.invoice / "invoice.json")["basic"]["dataName"] == json.loads(snapshot)["basic"]["dataOwnerId"]
