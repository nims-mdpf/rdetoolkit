"""Versioned diagnostic envelope shared by the agent-facing CLI commands.

``nodes lint --json``, ``doctor --format json`` and ``report diagnose --json``
all emit :func:`envelope`. Callers pass only deliberately selected fields:
nothing here serializes exceptions, configuration values, locals or arbitrary
objects, and :func:`safe_error` reduces a recorded run error to catalog text.
Identifiers read from files are passed through :func:`safe_identifier` (#670).
"""

from __future__ import annotations

import json
import re
from typing import Any

from rdetoolkit import __version__
from rdetoolkit.errors import ERROR_CATALOG

DIAGNOSTICS_SCHEMA_VERSION = "1"
DIAGNOSTICS_FORMAT = "rdetoolkit.diagnostics"
#: Entries kept per list (``diagnostics``, and the command's own lists); the rest set ``truncated``.
MAX_ENTRIES = 200
MAX_IDENTIFIER_LENGTH = 200
#: Node, flow and call ids as rdetoolkit forms them (``pkg.mod.func``, ``mod.f.<locals>.g``,
#: ``<node_id>#<seq>``). Whitespace, slashes, backslashes, ``:``, ``=`` and quotes never match.
_IDENTIFIER = re.compile(rf"\w[\w.<>#-]{{0,{MAX_IDENTIFIER_LENGTH - 1}}}\Z")

#: Name and guidance for a recorded error without a v2 catalog entry.
_UNCATALOGUED_ERROR = {
    "name": "ExecutionError",
    "message": "An execution failure was recorded; runtime error text is omitted.",
    "remediation": "Inspect the original run artifacts locally and reproduce the failing operation with its inputs.",
}


def diagnostic(
    *,
    code: int | None,
    severity: str,
    name: str,
    message: str,
    remediation: str,
    subject: str,
    location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one finding.

    Args:
        code: Catalog integer, or None for a documented symbolic finding.
        severity: ``error``, ``warning``, or ``info``.
        name: Catalog name, or the documented symbolic name when ``code`` is None.
        message: Fixed or catalog description; never raw exception text.
        remediation: Actionable guidance.
        subject: Stable identifier the finding is about (node id, check id, ...).
        location: Optional affected source location or project-relative path.

    Returns:
        A JSON-compatible finding.
    """
    result: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "name": name,
        "message": message,
        "remediation": remediation,
        "subject": subject,
    }
    if location is not None:
        result["location"] = location
    return result


def envelope(diagnostics: list[dict[str, Any]], *, truncated: bool = False, **extra: Any) -> dict[str, Any]:
    """Wrap findings in the versioned, deterministically ordered envelope.

    Args:
        diagnostics: Findings built by :func:`diagnostic`.
        truncated: The caller already capped one of its own lists.
        **extra: Command-specific, deliberately selected JSON fields.

    Returns:
        ``schema_version``, ``format``, ``producer``, ``status`` (``failed`` if
        any error, ``warning`` if any warning, otherwise ``passed``, computed
        before capping), the first :data:`MAX_ENTRIES` sorted findings,
        ``truncated``, and ``extra``. Process exit codes remain each command's decision.
    """
    ordered = sorted(
        diagnostics,
        key=lambda item: (item["subject"], item["name"], json.dumps(item, ensure_ascii=False, sort_keys=True)),
    )
    severities = {item["severity"] for item in ordered}
    status = "failed" if "error" in severities else "warning" if "warning" in severities else "passed"
    return {
        **extra,
        "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "format": DIAGNOSTICS_FORMAT,
        "producer": {"name": "rdetoolkit", "version": __version__},
        "status": status,
        "diagnostics": ordered[:MAX_ENTRIES],
        "truncated": truncated or len(ordered) > MAX_ENTRIES,
    }


def safe_identifier(value: object) -> str | None:
    """Return ``value`` if it is an identifier rdetoolkit could have written, else None.

    Args:
        value: A node, flow or call id read from a file, so not trusted.

    Returns:
        The string unchanged when it matches the identifier pattern and length
        cap, otherwise None (the caller flags the omission; the value is never echoed).
    """
    return value if isinstance(value, str) and _IDENTIFIER.match(value) else None


def safe_error(error: object) -> dict[str, Any]:
    """Reduce a recorded run error to its code and catalog text.

    Args:
        error: An ``error`` mapping from a RunReport, or anything else.

    Returns:
        ``code``, ``name``, ``message`` and ``remediation``. A v2 catalog code
        gets its catalog name, message template and remediation; any other
        integer code (including a v1 ``StructuredError`` passthrough, whose
        number may collide with a v2 code) keeps the integer under the fixed
        name ``ExecutionError``. The runtime message is never copied.
    """
    record = error if isinstance(error, dict) else {}
    candidate = record.get("code")
    code = candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None
    definition = ERROR_CATALOG.get(code) if code is not None and record.get("name") != "StructuredError" else None
    if definition is None:
        return {"code": code, **_UNCATALOGUED_ERROR}
    return {
        "code": code,
        "name": definition.name,
        "message": definition.message_template,
        "remediation": definition.remediation,
    }
