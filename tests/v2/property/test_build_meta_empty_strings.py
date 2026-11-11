"""Issue 598 EP/BV: stripped string policy is deterministic and preserves inputs.

| Partition / boundary | Expected | Test ID |
|---|---|---|
| generated strings with whitespace, both empty-string policies | retain trimmed values or omit empty ones | I598-PBT-001 |
| canonical None plus an originalName value | canonical absence keeps PR 594 precedence | I598-PBT-001 |
"""

from __future__ import annotations

from typing import Any

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
