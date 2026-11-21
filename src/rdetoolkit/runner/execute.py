"""Single-tile eager flow execution for the v2 Runner."""

from __future__ import annotations

import inspect
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

# Tile outputs are summarized by the call log's own helper, never a copy: a
# Runner-side duplicate drifted from it (public-module type names, #641), so
# one value read differently in a node record and in the tile outputs.
from rdetoolkit.core.calllog import CallLogRecorder, CallSequence, NodeCallRecord, NodeInvocation, TypeSummary, _summarize_outputs
from rdetoolkit.core.context import RunContext, get_reserved_mapping
from rdetoolkit.core.injection import resolve_flow_kwargs
from rdetoolkit.errors import ERROR_CATALOG, RdeError, RdeExecutionError
from rdetoolkit.report.events import Event, EventSink
from rdetoolkit.report.failure import FailureDiagnostic
from rdetoolkit.runner.finalize import processing_error_record
from rdetoolkit.types import RdeConfig


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result of one eager flow execution for a single tile."""

    iteration_index: int
    status: Literal["completed", "failed"]
    call_records: tuple[NodeCallRecord, ...]
    outputs: tuple[TypeSummary, ...]
    error: dict[str, Any] | None = None
    datatile_id: str = ""
    title: str = ""
    target: str | None = None
    stacktrace: str | None = None
    #: Phase-aware diagnostic of a failed tile (#686). The Runner moves it to
    #: the diagnostics sidecar; it is in neither the run report nor the
    #: per-iteration detail file.
    diagnostic: FailureDiagnostic | None = None


class InvocationEventEmitter:
    """Turn the recorder's in-flight notifications into events (#689).

    The events are written as the node runs -- unlike the ``node.started`` /
    ``node.completed`` / ``node.failed`` replay after the tile -- so a
    ``FileEventSink`` (which flushes every line) holds the start of a node
    whose process died before it returned. Failures to write are the
    recorder's to contain; this adapter only maps fields.

    Args:
        event_sink: Sink receiving the events.
        run_id: Current run identifier.
    """

    def __init__(self, event_sink: EventSink, *, run_id: str) -> None:
        self._event_sink = event_sink
        self._run_id = run_id

    def invocation_started(self, invocation: NodeInvocation) -> None:
        """Emit ``node.invocation_started``.

        Args:
            invocation: The invocation whose body is about to run.
        """
        self._event_sink.emit(
            Event.node_invocation_started(
                run_id=self._run_id,
                node_id=invocation.node_id,
                invocation_id=invocation.invocation_id,
                iteration_index=invocation.iteration_index,
                parent_invocation_id=invocation.parent_invocation_id,
            ),
        )

    def invocation_finished(self, invocation: NodeInvocation, record: NodeCallRecord) -> None:
        """Emit ``node.invocation_finished`` correlated to the recorded call.

        Args:
            invocation: The invocation that ended.
            record: Its call-log record.
        """
        error = record.error or {}
        self._event_sink.emit(
            Event.node_invocation_finished(
                run_id=self._run_id,
                node_id=invocation.node_id,
                invocation_id=invocation.invocation_id,
                iteration_index=invocation.iteration_index,
                outcome=record.status,
                call_id=record.call_id,
                duration_ms=record.duration_ms,
                error_type=str(error.get("type", "")),
            ),
        )


class TileExecutionError(RdeExecutionError):
    """Catalogued tile failure carrying the recorder's primary snapshot."""

    def __init__(self, result: ExecutionResult, cause: Exception) -> None:
        error = result.error or _failed_error(cause, result.call_records)
        super().__init__(
            code=int(error["code"]),
            name=str(error["name"]),
            message=str(error["message"]),
            call_id=str(error.get("call_id", "")) or None,
        )
        self.result = result


def run_tile(
    flow_fn: Callable[..., Any],
    run_context: RunContext,
    *,
    event_sink: EventSink,
    run_id: str,
    config: RdeConfig,
    emit_iteration_events: bool = True,
    sequence: CallSequence | None = None,
) -> ExecutionResult:
    """Execute one tile by injecting reserved values and calling the flow eagerly.

    Args:
        flow_fn: Flow function to execute.
        run_context: Per-tile reserved values.
        event_sink: Sink receiving iteration lifecycle events.
        run_id: Current run identifier.
        config: Effective Runner configuration.
        emit_iteration_events: Whether this direct tile call owns iteration
            boundary events. Runner.iterate disables this and emits a wider
            boundary that also covers invoice preparation.
        sequence: The run's call counter (Design §3.4). The Runner passes one
            per run so ``seq`` and ``call_id`` keep increasing across tiles;
            ``None`` numbers this tile's calls from 1 on a private counter.

    Returns:
        Completed tile execution result.
    """
    if run_context.iteration is None:
        msg = "RunContext.iteration is required for tile execution."
        raise ValueError(msg)

    iteration_index = run_context.iteration.index
    kwargs = resolve_flow_kwargs(_flow_for_di(flow_fn), run_context)
    if emit_iteration_events:
        event_sink.emit(Event.iteration_started(run_id=run_id, index=iteration_index))
    recorder = CallLogRecorder(
        repr_head=config.provenance.repr_head,
        repr_head_len=config.provenance.repr_head_len,
        type_check=config.execution.type_check,
        iteration_index=iteration_index,
        sequence=sequence,
        invocation_listener=InvocationEventEmitter(event_sink, run_id=run_id),
    )
    try:
        with recorder:
            result = flow_fn(**kwargs)
    except Exception as exc:
        _emit_node_events(event_sink, run_id=run_id, records=recorder.records)
        if emit_iteration_events:
            event_sink.emit(Event.iteration_completed(run_id=run_id, index=iteration_index))
        error = _failed_error(exc, recorder.records)
        failed = ExecutionResult(
            iteration_index=iteration_index,
            status="failed",
            call_records=recorder.records,
            outputs=(),
            error=error,
            datatile_id=_datatile_id(run_context),
            stacktrace=traceback.format_exc(),
        )
        raise TileExecutionError(failed, exc) from exc
    outputs = _summarize_outputs(
        result,
        repr_head=config.provenance.repr_head,
        repr_head_len=config.provenance.repr_head_len,
    )
    _emit_node_events(event_sink, run_id=run_id, records=recorder.records)
    if emit_iteration_events:
        event_sink.emit(Event.iteration_completed(run_id=run_id, index=iteration_index))
    return ExecutionResult(
        iteration_index=iteration_index,
        status="completed",
        call_records=recorder.records,
        outputs=outputs,
        error=None,
        datatile_id=_datatile_id(run_context),
    )


#: Remediation for a plain exception escaping a v1 dataset callback (#783).
_CALLBACK_FAILURE_REMEDIATION = (
    "Inspect the chained original exception (__cause__); raise StructuredError "
    "(or ProcessingError) in the callback to choose the code and message."
)


def _failed_error(
    exc: Exception,
    records: tuple[NodeCallRecord, ...],
    *,
    callback_id: str | None = None,
) -> dict[str, Any]:
    """Return the tile error record for ``exc``.

    Args:
        exc: Exception that escaped the flow or the v1 dataset callback.
        records: Call records observed before the failure.
        callback_id: The v1 dataset callback's flow id when the tile ran one.
            A plain exception it raises outside any ``@node`` call keeps code
            3001 but names the callback: the catalogue wording points at a node
            call and its call-log entry, which the callback does not have.

    Returns:
        The error record (code, name, message, remediation, call_id).
    """
    error_def = ERROR_CATALOG[3001]
    failed_record = next((record for record in reversed(records) if record.status == "failed"), None)
    call_id = failed_record.call_id if failed_record is not None else "unknown"
    processing = processing_error_record(exc)
    if processing is not None:
        return {**processing, "call_id": call_id}
    if isinstance(exc, RdeError) and isinstance(exc.code, int):
        code = exc.code
        catalog_entry = ERROR_CATALOG.get(code, error_def)
        name = exc.name
        message = exc.message
    elif failed_record is None and callback_id is not None:
        return {
            "code": 3001,
            "name": error_def.name,
            "message": (
                f"Dataset callback {callback_id} failed ({type(exc).__name__}): {exc} "
                f"Remediation: {_CALLBACK_FAILURE_REMEDIATION}"
            ),
            "remediation": _CALLBACK_FAILURE_REMEDIATION,
            "call_id": call_id,
        }
    else:
        code = 3001
        catalog_entry = error_def
        name = error_def.name
        message = error_def.message_template.format(call_id=call_id, reason=str(exc))
    if "Remediation:" not in message:
        message = f"{message} Remediation: {catalog_entry.remediation}"
    return {
        "code": code,
        "name": name,
        "message": message,
        "remediation": catalog_entry.remediation,
        "call_id": call_id,
    }


def _datatile_id(run_context: RunContext) -> str:
    """Return a deterministic tile id from the first raw-file stem.

    Tiles without raw files use their decimal iteration index. This keeps the
    identifier stable without introducing timestamps or random values.
    """
    paths = run_context.paths
    if paths is not None and paths.rawfiles:
        return paths.rawfiles[0].stem
    if run_context.iteration is None:
        return "0"
    return str(run_context.iteration.index)


def _emit_node_events(event_sink: EventSink, *, run_id: str, records: tuple[NodeCallRecord, ...]) -> None:
    for record in sorted(records, key=lambda item: item.seq):
        event_sink.emit(Event.node_started(run_id=run_id, node_id=record.node_id, call_id=record.call_id))
        if record.status == "failed":
            error = record.error or {}
            event_sink.emit(
                Event.node_failed(
                    run_id=run_id,
                    node_id=record.node_id,
                    call_id=record.call_id,
                    error_type=str(error.get("type", "")),
                    error_msg=str(error.get("message", "")),
                ),
            )
            continue
        event_sink.emit(
            Event.node_completed(
                run_id=run_id,
                node_id=record.node_id,
                call_id=record.call_id,
                duration_ms=record.duration_ms,
            ),
        )


def _flow_for_di(flow_fn: Callable[..., Any]) -> Callable[..., Any]:
    signature = inspect.signature(flow_fn)
    reserved_by_name = {reserved_type.__name__: reserved_type for reserved_type in get_reserved_mapping().values()}
    parameters: list[inspect.Parameter] = []
    changed = False
    for parameter in signature.parameters.values():
        annotation = parameter.annotation
        if isinstance(annotation, str) and annotation in reserved_by_name:
            annotation = reserved_by_name[annotation]
            changed = True
        parameters.append(parameter.replace(annotation=annotation))

    if not changed:
        return flow_fn

    resolved_signature = signature.replace(parameters=parameters)
    flow_fn.__signature__ = resolved_signature  # type: ignore[attr-defined]
    flow_fn.__annotations__ = {parameter.name: parameter.annotation for parameter in parameters if parameter.annotation is not inspect.Signature.empty}
    if signature.return_annotation is not inspect.Signature.empty:
        flow_fn.__annotations__["return"] = signature.return_annotation
    return flow_fn
