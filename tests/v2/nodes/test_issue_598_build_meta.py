"""Issue 598 EP/BV: mapping definitions, explicit source matching and empty strings.

EP table
| Partition | Expected | Test ID |
|---|---|---|
| dict / read-only Mapping definition | same typed values, units and variable rows as a file; inputs unchanged | I598-EP-001 |
| filtered definition Mapping | excluded definitions neither validate nor write values | I598-EP-002 |
| key / original_name / both | select the declared source; both keeps PR 594 key precedence | I598-EP-003 |
| original_name without an alias | use the definition key | I598-EP-004 |
| empty or whitespace-only string, keep enabled | retain the stripped empty string | I598-EP-005 |
| variable empty strings, keep disabled / enabled | preserve row alignment, omit / retain cells | I598-EP-006 |
| parse_invoice_meta compatibility | preserve its existing whitespace-string behavior | I598-EP-007 |
| alias-only input with key matching | exclude it | I598-NEG-001 |
| key-only input with original_name matching | exclude it when the definition declares an alias | I598-NEG-002 |
| empty or whitespace-only string, default | exclude it after stripping | I598-NEG-003 |
| unsupported match mode | RdeConfigError 1004 | I598-NEG-004 |
| invalid number / integer / boolean, file or Mapping | StructuredError ecode 1 | I598-NEG-005 |
| empty numeric value, keep enabled | still fails schema conversion with ecode 1 | I598-NEG-006 |
| directly assigned action field, file or Mapping | StructuredError ecode 1 | I598-NEG-007 |

BV table
| Boundary | Expected | Test ID |
|---|---|---|
| zero definitions | empty metadata | I598-BV-001 |
| exact empty, one space, mixed whitespace | same rule before and after trimming | I598-EP-005 / I598-NEG-003 |
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import pytest

from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes import build_meta, parse_invoice_meta, save_meta
from rdetoolkit.testing import make_invoice, make_output_context

MatchMode = Literal["key", "original_name", "both"]


def _definition_file(tmp_path: Path, definitions: Mapping[str, Any]) -> Path:
    path = tmp_path / "metadata-def.json"
    path.write_text(json.dumps(dict(definitions)), encoding="utf-8")
    return path


@pytest.mark.parametrize("readonly", [False, True], ids=["dict", "mapping-proxy"])
def test_mapping_matches_file_without_mutation__i598_ep_001(tmp_path: Path, readonly: bool) -> None:
    """I598-EP-001: in-memory definitions preserve conversion, units and row ordering."""
    # Given: constants, repeated values and both referenced and literal units
    definitions = {
        "temperature": {"schema": {"type": "number"}, "originalName": "T", "unit": "$U"},
        "position": {"schema": {"type": "integer"}, "variable": 1, "unit": "mm"},
        "label": {"schema": {"type": "string"}},
    }
    before = deepcopy(definitions)
    values = {"T": "12.5", "U": "K", "label": "sample"}
    repeated = {"position": [1, 2]}
    source: Mapping[str, Any] = MappingProxyType(definitions) if readonly else definitions
    path = _definition_file(tmp_path, definitions)
    # When: building and saving through both public definition forms
    mapped = save_meta(build_meta(values, source, repeated=repeated), make_output_context(tmp_path / "mapped"))
    file_based = save_meta(build_meta(values, path, repeated=repeated), make_output_context(tmp_path / "file"))
    # Then: their complete artifacts agree and no caller-owned data was modified
    expected = {
        "constant": {"temperature": {"value": 12.5, "unit": "K"}, "label": {"value": "sample"}},
        "variable": [{"position": {"value": 1, "unit": "mm"}}, {"position": {"value": 2, "unit": "mm"}}],
    }
    assert json.loads(mapped.read_text(encoding="utf-8")) == expected
    assert mapped.read_bytes() == file_based.read_bytes()
    assert definitions == before
    assert values == {"T": "12.5", "U": "K", "label": "sample"}
    assert repeated == {"position": [1, 2]}


def test_filtered_mapping_excludes_other_types__i598_ep_002() -> None:
    """I598-EP-002: a filtered Mapping avoids temporary files and unrelated validation."""
    # Given: a shared definition and an invalid measurement of an excluded type
    shared = {"temperature": {"schema": {"type": "number"}}, "other": {"schema": {"type": "integer"}}}
    selected = {key: definition for key, definition in shared.items() if key == "temperature"}
    # When: passing only the measured type's definition
    metadata = build_meta({"temperature": "12.5", "other": "invalid"}, selected)
    # Then: unrelated values are neither validated nor written
    assert metadata.custom == {"temperature": 12.5}
    assert metadata.variable == []


@pytest.mark.parametrize("match, expected", [("key", 2), ("original_name", 7), ("both", 2)])
def test_matching_mode_selects_source__i598_ep_003(tmp_path: Path, match: MatchMode, expected: int) -> None:
    """I598-EP-003: source selection is explicit and the default precedence is retained."""
    # Given: both the definition key and originalName with distinct values
    path = _definition_file(tmp_path, {"k": {"schema": {"type": "integer"}, "originalName": "raw"}})
    # When: choosing a matching mode
    metadata = build_meta({"k": 2, "raw": 7}, path, match=match)
    # Then: only the requested source supplies the field
    assert metadata.custom == {"k": expected}


def test_original_matching_without_alias_uses_key__i598_ep_004(tmp_path: Path) -> None:
    """I598-EP-004: definitions without originalName retain their definition key."""
    # Given: a definition without an alias
    path = _definition_file(tmp_path, {"k": {"schema": {"type": "integer"}}})
    # When: selecting original_name matching
    metadata = build_meta({"k": 2}, path, match="original_name")
    # Then: the only available name is used
    assert metadata.custom == {"k": 2}


@pytest.mark.parametrize("value", ["", " ", "\t \n"])
def test_keep_empty_strings_retains_empty_value__i598_ep_005(tmp_path: Path, value: str) -> None:
    """I598-EP-005: keep_empty_strings retains an empty string after trimming."""
    # Given: a string definition and an empty or whitespace-only measurement
    path = _definition_file(tmp_path, {"s": {"schema": {"type": "string"}}})
    # When: explicitly retaining empty strings
    metadata = build_meta({"s": value}, path, keep_empty_strings=True)
    # Then: the stripped empty string remains a real string value
    assert metadata.custom == {"s": ""}


@pytest.mark.parametrize("keep", [False, True])
def test_variable_empty_strings_keep_row_alignment__i598_ep_006(tmp_path: Path, keep: bool) -> None:
    """I598-EP-006: omission and retention preserve repeated row positions."""
    # Given: a variable string column with empty, whitespace and nonempty values
    path = _definition_file(tmp_path, {"s": {"schema": {"type": "string"}, "variable": 1}})
    repeated = {"s": ["", "  ", " x "]}
    # When: selecting the empty-string policy
    metadata = build_meta({}, path, repeated=repeated, keep_empty_strings=keep)
    # Then: missing cells keep their rows and nonempty values are still trimmed
    empty = {"s": {"value": ""}} if keep else {}
    assert metadata.variable == [empty, empty, {"s": {"value": "x"}}]
    assert repeated == {"s": ["", "  ", " x "]}


def test_invoice_parser_keeps_legacy_string_rule__i598_ep_007(tmp_path: Path) -> None:
    """I598-EP-007: the shared converter does not change parse_invoice_meta's contract."""
    # Given: an invoice string containing one space
    path = _definition_file(tmp_path, {"s": {"schema": {"type": "string"}}})
    invoice = make_invoice({"s": " "})
    # When: using the existing invoice node
    metadata = parse_invoice_meta(invoice, path)
    # Then: its legacy pre-trim emptiness check still keeps the stripped string
    assert metadata.custom == {"s": ""}


@pytest.mark.parametrize("value", [3, None])
def test_key_matching_ignores_alias_only_input__i598_neg_001(tmp_path: Path, value: Any) -> None:
    """I598-NEG-001: Meta's legacy alias fallback cannot bypass key-only matching."""
    # Given: an alias-only measurement
    path = _definition_file(tmp_path, {"k": {"schema": {"type": "integer"}, "originalName": "raw"}})
    # When: allowing only definition keys
    metadata = build_meta({"raw": value}, path, match="key")
    # Then: the alias is excluded
    assert metadata.custom == {}


@pytest.mark.parametrize("value", [3, None])
def test_original_matching_ignores_key_only_input__i598_neg_002(tmp_path: Path, value: Any) -> None:
    """I598-NEG-002: canonical values cannot bypass original-name-only matching."""
    # Given: a definition with an alias, but only its canonical key is supplied
    path = _definition_file(tmp_path, {"k": {"schema": {"type": "integer"}, "originalName": "raw"}})
    # When: allowing only original names
    metadata = build_meta({"k": value}, path, match="original_name")
    # Then: the canonical source is excluded
    assert metadata.custom == {}


@pytest.mark.parametrize("value", ["", " ", "\t \n"])
def test_default_omits_empty_after_trimming__i598_neg_003(tmp_path: Path, value: str) -> None:
    """I598-NEG-003: exact empty strings and whitespace-only strings agree by default."""
    # Given: the same string schema for each form of empty measurement
    path = _definition_file(tmp_path, {"s": {"schema": {"type": "string"}}})
    # When: using the default empty-string policy
    metadata = build_meta({"s": value}, path)
    # Then: no empty field is written
    assert metadata.custom == {}


@pytest.mark.parametrize("match", ["", "invalid", "KEY", "originalName", None, 1])
def test_unknown_matching_mode_is_cataloged__i598_neg_004(tmp_path: Path, match: Any) -> None:
    """I598-NEG-004: unsupported modes fail with the registered usage error."""
    # Given: an existing definition and an unsupported matching mode
    path = _definition_file(tmp_path, {"s": {"schema": {"type": "string"}}})
    # When: selecting that mode
    with pytest.raises(RdeConfigError) as raised:
        build_meta({"s": "x"}, path, match=match)
    # Then: both the exception class and cataloged integer code are preserved
    assert raised.value.code == 1004
    assert raised.value.name == ERROR_CATALOG[1004].name == "InvalidMetadataMatchMode"


@pytest.mark.parametrize("source_kind", ["file", "mapping"])
@pytest.mark.parametrize("schema_type", ["number", "integer", "boolean"])
def test_mapping_preserves_conversion_errors__i598_neg_005(tmp_path: Path, source_kind: str, schema_type: str) -> None:
    """I598-NEG-005: accepting mappings never bypasses schema validation."""
    # Given: an invalid typed measurement and either definition source
    definitions = {"k": {"schema": {"type": schema_type}}}
    source = _definition_file(tmp_path, definitions) if source_kind == "file" else definitions
    # When: validating the malformed value
    with pytest.raises(StructuredError) as raised:
        build_meta({"k": "invalid"}, source)
    # Then: the established v1 conversion exception and error code survive
    assert raised.value.ecode == 1


@pytest.mark.parametrize("schema_type, value", [("number", ""), ("integer", " ")])
def test_empty_numeric_string_still_validates__i598_neg_006(tmp_path: Path, schema_type: str, value: str) -> None:
    """I598-NEG-006: retaining empty strings cannot turn one into a valid number."""
    # Given: a numeric schema and an empty string requested for retention
    path = _definition_file(tmp_path, {"k": {"schema": {"type": schema_type}}})
    # When: preserving that string through conversion
    with pytest.raises(StructuredError) as raised:
        build_meta({"k": value}, path, keep_empty_strings=True)
    # Then: numeric validation still fails with its original code
    assert raised.value.ecode == 1


@pytest.mark.parametrize("source_kind", ["file", "mapping"])
def test_mapping_preserves_action_rejection__i598_neg_007(tmp_path: Path, source_kind: str) -> None:
    """I598-NEG-007: mapping definitions retain the action-derived field contract."""
    # Given: an action field that cannot be directly assigned
    definitions = {"k": {"schema": {"type": "number"}, "action": "$source"}}
    source = _definition_file(tmp_path, definitions) if source_kind == "file" else definitions
    # When: supplying the derived field directly
    with pytest.raises(StructuredError) as raised:
        build_meta({"k": 1}, source)
    # Then: the same action validation failure propagates
    assert raised.value.ecode == 1


def test_zero_definitions_produce_empty_metadata__i598_bv_001() -> None:
    """I598-BV-001: an empty mapping is a valid empty definition, without disk I/O."""
    # Given: a value with no selected definition
    # When: building from an empty Mapping
    metadata = build_meta({"unused": 1}, {})
    # Then: neither constants nor variable rows are invented
    assert metadata.custom == {}
    assert metadata.variable == []
