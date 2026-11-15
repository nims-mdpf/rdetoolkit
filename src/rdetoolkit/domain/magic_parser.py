"""Bounded, non-executable expression grammar for v2 invoice interpolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn, TypeGuard

from rdetoolkit.errors import ERROR_CATALOG, RdeValidationError

MAX_TEMPLATE_LENGTH = 16_384
MAX_EXPRESSIONS = 128

_INVOICE_SECTIONS = frozenset({"basic", "custom", "sample"})
_SECTIONS_BY_SCOPE = {
    "invoice": _INVOICE_SECTIONS,
    "invoice-original": _INVOICE_SECTIONS,
    "invoice-current": _INVOICE_SECTIONS,
    "metadata": frozenset({"constant"}),
}
_SCOPED_SEGMENT_COUNT = 3


class MagicExpressionError(RdeValidationError):
    """Catalogued expression error retaining its character offset.

    Attributes:
        offset: Zero-based position of the invalid expression opener.
        reason: Value-free grammar violation, without repeated remediation.
    """

    def __init__(self, reason: str, offset: int) -> None:
        """Create an error without retaining private template text.

        Args:
            reason: Value-free explanation of the grammar violation.
            offset: Character offset in the original template.
        """
        definition = ERROR_CATALOG[4005]
        super().__init__(code=4005, name=definition.name, message=f"{reason} at offset {offset}. Remediation: {definition.remediation}")
        self.offset = offset
        self.reason = reason


@dataclass(frozen=True, slots=True)
class LiteralToken:
    """Literal template text after removing dollar escapes.

    Attributes:
        text: Text copied verbatim into the resolved field.
    """

    text: str


@dataclass(frozen=True, slots=True)
class ExpressionToken:
    """A validated direct source reference and its template position.

    Attributes:
        expression: Expression text with outer whitespace removed.
        scope: Original/current invoice, metadata, or filename source.
        section: Direct source section, empty for filename.
        key: Direct source key, empty for filename.
        offset: Zero-based character offset of the expression opener.
    """

    expression: str
    scope: str
    section: str
    key: str
    offset: int


def contains_expression(value: object) -> TypeGuard[str]:
    """Identify string fields that opt into the interpolation contract.

    Args:
        value: Invoice field to inspect without parsing ordinary text.

    Returns:
        True for strings containing an expression or escaped opener.
    """
    return isinstance(value, str) and "${" in value


def parse_template(template: str) -> tuple[LiteralToken | ExpressionToken, ...]:
    """Parse a bounded v2 template without resolving or executing references.

    ``$${...}`` represents a literal ``${...}``. Ordinary braces outside an
    expression remain literal. Only surrounding expression whitespace is
    ignored; source names and keys never undergo normalization or traversal.

    Args:
        template: Field text containing supported interpolation expressions.

    Returns:
        Immutable literal and expression tokens in their original order.

    Raises:
        RdeValidationError: Code 4005 for unsupported syntax or exceeded bounds.
    """
    if len(template) > MAX_TEMPLATE_LENGTH:
        _invalid("Template length exceeds the supported limit", 0)
    tokens: list[LiteralToken | ExpressionToken] = []
    literal: list[str] = []
    cursor = 0
    expression_count = 0
    while cursor < len(template):
        opening = template.find("${", cursor)
        if opening == -1:
            literal.append(template[cursor:])
            break
        closing = _closing_offset(template, opening)
        if opening > cursor and template[opening - 1] == "$":
            literal.extend((template[cursor : opening - 1], template[opening : closing + 1]))
        else:
            literal.append(template[cursor:opening])
            _append_literal(tokens, literal)
            expression_count += 1
            _check_expression_count(expression_count, opening)
            tokens.append(_parse_expression(template[opening + 2 : closing], opening))
        cursor = closing + 1
    _append_literal(tokens, literal)
    return tuple(tokens)


def _closing_offset(template: str, opening: int) -> int:
    closing = template.find("}", opening + 2)
    if closing == -1:
        _invalid("Expression has no closing brace", opening)
    return closing


def _append_literal(tokens: list[LiteralToken | ExpressionToken], literal: list[str]) -> None:
    text = "".join(literal)
    if text:
        tokens.append(LiteralToken(text))
    literal.clear()


def _check_expression_count(count: int, offset: int) -> None:
    if count > MAX_EXPRESSIONS:
        _invalid("Expression count exceeds the supported limit", offset)


def _parse_expression(body: str, offset: int) -> ExpressionToken:
    expression = body.strip()
    if expression == "filename":
        return ExpressionToken(expression, "filename", "", "", offset)
    segments = expression.split(":")
    if len(segments) != _SCOPED_SEGMENT_COUNT:
        _invalid("Expression requires an exact supported source, section, and key", offset)
    scope, section, key = segments
    if section not in _SECTIONS_BY_SCOPE.get(scope, frozenset()):
        _invalid("Expression source or section is unsupported", offset)
    _validate_key(key, section, offset)
    return ExpressionToken(expression, scope, section, key, offset)


def _validate_key(key: str, section: str, offset: int) -> None:
    if not key or not all(character.isalnum() or character in "_-" for character in key):
        _invalid("Expression key must be a direct name without whitespace or traversal syntax", offset)
    if section == "sample" and key != "names":
        _invalid("Only sample names are supported", offset)


def _invalid(reason: str, offset: int) -> NoReturn:
    raise MagicExpressionError(reason, offset)
