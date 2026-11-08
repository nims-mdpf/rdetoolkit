"""GA575 EP/BV: definition-driven metadata uses only the public v2 API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from rdetoolkit import flow, workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes import save_meta
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import InputPaths, OutputContext
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


def _definition(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "metadata-def.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_definition_cast_filter_and_order__ga575_ep_1_2(tmp_path: Path) -> None:
    """GA575-EP-1/2: definition order, aliases, types and referenced units match v1."""
    from rdetoolkit.nodes import build_meta

    # Given: deliberately reordered values, absent fields and a raw unit source
    definition = _definition(tmp_path, {
        "temperature": {"schema": {"type": "number"}, "unit": "$TemperatureUnit", "originalName": "T"},
        "enabled": {"schema": {"type": "boolean"}},
        "date": {"schema": {"type": "string", "format": "date"}},
        "missing": {"schema": {"type": "number"}},
    })
    values = {"unknown": 99, "missing": None, "date": "2026-11-09", "enabled": "true", "T": "300", "TemperatureUnit": "K"}
    # When: building and saving with the v2 nodes
    metadata = build_meta(values, definition)
    path = save_meta(metadata, make_output_context(tmp_path / "out"))
    actual = json.loads(path.read_text(encoding="utf-8"))
    # Then: only defined values remain, with v1-equivalent types, units and order
    assert actual == {"constant": {"temperature": {"value": 300, "unit": "K"}, "enabled": {"value": True}, "date": {"value": "2026-11-09"}}, "variable": []}
    assert list(actual["constant"]) == ["temperature", "enabled", "date"]
    assert metadata.get("temperature") == 300


def test_all_variable_scalars_make_one_row__ga575_bv_1(tmp_path: Path) -> None:
    """GA575-BV-1: templates can put all scalar measurements in variable[0]."""
    from rdetoolkit.nodes import build_meta

    # Given: only variable definitions and scalar measured values
    definition = _definition(tmp_path, {"x": {"schema": {"type": "number"}, "variable": 1, "unit": "nm"}, "label": {"schema": {"type": "string"}, "variable": 1}})
    # When: building metadata without hand-written list conversion
    metadata = build_meta({"label": "sample", "x": "2.5"}, definition)
    path = save_meta(metadata, make_output_context(tmp_path / "out"))
    # Then: one complete row is written in definition order
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert actual == {"constant": {}, "variable": [{"x": {"value": 2.5, "unit": "nm"}, "label": {"value": "sample"}}]}
    assert list(actual["variable"][0]) == ["x", "label"]


@pytest.mark.parametrize("values", [{}, {"x": None}, {"x": []}])
def test_empty_variable_inputs_make_no_rows__ga575_bv_1(tmp_path: Path, values: dict[str, Any]) -> None:
    """GA575-BV-1: missing, absent and empty repeated measurements create no rows."""
    from rdetoolkit.nodes import build_meta

    # Given: one variable definition without usable values
    definition = _definition(tmp_path, {"x": {"schema": {"type": "number"}, "variable": 1}})
    # When: constructing metadata, including an explicitly empty repeated mapping
    metadata = build_meta(values, definition, repeated={})
    # Then: no value or row is invented
    assert metadata.custom == {}
    assert metadata.variable == []


def test_repeated_values_and_units__ga575_bv_2(tmp_path: Path) -> None:
    """GA575-BV-2: repeated values carry row-specific references and sparse rows."""
    from rdetoolkit.nodes import build_meta

    # Given: repeated columns with unequal lengths and units supplied by another key
    definition = _definition(tmp_path, {"x": {"schema": {"type": "number"}, "variable": 1, "unit": "$U"}, "label": {"schema": {"type": "string"}, "variable": 1}})
    # When: using the explicit repeated-values API
    metadata = build_meta({"U": ["K", "C"]}, definition, repeated={"label": ["first"], "x": ["300", "30"]})
    path = save_meta(metadata, make_output_context(tmp_path / "out"))
    # Then: no row is lost or filled with invented values
    assert json.loads(path.read_text(encoding="utf-8"))["variable"] == [{"x": {"value": 300, "unit": "K"}, "label": {"value": "first"}}, {"x": {"value": 30, "unit": "C"}}]


@pytest.mark.parametrize("definition, values", [
    ({"x": {"schema": {"type": "number"}}}, {"x": "invalid"}),
    ({"x": {"schema": {"type": "integer"}}}, {"x": "1.5"}),
    ({"x": {"schema": {"type": "boolean"}}}, {"x": "invalid"}),
    ({"x": {"schema": {"type": "string"}, "action": "1"}}, {"x": "forbidden"}),
])
def test_invalid_values_keep_error_code__ga575_neg_1(tmp_path: Path, definition: dict[str, Any], values: dict[str, Any]) -> None:
    """GA575-NEG-1: conversion and action errors retain their public error contract."""
    from rdetoolkit.nodes import build_meta

    # Given: a definition/value pair rejected by the v1 conversion rules
    path = _definition(tmp_path, definition)
    # When: using the v2 construction node
    with pytest.raises(StructuredError) as raised:
        build_meta(values, path)
    # Then: the original exception type and error code survive
    assert raised.value.ecode == 1


@pytest.mark.parametrize("content", [None, "invalid JSON"])
def test_bad_definition_is_not_ignored__ga575_neg_2(tmp_path: Path, content: str | None) -> None:
    """GA575-NEG-2: an unreadable definition cannot silently produce empty metadata."""
    from rdetoolkit.nodes import build_meta

    # Given: a missing or syntactically invalid definition file
    path = tmp_path / "metadata-def.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    # When: building metadata
    with pytest.raises(FileNotFoundError if content is None else json.JSONDecodeError):
        build_meta({"x": 1}, path)
    # Then: no output artifact has been written
    assert not (tmp_path / "metadata.json").exists()


def test_v2_native_flow_writes_equivalent_metadata__ga575_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA575-EP-3: no v1 import or adapter is needed in the flow."""
    from rdetoolkit.nodes import build_meta

    # Given: a real Runner tree and a definition carrying a unit
    _build_tree(tmp_path / "data")
    definition = tmp_path / "data" / "tasksupport" / "metadata-def.json"
    definition.write_text('{"x": {"schema": {"type": "number"}, "unit": "g"}}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline(paths: InputPaths, out: OutputContext) -> None:
        metadata = build_meta({"x": "0.1", "unknown": "discard"}, paths.tasksupport / "metadata-def.json")
        save_meta(metadata, out)

    # When: executing only the public v2 flow and node API
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: Runner validation succeeds with the v1-equivalent artifact
    assert report.status == "success", report.error
    assert json.loads((tmp_path / "data" / "meta" / "metadata.json").read_text(encoding="utf-8")) == {"constant": {"x": {"value": 0.1, "unit": "g"}}, "variable": []}


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.lists(st.integers(min_value=-10000, max_value=10000), max_size=15))
def test_repeated_conversion_preserves_length_and_order__ga575_bv_2(tmp_path: Path, numbers: list[int]) -> None:
    """GA575-BV-2 property: conversion never skips, duplicates or reorders rows."""
    from rdetoolkit.nodes import build_meta

    # Given: a variable definition and arbitrary numeric string measurements
    definition = _definition(tmp_path, {"x": {"schema": {"type": "number"}, "variable": 1, "unit": "g"}})
    # When: converting them through the public node
    metadata = build_meta({}, definition, repeated={"x": [str(value) for value in numbers]})
    # Then: the typed sequence, length and units are preserved
    assert [row["x"]["value"] for row in metadata.variable] == numbers
    assert all(row["x"]["unit"] == "g" for row in metadata.variable)
