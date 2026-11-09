"""PR585 metadata regression: normalize each definition independently."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes import build_meta, save_meta
from rdetoolkit.testing import make_output_context


@pytest.mark.parametrize("constant, variable", [("constant", "variable"), ("T", "variable"), ("constant", "T")])
@pytest.mark.parametrize("reverse", [False, True])
def test_shared_source_keeps_constant_and_variable__r585_meta_1(tmp_path: Path, constant: str, variable: str, reverse: bool) -> None:
    """R585-META-1: sharing an originalName never changes another field's input."""
    # Given: constant and variable definitions aliasing the same measured source
    definitions = [
        (constant, {"schema": {"type": "number"}, "originalName": "T", "unit": "$U"}),
        (variable, {"schema": {"type": "number"}, "originalName": "T", "variable": 1, "unit": "$U"}),
    ]
    path = tmp_path / "metadata-def.json"
    path.write_text(json.dumps(dict(reversed(definitions) if reverse else definitions)), encoding="utf-8")
    values = {"T": "12.5", "U": "K"}
    # When: constructing and saving only through the public v2 API
    meta = build_meta(values, path)
    saved = save_meta(meta, make_output_context(tmp_path / "out"))
    # Then: both typed destinations survive as one scalar and one whole row
    assert json.loads(saved.read_text()) == {
        "constant": {constant: {"value": 12.5, "unit": "K"}},
        "variable": [{variable: {"value": 12.5, "unit": "K"}}],
    }
    assert values == {"T": "12.5", "U": "K"}


@pytest.mark.parametrize("values", [{}, {"T": None}])
def test_absent_alias_has_no_values__r585_meta_2(tmp_path: Path, values: dict[str, Any]) -> None:
    """R585-META-2: missing sources do not invent constants or variable rows."""
    # Given: two aliases without an actual source value
    path = tmp_path / "metadata-def.json"
    path.write_text(json.dumps({"c": {"schema": {"type": "number"}, "originalName": "T"}, "v": {"schema": {"type": "number"}, "originalName": "T", "variable": 1}}))
    # When: constructing metadata
    meta = build_meta(values, path)
    # Then: absent measurements remain absent
    assert meta.custom == {} and meta.variable == []


def test_bad_shared_source_keeps_validation_error__r585_meta_2(tmp_path: Path) -> None:
    """R585-META-2: normalization cannot hide a constant's conversion failure."""
    # Given: a variable first, followed by a constant using the same invalid source
    path = tmp_path / "metadata-def.json"
    path.write_text(json.dumps({"v": {"schema": {"type": "string"}, "originalName": "T", "variable": 1}, "c": {"schema": {"type": "number"}, "originalName": "T"}}))
    # When / Then: the constant's existing validation error is still raised
    with pytest.raises(StructuredError) as raised:
        build_meta({"T": "bad"}, path)
    assert raised.value.ecode == 1


def test_repeated_override_keeps_constant_alias__r585_meta_2(tmp_path: Path) -> None:
    """R585-META-2: a canonical repeated column does not overwrite a shared scalar."""
    # Given: one source shared by constant and variable definitions
    path = tmp_path / "metadata-def.json"
    path.write_text(json.dumps({"c": {"schema": {"type": "number"}, "originalName": "T"}, "v": {"schema": {"type": "number"}, "originalName": "T", "variable": 1}}))
    values = {"T": 3}
    repeated = {"v": [4, 5]}
    # When: the canonical variable column overrides its aliased scalar
    meta = build_meta(values, path, repeated=repeated)
    # Then: the constant and caller-owned inputs remain intact
    assert meta.custom == {"c": 3}
    assert meta.variable == [{"v": {"value": 4}}, {"v": {"value": 5}}]
    assert values == {"T": 3} and repeated == {"v": [4, 5]}
