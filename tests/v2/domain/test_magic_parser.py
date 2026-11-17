"""Versioned strict expression grammar, limits, and literal preservation."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from rdetoolkit.domain.magic_parser import (
    MAX_EXPRESSIONS,
    MAX_TEMPLATE_LENGTH,
    ExpressionToken,
    LiteralToken,
    parse_template,
)
from rdetoolkit.errors import RdeValidationError


@pytest.mark.parametrize(
    ("expression", "scope", "section", "key"),
    [
        ("filename", "filename", "", ""),
        ("invoice:basic:dataName", "invoice", "basic", "dataName"),
        ("invoice:custom:temperature", "invoice", "custom", "temperature"),
        ("invoice:sample:names", "invoice", "sample", "names"),
        ("invoice-original:basic:dataName", "invoice-original", "basic", "dataName"),
        ("invoice-current:custom:temperature", "invoice-current", "custom", "temperature"),
        ("metadata:constant:temperature", "metadata", "constant", "temperature"),
        ("metadata:constant:温度-K_2", "metadata", "constant", "温度-K_2"),
    ],
)
def test_supported_grammar__ep_001_010(expression: str, scope: str, section: str, key: str) -> None:
    """EP-001/010: Every supported source has an unambiguous parsed shape."""
    # Given: one supported expression.
    template = "${" + expression + "}"
    # When: parsing its template.
    tokens = parse_template(template)
    # Then: the exact source and location are retained.
    assert tokens == (ExpressionToken(expression, scope, section, key, 0),)


@pytest.mark.parametrize("literal", ["", "plain", "{ordinary}", "right}brace", "cost $5", "$", "$$"])
def test_plain_literal__ep_002(literal: str) -> None:
    """EP-002: Ordinary text, including braces, remains byte-equivalent."""
    # Given: text without an expression opener.
    # When: parsing the text.
    tokens = parse_template(literal)
    # Then: only the original literal is returned.
    assert tokens == ((LiteralToken(literal),) if literal else ())


@pytest.mark.parametrize("body", ["filename", "unknown:x", "", "invoice:basic:dataName"])
def test_escape_is_literal__ep_003_bv_004(body: str) -> None:
    """EP-003/BV-004: An escaped opener suppresses expression evaluation."""
    # Given: a complete escaped placeholder.
    # When: parsing it.
    tokens = parse_template("prefix_$${" + body + "}")
    # Then: the dollar escape is removed and the expression remains literal.
    assert tokens == (LiteralToken("prefix_${" + body + "}"),)


def test_outer_whitespace__ep_004() -> None:
    """EP-004: Outer whitespace is ignored without changing key semantics."""
    # Given: a supported expression padded with whitespace.
    # When: parsing it.
    tokens = parse_template("${ \tfilename\n}")
    # Then: the normalized expression is retained.
    assert tokens == (ExpressionToken("filename", "filename", "", "", 0),)


@pytest.mark.parametrize(
    "template",
    [
        "${}", "${ }", "${", "${filename", "${{filename}", "${filename${filename}}",
        "$${filename", "${filename:extra}", "${filename:}", "${filename::}",
        "${unknown}", "${invoice}", "${invoice:basic}", "${invoice::key}",
        "${invoice:basic:}", "${invoice:basic:dataName:extra}", "${invoice:other:key}",
        "${invoice:sample:id}", "${invoice:sample:names:extra}",
        "${invoice-original:basic}", "${invoice-current:sample:ids}",
        "${metadata}", "${metadata:constant}", "${metadata:variable:key}",
        "${metadata:constant:}", "${metadata:constant:key:extra}",
        "${metadata:constant:a.b}", "${metadata:constant:a/b}", "${metadata:constant:a\\b}",
        "${metadata:constant:a[0]}", "${metadata:constant:a b}",
        "${metadata:constant:a\tb}", "${metadata:constant:a$b}",
        "${filename }${invalid}", "${invoice :basic:dataName}",
    ],
)
def test_invalid_grammar__ep_005_006_007(template: str) -> None:
    """EP-005/006/007: Unsupported syntax fails with a catalogued code."""
    # Given: an invalid expression after a harmless literal prefix.
    # When: parsing the template.
    with pytest.raises(RdeValidationError) as caught:
        parse_template("safe_" + template)
    # Then: the error identifies the grammar boundary and remediation.
    assert caught.value.code == 4009
    assert "offset" in str(caught.value)
    assert "Remediation:" in str(caught.value)


def test_error_does_not_expose_template__ep_008() -> None:
    """EP-008: Diagnostics exclude incidental private literal and expression text."""
    # Given: a template containing private text and an invalid key.
    template = "private-experiment_${metadata:constant:secret/key}"
    # When: parsing the malformed expression.
    with pytest.raises(RdeValidationError) as caught:
        parse_template(template)
    # Then: location is available without leaking either value.
    assert caught.value.code == 4009
    assert "offset 19" in str(caught.value)
    assert "private-experiment" not in str(caught.value)
    assert "secret/key" not in str(caught.value)


def test_mixed_tokens_and_offsets__ep_009_bv_003() -> None:
    """EP-009/BV-003: Adjacent expressions remain distinct with source offsets."""
    # Given: a mixture of literals, adjacent expressions, and an escape.
    template = "x${filename}${invoice:sample:names}_$${filename}"
    # When: parsing the whole template.
    tokens = parse_template(template)
    # Then: token boundaries preserve exact expression positions.
    assert tokens == (
        LiteralToken("x"),
        ExpressionToken("filename", "filename", "", "", 1),
        ExpressionToken("invoice:sample:names", "invoice", "sample", "names", 12),
        LiteralToken("_${filename}"),
    )


def test_template_length_at_limit__bv_001() -> None:
    """BV-001: The exact declared template length is supported."""
    # Given: a literal of the maximum allowed length.
    template = "x" * MAX_TEMPLATE_LENGTH
    # When: parsing it.
    tokens = parse_template(template)
    # Then: no truncation occurs.
    assert tokens == (LiteralToken(template),)


def test_template_length_over_limit__bv_001() -> None:
    """BV-001: One character above the template limit is rejected."""
    # Given: a template beyond the supported bound.
    # When: parsing it.
    with pytest.raises(RdeValidationError) as caught:
        parse_template("x" * (MAX_TEMPLATE_LENGTH + 1))
    # Then: a catalogued length diagnostic is raised.
    assert caught.value.code == 4009
    assert "length" in str(caught.value)


def test_expression_count_at_limit__bv_002() -> None:
    """BV-002: The exact declared expression count is supported."""
    # Given: the maximum number of adjacent expressions.
    template = "${filename}" * MAX_EXPRESSIONS
    # When: parsing it.
    tokens = parse_template(template)
    # Then: every expression remains represented.
    assert len(tokens) == MAX_EXPRESSIONS
    assert all(isinstance(token, ExpressionToken) for token in tokens)


def test_expression_count_over_limit__bv_002() -> None:
    """BV-002: One expression above the supported count is rejected."""
    # Given: a template beyond the supported expression count.
    # When: parsing it.
    with pytest.raises(RdeValidationError) as caught:
        parse_template("${filename}" * (MAX_EXPRESSIONS + 1))
    # Then: the bound is enforced with a catalogued error.
    assert caught.value.code == 4009
    assert "count" in str(caught.value)


@pytest.mark.property
@given(st.text(alphabet=st.characters(blacklist_characters="$", blacklist_categories=("Cs",)), max_size=300))
def test_literal_roundtrip__pbt_001(literal: str) -> None:
    """PBT-001: Arbitrary ordinary Unicode text survives parsing exactly."""
    # Given: arbitrary literal Unicode text without interpolation openers.
    # When: parsing the text.
    tokens = parse_template(literal)
    # Then: concatenating literals recovers the original input.
    assert all(isinstance(token, LiteralToken) for token in tokens)
    assert "".join(token.text for token in tokens if isinstance(token, LiteralToken)) == literal


@pytest.mark.property
@given(st.lists(st.sampled_from(["${filename}", "${invoice:sample:names}", "$${unknown}", "_"]), max_size=80))
def test_parse_is_deterministic__pbt_002(parts: list[str]) -> None:
    """PBT-002: Repeated parsing produces the same immutable token sequence."""
    # Given: a composed supported template with escaped literals.
    template = "".join(parts)
    # When: independently parsing it twice.
    first = parse_template(template)
    second = parse_template(template)
    # Then: token values and positions are stable.
    assert first == second
    assert hash(first) == hash(second)
