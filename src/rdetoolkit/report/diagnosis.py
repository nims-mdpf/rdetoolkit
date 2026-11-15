"""``report diagnose``: the failures a RunReport records, with run-bound evidence.

The RunReport is the primary record and the only source of failures. The
supporting evidence next to it -- ``iterations/iteration_<index>.json`` and
``events_<run_id>.jsonl`` -- is checked for provenance (schema version and
``run_id``) and only *described* by flags, never merged in: the iteration files
are reused by index across runs, so a later run's detail must never be
attributed to an earlier report (#669). Nothing here infers dependencies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from rdetoolkit.report.diagnostics import MAX_ENTRIES, diagnostic, envelope, safe_error, safe_identifier
from rdetoolkit.report.run_report import ITERATION_DETAIL_SCHEMA_VERSION, RUN_REPORT_SCHEMA_VERSION, RunReport

_MAX_REPORT_BYTES = 16 * 1024 * 1024
_MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
_EVENT_SCHEMA_VERSION = "1"
_EVENTS_TRUNCATED_CODE = 1002
#: ``run_id`` names the sibling event log, so it must be a plain file-name part.
_RUN_ID = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,199}\Z")


def _require(condition: bool) -> None:
    if not condition:
        message = "Report fields do not match the supported RunReport contract."
        raise ValueError(message)


def _valid_calls(calls: object) -> bool:
    return isinstance(calls, list) and all(
        isinstance(call, dict)
        and isinstance(call.get("call_id"), str)
        and isinstance(call.get("node_id"), str)
        and call.get("status") in ("completed", "failed")
        for call in calls
    )


def _validate_iteration(iteration: object) -> None:
    _require(isinstance(iteration, dict))
    iteration = cast("dict[str, Any]", iteration)
    index = iteration.get("index")
    _require(type(index) is int and index >= 0)
    _require(iteration.get("status") in ("completed", "failed"))
    _require(_valid_calls(iteration.get("node_calls", [])))
    _require(iteration.get("error") is None or isinstance(iteration["error"], dict))


def _read_report(path: Path) -> RunReport:
    with path.open("rb") as handle:
        contents = handle.read(_MAX_REPORT_BYTES + 1)
    _require(len(contents) <= _MAX_REPORT_BYTES)
    data = json.loads(contents.decode("utf-8"))
    _require(isinstance(data, dict))
    _require(data.get("schema_version") == RUN_REPORT_SCHEMA_VERSION)
    _require(isinstance(data.get("run_id"), str) and _RUN_ID.fullmatch(data["run_id"]) is not None)
    _require(data.get("status") in ("success", "partial", "failed"))
    iterations = data.get("iterations", [])
    _require(isinstance(iterations, list))
    for iteration in iterations:
        _validate_iteration(iteration)
    _require(len({iteration["index"] for iteration in iterations}) == len(iterations))
    _require(data.get("error") is None or isinstance(data["error"], dict))
    return RunReport.from_json(json.dumps(data))


def _detail_state(detail: object, *, run_id: str, index: int) -> str:
    if not isinstance(detail, dict):
        return "corrupt"
    if "run_id" not in detail or "schema_version" not in detail:
        return "unverified"  # written before iteration details were versioned
    if detail["schema_version"] != ITERATION_DETAIL_SCHEMA_VERSION:
        return "unsupported"
    if detail["run_id"] != run_id or type(detail.get("iteration_index")) is not int or detail["iteration_index"] != index:
        return "mismatched"
    return "verified" if _valid_calls(detail.get("call_records")) else "corrupt"


def _read_detail(path: Path, *, run_id: str, index: int) -> tuple[str, dict[str, Any] | None]:
    try:
        if path.stat().st_size > _MAX_EVIDENCE_BYTES:
            return "truncated", None
        detail = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "missing", None
    except (OSError, UnicodeError, ValueError, RecursionError):
        return "corrupt", None
    state = _detail_state(detail, run_id=run_id, index=index)
    return state, detail if state == "verified" else None


def _detail_flags(detail: dict[str, Any], iteration: dict[str, Any]) -> list[str]:
    """Compare a verified detail with the report's own call summary."""
    primary = {(call["call_id"], call["node_id"], call["status"]) for call in iteration.get("node_calls", [])}
    supporting = {(call["call_id"], call["node_id"], call["status"]) for call in detail["call_records"]}
    flags = []
    if supporting - primary:
        flags.append("mismatched")
    if primary - supporting or detail.get("truncated") or detail.get("call_records_truncated"):
        flags.append("truncated")
    return flags


def _iteration_evidence(report: RunReport, root: Path) -> list[dict[str, Any]]:
    results = []
    for iteration in sorted(report.iterations, key=lambda item: item["index"])[:MAX_ENTRIES]:
        index = iteration["index"]
        relative = f"iterations/iteration_{index}.json"
        state, detail = _read_detail(root / relative, run_id=report.run_id, index=index)
        flags = [] if state == "verified" else [state]
        if detail is not None:
            flags.extend(_detail_flags(detail, iteration))
        results.append({"iteration_index": index, "iteration_detail": {"path": relative, "state": state, "flags": sorted(set(flags))}})
    return results


def _event_flags(record: object, run_id: str) -> list[str]:
    if not isinstance(record, dict):
        return ["corrupt"]
    if record.get("schema_version") != _EVENT_SCHEMA_VERSION:
        return ["unsupported"]
    if record.get("run_id") != run_id:
        return ["mismatched"]
    payload = record.get("payload", {})
    if not isinstance(payload, dict) or not (isinstance(record.get("name"), str) or record.get("type") == "run.meta"):
        return ["corrupt"]
    if record.get("name") == "warning" and payload.get("code") == _EVENTS_TRUNCATED_CODE:
        return ["truncated"]
    return []


def _scan_events(path: Path, run_id: str) -> tuple[set[str], int]:
    flags: set[str] = set()
    verified = 0
    completed = False
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except (ValueError, RecursionError):
                flags.add("corrupt")
                continue
            conditions = _event_flags(record, run_id)
            flags.update(conditions)
            if {"corrupt", "unsupported", "mismatched"} & set(conditions):
                continue
            verified += 1
            completed |= record.get("name") == "run.completed"
    if not completed:
        flags.add("incomplete")
    return flags, verified


def _events_evidence(report: RunReport, root: Path) -> dict[str, Any]:
    relative = f"events_{report.run_id}.jsonl"
    path = root / relative
    try:
        if path.stat().st_size > _MAX_EVIDENCE_BYTES:
            flags, verified = {"truncated"}, 0
        else:
            flags, verified = _scan_events(path, report.run_id)
    except FileNotFoundError:
        flags, verified = {"missing"}, 0
    except (OSError, UnicodeError):
        flags, verified = {"corrupt"}, 0
    return {"path": relative, "flags": sorted(flags), "verified_records": verified}


def _failure(error: object, *, index: int | None, call: dict[str, Any] | None) -> dict[str, Any]:
    # Ids come from a file anyone could have edited: one that rdetoolkit could
    # not have written is replaced by null and named in ``redacted``.
    ids = {field: safe_identifier(call[field]) if call else None for field in ("node_id", "call_id")}
    return {
        "iteration_index": index,
        **ids,
        "redacted": sorted(field for field, value in ids.items() if call and value is None),
        **safe_error(error),
        "source": "report",
    }


def _iteration_failures(iteration: dict[str, Any]) -> list[dict[str, Any]]:
    failed_calls = [call for call in iteration.get("node_calls", []) if call["status"] == "failed"]
    error = iteration.get("error") or {}
    # Only the call the error names inherits its code: a caught node failure
    # must not be relabelled by a later, unrelated tile error.
    failures = [
        _failure(error if error.get("call_id") == call["call_id"] else None, index=iteration["index"], call=call)
        for call in failed_calls
    ]
    if iteration["status"] == "failed" and not any(error.get("call_id") == call["call_id"] for call in failed_calls):
        failures.append(_failure(error, index=iteration["index"], call=None))
    return failures


def _failures(report: RunReport) -> list[dict[str, Any]]:
    failures = [
        failure
        for iteration in sorted(report.iterations, key=lambda item: item["index"])
        for failure in _iteration_failures(iteration)
    ]
    if not failures and (report.error or report.status in {"failed", "partial"}):
        failures.append(_failure(report.error, index=None, call=None))
    return failures


def _evidence_diagnostics(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [evidence["events"], *(item["iteration_detail"] for item in evidence["iterations"])]
    return [
        diagnostic(
            code=None, severity="warning", name=f"SupportingEvidence{flag.title()}", subject=entry["path"],
            message=f"Supporting evidence is {flag}; the report's own results remain authoritative.",
            remediation="Keep the report, its iteration details and its event log together; inspect them locally before drawing further conclusions.",
        )
        for entry in entries
        for flag in entry["flags"]
    ]


def _failure_subject(failure: dict[str, Any]) -> str:
    if failure["call_id"] is not None:
        return str(failure["call_id"])
    return "run" if failure["iteration_index"] is None else f"iteration:{failure['iteration_index']}"


def diagnose_report(path: Path) -> dict[str, Any]:
    """Diagnose one saved RunReport without inferring dependencies or copying runtime values.

    Args:
        path: ``run_report_<run_id>.json``. Its sibling evidence is checked by run id.

    Returns:
        The diagnostics envelope with ``command``, ``source``, ``run_id``,
        ``run_status``, ``failures`` and ``evidence``. Evidence paths are
        relative to the report. ``failures`` and ``evidence.iterations`` keep
        their first :data:`MAX_ENTRIES` entries and set ``truncated`` beyond that.

    Raises:
        OSError: The report cannot be read.
        ValueError: Its JSON, schema version or field shapes are not supported.
        RecursionError: Its JSON nests too deeply to parse.
    """
    report = _read_report(path)
    evidence = {"iterations": _iteration_evidence(report, path.parent), "events": _events_evidence(report, path.parent)}
    failures = _failures(report)
    findings = [
        diagnostic(
            code=item["code"], severity="error", name=item["name"], message=item["message"],
            remediation=item["remediation"], subject=_failure_subject(item),
        )
        for item in failures
    ]
    findings.extend(_evidence_diagnostics(evidence))
    return envelope(
        findings,
        truncated=len(failures) > MAX_ENTRIES or len(report.iterations) > MAX_ENTRIES,
        command="report diagnose",
        source={"format": "rdetoolkit.run-report", "schema_version": report.schema_version},
        run_id=report.run_id,
        run_status=report.status,
        failures=failures[:MAX_ENTRIES],
        evidence=evidence,
    )
