"""Run aggregation and per-iteration streaming for the v2 Runner."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.finalize import atomic_write_text


class RunAggregator:
    """Aggregate tile execution results without depending on EventSink.

    The aggregator streams full per-tile details to disk as each result arrives
    and retains only lightweight summaries for the final ``RunReport``.
    """

    def __init__(
        self,
        *,
        run_id: str,
        flow_id: str,
        mode: str,
        config_digest: str,
        logs_dir: Path,
    ) -> None:
        """Create a run aggregator.

        Args:
            run_id: Current run identifier.
            flow_id: Fully-qualified flow identifier.
            mode: Lowercase internal mode name.
            config_digest: Digest of the effective config.
            logs_dir: Directory containing the ``iterations`` subdirectory.
        """
        self.run_id = run_id
        self.flow_id = flow_id
        self.mode = mode
        self.config_digest = config_digest
        self.logs_dir = logs_dir
        self.iterations: list[dict[str, Any]] = []
        self._iterations_dir = logs_dir / "iterations"
        self._iterations_dir.mkdir(parents=True, exist_ok=True)

    def record(self, result: ExecutionResult) -> None:
        """Record and stream a tile result.

        Args:
            result: Tile execution result.
        """
        payload = _result_payload(result)
        self._write_iteration(result.iteration_index, payload)
        self.iterations.append(_summary_payload(result))

    def build_report(
        self,
        *,
        status: str,
        started_at: str,
        duration_ms: float,
        warnings: list[dict[str, Any]] | None = None,
        error: dict[str, Any] | None = None,
    ) -> RunReport:
        """Build the final run report from recorded summaries.

        Args:
            status: Final run status.
            started_at: Run start timestamp.
            duration_ms: Run duration in milliseconds.
            warnings: Warning summaries.
            error: Optional terminal error summary.

        Returns:
            Final run report.
        """
        return RunReport(
            run_id=self.run_id,
            status=status,
            flow_id=self.flow_id,
            mode=self.mode,
            started_at=started_at,
            duration_ms=duration_ms,
            config_digest=self.config_digest,
            iterations=list(self.iterations),
            warnings=warnings or [],
            error=error,
        )

    def _write_iteration(self, iteration_index: int, payload: dict[str, Any]) -> None:
        path = self._iterations_dir / f"iteration_{iteration_index}.json"
        # Atomic so a reader (or a SIGTERM mid-write) never sees half a tile.
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _result_payload(result: ExecutionResult) -> dict[str, Any]:
    return {
        "iteration_index": result.iteration_index,
        "status": result.status,
        "call_records": [asdict(record) for record in result.call_records],
        "outputs": [asdict(output) for output in result.outputs],
        "error": result.error,
    }


def _summary_payload(result: ExecutionResult) -> dict[str, Any]:
    return {
        "index": result.iteration_index,
        "datatile_id": result.datatile_id or str(result.iteration_index),
        "status": result.status,
        "node_calls": [
            {
                "call_id": record.call_id,
                "node_id": record.node_id,
                "seq": record.seq,
                "status": record.status,
                "duration_ms": record.duration_ms,
            }
            for record in result.call_records
        ],
        "error": result.error,
        "title": result.title,
        "target": result.target,
        "stacktrace": result.stacktrace,
    }
