"""Public compatibility contracts for rule mappings (issue #728)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from rdetoolkit.errors import RdeValidationError
from rdetoolkit.invoicefile import RuleBasedReplacer


def test_explicit_rules_override_stored_rules__728_ep_001() -> None:
    """728-EP-001: Explicit rules alone select destinations and values."""
    # Given: stored and explicit rules name different fields and placeholders.
    replacer = RuleBasedReplacer()
    replacer.set_rule("basic.dataName", "stored")
    source: dict[str, Any] = {"basic": {"dataName": "keep"}}
    rules = {"custom.label": "explicit"}
    replacements = {"stored": "wrong", "explicit": "right"}
    # When: an explicit mapping is applied.
    result = replacer.get_apply_rules_obj(replacements, source, mapping_rules=rules)
    # Then: only the explicit field changes and read-only inputs stay intact.
    assert result == {"basic": {"dataName": "keep"}, "custom": {"label": "right"}}
    assert source == result
    assert replacer.rules == {"basic.dataName": "stored"}
    assert rules == {"custom.label": "explicit"}
    assert replacements == {"stored": "wrong", "explicit": "right"}


def test_default_rules_mutate_source__728_ep_002() -> None:
    """728-EP-002: Omitting mapping_rules preserves successful source mutation."""
    # Given: a stored rule and a mutable source containing unrelated fields.
    replacer = RuleBasedReplacer()
    replacer.set_rule("basic.dataName", "name")
    source: dict[str, Any] = {"basic": {"dataName": "old", "description": "keep"}}
    # When: using the compatibility API with no explicit override.
    result = replacer.get_apply_rules_obj({"name": "new"}, source)
    # Then: the requested assignment mutates the source and preserves siblings.
    assert source == {"basic": {"dataName": "new", "description": "keep"}}
    assert result == source == replacer.last_apply_result


def test_missing_replacement_is_empty_string__728_ep_003() -> None:
    """728-EP-003: Missing replacements retain the legacy empty-string value."""
    # Given: a rule whose replacement key is absent.
    replacer = RuleBasedReplacer()
    source: dict[str, Any] = {"basic": {"dataName": "old"}}
    # When: applying the explicit rule with an empty replacement dictionary.
    result = replacer.get_apply_rules_obj({}, source, mapping_rules={"basic.dataName": "missing"})
    # Then: only the explicitly targeted value becomes an empty string.
    assert result == source == {"basic": {"dataName": ""}}


def test_replacement_objects_are_not_borrowed__728_ep_004() -> None:
    """728-EP-004: Editing the result does not mutate supplied replacement data."""
    # Given: a replacement that contains mutable nested data.
    replacer = RuleBasedReplacer()
    replacements = {"names": ["sample"]}
    # When: applying a nested rule and later editing the result.
    result = replacer.get_apply_rules_obj(replacements, None, mapping_rules={"sample.names": "names"})
    result["sample"]["names"].append("second")
    # Then: caller-owned replacements remain unchanged.
    assert replacements == {"names": ["sample"]}


def test_nested_source_references_observe_updates__728_ep_008() -> None:
    """728-EP-008: Successful assignments preserve existing nested identities."""
    # Given: a caller retains a reference to an existing nested source object.
    replacer = RuleBasedReplacer()
    basic = {"dataName": "old"}
    source = {"basic": basic}
    # When: applying a rule to that nested object.
    result = replacer.get_apply_rules_obj({"name": "new"}, source, mapping_rules={"basic.dataName": "name"})
    # Then: the retained source reference observes the assignment as in v1.
    assert basic["dataName"] == "new"
    assert source["basic"] is basic
    assert result == source


@pytest.mark.parametrize("ancestor", [None, "scalar", ["list"]])
def test_scalar_ancestor_is_rejected__728_ep_005(ancestor: object) -> None:
    """728-EP-005: An existing scalar/list ancestor is never discarded."""
    # Given: the target must traverse a non-object value.
    replacer = RuleBasedReplacer()
    replacer.last_apply_result = {"previous": "keep"}
    source: dict[str, Any] = {"basic": ancestor}
    before = deepcopy(source)
    # When: attempting to assign below that value.
    with pytest.raises(RdeValidationError) as caught:
        replacer.get_apply_rules_obj({"name": "new"}, source, mapping_rules={"basic.dataName": "name"})
    # Then: a catalogued error preserves the source and previous result.
    assert caught.value.code == 4008
    assert "basic" in str(caught.value)
    assert source == before
    assert replacer.last_apply_result == {"previous": "keep"}


@pytest.mark.parametrize("paths", [("basic", "basic.dataName"), ("basic.dataName", "basic")])
def test_overlapping_rules_are_rejected__728_ep_006(paths: tuple[str, str]) -> None:
    """728-EP-006: Parent/child conflicts are rejected in both mapping orders."""
    # Given: two rules assign to a parent and one of its children.
    replacer = RuleBasedReplacer()
    source: dict[str, Any] = {"basic": {"dataName": "keep"}}
    before = deepcopy(source)
    # When: applying overlapping destinations.
    with pytest.raises(RdeValidationError) as caught:
        replacer.get_apply_rules_obj({"value": "new"}, source, mapping_rules=dict.fromkeys(paths, "value"))
    # Then: rule order does not affect the rejected, unchanged result.
    assert caught.value.code == 4008
    assert source == before
    assert replacer.last_apply_result == {}


@pytest.mark.parametrize("path", ["", ".basic", "basic.", "basic..dataName", "."])
def test_empty_path_segments_are_rejected__728_ep_007(path: str) -> None:
    """728-EP-007: Empty path segments are invalid rather than empty JSON keys."""
    # Given: a malformed dotted destination and an unrelated existing value.
    replacer = RuleBasedReplacer()
    source: dict[str, Any] = {"keep": 1}
    # When: applying the malformed path.
    with pytest.raises(RdeValidationError) as caught:
        replacer.get_apply_rules_obj({"value": "new"}, source, mapping_rules={path: "value"})
    # Then: no assignment or empty key is published.
    assert caught.value.code == 4008
    assert source == {"keep": 1}
    assert replacer.last_apply_result == {}


def test_explicit_empty_rules_disable_replacement__728_bv_001() -> None:
    """728-BV-001: An explicit empty mapping does not fall back to stored rules."""
    # Given: stored rules would replace an existing value.
    replacer = RuleBasedReplacer()
    replacer.set_rule("basic.dataName", "name")
    source: dict[str, Any] = {"basic": {"dataName": "keep"}}
    # When: explicitly selecting no rules.
    result = replacer.get_apply_rules_obj({"name": "new"}, source, mapping_rules={})
    # Then: the source stays unchanged.
    assert result == source == {"basic": {"dataName": "keep"}}


def test_absent_source_creates_mapping__728_bv_002() -> None:
    """728-BV-002: Unknown object paths are created when no source is supplied."""
    # Given: no source object and one nested destination.
    replacer = RuleBasedReplacer()
    # When: applying the supplied mapping.
    result = replacer.get_apply_rules_obj({"value": 0}, None, mapping_rules={"custom.value": "value"})
    # Then: a new object preserves the replacement's scalar type.
    assert result == {"custom": {"value": 0}}


def test_late_failure_does_not_publish_earlier_assignment__728_bv_003() -> None:
    """728-BV-003: A later conflict rolls back all assignments in this operation."""
    # Given: a valid assignment precedes one that traverses a scalar.
    replacer = RuleBasedReplacer()
    source: dict[str, Any] = {"basic": {"dataName": "keep"}, "sample": "existing"}
    before = deepcopy(source)
    # When: applying both rules together.
    with pytest.raises(RdeValidationError) as caught:
        replacer.get_apply_rules_obj({"value": "new"}, source, mapping_rules={"basic.dataName": "value", "sample.names": "value"})
    # Then: the first rule has not partially changed the source.
    assert caught.value.code == 4008
    assert source == before
    assert replacer.last_apply_result == {}
