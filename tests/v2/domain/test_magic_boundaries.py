"""Boundary contracts for strict interpolation publication and diagnostics.

EP/BV: B01 local omission length accounts for collapsed separators; B02 absent
auto target has no eligible fields; B03 non-object source fails 4006; B04 schema
failure identifies a standard field; B05 tempfile failure leaves no output;
B06 disabled/non-object static template inputs remain untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, resolve_invoice
from rdetoolkit.domain.magic_service import apply_interpolation, validate_templates
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.fileops import readf_json, writef_json
from tests.v2.domain.test_magic_service import _bundle


def test_omission_counts_actual_output_length() -> None:
    """B01: A collapsed separator must not count against output length."""
    # Given: a valid template whose omitted separator run is much longer than its result
    context = ResolutionContext.from_sources(
        original_invoice={"custom": {"value": "x" * 1000}},
        current_invoice={"basic": {"dataName": "label", "description": "_" * 16000 + "${invoice:custom:absent}_${invoice:custom:value}"}},
    )
    # When: explicitly omitting the absent field
    result = resolve_invoice(context, options=MagicOptions(missing="omit"))
    # Then: the limit applies to the actual resulting text
    assert result["basic"]["description"] == "_" + "x" * 1000


@pytest.mark.parametrize("policy", ["auto", "disabled"])
def test_absent_auto_target_has_no_eligible_fields(tmp_path: Path, policy: str) -> None:
    """B02: An absent optional target cannot opt into interpolation."""
    # Given: no tile invoice and no forced-on policy
    paths, snapshot = _bundle(tmp_path, "plain")
    (paths.invoice / "invoice.json").unlink()
    # When: discovering whether this stage has an eligible field
    preview = apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(policy=policy), iteration_index=0, mode="invoice")
    # Then: no invoice is created and no replacement is planned
    assert preview.diagnostics == ()
    assert not (paths.invoice / "invoice.json").exists()


@pytest.mark.parametrize("source", [[], None, "private"])
def test_non_object_source_is_rejected(tmp_path: Path, source: object) -> None:
    """B03: JSON scalars and arrays cannot masquerade as invoice sources."""
    # Given: a non-object JSON source
    paths, snapshot = _bundle(tmp_path, "plain")
    path = paths.invoice / "invoice.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    before = path.read_bytes()
    # When: explicitly requesting interpolation
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(policy="enabled"), iteration_index=0, mode="invoice")
    # Then: its type and privacy-safe error preserve the source
    assert caught.value.code == 4006
    assert "private" not in str(caught.value)
    assert path.read_bytes() == before


def test_standard_schema_error_identifies_field(tmp_path: Path) -> None:
    """B04: Standard invoice validation also preserves field-level context."""
    # Given: an invalid standard field and an otherwise resolvable template
    paths, snapshot = _bundle(tmp_path, "${invoice:basic:dataOwnerId}")
    current = readf_json(paths.invoice / "invoice.json")
    current["basic"]["dataOwnerId"] = "private-invalid-owner"
    writef_json(paths.invoice / "invoice.json", current)
    # When: validating the replacement before publication
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    # Then: only the standard field location appears
    assert caught.value.code == 4007
    assert "basic.dataOwnerId" in str(caught.value)
    assert "private-invalid-owner" not in str(caught.value)


def test_tempfile_failure_preserves_invoice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B05: Failure before a temporary file exists preserves the invoice."""
    # Given: a valid replacement and a filesystem that refuses a temporary file
    paths, snapshot = _bundle(tmp_path, "${invoice:basic:dataOwnerId}")
    before = (paths.invoice / "invoice.json").read_bytes()

    def refuse_tempfile(*args: Any, **kwargs: Any) -> None:
        message = "private-path"
        raise OSError(message)

    monkeypatch.setattr("rdetoolkit.domain.magic_service.tempfile.NamedTemporaryFile", refuse_tempfile)
    # When: publishing the validated result
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    # Then: no output or private exception text is published
    assert caught.value.code == 4007
    assert "private-path" not in str(caught.value)
    assert (paths.invoice / "invoice.json").read_bytes() == before


@pytest.mark.parametrize("basic", [None, [], 0])
def test_non_object_basic_is_untouched(tmp_path: Path, basic: object) -> None:
    """B06: Field allowlisting never coerces unsupported containers or scalars."""
    # Given: an invoice with no eligible string field
    paths, snapshot = _bundle(tmp_path, "plain")
    writef_json(paths.invoice / "invoice.json", {"basic": basic})
    before = (paths.invoice / "invoice.json").read_bytes()
    # When: asking both static and artifact interpolation to inspect it
    pending = validate_templates({"basic": basic}, MagicOptions())
    apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=0, mode="invoice")
    # Then: downstream invoice validation owns the non-string shape
    assert pending is False
    assert (paths.invoice / "invoice.json").read_bytes() == before


def test_static_disabled_preserves_malformed_template() -> None:
    """B06: Explicitly disabled interpolation preserves even malformed text."""
    # Given: an invalid expression intentionally kept literal
    invoice = {"basic": {"dataName": "${}"}}
    # When: validating template syntax under the disabled policy
    pending = validate_templates(invoice, MagicOptions(policy="disabled"))
    # Then: the expression is not parsed
    assert pending is False
