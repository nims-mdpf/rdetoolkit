"""Deferred sources in the pure preview (#727).

EP/BV: deferred scope is reported without reading it; destinations holding a
deferred token skip output checks; unknown scope names are rejected;
resolve_invoice never defers.
"""

from typing import Any

import pytest

from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, preview_invoice, resolve_invoice


def _context(name: str, *, metadata: dict[str, Any] | None = None, invoice: dict[str, Any] | None = None) -> ResolutionContext:
    return ResolutionContext.from_sources(
        original_invoice=invoice or {"custom": {"batch": "B-1"}},
        current_invoice={"basic": {"dataName": name}},
        metadata=metadata,
    )


def test_deferred_metadata_token_is_not_read__deferred_p1() -> None:
    # Given: a metadata expression with no metadata source at all.
    context = _context("${metadata:constant:thickness}")
    # When: previewing with metadata deferred.
    result = preview_invoice(context, deferred_scopes=frozenset({"metadata"}))
    # Then: one deferred diagnostic with no error code.
    (item,) = result.diagnostics
    assert (item.status, item.reason, item.code) == ("deferred", "deferred_source", None)
    assert item.destination == "basic.dataName"
    assert item.source_scope == "metadata"


def test_without_deferral_missing_metadata_is_unavailable__deferred_p2() -> None:
    # Given: the same context without deferral.
    result = preview_invoice(_context("${metadata:constant:thickness}"))
    # Then: the default behavior is unchanged.
    assert result.diagnostics[0].status == "unavailable"
    assert result.diagnostics[0].code == 4010


def test_other_scopes_still_resolve_when_one_is_deferred__deferred_p3() -> None:
    # Given: a mix of resolvable and deferred tokens.
    context = _context("${invoice:custom:batch}_${metadata:constant:thickness}")
    # When: previewing with metadata deferred.
    result = preview_invoice(context, deferred_scopes=frozenset({"metadata"}))
    # Then: each token keeps its own status.
    assert [item.status for item in result.diagnostics] == ["resolved", "deferred"]


def test_deferred_token_skips_output_checks_under_omit__deferred_p4() -> None:
    # Given: omit policy where the only token is deferred, so the output is unknown.
    context = _context("${metadata:constant:thickness}")
    # When: previewing.
    result = preview_invoice(context, options=MagicOptions(missing="omit"), deferred_scopes=frozenset({"metadata"}))
    # Then: no spurious invalid_data_name 4007 is reported.
    assert all(item.code is None for item in result.diagnostics)
    assert [item.reason for item in result.diagnostics] == ["deferred_source"]


def test_deferral_does_not_hide_other_errors__deferred_p5() -> None:
    # Given: a deferred token next to a missing invoice key.
    context = _context("${metadata:constant:thickness}${invoice:custom:absent}")
    # When: previewing.
    result = preview_invoice(context, deferred_scopes=frozenset({"metadata"}))
    # Then: the real problem is still reported.
    assert [(item.status, item.code) for item in result.diagnostics] == [("deferred", None), ("unavailable", 4010)]


def test_schema_validation_skipped_when_deferred__deferred_p6() -> None:
    # Given: a schema the unresolved candidate would violate.
    schema = {"type": "object", "properties": {"basic": {"properties": {"dataName": {"maxLength": 1}}}}}
    context = _context("${metadata:constant:thickness}")
    # When: previewing with the deferral.
    deferred = preview_invoice(context, schema=schema, deferred_scopes=frozenset({"metadata"}))
    # Then: schema checks are skipped because the candidate is incomplete.
    assert all(item.reason != "schema_violation" for item in deferred.diagnostics)


def test_unknown_deferred_scope_rejected__deferred_n1() -> None:
    # Given: a scope name the parser never produces.
    # When/Then: the preview rejects it up front.
    with pytest.raises(ValueError, match="deferred"):
        preview_invoice(_context("x"), deferred_scopes=frozenset({"bogus"}))


def test_resolve_invoice_has_no_deferral__deferred_n2() -> None:
    # Given/When/Then: resolution does not accept deferral.
    with pytest.raises(TypeError):
        resolve_invoice(_context("${metadata:constant:thickness}"), deferred_scopes=frozenset({"metadata"}))  # type: ignore[call-arg]


def test_preview_full_resolution_can_still_fail_final_schema__rde002() -> None:
    # Given: a name that resolves, but violates the destination schema.
    context = _context("${invoice:custom:batch}")
    schema = {"type": "object", "properties": {"basic": {"properties": {"dataName": {"maxLength": 1}}}}}
    # When: previewing without and then with the schema.
    plain = preview_invoice(context)
    checked = preview_invoice(context, schema=schema)
    # Then: resolution alone succeeds; only the schema check reveals the final failure.
    assert all(item.code is None for item in plain.diagnostics)
    assert [(item.reason, item.code) for item in checked.diagnostics if item.code] == [("schema_violation", 4007)]
