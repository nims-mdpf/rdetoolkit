"""Versioned strict magic resolution contracts; tables in local/develop/v2/magic704."""

from __future__ import annotations

from pathlib import Path
from dataclasses import FrozenInstanceError
import json
from typing import Any

import pytest

from hypothesis import given, strategies as st

from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, preview_invoice, resolve_invoice
from rdetoolkit.errors import RdeValidationError


def _context(template: str, *, rawfiles: tuple[Path, ...] = (), value: Any = "tile") -> ResolutionContext:
    return ResolutionContext.from_sources(
        original_invoice={"basic": {"dataOwnerId": value}},
        current_invoice={"basic": {"dataName": template}},
        metadata={"constant": {"name": {"value": value}}},
        rawfiles=rawfiles,
    )


@pytest.mark.parametrize("rawfiles", [(), (Path("one.csv"),), (Path("one.csv"), Path("two.csv"))])
@pytest.mark.parametrize("template", ["${invoice:basic:dataOwnerId}", "${metadata:constant:name}"])
def test_sources_without_filename(rawfiles: tuple[Path, ...], template: str) -> None:
    # Given: independent invoice/metadata sources and any rawfile count
    context = _context(template, rawfiles=rawfiles)
    # When: resolving without requesting filename
    result = resolve_invoice(context)
    # Then: rawfiles never gate the result
    assert result["basic"]["dataName"] == "tile"


@pytest.mark.parametrize("rawfiles", [(), (Path("one.csv"), Path("two.csv"))])
def test_unavailable_filename(rawfiles: tuple[Path, ...]) -> None:
    # Given: a filename reference with no unique file
    context = _context("${filename}", rawfiles=rawfiles)
    # When: strict resolution requests that source
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: a targeted catalogued source error is raised
    assert caught.value.code == 4006


def test_unique_filename() -> None:
    # Given: exactly one selected input
    context = _context("${filename}", rawfiles=(Path("directory/file.csv"),))
    # When: resolving the filename
    result = resolve_invoice(context, options=MagicOptions())
    # Then: only its basename is used
    assert result["basic"]["dataName"] == "file.csv"


def test_immutable_scopes() -> None:
    # Given: mutable original/current sources and a nested metadata entry
    original = {"basic": {"dataOwnerId": "original"}}
    current = {"basic": {"dataName": "${invoice:basic:dataOwnerId}_${invoice-current:basic:dataOwnerId}", "dataOwnerId": "current"}}
    metadata = {"constant": {"name": {"value": "before"}}}
    context = ResolutionContext.from_sources(original_invoice=original, current_invoice=current, metadata=metadata)
    original["basic"]["dataOwnerId"] = "changed"
    current["basic"]["dataOwnerId"] = "changed"
    metadata["constant"]["name"]["value"] = "changed"
    # When: resolving snapshots after the source mappings change
    result = resolve_invoice(context)
    result["basic"]["dataOwnerId"] = "output mutation"
    # Then: neither earlier changes nor returned mapping changes reach snapshots
    assert result["basic"]["dataName"] == "original_current"
    assert context.current_invoice["basic"]["dataOwnerId"] == "current"
    assert context.metadata == {"constant": {"name": {"value": "before"}}}
    with pytest.raises(FrozenInstanceError):
        context.iteration_index = 42  # type: ignore[misc]


@pytest.mark.parametrize("value", [None, "", []])
@pytest.mark.parametrize("template", ["pre_${invoice:basic:dataOwnerId}_post", "pre_${metadata:constant:name}_post"])
def test_missing_states(value: Any, template: str) -> None:
    # Given: null, empty string, or empty list in an otherwise present source
    context = _context(template, value=value)
    # When: strict interpolation requests the value
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: strict mode errors and the explicit omit policy is stable
    assert caught.value.code == 4006
    assert resolve_invoice(context, options=MagicOptions(missing="omit"))["basic"]["dataName"] == "pre_post"


@pytest.mark.parametrize("original", [{}, {"basic": {}}, {"basic": None}])
def test_absent_invoice_source(original: dict[str, Any]) -> None:
    # Given: a section/key unavailable in the original invoice
    context = ResolutionContext.from_sources(original_invoice=original, current_invoice={"basic": {"dataName": "pre_${invoice:basic:absent}_post"}})
    # When: the source is requested under strict policy
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: source absence is catalogued and omit is available explicitly
    assert caught.value.code == 4006
    assert resolve_invoice(context, options=MagicOptions(missing="omit"))["basic"]["dataName"] == "pre_post"


@pytest.mark.parametrize("metadata", [None, {}, {"constant": {}}, {"constant": {"name": {}}}])
def test_absent_metadata_source(metadata: dict[str, Any] | None) -> None:
    # Given: a missing metadata source, section, entry or value
    context = ResolutionContext.from_sources(original_invoice={}, current_invoice={"basic": {"dataName": "${metadata:constant:name}"}}, metadata=metadata)
    # When: strict interpolation requests metadata
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: missing data never silently vanishes
    assert caught.value.code == 4006


@pytest.mark.parametrize("value", [0, False, "e\u0301", "a/b\\c", "日本語", 1.25])
def test_scalar_values(value: Any) -> None:
    # Given: a scientific identifier or false/zero scalar
    context = _context("${invoice:basic:dataOwnerId}", value=value)
    # When: interpolation formats a scalar
    result = resolve_invoice(context)
    # Then: Unicode code points and path-looking labels are preserved
    assert result["basic"]["dataName"] == str(value)


@pytest.mark.parametrize("value", [{"nested": "secret"}, ["nonempty"], float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("missing", ["error", "omit"])
def test_invalid_source_types(value: Any, missing: str) -> None:
    # Given: a non-scalar or non-finite source
    context = _context("${invoice:basic:dataOwnerId}", value=value)
    # When: either missing policy resolves the invalid type
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context, options=MagicOptions(missing=missing))  # type: ignore[arg-type]
    # Then: omit cannot hide malformed source types
    assert caught.value.code == 4006


@pytest.mark.parametrize("sample", [{}, {"names": None}, {"names": "not-list"}, {"names": ["good", 3]}, {"names": [None]}])
def test_invalid_sample_names(sample: dict[str, Any]) -> None:
    # Given: missing or wrongly typed sample names
    context = ResolutionContext.from_sources(original_invoice={"sample": sample}, current_invoice={"basic": {"dataName": "${invoice:sample:names}"}})
    # When: names are requested
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: samples require an explicit list of strings
    assert caught.value.code == 4006


@pytest.mark.parametrize("names", [[], ["", ""]])
def test_empty_sample_names(names: list[str]) -> None:
    # Given: an empty list or a list containing only empty strings
    context = ResolutionContext.from_sources(original_invoice={"sample": {"names": names}}, current_invoice={"basic": {"dataName": "a_${invoice:sample:names}_b"}})
    # When: strict mode requests sample names
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: the missing policy also applies to empty sample lists
    assert caught.value.code == 4006
    assert resolve_invoice(context, options=MagicOptions(missing="omit"))["basic"]["dataName"] == "a_b"


def test_sample_names_join_in_order() -> None:
    # Given: sample names including an empty optional entry
    context = ResolutionContext.from_sources(original_invoice={"sample": {"names": ["β", "", "alpha"]}}, current_invoice={"basic": {"dataName": "${invoice-original:sample:names}"}})
    # When: resolving the explicit original scope
    result = resolve_invoice(context)
    # Then: nonempty names retain order and join with an underscore
    assert result["basic"]["dataName"] == "β_alpha"


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("a_${invoice:basic:dataOwnerId}_b", "a_b"),
        ("a_${invoice:basic:dataOwnerId}${invoice:basic:dataOwnerId}_b", "a_b"),
        ("a__${invoice:basic:dataOwnerId}__b", "a_b"),
        ("a__b_${invoice:basic:dataOwnerId}_c", "a__b_c"),
        ("${invoice:basic:dataOwnerId}_b", "_b"),
        ("a_${invoice:basic:dataOwnerId}", "a_"),
    ],
)
def test_omit_separators(template: str, expected: str) -> None:
    # Given: an omitted value surrounded by literal underscores
    context = _context(template, value=None)
    # When: explicitly selecting omission
    result = resolve_invoice(context, options=MagicOptions(missing="omit"))
    # Then: only the join straddling the omission collapses
    assert result["basic"]["dataName"] == expected


@pytest.mark.parametrize("value", ["", "x" * 4097, "line\nbreak", "tab\there", "\x00", "\x7f", "\x85"])
def test_invalid_name_boundaries(value: str) -> None:
    # Given: an output exceeding the name limits or containing controls
    context = _context("${invoice:basic:dataOwnerId}", value=value)
    # When: resolution validates the final name
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: empty source and invalid final output are distinguished
    assert caught.value.code == (4006 if value == "" else 4007)


@pytest.mark.parametrize("size", [1, 4096])
def test_valid_name_boundaries(size: int) -> None:
    # Given: the first or last allowed name length
    context = _context("${invoice:basic:dataOwnerId}", value="x" * size)
    # When: resolving the name
    result = resolve_invoice(context)
    # Then: both inclusive limits are accepted
    assert len(result["basic"]["dataName"]) == size


@pytest.mark.parametrize("policy", ["auto", "enabled", "disabled"])
def test_policy(policy: str) -> None:
    # Given: an expression and an explicit v2 policy
    context = _context("${invoice:basic:dataOwnerId}")
    # When: resolving that policy
    result = resolve_invoice(context, options=MagicOptions(policy=policy))  # type: ignore[arg-type]
    # Then: only explicit disabling keeps the literal expression
    assert result["basic"]["dataName"] == ("${invoice:basic:dataOwnerId}" if policy == "disabled" else "tile")


@pytest.mark.parametrize("options", [{"policy": "typo"}, {"policy": True}, {"missing": "typo"}, {"missing": None}])
def test_invalid_policy(options: dict[str, Any]) -> None:
    # Given: malformed typed options at the public boundary
    # When: constructing options
    with pytest.raises(RdeValidationError) as caught:
        MagicOptions(**options)
    # Then: an actionable catalogued policy error is returned
    assert caught.value.code == 4005


@pytest.mark.parametrize("template", ["${}", "${filename:extra}", "${unsupported}", "${"])
def test_malformed_templates(template: str) -> None:
    # Given: a malformed expression in an eligible field
    context = _context(template)
    # When: auto mode sees template syntax
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: it cannot survive silently as an output name
    assert caught.value.code == 4005


def test_fields() -> None:
    # Given: eligible and forbidden string, scalar and nested fields
    current = {"basic": {"dataName": "${invoice:basic:dataOwnerId}", "description": "label ${invoice:basic:dataOwnerId}", "dataOwnerId": "${filename}"}, "custom": {"text": "${filename}", "list": ["${filename}"], "number": 0}}
    context = ResolutionContext.from_sources(original_invoice={"basic": {"dataOwnerId": "owner"}}, current_invoice=current)
    # When: interpolating invoice fields
    result = resolve_invoice(context)
    # Then: only the explicit string allowlist changes
    assert result["basic"]["dataName"] == "owner"
    assert result["basic"]["description"] == "label owner"
    assert result["basic"]["dataOwnerId"] == "${filename}"
    assert result["custom"] == current["custom"]
    assert current["basic"]["dataName"] == "${invoice:basic:dataOwnerId}"


@pytest.mark.parametrize("value", [17, ["${filename}"], {"text": "${filename}"}, None])
def test_non_string_allowlisted_values_unchanged(value: Any) -> None:
    # Given: a non-string value in an allowlisted field
    context = ResolutionContext.from_sources(original_invoice={}, current_invoice={"basic": {"dataName": "plain", "description": value}})
    # When: resolving strings only
    result = resolve_invoice(context)
    # Then: lists, objects and scalars are never stringified
    assert result["basic"]["description"] == value


def test_schema_failure() -> None:
    # Given: a source value incompatible with the destination schema
    context = _context("${invoice:basic:dataOwnerId}", value="secret-output")
    schema = {"type": "object", "properties": {"basic": {"type": "object", "properties": {"dataName": {"const": "approved"}}}}}
    # When: validating the interpolated candidate
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context, schema=schema)
    # Then: the field is identified without values and the context stays unchanged
    assert caught.value.code == 4007
    assert "basic.dataName" in str(caught.value)
    assert "secret-output" not in str(caught.value)
    assert context.current_invoice["basic"]["dataName"] == "${invoice:basic:dataOwnerId}"


@pytest.mark.parametrize("keyword", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_external_schema_references(keyword: str, tmp_path: Path) -> None:
    # Given: a schema reference naming a file that must never be opened
    secret = tmp_path / "secret.json"
    secret.write_text('{"const": "private-file-value"}', encoding="utf-8")
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", keyword: secret.as_uri()}
    context = _context("${invoice:basic:dataOwnerId}")
    # When: preview and resolution encounter the external reference
    preview = preview_invoice(context, schema=schema)
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context, schema=schema)
    # Then: they return an ordinary catalogued error without retrieving the file
    assert caught.value.code == 4007
    assert preview.diagnostics[-1].reason == "external_schema_reference"
    assert "private-file-value" not in json.dumps(preview.to_dict())


@pytest.mark.parametrize("schema", [{"$ref": "#/$defs/absent"}, {"type": "unrecognised"}, {"$ref": "#"}])
def test_invalid_or_unresolved_schema(schema: dict[str, Any]) -> None:
    # Given: an invalid schema or a local reference without a definition
    context = _context("${invoice:basic:dataOwnerId}")
    # When: preview and resolution inspect the schema
    preview = preview_invoice(context, schema=schema)
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context, schema=schema)
    # Then: jsonschema internals never escape the domain boundary
    assert caught.value.code == 4007
    assert preview.diagnostics[-1].code == 4007


def test_plain_fields_are_not_interpolated() -> None:
    # Given: an ordinary label outside interpolation policy limits
    context = _context("plain\nlabel")
    # When: auto mode detects no expression syntax
    result = resolve_invoice(context)
    # Then: ordinary invoice validation remains the Runner's responsibility
    assert result["basic"]["dataName"] == "plain\nlabel"
    assert preview_invoice(context).diagnostics == ()


@pytest.mark.parametrize("source", [{"basic": {"secret": object()}}, {"self": None}])
def test_non_json_sources(source: dict[str, Any]) -> None:
    # Given: unsupported JSON material or a recursive mapping
    if "self" in source:
        source["self"] = source
    # When: snapshot creation validates the external source boundary
    with pytest.raises(RdeValidationError) as caught:
        ResolutionContext.from_sources(original_invoice=source, current_invoice={})
    # Then: the error is catalogued without exposing the source value
    assert caught.value.code == 4006


def test_oversized_description_and_missing_basic() -> None:
    # Given: an interpolated description exceeding its explicit output budget
    context = ResolutionContext.from_sources(original_invoice={"custom": {"text": "x" * 16385}}, current_invoice={"basic": {"dataName": "plain", "description": "${invoice:custom:text}"}})
    # When: rendering the bounded description
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: the candidate fails without requiring a dataName expression
    assert caught.value.code == 4007
    empty_context = ResolutionContext.from_sources(original_invoice={}, current_invoice={})
    assert resolve_invoice(empty_context) == {}


def test_preview(tmp_path: Path) -> None:
    # Given: private source material and an otherwise empty filesystem
    context = _context("literal-secret_${invoice:basic:dataOwnerId}", value="private-value")
    before = list(tmp_path.rglob("*"))
    # When: producing a preview repeatedly
    preview = preview_invoice(context)
    encoded = json.dumps(preview.to_dict(), sort_keys=True)
    # Then: it is deterministic, redacted and writes nothing
    assert encoded == json.dumps(preview_invoice(context).to_dict(), sort_keys=True)
    assert preview.schema_version == "1"
    assert preview.diagnostics[0].status == "resolved"
    assert "private-value" not in encoded + repr(preview) + repr(context)
    assert "literal-secret" not in encoded + repr(preview)
    assert list(tmp_path.rglob("*")) == before


@pytest.mark.parametrize(("template", "policy", "status", "code"), [("${filename}", "auto", "unavailable", 4006), ("${}", "auto", "invalid", 4005), ("${filename}", "disabled", "disabled", None), ("${}", "disabled", "disabled", None)])
def test_preview_failure_and_disabled(template: str, policy: str, status: str, code: int | None) -> None:
    # Given: a missing source, invalid expression or explicit disable
    context = _context(template)
    # When: inspecting the outcome without committing a candidate
    preview = preview_invoice(context, options=MagicOptions(policy=policy))  # type: ignore[arg-type]
    # Then: diagnostics identify the field, source status and catalogued code
    diagnostic = preview.diagnostics[0]
    assert diagnostic.destination == "basic.dataName"
    assert diagnostic.status == status
    assert diagnostic.code == code
    assert diagnostic.iteration_index == 0


def test_rdeformat_not_applicable() -> None:
    # Given: a mode that does not have an interpolation stage
    context = ResolutionContext.from_sources(original_invoice={}, current_invoice={"basic": {"dataName": "${filename}"}}, mode="rdeformat")
    # When: previewing or resolving that stage
    preview = preview_invoice(context)
    # Then: omission is explicit and the candidate is unchanged
    assert preview.diagnostics[0].status == "not_applicable"
    assert resolve_invoice(context)["basic"]["dataName"] == "${filename}"


@pytest.mark.property
@given(st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")), min_size=1, max_size=128).filter(lambda value: "${" not in value))
def test_resolution_property(value: str) -> None:
    # Given: arbitrary scientific scalar text
    context = _context("${invoice:basic:dataOwnerId}", value=value)
    # When: the same immutable context is resolved repeatedly
    first = resolve_invoice(context)
    second = resolve_invoice(context)
    # Then: the result is deterministic and source text is never reinterpreted
    assert first == second
    assert first["basic"]["dataName"] == value
