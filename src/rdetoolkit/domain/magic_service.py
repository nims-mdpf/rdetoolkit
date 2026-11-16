"""Filesystem boundary for strict v2 invoice interpolation."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any

from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, ResolutionPreview, preview_invoice, resolve_invoice
from rdetoolkit.domain.magic_parser import ExpressionToken, LiteralToken, MagicExpressionError, contains_expression, parse_template
from rdetoolkit.domain.service_errors import validation_error
from rdetoolkit.domain.validation import InvoiceValidator
from rdetoolkit.exceptions import InvoiceSchemaValidationError, StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.models.rde2types import RdeDatasetPaths


def apply_interpolation(
    dataset_paths: RdeDatasetPaths,
    *,
    original_invoice_snapshot: str | None,
    options: MagicOptions,
    iteration_index: int,
    mode: str,
) -> ResolutionPreview:
    """Resolve one tile and atomically publish a validated invoice candidate.

    Args:
        dataset_paths: Explicit paths of the current tile.
        original_invoice_snapshot: Run-private original invoice JSON value.
        options: Versioned interpolation and missing-value policies.
        iteration_index: Tile index for source diagnostics.
        mode: Effective registration mode.

    Returns:
        Redacted dependency diagnostics from the same resolution contract.

    Raises:
        RdeValidationError: Syntax (4005), source (4006), or output (4007) error.
    """
    path = dataset_paths.invoice / "invoice.json"
    if not path.exists() and options.policy != "enabled":
        return ResolutionPreview(())
    current = _read_source(path, "invoice-current", iteration_index)
    metadata = _tile_metadata(dataset_paths, current, options, iteration_index)
    context = ResolutionContext.from_sources(
        original_invoice=json.loads(original_invoice_snapshot) if original_invoice_snapshot is not None else {},
        current_invoice=current,
        metadata=metadata,
        rawfiles=tuple(dataset_paths.rawfiles),
        iteration_index=iteration_index,
        mode=mode,
    )
    preview = preview_invoice(context, options=options)
    candidate = resolve_invoice(context, options=options)
    if candidate != current:
        _validate_candidate(candidate, dataset_paths.output_paths.invoice_schema_json, iteration_index)
        _publish_invoice(path, candidate)
    return preview


def _read_source(path: Path, scope: str, index: int) -> dict[str, Any]:
    try:
        source = readf_json(path)
    except (OSError, ValueError, StructuredError):
        raise validation_error(4006, f"Source {scope} JSON is unavailable at tile {index}.") from None
    if not isinstance(source, dict):
        raise validation_error(4006, f"Source {scope} must be a JSON object at tile {index}.")
    return source


def _tile_metadata(
    paths: RdeDatasetPaths,
    invoice: dict[str, Any],
    options: MagicOptions,
    index: int,
) -> dict[str, Any] | None:
    if options.policy == "disabled" or not _needs_metadata(invoice, index):
        return None
    path = paths.meta / "metadata.json"
    return _read_source(path, "metadata:constant", index) if path.exists() else None


def _needs_metadata(invoice: dict[str, Any], index: int) -> bool:
    basic = invoice.get("basic", {})
    if not isinstance(basic, dict):
        return False
    for field in ("dataName", "description"):
        template = basic.get(field)
        if contains_expression(template) and any(
            isinstance(token, ExpressionToken) and token.scope == "metadata" for token in _parse_field(template, field, index)
        ):
            return True
    return False


def _parse_field(template: str, field: str, index: int | None = None) -> tuple[LiteralToken | ExpressionToken, ...]:
    try:
        return parse_template(template)
    except MagicExpressionError as exc:
        tile = "" if index is None else f" at tile {index}"
        reason = f"Field basic.{field}{tile}: {exc.reason}"
        raise MagicExpressionError(reason, exc.offset) from exc


def _validate_candidate(candidate: dict[str, Any], schema: Path, index: int) -> None:
    try:
        InvoiceValidator(schema).validate(obj=candidate, preserve_none_values=True)
    except (InvoiceSchemaValidationError, OSError, ValueError, StructuredError) as exc:
        field = _schema_field(exc)
        raise validation_error(4007, f"Field {field} fails invoice schema validation at tile {index}.") from None


def _schema_field(error: Exception) -> str:
    location = ".".join(str(part) for part in getattr(error.__cause__, "absolute_path", ()))
    if location:
        return location
    match = re.search(r"Field: ([^\n]+)", str(error))
    return match[1] if match else "invoice"


def _publish_invoice(path: Path, candidate: dict[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".invoice-", suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
        writef_json(temporary, candidate)
        os.replace(temporary, path)
        temporary = None
    except (OSError, StructuredError):
        raise validation_error(4007, "Atomic invoice replacement failed; check write permissions and free space.") from None
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def validate_templates(invoice: dict[str, Any], options: MagicOptions) -> bool:
    """Check eligible template syntax without resolving runtime-only sources.

    Args:
        invoice: Original invoice available during validate-only.
        options: Effective policy; disabled explicitly preserves literals.

    Returns:
        Whether runtime resolution needs a per-tile preview after processing.

    Raises:
        RdeValidationError: Code 4005 for an invalid eligible expression.
    """
    if options.policy == "disabled":
        return False
    basic = invoice.get("basic", {})
    if not isinstance(basic, dict):
        return False
    pending = False
    for field in ("dataName", "description"):
        template = basic.get(field)
        if contains_expression(template):
            tokens = _parse_field(template, field)
            pending |= any(isinstance(token, ExpressionToken) for token in tokens)
    return pending


def template_destinations(invoice: Mapping[str, Any], options: MagicOptions) -> frozenset[tuple[str, ...]]:
    """Find string destinations whose values await the interpolation stage.

    Args:
        invoice: Source invoice whose final values may depend on interpolation.
        options: Effective policy; disabled preserves all source literals.

    Returns:
        Exact paths of eligible templates, including escaped expression openers.

    """
    if options.policy == "disabled":
        return frozenset()
    basic = invoice.get("basic", {})
    if not isinstance(basic, dict):
        return frozenset()
    destinations: set[tuple[str, ...]] = set()
    for field in ("dataName", "description"):
        template = basic.get(field)
        if contains_expression(template):
            destinations.add(("basic", field))
    return frozenset(destinations)
