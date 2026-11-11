"""PR 606 EP/BV: nullable aliases and typed blank values.

EP table
| Partition | Expected | Test ID |
|---|---|---|
| absent / null originalName, file / Mapping, all modes | definition key supplies value | P606-EP-001 |
| explicit empty alias, file / Mapping, all modes | alias retained; both keeps canonical precedence | P606-EP-002 |
| typed blanks, default, constant / variable | omit cells before conversion; preserve rows | P606-NEG-001 |
| typed blanks, keep enabled, constant / variable | StructuredError ecode 1 | P606-NEG-002 |
| invoice typed whitespace | legacy StructuredError ecode 1 | P606-NEG-003 |

BV table
| Boundary | Expected | Test ID |
|---|---|---|
| missing, null and zero-length alias | absent and null fall back; empty is an explicit alias | P606-EP-001 / 002 |
| zero-length / whitespace-only number, integer, boolean | omit by default; reject when retained | P606-NEG-001 / 002 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes import build_meta, parse_invoice_meta
from rdetoolkit.testing import make_invoice

MatchMode = Literal["key", "original_name", "both"]


def _source(tmp_path: Path, definitions: dict[str, Any], source_kind: str) -> Path | dict[str, Any]:
    if source_kind == "mapping":
        return definitions
    path = tmp_path / "metadata-def.json"
    path.write_text(json.dumps(definitions), encoding="utf-8")
    return path


@pytest.mark.parametrize("source_kind", ["file", "mapping"])
@pytest.mark.parametrize("match", ["key", "original_name", "both"])
@pytest.mark.parametrize("alias_state", ["absent", "null"])
def test_missing_alias_uses_definition_key__p606_ep_001(
    tmp_path: Path, source_kind: str, match: MatchMode, alias_state: str,
) -> None:
    """P606-EP-001: nullable originalName behaves like an omitted originalName."""
    # Given: an optional alias and a measured value under the definition key
    definition: dict[str, Any] = {"schema": {"type": "string"}}
    if alias_state == "null":
        definition["originalName"] = None
    source = _source(tmp_path, {"sample": definition}, source_kind)
    # When: applying any supported matching mode
    metadata = build_meta({"sample": "A001", "": "unrelated"}, source, match=match)
    # Then: null never replaces the usable definition key
    assert metadata.custom == {"sample": "A001"}


@pytest.mark.parametrize("source_kind", ["file", "mapping"])
@pytest.mark.parametrize("match, expected", [("key", "canonical"), ("original_name", "alias"), ("both", "canonical")])
def test_explicit_empty_alias_is_preserved__p606_ep_002(
    tmp_path: Path, source_kind: str, match: MatchMode, expected: str,
) -> None:
    """P606-EP-002: an explicitly empty alias retains its existing meaning."""
    # Given: distinct values under the definition key and its empty-string alias
    source = _source(tmp_path, {"sample": {"schema": {"type": "string"}, "originalName": ""}}, source_kind)
    # When: choosing the source matching policy
    metadata = build_meta({"sample": "canonical", "": "alias"}, source, match=match)
    # Then: empty aliases remain usable without changing canonical precedence
    assert metadata.custom == {"sample": expected}


@pytest.mark.parametrize("source_kind", ["file", "mapping"])
@pytest.mark.parametrize("schema_type", ["number", "integer", "boolean"])
@pytest.mark.parametrize("blank", ["", " \t\n"], ids=["empty", "whitespace"])
@pytest.mark.parametrize("variable", [False, True], ids=["constant", "variable"])
def test_typed_blank_is_omitted_by_default__p606_neg_001(
    tmp_path: Path, source_kind: str, schema_type: str, blank: str, variable: bool,
) -> None:
    """P606-NEG-001: normalized blanks are absent even for non-string schemas."""
    # Given: an empty or whitespace-only measurement of a non-string field
    source = _source(tmp_path, {"k": {"schema": {"type": schema_type}, "variable": int(variable)}}, source_kind)
    # When: using the default omission policy
    metadata = build_meta({"k": blank}, source)
    # Then: conversion is skipped for the blank cell and variable rows stay aligned
    assert metadata.custom == {}
    assert metadata.variable == ([{}] if variable else [])


@pytest.mark.parametrize("source_kind", ["file", "mapping"])
@pytest.mark.parametrize("schema_type", ["number", "integer", "boolean"])
@pytest.mark.parametrize("blank", ["", " \t\n"], ids=["empty", "whitespace"])
@pytest.mark.parametrize("variable", [False, True], ids=["constant", "variable"])
def test_retained_typed_blank_fails_conversion__p606_neg_002(
    tmp_path: Path, source_kind: str, schema_type: str, blank: str, variable: bool,
) -> None:
    """P606-NEG-002: retention cannot make a blank a number, integer or boolean."""
    # Given: the same typed blank with retention explicitly requested
    source = _source(tmp_path, {"k": {"schema": {"type": schema_type}, "variable": int(variable)}}, source_kind)
    # When: passing the retained blank through schema conversion
    with pytest.raises(StructuredError) as raised:
        build_meta({"k": blank}, source, keep_empty_strings=True)
    # Then: the existing conversion exception and integer error code are preserved
    assert raised.value.ecode == 1


@pytest.mark.parametrize("schema_type", ["number", "integer", "boolean"])
def test_invoice_typed_whitespace_keeps_error__p606_neg_003(tmp_path: Path, schema_type: str) -> None:
    """P606-NEG-003: build_meta's normalization does not alter the invoice node."""
    # Given: an invoice with a whitespace-only non-string measurement
    source = _source(tmp_path, {"k": {"schema": {"type": schema_type}}}, "file")
    assert isinstance(source, Path)
    invoice = make_invoice({"k": " \t\n"})
    # When: using the existing invoice parsing API
    with pytest.raises(StructuredError) as raised:
        parse_invoice_meta(invoice, source)
    # Then: the legacy conversion failure is preserved
    assert raised.value.ecode == 1
