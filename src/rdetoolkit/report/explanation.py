"""``report explain``: why a run failed, from its report and its failure diagnostics (#687).

The run report says *that* a run failed and with which catalog code; the
failure-diagnostics sidecar (``diagnostics_<run_id>.json``, #686) says
*where*: the lifecycle phase, the exception chain and the source frame. This
module joins the two for one run, read from the files next to the report:

* The report stays the authority on outcome. Every failure it records is
  explained; a sidecar entry adds phase, exception and location to it.
* The sidecar is used only when its format, version and ``run_id`` match the
  report. Otherwise -- a historic report, a moved file, another run's file --
  the explanation falls back to what the report records and says that the
  diagnostics are unavailable. Nothing is filled in by guessing.
* A successful run is not given a cause.

Two renderings share one analysis. The JSON document is the versioned
diagnostics envelope and follows its rules: identifiers and paths that
rdetoolkit could not have written are redacted, and no exception message or
other runtime text is copied. The text rendering is for the developer at the
terminal and shows the recorded exception messages (the same text the run
report and ``job.failed`` already carry), with control characters escaped.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdetoolkit.report.diagnosis import evidence_findings, failure_subject, read_report_evidence
from rdetoolkit.report.diagnostics import MAX_ENTRIES, diagnostic, envelope, safe_error, safe_identifier
from rdetoolkit.report.failure import FAILURE_DIAGNOSTICS_FORMAT, FAILURE_DIAGNOSTICS_SCHEMA_VERSION, FAILURE_PHASES, diagnostics_filename
from rdetoolkit.report.run_report import RunReport

EXPLAIN_COMMAND = "report explain"
#: Same bound as the other supporting evidence ``report diagnose`` reads.
_MAX_SIDECAR_BYTES = 64 * 1024 * 1024
_MAX_TEXT = 200
#: Exception classes and frame functions as Python names them
#: (``pkg.mod.Error``, ``Runner.post_validate``, ``<module>``, ``f.<locals>.g``).
_CODE_NAME = re.compile(r"[\w.<>-]{1,200}\Z")
#: Annotation text as the call log renders it (``int``, ``str | None``, ``list[int]``).
_TYPE_TEXT = re.compile(r"[\w.<>\[\], |-]{1,200}\Z")
#: One relative path segment: no separators, no drive, no ``..``.
_PATH_SEGMENT = re.compile(r"[\w.@+-]{1,200}\Z")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_RELATIONS = ("primary", "cause", "context")
_OPTIONAL_TEXT_FIELDS = ("name", "message", "node_id", "call_id", "parameter", "expected_type", "actual_type", "artifact_path")
_REDACTED = "<redacted>"
#: ``module:qualname`` -- a flow id has at most one ``:``.
_FLOW_ID_PARTS = 2


class IterationNotInReportError(LookupError):
    """``--iteration`` names a tile the report does not record."""


@dataclass(frozen=True, slots=True)
class Explanation:
    """The analysis of one run, ready to render.

    Attributes:
        document: The JSON envelope (``command: "report explain"``).
        entries: One raw entry per explained failure, for the text rendering.
        report: The run report.
    """

    document: dict[str, Any]
    entries: tuple[dict[str, Any], ...]
    report: RunReport


# --------------------------------------------------------------------------- sidecar


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_frame(frame: object) -> bool:
    return (
        isinstance(frame, dict)
        and isinstance(frame.get("file"), str)
        and (frame.get("line") is None or _is_int(frame.get("line")))
        and isinstance(frame.get("function"), str)
    )


def _valid_summary(summary: object) -> bool:
    return (
        isinstance(summary, dict)
        and summary.get("relation") in _RELATIONS
        and isinstance(summary.get("type"), str)
        and isinstance(summary.get("message"), str)
        and isinstance(summary.get("frames"), list)
        and all(_valid_frame(frame) for frame in summary["frames"])
    )


def _valid_entry(entry: object) -> bool:
    if not isinstance(entry, dict) or entry.get("phase") not in FAILURE_PHASES:
        return False
    index = entry.get("iteration_index")
    return (
        (entry.get("code") is None or _is_int(entry.get("code")))
        and (index is None or (_is_int(index) and index >= 0))
        and all(entry.get(name) is None or isinstance(entry.get(name), str) for name in _OPTIONAL_TEXT_FIELDS)
        and (entry.get("location") is None or _valid_frame(entry.get("location")))
        and (entry.get("exception") is None or _valid_summary(entry.get("exception")))
        and isinstance(entry.get("causes", []), list)
        and all(_valid_summary(cause) for cause in entry.get("causes", []))
    )


def _sidecar_state(document: object, run_id: str) -> str:
    if not isinstance(document, dict):
        return "corrupt"
    if document.get("format") != FAILURE_DIAGNOSTICS_FORMAT or document.get("schema_version") != FAILURE_DIAGNOSTICS_SCHEMA_VERSION:
        return "unsupported"
    if document.get("run_id") != run_id:
        return "mismatched"
    diagnostics = document.get("diagnostics")
    if not isinstance(diagnostics, list) or not all(_valid_entry(entry) for entry in diagnostics):
        return "corrupt"
    return "verified"


def _load_sidecar(path: Path, run_id: str) -> tuple[str, dict[str, Any] | None]:
    try:
        if path.stat().st_size > _MAX_SIDECAR_BYTES:
            return "truncated", None
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "missing", None
    except (OSError, UnicodeError, ValueError, RecursionError):
        return "corrupt", None
    state = _sidecar_state(document, run_id)
    return state, document if state == "verified" else None


def _read_sidecar(root: Path, report: RunReport) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    """Read the run's sidecar; return its evidence entry and verified diagnostics.

    A successful run writes no sidecar, so its absence is not flagged there.
    """
    relative = diagnostics_filename(report.run_id)
    state, document = _load_sidecar(root / relative, report.run_id)
    flags: list[str] = []
    if state != "verified" and not (state == "missing" and report.status == "success"):
        flags.append(state)
    if document is not None and document.get("truncated") is True:
        flags.append("truncated")
    evidence = {"path": relative, "state": state, "flags": flags}
    return evidence, None if document is None else list(document["diagnostics"])


# --------------------------------------------------------------------------- entries


def _iteration(report: RunReport, index: int | None) -> dict[str, Any] | None:
    if index is None:
        return None
    return next((item for item in report.iterations if item["index"] == index), None)


def _report_error(report: RunReport, failure: dict[str, Any]) -> dict[str, Any]:
    """Return the recorded error a report failure stands for, or an empty mapping."""
    iteration = _iteration(report, failure["iteration_index"])
    if iteration is None:
        return report.error or {}
    error = iteration.get("error") or {}
    if failure["call_id"] is None or error.get("call_id") == failure["call_id"]:
        return error
    # A node failure the flow caught: the call failed, its tile did not.
    return {}


def _text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _base_entry(source: str, **fields: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source": source,
        "phase": None,
        "iteration_index": None,
        "node_id": None,
        "call_id": None,
        "redacted": [],
        "code": None,
        "name": None,
        "message": None,
        "parameter": None,
        "expected_type": None,
        "actual_type": None,
        "artifact_path": None,
        "location": None,
        "exception": None,
        "causes": [],
    }
    entry.update(fields)
    return entry


def _report_entry(report: RunReport, failure: dict[str, Any]) -> dict[str, Any]:
    error = _report_error(report, failure)
    return _base_entry(
        "report",
        iteration_index=failure["iteration_index"],
        node_id=failure["node_id"],
        call_id=failure["call_id"],
        redacted=list(failure["redacted"]),
        code=failure["code"],
        name=_text_or_none(error.get("name")),
        message=_text_or_none(error.get("message")),
    )


def _sidecar_entry(diagnostic_entry: dict[str, Any]) -> dict[str, Any]:
    fields = {key: diagnostic_entry.get(key) for key in ("phase", "iteration_index", "code", "location", "exception", *_OPTIONAL_TEXT_FIELDS)}
    return _base_entry("diagnostics", causes=list(diagnostic_entry.get("causes", [])), **fields)


def _covered(failure: dict[str, Any], sidecar: list[dict[str, Any]]) -> bool:
    """Whether a sidecar entry already explains a failure the report records."""
    if failure["call_id"] is not None:
        return any(entry.get("call_id") == failure["call_id"] for entry in sidecar)
    if failure["iteration_index"] is not None:
        return any(entry.get("iteration_index") == failure["iteration_index"] for entry in sidecar)
    return bool(sidecar)


def _entries(report: RunReport, failures: list[dict[str, Any]], sidecar: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    # A successful run is never given a cause from a stray diagnostics file.
    if sidecar is None or report.status == "success":
        entries = [_report_entry(report, failure) for failure in failures]
    else:
        entries = [_sidecar_entry(item) for item in sidecar]
        entries.extend(_report_entry(report, failure) for failure in failures if not _covered(failure, sidecar))
    # Tiles in order, run-level failures last; stable within a tile.
    return sorted(entries, key=lambda entry: (entry["iteration_index"] is None, entry["iteration_index"] or 0))


# ------------------------------------------------------------------ public (JSON) view


def _safe_code_name(value: object) -> str | None:
    return value if isinstance(value, str) and _CODE_NAME.match(value) else None


def _safe_type_text(value: object) -> str | None:
    return value if isinstance(value, str) and _TYPE_TEXT.match(value) else None


def _safe_relative_path(value: object) -> str | None:
    """Return a relative POSIX path made of plain segments, else None."""
    if not isinstance(value, str) or not value or len(value) > _MAX_TEXT * 4:
        return None
    segments = value.split("/")
    if any(segment in ("", ".", "..") or not _PATH_SEGMENT.match(segment) for segment in segments):
        return None
    return value


def _public_frame(frame: dict[str, Any] | None) -> dict[str, Any] | None:
    if frame is None:
        return None
    return {"file": _safe_relative_path(frame["file"]), "line": frame["line"], "function": _safe_code_name(frame["function"])}


def _frame_redacted(frame: dict[str, Any] | None) -> bool:
    public = _public_frame(frame)
    return public is not None and (public["file"] is None or public["function"] is None)


def _public_exception(summary: dict[str, Any] | None, *, full_traceback: bool) -> dict[str, Any] | None:
    if summary is None:
        return None
    frames = summary["frames"]
    result: dict[str, Any] = {
        "relation": summary["relation"],
        "type": _safe_code_name(summary["type"]),
        "location": _public_frame(frames[-1]) if frames else None,
    }
    if full_traceback:
        result["frames"] = [_public_frame(frame) for frame in frames]
        result["frames_truncated"] = summary.get("frames_truncated") is True
    return result


_SANITIZERS: dict[str, Callable[[object], str | None]] = {
    "node_id": safe_identifier,
    "call_id": safe_identifier,
    "parameter": safe_identifier,
    "expected_type": _safe_type_text,
    "actual_type": _safe_type_text,
    "artifact_path": _safe_relative_path,
}


def _remediation(code: int | None, name: str | None) -> str:
    published = safe_error({"code": code, "name": name})
    return str(published["remediation"])


def _public_entry(entry: dict[str, Any], *, full_traceback: bool) -> dict[str, Any]:
    safe = {field: sanitize(entry[field]) for field, sanitize in _SANITIZERS.items()}
    redacted = set(entry["redacted"]) | {field for field, value in safe.items() if entry[field] is not None and value is None}
    if _frame_redacted(entry["location"]):
        redacted.add("location")
    return {
        "source": entry["source"],
        "phase": entry["phase"],
        "iteration_index": entry["iteration_index"],
        **safe,
        "redacted": sorted(redacted),
        **safe_error({"code": entry["code"], "name": entry["name"]}),
        "location": _public_frame(entry["location"]),
        "exception": _public_exception(entry["exception"], full_traceback=full_traceback),
        "causes": [_public_exception(cause, full_traceback=full_traceback) for cause in entry["causes"]],
    }


def _summary(report: RunReport) -> dict[str, int]:
    return {
        "iterations": len(report.iterations),
        "failed_iterations": sum(1 for item in report.iterations if item["status"] == "failed"),
        "node_calls": sum(len(item.get("node_calls", [])) for item in report.iterations),
        "failed_node_calls": sum(1 for item in report.iterations for call in item.get("node_calls", []) if call["status"] == "failed"),
    }


def _safe_flow_id(flow_id: str) -> str | None:
    """``module:qualname`` with both parts identifiers, else None."""
    parts = flow_id.split(":")
    return flow_id if 1 <= len(parts) <= _FLOW_ID_PARTS and all(safe_identifier(part) for part in parts) else None


def _findings(public: list[dict[str, Any]], evidence_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = [
        diagnostic(
            code=item["code"], severity="error", name=item["name"], message=item["message"],
            remediation=item["remediation"], subject=failure_subject(item),
        )
        for item in public
    ]
    findings.extend(evidence_findings(evidence_entries))
    return findings


def explain_report(path: Path, *, iteration: int | None = None, full_traceback: bool = False) -> Explanation:
    """Explain the failures of one saved run.

    Args:
        path: ``run_report_<run_id>.json``. The sidecar, iteration details and
            event log are looked up next to it by the report's ``run_id``.
        iteration: Explain only this tile index.
        full_traceback: Add every recorded frame (file, line, function) of
            each exception to the JSON document and the text rendering.

    Returns:
        The analysis. ``document`` is the diagnostics envelope with
        ``command``, ``source``, ``run_id``, ``run_status``, ``mode``,
        ``flow_id``, ``summary``, ``diagnostics_available``, ``explanations``
        and ``evidence`` (``iterations``, ``events``, ``diagnostics``).

    Raises:
        OSError: The report cannot be read.
        ValueError: Its JSON, schema version or field shapes are not supported.
        RecursionError: Its JSON nests too deeply to parse.
        IterationNotInReportError: ``iteration`` is not a tile of the report.
    """
    report, failures, evidence = read_report_evidence(path)
    if iteration is not None and _iteration(report, iteration) is None:
        msg = f"iteration {iteration} is not recorded in the report"
        raise IterationNotInReportError(msg)
    sidecar_evidence, sidecar = _read_sidecar(path.parent, report)
    entries = [entry for entry in _entries(report, failures, sidecar) if iteration is None or entry["iteration_index"] == iteration]
    for entry in entries:
        tile = _iteration(report, entry["iteration_index"])
        entry["datatile_id"] = None if tile is None else _text_or_none(tile.get("datatile_id"))
    public = [_public_entry(entry, full_traceback=full_traceback) for entry in entries]
    evidence = {**evidence, "diagnostics": sidecar_evidence}
    evidence_entries = [evidence["events"], sidecar_evidence, *(item["iteration_detail"] for item in evidence["iterations"])]
    document = envelope(
        _findings(public, evidence_entries),
        truncated=len(public) > MAX_ENTRIES or len(report.iterations) > MAX_ENTRIES,
        command=EXPLAIN_COMMAND,
        source={"format": "rdetoolkit.run-report", "schema_version": report.schema_version},
        run_id=report.run_id,
        run_status=report.status,
        mode=safe_identifier(report.mode),
        flow_id=_safe_flow_id(report.flow_id),
        summary=_summary(report),
        diagnostics_available=sidecar is not None,
        explanations=public[:MAX_ENTRIES],
        evidence=evidence,
    )
    return Explanation(document=document, entries=tuple(entries[:MAX_ENTRIES]), report=report)


# --------------------------------------------------------------------------- text view


def _display(text: str) -> str:
    """Escape control characters so a recorded message cannot drive the terminal."""
    return _CONTROL.sub(lambda match: f"\\x{ord(match.group()):02x}", text)


def _display_block(text: str, indent: str) -> str:
    lines = _display(text).splitlines() or [""]
    return ("\n" + indent).join(lines)


def _frame_text(frame: dict[str, Any]) -> str:
    line = "?" if frame["line"] is None else str(frame["line"])
    return f"{_display(frame['file'])}:{line} in {_display(frame['function'])}"


def _reason(entry: dict[str, Any]) -> str | None:
    """The deepest recorded exception -- what actually went wrong -- else the published message."""
    chain = [item for item in (entry["exception"], *entry["causes"]) if item is not None]
    if chain:
        deepest = chain[-1]
        return f"{deepest['type']}: {deepest['message']}" if deepest["message"] else str(deepest["type"])
    return entry["message"]


def _status_line(report: RunReport) -> str:
    summary = _summary(report)
    total, failed = summary["iterations"], summary["failed_iterations"]
    if report.status == "partial":
        return f"status: partial ({failed} of {total} iterations failed; the others completed)"
    if report.status == "failed":
        return f"status: failed ({failed} of {total} iterations failed)"
    return f"status: {_display(report.status)} ({total} iterations)"


def _shown(value: object, *, redacted: bool) -> str:
    if redacted:
        return _REDACTED
    return "not recorded" if value is None else _display(str(value))


def _where_lines(entry: dict[str, Any], public: dict[str, Any]) -> list[str]:
    lines = [f"  phase: {entry['phase'] or 'not recorded'}"]
    if entry["iteration_index"] is None:
        lines.append("  iteration: none (the failure belongs to the run)")
    else:
        # The tile id is the first input file's stem: shown to the developer,
        # never put into the JSON envelope (no input file names there).
        tile = entry.get("datatile_id")
        suffix = f" (input: {_display(tile)})" if tile else ""
        lines.append(f"  iteration: {entry['iteration_index']}{suffix}")
    redacted = set(public["redacted"])
    lines.append(f"  node: {_shown(public['node_id'], redacted='node_id' in redacted)}")
    if public["call_id"] is not None or "call_id" in redacted:
        lines.append(f"  call_id: {_shown(public['call_id'], redacted='call_id' in redacted)}")
    else:
        lines.append("  call_id: none (no executed node call is recorded for this failure)")
    return lines


def _cause_lines(entry: dict[str, Any], public: dict[str, Any]) -> list[str]:
    lines = [f"  error: {public['code'] if public['code'] is not None else '-'} {_display(entry['name'] or public['name'])}"]
    if entry["exception"] is not None:
        lines.append(f"  exception: {_display(entry['exception']['type'])}")
    if entry["location"] is not None:
        lines.append(f"  location: {_frame_text(entry['location'])}")
    if public["parameter"] is not None:
        lines.append(f"  parameter: {public['parameter']} (expected {public['expected_type']}, got {public['actual_type']})")
    if public["artifact_path"] is not None:
        lines.append(f"  artifact: {public['artifact_path']}")
    reason = _reason(entry)
    lines.append(f"  reason: {_display_block(reason, '    ') if reason else 'not recorded'}")
    lines.append(f"  remediation: {_remediation(entry['code'], entry['name'])}")
    return lines


def _traceback_lines(entry: dict[str, Any]) -> list[str]:
    chain = [item for item in (entry["exception"], *entry["causes"]) if item is not None]
    if not chain:
        return ["  traceback: unavailable (no frames are recorded for this failure)"]
    lines = ["  traceback (file, line and function of each recorded frame, outermost first):"]
    for item in chain:
        lines.append(f"    {_display(item['type'])} ({item['relation']})")
        lines.extend(f"      {_frame_text(frame)}" for frame in item["frames"])
        if item.get("frames_truncated") is True:
            lines.append("      ... outer frames were not recorded")
    return lines


def _file_lines(explanation: Explanation, report_path: Path) -> list[str]:
    evidence = explanation.document["evidence"]
    base = report_path.parent
    sidecar = evidence["diagnostics"]
    lines = ["files:", f"  run report: {_display(str(report_path))}"]
    lines.append(f"  failure diagnostics: {_display(str(base / sidecar['path']))} ({sidecar['state']})")
    explained = {entry["iteration_index"] for entry in explanation.entries}
    for item in evidence["iterations"]:
        if item["iteration_index"] in explained:
            detail = item["iteration_detail"]
            lines.append(f"  iteration {item['iteration_index']} detail: {_display(str(base / detail['path']))} ({detail['state']})")
    events = evidence["events"]
    lines.append(f"  events: {_display(str(base / events['path']))}" + (f" ({', '.join(events['flags'])})" if events["flags"] else ""))
    return lines


def _availability_line(explanation: Explanation) -> str | None:
    if explanation.report.status == "success" or explanation.document["diagnostics_available"]:
        return None
    state = explanation.document["evidence"]["diagnostics"]["state"]
    return (
        f"failure diagnostics: unavailable ({state}). Phase, exception and source location are not known; "
        "the explanation below is what the run report records."
    )


def render_text(explanation: Explanation, report_path: Path, *, full_traceback: bool = False) -> str:
    """Render an explanation for the terminal.

    Args:
        explanation: The result of :func:`explain_report`.
        report_path: The report path as the user gave it; file paths are shown next to it.
        full_traceback: Show every recorded frame of each exception.

    Returns:
        The text, without a trailing newline.
    """
    report = explanation.report
    document = explanation.document
    lines = [f"run_id: {report.run_id}", _status_line(report), f"mode: {_shown(document['mode'], redacted=document['mode'] is None)}"]
    lines.append(f"flow: {_shown(document['flow_id'], redacted=document['flow_id'] is None)}")
    notice = _availability_line(explanation)
    if notice is not None:
        lines.append(notice)
    if not explanation.entries:
        lines.append("")
        lines.append("No failure is recorded for this run; there is nothing to explain." if report.status == "success" else "No failure is recorded for the selected iteration.")
    for number, (entry, public) in enumerate(zip(explanation.entries, document["explanations"], strict=True), start=1):
        lines.extend(("", f"failure {number} of {len(explanation.entries)} (from the {'failure diagnostics' if entry['source'] == 'diagnostics' else 'run report'}):"))
        lines.extend(_where_lines(entry, public))
        lines.extend(_cause_lines(entry, public))
        if full_traceback:
            lines.extend(_traceback_lines(entry))
    lines.append("")
    lines.extend(_file_lines(explanation, report_path))
    warnings = [finding for finding in document["diagnostics"] if finding["severity"] == "warning"]
    lines.extend(f"warning: {finding['subject']}: {finding['message']}" for finding in warnings)
    return "\n".join(lines)
