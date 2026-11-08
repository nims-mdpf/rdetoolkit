"""GA570 EP/BV: absent metadata values are excluded before conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.rde2util import Meta


@pytest.mark.parametrize("schema_type", ["number", "string", "boolean", "integer"])
def test_none_is_not_assigned__ga570_ep_1(tmp_path: Path, schema_type: str) -> None:
    """GA570-EP-1: None never becomes the string 'None' or triggers a cast."""
    # Given: an absent typed value alongside a valid string measurement
    definition = tmp_path / "metadata-def.json"
    definition.write_text(json.dumps({"x": {"schema": {"type": schema_type}}, "y": {"schema": {"type": "string"}}}), encoding="utf-8")
    metadata = Meta(definition)
    # When: assigning and writing through the public Tier 1 API
    assigned = metadata.assign_vals({"x": None, "y": "ok"})
    destination = tmp_path / "metadata.json"
    metadata.writefile(str(destination))
    # Then: the absent value is excluded and the valid sibling survives
    assert assigned["assigned"] == {"y"}
    assert json.loads(destination.read_text(encoding="utf-8")) == {"constant": {"y": {"value": "ok"}}, "variable": []}


def test_all_none_produces_empty_metadata__ga570_bv_1(tmp_path: Path) -> None:
    """GA570-BV-1: the all-absent boundary writes an empty metadata object."""
    # Given: one optional numeric field and no value
    definition = tmp_path / "metadata-def.json"
    definition.write_text('{"x": {"schema": {"type": "number"}}}', encoding="utf-8")
    metadata = Meta(definition)
    # When: assigning only None
    assignment = metadata.assign_vals({"x": None})
    # Then: no field is registered
    assert assignment["assigned"] == set()
    assert metadata.metaConst == {}
    assert metadata.metaVar == []


def test_none_unit_reference_is_absent__ga570_bv_2(tmp_path: Path) -> None:
    """GA570-BV-2: a missing unit source does not emit unit='None'."""
    # Given: a measured value referencing an absent unit
    definition = tmp_path / "metadata-def.json"
    definition.write_text('{"x": {"schema": {"type": "number"}, "unit": "$unit"}}', encoding="utf-8")
    metadata = Meta(definition)
    # When: assigning and writing the measurement
    metadata.assign_vals({"x": 3, "unit": None})
    destination = tmp_path / "metadata.json"
    metadata.writefile(str(destination))
    # Then: no artificial unit is introduced
    assert json.loads(destination.read_text(encoding="utf-8"))["constant"]["x"] == {"value": 3}


def test_invalid_nonempty_numeric_still_fails__ga570_neg_1(tmp_path: Path) -> None:
    """GA570-NEG-1: the fix never suppresses a genuine conversion failure."""
    # Given: a numeric definition and an invalid nonempty value
    definition = tmp_path / "metadata-def.json"
    definition.write_text('{"x": {"schema": {"type": "number"}}}', encoding="utf-8")
    metadata = Meta(definition)
    # When: assigning invalid data
    with pytest.raises(StructuredError) as raised:
        metadata.assign_vals({"x": "not-a-number"})
    # Then: the existing exception type and user error code remain unchanged
    assert raised.value.ecode == 1
