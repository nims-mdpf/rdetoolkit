"""GA563 EP/BV: v2 metadata retains units and repeated value rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit.nodes import save_meta
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import Metadata


def test_constant_unit_survives_edits__ga563_ep_1_bv_2(tmp_path: Path) -> None:
    """GA563-EP-1/BV-2: setting a value later does not discard its unit."""
    # Given: a measured value with a declared unit
    metadata = Metadata()
    metadata.set("c_rate", 0.1, unit="g")
    # When: editing the value and saving through the public v2 node
    metadata.set("c_rate", 0.2)
    path = save_meta(metadata, make_output_context(tmp_path))
    # Then: the unit and current value match the v1 JSON shape
    assert json.loads(path.read_text(encoding="utf-8")) == {"constant": {"c_rate": {"value": 0.2, "unit": "g"}}, "variable": []}


def test_variable_rows_are_written__ga563_ep_2(tmp_path: Path) -> None:
    """GA563-EP-2: variable rows are not silently replaced with an empty list."""
    # Given: repeated cells with different units in each row
    rows = [{"temperature": {"value": 300, "unit": "K"}}, {"temperature": {"value": 30, "unit": "C"}}]
    metadata = Metadata(variable=rows)
    # When: saving them
    path = save_meta(metadata, make_output_context(tmp_path))
    # Then: all repeated cells are retained without mutating the container
    assert json.loads(path.read_text(encoding="utf-8")) == {"constant": {}, "variable": rows}
    assert metadata.variable == rows


def test_existing_unannotated_metadata_shape__ga563_bv_1(tmp_path: Path) -> None:
    """GA563-BV-1: existing construction keeps the previous output contract."""
    # Given: existing v2 code without unit or variable information
    metadata = Metadata(custom={"sample": "x"}, basic={"dataName": "excluded"})
    # When: writing it
    path = save_meta(metadata, make_output_context(tmp_path))
    # Then: the old constant shape remains valid
    assert json.loads(path.read_text(encoding="utf-8")) == {"constant": {"sample": {"value": "x"}}, "variable": []}


@pytest.mark.parametrize("variable", [False, True])
def test_unserializable_values_are_never_dropped__ga563_neg_1(tmp_path: Path, variable: bool) -> None:
    """GA563-NEG-1: unsupported cell values fail rather than disappearing."""
    # Given: a non-JSON value in a constant or repeated cell
    metadata = Metadata(variable=[{"x": {"value": object()}}] if variable else [], custom={} if variable else {"x": object()})
    out = make_output_context(tmp_path)
    # When: attempting to save it
    with pytest.raises(TypeError, match="not JSON serializable"):
        save_meta(metadata, out)
    # Then: no misleading metadata file was published
    assert not (out.meta / "metadata.json").exists()
