"""Read-only magic resolution preview in ``run --explain`` (#727).

EP/BV: statuses per mode and policy; redaction of source values; structured
diagnostics for missing sources; deferred metadata and row-built invoices;
whole-tree immutability; schema conformance of every payload.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from rdetoolkit.runner.preview import preview_registration
from tests.v2.contract.fixtures import _generate

SECRET = "SENSITIVE-VALUE-7f3a"


def _schema() -> dict[str, Any]:
    return json.loads((Path(__file__).parents[3] / "src/rdetoolkit/static/registration-explain.schema.json").read_text())


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _project(root: Path, mode: str, *, name: str | None = None, invoice: dict[str, Any] | None = None, policy: str | None = None) -> None:
    _generate.materialize_case(_generate.oracle_case(f"v1/{mode}/ok"), root)
    path = root / "data" / "invoice" / "invoice.json"
    payload = json.loads(path.read_text())
    if invoice:
        for section, values in invoice.items():
            payload.setdefault(section, {}).update(values)
    if name is not None:
        payload.setdefault("basic", {})["dataName"] = name
    path.write_text(json.dumps(payload))
    if mode == "invoice":
        schema_path = root / "data" / "tasksupport" / "invoice.schema.json"
        extra = [key for key in ("custom", "sample") if key in payload]
        properties = {"custom": {"type": "object", "label": {"ja": "c", "en": "c"}, "required": [], "properties": {"batch": {"type": "string", "label": {"ja": "b", "en": "b"}}}}}
        schema_path.write_text(json.dumps({"required": extra, "properties": {key: properties.get(key, {"type": "object", "label": {"ja": "s", "en": "s"}, "properties": {}}) for key in extra}}))
    lines = ["system:", f"  extended_mode: {mode}"] if mode != "invoice" else []
    if policy is not None:
        lines = lines or ["system:"]
        lines += [f"  magic_variable: {'true' if policy != 'disabled' else 'false'}"]
    if lines:
        (root / "rdeconfig.yaml").write_text("\n".join(lines) + "\n")


def _explain(root: Path) -> dict[str, Any]:
    payload = preview_registration(root).to_dict()
    jsonschema.validate(json.loads(json.dumps(payload)), _schema())
    return payload["magic_preview"]  # type: ignore[no-any-return]


def test_resolved_template_previewed_without_values__magic_p1(tmp_path: Path) -> None:
    # Given: a dataName template over a sensitive invoice custom value.
    _project(tmp_path, "invoice", name="${invoice:custom:batch}", invoice={"custom": {"batch": SECRET}})
    before = _snapshot(tmp_path)
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: one previewed tile, resolved diagnostic, value absent from the whole output.
    assert (preview["status"], preview["reason"]) == ("previewed", "pre_flow_snapshot")
    assert preview["checks"] == ["syntax", "source_resolution", "normalization", "output_limits"]
    assert preview["not_checked"] == ["invoice_schema", "invoice_standard_checks", "flow_side_effects"]
    (tile,) = preview["tiles"]
    assert (tile["index"], tile["status"], tile["reason"]) == (0, "previewed", "pre_flow_snapshot")
    assert [d["status"] for d in tile["diagnostics"]] == ["resolved"]
    assert SECRET not in json.dumps(preview_registration(tmp_path).to_dict())
    assert before == _snapshot(tmp_path)


def test_sensitive_sample_and_filename_never_emitted__magic_p2(tmp_path: Path) -> None:
    # Given: sample and filename sources feeding the templates.
    _project(tmp_path, "invoice", name="${invoice:sample:names}_${filename}", invoice={"sample": {"sampleId": "", "names": [SECRET], "ownerId": "0" * 56}})
    (tmp_path / "data" / "inputdata" / "invoice_input.txt").rename(tmp_path / "data" / "inputdata" / f"{SECRET}.txt")
    # When: explaining.
    payload = preview_registration(tmp_path).to_dict()
    # Then: neither the value nor raw filename appears in the diagnostics.
    magic = json.dumps(payload["magic_preview"])
    assert SECRET not in magic
    assert [d["status"] for d in payload["magic_preview"]["tiles"][0]["diagnostics"]] == ["resolved", "resolved"]


def test_missing_source_is_structured_unavailable__magic_p3(tmp_path: Path) -> None:
    # Given: a template naming an invoice key that does not exist.
    _project(tmp_path, "invoice", name="${invoice:custom:absent}")
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: unavailable, catalogued code 4010, destination and remedy present.
    (diagnostic,) = preview["tiles"][0]["diagnostics"]
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["code"] == 4010
    assert diagnostic["destination"] == "basic.dataName"
    assert diagnostic["remediation"]


def test_metadata_tokens_are_deferred__magic_p4(tmp_path: Path) -> None:
    # Given: a metadata expression, whose metadata the flow will produce.
    _project(tmp_path, "invoice", name="${metadata:constant:thickness}")
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: deferred without an error code.
    (diagnostic,) = preview["tiles"][0]["diagnostics"]
    assert (diagnostic["status"], diagnostic["reason"], diagnostic["code"]) == ("deferred", "deferred_source", None)


def test_no_rawfile_filename_is_unavailable__magic_p5(tmp_path: Path) -> None:
    # Given: invoice mode without any input file and a filename template.
    _project(tmp_path, "invoice", name="${filename}")
    (tmp_path / "data" / "inputdata" / "invoice_input.txt").unlink()
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: the filename expression is unavailable because it is not unique.
    (diagnostic,) = preview["tiles"][0]["diagnostics"]
    assert (diagnostic["status"], diagnostic["reason"]) == ("unavailable", "filename_not_unique")


def test_multidatatile_tiles_use_their_own_file__magic_p6(tmp_path: Path) -> None:
    # Given: a MultiDataTile project with a filename template.
    _project(tmp_path, "multidatatile", name="${filename}")
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: each tile is previewed against its own single input.
    assert preview["tiles"]
    assert all(tile["status"] == "previewed" for tile in preview["tiles"])
    assert all([d["status"] for d in tile["diagnostics"]] == ["resolved"] for tile in preview["tiles"])


def test_disabled_policy__magic_p7(tmp_path: Path) -> None:
    # Given: magic variables disabled in configuration.
    _project(tmp_path, "invoice", name="${invoice:basic:dataOwnerId}", policy="disabled")
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: disabled at the top, with the per-field disabled diagnostic kept.
    assert (preview["status"], preview["reason"]) == ("disabled", "policy_disabled")
    assert [d["status"] for d in preview["tiles"][0]["diagnostics"]] == ["disabled"]


def test_no_templates__magic_p8(tmp_path: Path) -> None:
    # Given: a plain dataName.
    _project(tmp_path, "invoice", name="plain")
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: nothing to preview and no diagnostics.
    assert (preview["status"], preview["reason"]) == ("no_templates", "no_eligible_templates")
    assert all(tile["diagnostics"] == [] for tile in preview["tiles"])


def test_rdeformat_not_applicable__magic_p9(tmp_path: Path) -> None:
    # Given: RDEFormat, whose lifecycle has no magic stage.
    _project(tmp_path, "rdeformat")
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: not applicable with no tiles.
    assert (preview["status"], preview["reason"], preview["tiles"]) == ("not_applicable", "mode_has_no_magic_stage", [])


@pytest.mark.parametrize("mode", ["smarttable", "excelinvoice"])
def test_row_built_tiles_are_deferred__magic_p10(tmp_path: Path, mode: str) -> None:
    # Given: a table mode with a template in the base invoice.
    _project(tmp_path, mode, name="${invoice:basic:dataOwnerId}")
    # When: explaining.
    preview = _explain(tmp_path)
    # Then: row tiles are deferred without diagnostics; no tile claims a previewed row invoice.
    statuses = {(tile["status"], tile["reason"]) for tile in preview["tiles"]}
    assert ("deferred", "row_invoice_built_at_runtime") in statuses
    assert all(tile["diagnostics"] == [] for tile in preview["tiles"] if tile["status"] != "previewed")
    assert statuses <= {("deferred", "row_invoice_built_at_runtime"), ("skipped", "precompleted_tile")}


@pytest.mark.parametrize("mode", ["invoice", "multidatatile", "smarttable", "excelinvoice", "rdeformat"])
def test_explain_never_mutates_tree__magic_p11(tmp_path: Path, mode: str) -> None:
    # Given: each mode with a template and a sensitive value.
    _project(tmp_path, mode, name="${invoice:basic:description}_${metadata:constant:x}", invoice={"basic": {"description": SECRET}})
    before = _snapshot(tmp_path)
    # When: explaining twice.
    first = preview_registration(tmp_path).to_dict()
    second = preview_registration(tmp_path).to_dict()
    # Then: deterministic, schema valid, redacted, and no byte of the tree changed.
    assert first == second
    jsonschema.validate(json.loads(json.dumps(first)), _schema())
    assert SECRET not in json.dumps(first)
    assert before == _snapshot(tmp_path)

