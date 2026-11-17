"""Atomic invoice publication and independent filesystem source contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.domain.invoice_service import InvoiceService, build_tile_dataset_paths
from rdetoolkit.domain.service_errors import validation_error
from rdetoolkit.domain.magic import MagicOptions
from rdetoolkit.domain.magic_service import apply_interpolation
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.types import InputPaths, OutputContext
from rdetoolkit.types import RdeConfig
from tests.v2.contract.fixtures import _generate


def _bundle(tmp_path: Path, template: str) -> tuple[RdeDatasetPaths, str]:
    _generate.materialize_sut_case("invoice", tmp_path)
    root = tmp_path / "data"
    source = readf_json(root / "invoice/invoice.json")
    source["basic"]["dataName"] = template
    writef_json(root / "invoice/invoice.json", source)
    out = OutputContext.from_resource_paths(resolve_tile_paths(root, 0))
    paths = InputPaths(inputdata=root / "inputdata", invoice=root / "invoice", tasksupport=root / "tasksupport", rawfiles=())
    bundle = build_tile_dataset_paths(paths=paths, out=out, invoice_org=root / "invoice/invoice.json")
    bundle.meta.mkdir(parents=True, exist_ok=True)
    return bundle, json.dumps(source)


@pytest.mark.parametrize("mode", ["invoice", "excelinvoice", "multidatatile", "smarttable"])
def test_service_no_rawfiles(tmp_path: Path, mode: str) -> None:
    """RUN08: Four applicable modes can resolve metadata without raw files."""
    # Given: a tile with metadata and no raw attachment
    paths, snapshot = _bundle(tmp_path, "${metadata:constant:name}")
    writef_json(paths.meta / "metadata.json", {"constant": {"name": {"value": "resolved"}}})
    # When: the strict artifact stage runs for a supported mode
    result = apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=2, mode=mode)
    # Then: metadata alone is sufficient and diagnostics identify this tile
    assert readf_json(paths.invoice / "invoice.json")["basic"]["dataName"] == "resolved"
    assert result.diagnostics[0].iteration_index == 2


@pytest.mark.parametrize("failure,code", [("no_filename", 4010), ("metadata_missing", 4010), ("metadata_invalid", 4010), ("invoice_missing", 4010), ("schema_missing", 4007), ("write", 4007), ("write_json", 4007)])
def test_service_failure(tmp_path: Path, failure: str, code: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """RUN09: Source and publication failures never publish a partial invoice."""
    # Given: a requested source or publication failure
    template = "${filename}" if failure == "no_filename" else "${metadata:constant:name}"
    paths, snapshot = _bundle(tmp_path, template)
    path = paths.invoice / "invoice.json"
    writef_json(paths.meta / "metadata.json", {"constant": {"name": {"value": "resolved"}}})
    if failure == "metadata_missing":
        (paths.meta / "metadata.json").unlink()
    elif failure == "metadata_invalid":
        (paths.meta / "metadata.json").write_text("invalid", encoding="utf-8")
    elif failure == "invoice_missing":
        path.unlink()
    elif failure == "schema_missing":
        paths.invoice_schema_json.unlink()
    elif failure == "write":
        def fail_replace(*args: Any) -> None:
            message = "private filename"
            raise OSError(message)
        monkeypatch.setattr("rdetoolkit.domain.magic_service.os.replace", fail_replace)
    elif failure == "write_json":
        def fail_write(*args: Any) -> None:
            message = "private filename"
            raise StructuredError(message)
        monkeypatch.setattr("rdetoolkit.domain.magic_service.writef_json", fail_write)
    before = path.read_bytes() if path.exists() else None
    # When: resolving the tile
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(policy="enabled"), iteration_index=0, mode="invoice")
    # Then: precise errors leave the invoice and directory free of partial output
    assert caught.value.code == code
    assert "private filename" not in str(caught.value)
    assert (path.read_bytes() if path.exists() else None) == before
    assert list(paths.invoice.glob(".invoice-*")) == []


def test_irrelevant_metadata_not_loaded(tmp_path: Path) -> None:
    """RUN08: Invoice-only references do not load unrelated metadata."""
    # Given: a valid invoice-only expression and malformed unrelated metadata
    paths, snapshot = _bundle(tmp_path, "${invoice:basic:dataOwnerId}")
    (paths.meta / "metadata.json").write_text("private invalid data", encoding="utf-8")
    # When: resolving its independent invoice source
    apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    # Then: no metadata dependency is introduced
    assert readf_json(paths.invoice / "invoice.json")["basic"]["dataName"] == json.loads(snapshot)["basic"]["dataOwnerId"]


def test_schema_failure_identifies_destination(tmp_path: Path) -> None:
    """RUN09: Schema diagnostics identify the generated field without its value."""
    # Given: a substitution that violates a downstream field constraint
    paths, snapshot = _bundle(tmp_path, "${metadata:constant:name}")
    writef_json(paths.meta / "metadata.json", {"constant": {"name": {"value": "private-value"}}})
    schema = readf_json(paths.invoice_schema_json)
    basic = schema.setdefault("properties", {}).setdefault("basic", {"type": "object"})
    basic.setdefault("properties", {})["dataName"] = {"type": "string", "maxLength": 2}
    writef_json(paths.invoice_schema_json, schema)
    before = (paths.invoice / "invoice.json").read_bytes()
    # When: validating the full replacement candidate
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=1, mode="invoice")
    # Then: only the failing field and tile identify the problem
    assert caught.value.code == 4007
    assert "basic.dataName" in str(caught.value)
    assert "private-value" not in str(caught.value)
    assert (paths.invoice / "invoice.json").read_bytes() == before


def test_service_owns_strict_magic_hook(tmp_path: Path) -> None:
    """RUN12: A per-call updater owns v2 policy without bypassing the service."""
    # Given: no raw files and the legacy flag's false default
    paths, _ = _bundle(tmp_path, "plain")
    calls: list[str] = []
    # When: a v2 magic operation is provided to the common service
    InvoiceService().apply_step("magic", config=RdeConfig(), dataset_paths=paths, magic_updater=lambda: calls.append("strict"))
    # Then: the operation is invoked once rather than gated by legacy rules
    assert calls == ["strict"]


def test_strict_magic_hook_preserves_failure(tmp_path: Path) -> None:
    """RUN12: Strict updater errors propagate unchanged through the service."""
    # Given: a catalogued error from the strict operation
    paths, _ = _bundle(tmp_path, "plain")
    before = (paths.invoice / "invoice.json").read_bytes()
    expected = validation_error(4010, "Requested source is absent.")

    def fail_update() -> None:
        raise expected

    # When: the common service invokes that operation
    with pytest.raises(RdeValidationError) as caught:
        InvoiceService().apply_step("magic", config=RdeConfig(), dataset_paths=paths, magic_updater=fail_update)
    # Then: type, integer code, and invoice contents remain intact
    assert caught.value is expected
    assert caught.value.code == 4010
    assert (paths.invoice / "invoice.json").read_bytes() == before
