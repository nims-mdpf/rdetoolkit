"""Finalize v2 Runner outputs."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import Any

from rdetoolkit.errors import ERROR_CATALOG, write_job_errorlog_file
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.types import RdeConfig


_DEFAULT_FAILURE_CODE = 3001

#: ``RunReport.error.name`` marking a record whose code came from a raised
#: ``StructuredError`` rather than from ``ERROR_CATALOG``. Reusing the existing
#: ``name`` field keeps the RunReport schema at version "2" (Design §8.3).
PASSTHROUGH_ERROR_NAME = "StructuredError"

_EMPTY_PASSTHROUGH_MESSAGE = "StructuredError raised without a message"


def structured_error_record(exc: BaseException | None) -> dict[str, Any] | None:
    """Return a verbatim error record for any v1 ``StructuredError``.

    The v1 public API carries ``emsg``/``ecode`` — not ``message``/``code`` —
    and RDE consumers rely on those two values reaching ``job.failed``
    unchanged (Design §6.3). The scope is **every** ``StructuredError`` that
    reaches an error translator, not only user code: v1's
    ``catch_exception_with_message`` publishes an internally raised
    ``StructuredError`` verbatim too, and the unified Runner must not diverge
    from that. Catalog codes survive only where a v2 domain error already
    wrapped the failure — in particular validation stays 4001/4002/4003,
    because ``pre_validate`` / ``post_validate`` raise ``RdeValidationError``
    instead of letting the underlying exception through.

    This record is also the marker telling :func:`finalize` to honor an
    off-catalog code.

    Args:
        exc: Candidate exception, typically a raised error or its ``__cause__``.

    Returns:
        The passthrough record, or ``None`` when ``exc`` is not a
        ``StructuredError``.
    """
    if not isinstance(exc, StructuredError):
        return None
    # job.failed is an int contract, so a malformed ecode cannot be published.
    code = exc.ecode if isinstance(exc.ecode, int) and not isinstance(exc.ecode, bool) else _DEFAULT_FAILURE_CODE
    message = exc.emsg or str(exc) or _EMPTY_PASSTHROUGH_MESSAGE
    return {"code": code, "name": PASSTHROUGH_ERROR_NAME, "message": message}


class RunFinalizer:
    """Persist the final report through the single Runner-owned finalization path."""

    def __init__(self, *, data_root: Path | Callable[[], Path]) -> None:
        """Create a finalizer.

        Args:
            data_root: The run's resolved data root, or a provider for it. The
                finalizer never resolves one itself: the Runner decided it once
                before anything was created (ruling #1).
        """
        self._data_root = data_root

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        """Persist final artifacts for one completed lifecycle.

        Args:
            report: Primary run report.
            config: Effective canonical configuration.
        """
        data_root = self._data_root() if callable(self._data_root) else self._data_root
        finalize(report, config, data_root=data_root)


def finalize(report: RunReport, config: RdeConfig, *, data_root: Path) -> None:
    """Persist the run report and write ``job.failed`` for failed runs.

    The ``job.failed`` file is delegated to v1 ``write_job_errorlog_file`` so
    the RDE platform format stays owned by the existing public API.

    Args:
        report: Run report produced by the Runner.
        config: Effective v2 Runner configuration.
        data_root: The run's single resolved data root.
    """
    _ = config
    _write_run_report(report, data_root=data_root)
    if report.status == "failed":
        code, message = _failure_error(report)
        failure_path = (data_root / "job.failed").resolve()
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        write_job_errorlog_file(code, message, filename=str(failure_path))


def _write_run_report(report: RunReport, *, data_root: Path) -> None:
    logs_dir = data_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    report_path = logs_dir / f"run_report_{report.run_id}.json"
    report_path.write_text(report.to_json(), encoding="utf-8")


def _failure_error(report: RunReport) -> tuple[int, str]:
    error = report.error or {}
    code = _failure_code(error)
    raw_message: Any = error.get("message")
    if isinstance(raw_message, str) and raw_message:
        return code, raw_message
    if code in ERROR_CATALOG:
        return code, _fallback_message(code)
    return code, _EMPTY_PASSTHROUGH_MESSAGE


def _failure_code(error: dict[str, Any]) -> int:
    """Resolve the int code written to ``job.failed``.

    An off-catalog code is honored only for a passthrough record, because that
    code was chosen by user code and is part of the v1 contract; every other
    off-catalog value is a framework defect and is replaced by the default.
    """
    raw_code = error.get("code", _DEFAULT_FAILURE_CODE)
    code = raw_code if isinstance(raw_code, int) else _DEFAULT_FAILURE_CODE
    if code in ERROR_CATALOG or error.get("name") == PASSTHROUGH_ERROR_NAME:
        return code
    return _DEFAULT_FAILURE_CODE


class _UnknownPlaceholders(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "unknown"


def _fallback_message(code: int) -> str:
    """Render a catalog message template with any placeholders neutralized.

    Templates such as ``"Node execution failed for call {call_id}: {reason}"``
    are caller-formatted; job.failed must never contain raw ``{placeholder}``
    text (Design §6.3).
    """
    return ERROR_CATALOG[code].message_template.format_map(_UnknownPlaceholders())
