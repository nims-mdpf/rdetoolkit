"""Pure, versioned invoice interpolation with immutable source snapshots.

Only string values in ``basic.dataName`` and ``basic.description`` are
interpolated. Other fields, including objects and arrays, remain untouched.
Source values are formatted once and never interpreted as templates.
"""

from __future__ import annotations

import json
import math
import unicodedata
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from rdetoolkit.domain.magic_parser import ExpressionToken, LiteralToken, MagicExpressionError, contains_expression, parse_template
from rdetoolkit.domain.service_errors import validation_error
from rdetoolkit.errors import ERROR_CATALOG

MAX_NAME_LENGTH = 4096
MAX_OUTPUT_LENGTH = 16_384
_FIELDS = ("dataName", "description")
_ABSENT = object()


@dataclass(frozen=True, slots=True)
class MagicOptions:
    """Version 1 interpolation and missing-value policy.

    Attributes:
        policy: Auto detects syntax; enabled resolves it; disabled preserves it.
        missing: Error rejects missing values; omit removes them explicitly.
    """

    policy: Literal["auto", "enabled", "disabled"] = "auto"
    missing: Literal["error", "omit"] = "error"

    def __post_init__(self) -> None:
        if self.policy not in ("auto", "enabled", "disabled"):
            raise validation_error(4005, "Interpolation policy must be auto, enabled, or disabled.")
        if self.missing not in ("error", "omit"):
            raise validation_error(4005, "Interpolation missing policy must be error or omit.")


_DEFAULT_OPTIONS = MagicOptions()


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    """Independent immutable JSON snapshots for one tile's interpolation.

    Construct with :meth:`from_sources`. Snapshot properties return detached
    mappings, so neither callers nor earlier tiles can modify retained data.

    Attributes:
        rawfiles: Explicit selected inputs; filename requires exactly one.
        iteration_index: Zero-based tile index used in diagnostics.
        mode: Registration mode, including RDEFormat's omitted magic stage.
        schema_version: Context contract version.
    """

    _original_json: str = field(repr=False)
    _current_json: str = field(repr=False)
    _metadata_json: str | None = field(repr=False)
    rawfiles: tuple[Path, ...] = field(default=(), repr=False)
    iteration_index: int = 0
    mode: str = "invoice"
    schema_version: str = field(default="1", init=False)

    @classmethod
    def from_sources(
        cls,
        *,
        original_invoice: Mapping[str, Any],
        current_invoice: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
        rawfiles: tuple[Path, ...] = (),
        iteration_index: int = 0,
        mode: str = "invoice",
    ) -> ResolutionContext:
        """Capture source values without retaining caller-owned containers.

        Args:
            original_invoice: Run-start invoice values.
            current_invoice: Current tile invoice immediately before expansion.
            metadata: Current tile metadata, if available.
            rawfiles: Selected raw inputs, excluding generated row tables.
            iteration_index: Zero-based tile index.
            mode: Effective registration mode.

        Returns:
            A context whose nested source values cannot be mutated.

        Raises:
            RdeValidationError: Code 4006 for non-JSON source material.
        """
        return cls(
            _snapshot(original_invoice),
            _snapshot(current_invoice),
            _snapshot(metadata) if metadata is not None else None,
            tuple(rawfiles),
            iteration_index,
            mode,
        )

    @property
    def original_invoice(self) -> dict[str, Any]:
        """Return an independent copy of the run-start invoice."""
        return cast(dict[str, Any], json.loads(self._original_json))

    @property
    def current_invoice(self) -> dict[str, Any]:
        """Return an independent copy of the current tile invoice."""
        return cast(dict[str, Any], json.loads(self._current_json))

    @property
    def metadata(self) -> dict[str, Any] | None:
        """Return an independent metadata copy, or None for an absent source."""
        return cast(dict[str, Any], json.loads(self._metadata_json)) if self._metadata_json is not None else None


@dataclass(frozen=True, slots=True)
class ResolutionDiagnostic:
    """A value-free record of one expression or destination validation.

    Attributes:
        destination: Dotted destination field.
        expression: Validated expression text, without surrounding literals.
        offset: Character offset of the expression or field-level error.
        source_scope: Explicit source kind.
        source_path: Logical source path, never the source value.
        iteration_index: Zero-based tile index.
        status: Resolution, omission, explicit disable or error outcome.
        reason: Stable reason distinguishing missing source/key/null/empty/type.
        code: Catalogued integer error code, or None for successful outcomes.
        message: Redacted explanation identifying field and source.
        remediation: A concrete correction without source data.
    """

    destination: str
    expression: str
    offset: int
    source_scope: str
    source_path: str
    iteration_index: int
    status: str
    reason: str
    code: int | None
    message: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        """Return this value-free diagnostic as JSON-compatible data."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResolutionPreview:
    """Deterministic diagnostics without an invoice candidate or data values.

    Attributes:
        diagnostics: Ordered records for expressions and field-level failures.
        schema_version: Preview contract version, independent of RunReport.
    """

    diagnostics: tuple[ResolutionDiagnostic, ...]
    schema_version: str = field(default="1", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible preview with no resolved values."""
        return {"schema_version": self.schema_version, "diagnostics": [item.to_dict() for item in self.diagnostics]}


def resolve_invoice(
    context: ResolutionContext,
    *,
    options: MagicOptions = _DEFAULT_OPTIONS,
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a complete invoice candidate without mutating any source.

    Args:
        context: Immutable run-original and current-tile source snapshots.
        options: Explicit interpolation and missing-value policies.
        schema: Optional destination invoice schema with local references only.

    Returns:
        An independent invoice mapping after all requested checks pass.

    Raises:
        RdeValidationError: 4005 for syntax, 4006 for unavailable/invalid source
            values, or 4007 for invalid destination names or schema failures.
    """
    candidate, diagnostics = _evaluate(context, options, schema)
    for diagnostic in diagnostics:
        if diagnostic.code is not None:
            error = validation_error(diagnostic.code, diagnostic.message)
            error.detail = diagnostic.to_dict()
            raise error
    return candidate


def preview_invoice(
    context: ResolutionContext,
    *,
    options: MagicOptions = _DEFAULT_OPTIONS,
    schema: Mapping[str, Any] | None = None,
) -> ResolutionPreview:
    """Inspect interpolation with the same evaluator used by actual resolution.

    This operation performs no filesystem access and exposes no invoice
    candidate, source values, or resolved values. Failed expressions become
    diagnostics instead of being raised.

    Args:
        context: Immutable source snapshots available to the preview.
        options: Explicit interpolation and missing-value policies.
        schema: Optional destination invoice schema with local references only.

    Returns:
        Ordered redacted diagnostics; preview contract version 1.
    """
    _, diagnostics = _evaluate(context, options, schema)
    return ResolutionPreview(tuple(diagnostics))


def _snapshot(source: Mapping[str, Any]) -> str:
    try:
        return json.dumps(dict(source), ensure_ascii=False)
    except (TypeError, ValueError):
        raise validation_error(4006, "Interpolation source must contain JSON-compatible values.") from None


def _evaluate(
    context: ResolutionContext,
    options: MagicOptions,
    schema: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[ResolutionDiagnostic]]:
    candidate = context.current_invoice
    diagnostics: list[ResolutionDiagnostic] = []
    if context.mode.lower() == "rdeformat":
        diagnostics.append(_diagnostic(context, "", status="not_applicable", reason="mode_has_no_magic_stage"))
        return candidate, diagnostics
    basic = candidate.get("basic")
    if isinstance(basic, dict):
        _evaluate_fields(context, options, basic, diagnostics)
    if schema is not None and options.policy != "disabled" and not any(item.code is not None for item in diagnostics):
        _validate_schema(context, candidate, schema, diagnostics)
    return candidate, diagnostics


def _evaluate_fields(
    context: ResolutionContext,
    options: MagicOptions,
    basic: dict[str, Any],
    diagnostics: list[ResolutionDiagnostic],
) -> None:
    sources = {"invoice": context.original_invoice, "invoice-original": context.original_invoice, "invoice-current": context.current_invoice, "metadata": context.metadata}
    for key in _FIELDS:
        template = basic.get(key)
        if not contains_expression(template):
            continue
        destination = f"basic.{key}"
        if options.policy == "disabled":
            diagnostics.append(_diagnostic(context, destination, status="disabled", reason="policy_disabled"))
            continue
        try:
            tokens = parse_template(template)
        except MagicExpressionError as error:
            diagnostics.append(_diagnostic(context, destination, status="invalid", reason="invalid_expression", code=4005, message=str(error), offset=error.offset))
            continue
        basic[key] = _render(context, options, sources, tokens, destination, diagnostics)
        _validate_output(context, destination, basic[key], diagnostics)


def _render(
    context: ResolutionContext,
    options: MagicOptions,
    sources: Mapping[str, Any],
    tokens: tuple[LiteralToken | ExpressionToken, ...],
    destination: str,
    diagnostics: list[ResolutionDiagnostic],
) -> str:
    parts: list[LiteralToken | str] = []
    omitted = False
    for token in tokens:
        if isinstance(token, LiteralToken):
            _join_literal(parts, token, omitted)
            omitted = False
        else:
            text = _resolve_token(context, options, sources, token, destination, diagnostics)
            if text is None:
                omitted = True
                continue
            parts.append(text)
            omitted = False
    text_parts = [part.text if isinstance(part, LiteralToken) else part for part in parts]
    if sum(map(len, text_parts)) > MAX_OUTPUT_LENGTH:
        diagnostics.append(_diagnostic(context, destination, status="invalid", reason="output_too_long", code=4007))
        return ""
    return "".join(text_parts)


def _join_literal(parts: list[LiteralToken | str], token: LiteralToken, omitted: bool) -> None:
    previous = parts[-1] if parts else None
    text = token.text
    if omitted and isinstance(previous, LiteralToken) and previous.text.endswith("_") and text.startswith("_"):
        parts[-1] = LiteralToken(previous.text.rstrip("_") + "_")
        text = text.lstrip("_")
    if text:
        parts.append(LiteralToken(text))


def _resolve_token(
    context: ResolutionContext,
    options: MagicOptions,
    sources: Mapping[str, Any],
    token: ExpressionToken,
    destination: str,
    diagnostics: list[ResolutionDiagnostic],
) -> str | None:
    value, reason = _source_value(context, sources, token)
    if reason is None:
        value, reason = _format_value(value, sample=token.section == "sample")
    omittable = reason in ("missing_source", "missing_key", "null", "empty_string", "empty_list")
    if reason is not None:
        omit = options.missing == "omit" and omittable
        diagnostics.append(_diagnostic(context, destination, token, status="omitted" if omit else "unavailable", reason=reason, code=None if omit else 4006))
        return None
    diagnostics.append(_diagnostic(context, destination, token, status="resolved", reason="value_available"))
    return cast(str, value)


def _source_value(context: ResolutionContext, sources: Mapping[str, Any], token: ExpressionToken) -> tuple[Any, str | None]:
    if token.scope == "filename":
        return (context.rawfiles[0].name, None) if len(context.rawfiles) == 1 else (None, "filename_not_unique")
    source = sources[token.scope]
    if source is None:
        return None, "missing_source"
    value, reason = _member(source, token.section)
    if reason is not None:
        return value, reason
    value, reason = _member(value, token.key)
    if reason is None and token.scope == "metadata":
        return _member(value, "value")
    return value, reason


def _member(source: Any, key: str) -> tuple[Any, str | None]:
    if source is None:
        return None, "null"
    if not isinstance(source, Mapping):
        return None, "invalid_type"
    value = source.get(key, _ABSENT)
    return (None, "missing_key") if value is _ABSENT else (value, None)


def _format_value(value: Any, *, sample: bool) -> tuple[str | None, str | None]:
    reason = _missing_reason(value)
    if reason is not None:
        return None, reason
    if sample:
        return _sample_names(value)
    return _scalar(value)


def _missing_reason(value: Any) -> str | None:
    if value is None:
        return "null"
    if value == "":
        return "empty_string"
    if isinstance(value, list) and not value:
        return "empty_list"
    return None


def _scalar(value: Any) -> tuple[str | None, str | None]:
    if isinstance(value, float) and not math.isfinite(value):
        return None, "invalid_type"
    if isinstance(value, (str, int, float, bool)):
        return str(value), None
    return None, "invalid_type"


def _sample_names(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None, "invalid_type"
    names = [item for item in value if item]
    return ("_".join(names), None) if names else (None, "empty_list")


def _validate_output(context: ResolutionContext, destination: str, value: str, diagnostics: list[ResolutionDiagnostic]) -> None:
    if any(item.code is not None and item.destination == destination for item in diagnostics):
        return
    if destination == "basic.dataName" and _invalid_name(value):
        diagnostics.append(_diagnostic(context, destination, status="invalid", reason="invalid_data_name", code=4007))


def _invalid_name(value: str) -> bool:
    return not value or len(value) > MAX_NAME_LENGTH or any(unicodedata.category(char) == "Cc" for char in value)


def _validate_schema(
    context: ResolutionContext,
    candidate: dict[str, Any],
    schema: Mapping[str, Any],
    diagnostics: list[ResolutionDiagnostic],
) -> None:
    from jsonschema.exceptions import SchemaError  # noqa: PLC0415
    from jsonschema.validators import validator_for  # noqa: PLC0415
    from referencing import Registry  # noqa: PLC0415
    from referencing.exceptions import Unresolvable  # noqa: PLC0415

    try:
        if _external_reference(schema):
            diagnostics.append(_diagnostic(context, "", status="invalid", reason="external_schema_reference", code=4007))
            return
        validator = validator_for(schema)
        validator.check_schema(schema)
        error = next(validator(schema, registry=Registry()).iter_errors(candidate), None)
    except (SchemaError, Unresolvable, RecursionError):
        diagnostics.append(_diagnostic(context, "", status="invalid", reason="invalid_schema", code=4007))
        return
    if error is not None:
        destination = ".".join(str(part) for part in error.absolute_path)
        diagnostics.append(_diagnostic(context, destination, status="invalid", reason="schema_violation", code=4007))


def _external_reference(value: Any) -> bool:
    if isinstance(value, Mapping):
        if _has_external_reference(value):
            return True
        return any(_external_reference(item) for item in value.values())
    if isinstance(value, list):
        return any(_external_reference(item) for item in value)
    return False


def _has_external_reference(value: Mapping[str, Any]) -> bool:
    references = (value.get(key) for key in ("$ref", "$dynamicRef", "$recursiveRef"))
    return any(isinstance(reference, str) and not reference.startswith("#") for reference in references)


def _diagnostic(
    context: ResolutionContext,
    destination: str,
    token: ExpressionToken | None = None,
    *,
    status: str,
    reason: str,
    code: int | None = None,
    message: str = "",
    offset: int = 0,
) -> ResolutionDiagnostic:
    scope, path, expression = "", "", ""
    if token is not None:
        scope, expression, offset = token.scope, token.expression, token.offset
        path = ".".join(part for part in (scope, token.section, token.key) if part)
    location = f"{destination or 'invoice'} at tile {context.iteration_index}"
    detail = f"{location}: {reason}"
    if path:
        detail += f" from {path}"
    if message:
        detail += f"; {message}"
    remediation = ERROR_CATALOG[code].remediation if code is not None else ""
    return ResolutionDiagnostic(destination, expression, offset, scope, path, context.iteration_index, status, reason, code, detail, remediation)
