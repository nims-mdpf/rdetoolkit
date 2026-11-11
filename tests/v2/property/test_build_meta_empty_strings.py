"""Issue 598 EP/BV: stripped string policy is deterministic and preserves inputs.

| Partition / boundary | Expected | Test ID |
|---|---|---|
| generated strings with whitespace, both empty-string policies | retain trimmed values or omit empty ones | I598-PBT-001 |
| canonical None plus an originalName value | canonical absence keeps PR 594 precedence | I598-PBT-001 |
| generated keys, missing / null alias, every matching mode | key fallback and input immutability | P606-PBT-001 |
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

import pytest
from hypothesis import given, strategies as st

from rdetoolkit.nodes import build_meta


@pytest.mark.property
@given(text=st.text(alphabet="ab \t\n", max_size=12), keep=st.booleans(), canonical_none=st.booleans())
def test_empty_string_policy_is_stable__i598_pbt_001(text: str, keep: bool, canonical_none: bool) -> None:
    """I598-PBT-001: trimming, retention and key precedence agree on every string."""
    # Given: an aliased string and optionally a canonical None
    definitions = {"s": {"schema": {"type": "string"}, "originalName": "raw"}}
    values: dict[str, Any] = {"raw": text}
    if canonical_none:
        values["s"] = None
    before = values.copy()
    # When: applying the selected policy repeatedly to the same mapping
    first = build_meta(values, definitions, keep_empty_strings=keep)
    second = build_meta(values, definitions, keep_empty_strings=keep)
    # Then: empty handling is deterministic and caller values remain unchanged
    expected = {} if canonical_none or (not keep and not text.strip()) else {"s": text.strip()}
    assert first.custom == second.custom == expected
    assert values == before


@pytest.mark.property
@given(
    key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8),
    null_alias=st.booleans(),
    match=st.sampled_from(["key", "original_name", "both"]),
)
def test_nullable_alias_fallback_preserves_inputs__p606_pbt_001(
    key: str, null_alias: bool, match: Literal["key", "original_name", "both"],
) -> None:
    """P606-PBT-001: optional aliases keep generated canonical names usable."""
    # Given: a generated definition key with an absent or null alias
    definition: dict[str, Any] = {"schema": {"type": "string"}}
    if null_alias:
        definition["originalName"] = None
    definitions = {key: definition}
    before = deepcopy(definitions)
    values = {key: " A001 "}
    # When: selecting any matching mode without a usable alias
    first = build_meta(values, definitions, match=match)
    second = build_meta(values, definitions, match=match)
    # Then: the canonical source remains deterministic and inputs stay unchanged
    assert first.custom == second.custom == {key: "A001"}
    assert definitions == before
    assert values == {key: " A001 "}
