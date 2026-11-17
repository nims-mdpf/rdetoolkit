"""Config model and schema-format regressions for PR #757 (P2C01-P2F02)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit import workflows
from rdetoolkit.config.normalize import ConfigNormalizer, ConfigOrigin
from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, preview_invoice, resolve_invoice
from rdetoolkit.domain.magic_policy import options_from_config
from rdetoolkit.domain.magic_service import apply_interpolation
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.models.config import Config
from rdetoolkit.types import RdeConfig
from tests.v2.domain.test_magic_service import _bundle
from tests.v2.runner.test_magic_integration import _seed


@pytest.mark.parametrize("model,origin", [(Config, "v1"), (RdeConfig, "v1"), (RdeConfig, "v2")])
def test_model_omission_survives_origin(tmp_path: Path, origin: ConfigOrigin, model: type[Config] | type[RdeConfig]) -> None:
    """P2C01: Model defaults retain auto intent across both input origins."""
    # Given: a configuration model without an explicit magic flag
    source = model()
    # When: converting the model through either supported input contract
    normalized = ConfigNormalizer().normalize(source, root=tmp_path, origin=origin)
    # Then: omission remains distinct from explicit disabling
    assert "magic_variable" not in normalized.system.model_fields_set
    assert options_from_config(normalized).policy == "auto"
    assert source.system.model_fields_set == set()


@pytest.mark.parametrize("choice", ["omitted", "enabled", "false", "true"])
def test_legacy_model_flow_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, choice: str) -> None:
    """P2C02: Real flows honor omission and explicit switches on Config."""
    # Given: an invoice-only template and a legacy configuration model
    template = "${invoice:basic:dataOwnerId}"
    root = _seed(tmp_path, template)
    config = Config(custom={"interpolation": {"policy": "enabled"}}) if choice == "enabled" else Config()
    if choice in {"false", "true"}:
        config.system.magic_variable = choice == "true"
    owner = readf_json(root / "data/invoice/invoice.json")["basic"]["dataOwnerId"]
    monkeypatch.chdir(root)
    # When: executing the public flow entry point with Config
    report = workflows.run(flow=lambda: None, config=config)
    # Then: only explicit false preserves the template
    assert report.status == "success"
    assert readf_json(root / "data/invoice/invoice.json")["basic"]["dataName"] == (template if choice == "false" else owner)


@pytest.mark.parametrize("flag,policy", [(False, "enabled"), (True, "disabled")])
def test_legacy_model_rejects_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: bool, policy: str) -> None:
    """P2C03: Preserving omission does not hide explicitly conflicting flags."""
    # Given: conflicting explicit settings on a legacy configuration model
    root = _seed(tmp_path, "${invoice:basic:dataOwnerId}")
    path = root / "data/invoice/invoice.json"
    before = path.read_bytes()
    config = Config(system={"magic_variable": flag}, custom={"interpolation": {"policy": policy}})
    monkeypatch.chdir(root)
    # When: executing the flow entry point and interpreting its model
    with pytest.raises(RdeValidationError) as caught:
        options_from_config(ConfigNormalizer().normalize(config, root=root, origin="v1"))
    report = workflows.run(flow=lambda: None, config=config)
    # Then: the conflicting settings retain their catalogued failure
    assert caught.value.code == 4009
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4009
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "format_name,value",
    [
        ("date", "not-a-date"),
        ("date", "2025-02-29"),
        ("date", "2024-13-01"),
        ("uuid", "not-a-uuid"),
        ("uuid", "12345678-1234-1234-1234-12345678901"),
        ("uuid", "12345678-1234-1234-1234-12345678901g"),
        ("email", "missing-at"),
        ("email", ""),
        ("email", "another.invalid.address"),
        ("ipv4", "256.0.0.1"),
        ("ipv4", "127.0.0"),
        ("ipv4", "localhost"),
    ],
)
def test_format_rejection_matches_publication(tmp_path: Path, format_name: str, value: str) -> None:
    """P2F01: Pure format validation rejects the same candidates as saving."""
    # Given: a description template resolving to a malformed formatted value
    paths, snapshot = _bundle(tmp_path, "plain")
    path = paths.invoice / "invoice.json"
    invoice = readf_json(path)
    invoice["basic"]["description"] = "${metadata:constant:name}"
    writef_json(path, invoice)
    metadata = {"constant": {"name": {"value": value}}}
    writef_json(paths.meta / "metadata.json", metadata)
    schema = readf_json(paths.invoice_schema_json)
    schema.setdefault("properties", {}).setdefault("basic", {}).setdefault("properties", {})["description"] = {"type": "string", "format": format_name}
    writef_json(paths.invoice_schema_json, schema)
    context = ResolutionContext.from_sources(original_invoice=invoice, current_invoice=invoice, metadata=metadata)
    before = path.read_bytes()
    options = MagicOptions(missing="omit")
    # When: previewing, resolving, and attempting publication with that schema
    preview = preview_invoice(context, options=options, schema=schema)
    with pytest.raises(RdeValidationError) as resolved:
        resolve_invoice(context, options=options, schema=schema)
    with pytest.raises(RdeValidationError) as published:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=options, iteration_index=0, mode="invoice")
    # Then: each API identifies the format violation without changing invoice data
    assert any(item.code == 4007 and item.destination == "basic.description" and item.reason == "schema_violation" for item in preview.diagnostics)
    assert resolved.value.code == published.value.code == 4007
    assert context.current_invoice == invoice
    assert path.read_bytes() == before


@pytest.mark.parametrize("format_name,value", [("date", "2024-02-29"), ("uuid", "00000000-0000-0000-0000-000000000000"), ("email", "a@example.org"), ("ipv4", "255.255.255.255")])
def test_format_acceptance_matches_publication(tmp_path: Path, format_name: str, value: str) -> None:
    """P2F02: Valid formatted values have matching pure and saved results."""
    # Given: a valid formatted metadata value and destination schema
    paths, snapshot = _bundle(tmp_path, "${metadata:constant:name}")
    invoice = readf_json(paths.invoice / "invoice.json")
    metadata = {"constant": {"name": {"value": value}}}
    writef_json(paths.meta / "metadata.json", metadata)
    schema = readf_json(paths.invoice_schema_json)
    schema.setdefault("properties", {}).setdefault("basic", {}).setdefault("properties", {})["dataName"] = {"type": "string", "format": format_name}
    writef_json(paths.invoice_schema_json, schema)
    context = ResolutionContext.from_sources(original_invoice=invoice, current_invoice=invoice, metadata=metadata)
    # When: checking the pure APIs and publishing the same invoice
    preview = preview_invoice(context, schema=schema)
    candidate = resolve_invoice(context, schema=schema)
    apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    # Then: every check accepts and saves the same value
    assert all(item.code is None for item in preview.diagnostics)
    assert candidate["basic"]["dataName"] == value
    assert readf_json(paths.invoice / "invoice.json")["basic"]["dataName"] == value
