"""Versioned v2 run report schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


RUN_REPORT_SCHEMA_VERSION = "2"


@dataclass(frozen=True, slots=True)
class RunReport:
    """Summary of a v2 run.

    RunReport is constructed from primary run results. It is not derived from an
    EventSink; aggregation belongs to a later Runner phase.

    Attributes:
        run_id: Run identifier.
        status: Final status: ``success``, ``partial``, or ``failed``.
        flow_id: Flow identifier.
        mode: Lowercase internal mode name.
        started_at: ISO-8601 start timestamp.
        duration_ms: Run duration in milliseconds.
        config_digest: Digest of the effective config.
        iterations: Per-iteration result summaries.
        warnings: Warning summaries.
        error: Optional terminal error summary.
        schema_version: RunReport schema version.
    """

    run_id: str
    status: str
    flow_id: str
    mode: str
    started_at: str
    duration_ms: float
    config_digest: str
    iterations: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    error: dict[str, Any] | None = None
    schema_version: str = RUN_REPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a plain dict.

        Returns:
            Dict with ``schema_version`` as the first key.
        """
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "status": self.status,
            "flow_id": self.flow_id,
            "mode": self.mode,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "config_digest": self.config_digest,
            "iterations": self.iterations,
            "warnings": self.warnings,
            "error": self.error,
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize the report to JSON.

        Args:
            indent: JSON indentation level. Use ``None`` for compact JSON.

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_legacy_statuses(self) -> str:
        """Convert iteration results to the v1 workflow-status JSON shape.

        This compatibility helper is a total function. For failed runs where
        v1 exited before returning a value, the returned status list is the v2
        definition of the previously unobservable representation.

        Returns:
            JSON string containing v1-compatible workflow statuses.
        """
        return json.dumps(
            {"statuses": [self._legacy_status(iteration) for iteration in self.iterations]},
            ensure_ascii=False,
        )

    def _legacy_status(self, iteration: dict[str, Any]) -> dict[str, Any]:
        error = iteration.get("error")
        if not isinstance(error, dict):
            error = self.error if isinstance(self.error, dict) else {}
        raw_index = iteration.get("index")
        legacy_run_id = f"{raw_index:04d}" if isinstance(raw_index, int) else ""
        if raw_index is not None and not isinstance(raw_index, int):
            legacy_run_id = str(raw_index)
        completed = iteration.get("status") == "completed"
        title = iteration.get("title") or iteration.get("datatile_id") or ""
        message = error.get("message")
        if not completed:
            # v1 returned failed statuses from an ``ignore_errors`` run, so
            # their shape is observable v1 contract (Session J-REVIEW ruling #2,
            # decision A): ``workflows._create_error_status`` titled them by
            # mode and ``skip_exception_context`` prefixed the message.
            title = f"Structured Process Failed: {_legacy_failure_label(self.mode)}"
            message = f"Error: {message}" if message is not None else None
        return {
            "error_code": error.get("code"),
            "error_message": message,
            "mode": _legacy_mode(self.mode),
            "run_id": legacy_run_id,
            "stacktrace": iteration.get("stacktrace"),
            "status": "success" if completed else "failed",
            "target": iteration.get("target"),
            "title": title,
        }

    @classmethod
    def from_json(cls, json_str: str) -> RunReport:
        """Deserialize a report from JSON.

        Args:
            json_str: JSON string produced by ``to_json()``.

        Returns:
            RunReport instance.
        """
        data = json.loads(json_str)
        return cls(
            schema_version=data["schema_version"],
            run_id=data["run_id"],
            status=data["status"],
            flow_id=data["flow_id"],
            mode=data["mode"],
            started_at=data["started_at"],
            duration_ms=data["duration_ms"],
            config_digest=data["config_digest"],
            iterations=data.get("iterations", []),
            warnings=data.get("warnings", []),
            error=data.get("error"),
        )


def _legacy_failure_label(mode: str) -> str:
    """Return the mode label v1's ``workflows._process_mode`` put in failure titles."""
    return {
        "invoice": "Invoice",
        "excelinvoice": "Excelinvoice",
        "multidatatile": "MultiDataTile",
        "rdeformat": "rdeformat",
        "smarttable": "SmartTableInvoice",
    }.get(mode, mode)


def _legacy_mode(mode: str) -> str:
    return {
        "excelinvoice": "Excelinvoice",
        "multidatatile": "MultiDataTile",
        "smarttable": "SmartTableInvoice",
    }.get(mode, mode)
