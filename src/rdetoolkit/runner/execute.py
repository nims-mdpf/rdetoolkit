"""Single-tile eager flow execution for the v2 Runner."""

from __future__ import annotations

import inspect
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast

from rdetoolkit.core.calllog import CallLogRecorder, CallSequence, NodeCallRecord, TypeSummary
from rdetoolkit.core.context import RunContext, get_reserved_mapping
from rdetoolkit.core.injection import resolve_flow_kwargs
from rdetoolkit.errors import ERROR_CATALOG, RdeError, RdeExecutionError
from rdetoolkit.report.events import Event, EventSink
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


class TileExecutionError(RdeExecutionError):
    """Catalogued tile failure carrying the recorder's primary snapshot."""

    def __init__(self, result: ExecutionResult, cause: Exception) -> None:
        error = result.error or _failed_error(cause, result.call_records)
        super().__init__(  # type: ignore[call-arg]
            code=int(error["code"]),  # type: ignore[arg-type]
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
        type_check=cast("Literal['off', 'warn', 'strict']", config.execution.type_check),
        iteration_index=iteration_index,
        sequence=sequence,
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


def _summarize_outputs(value: Any, *, repr_head: str, repr_head_len: int) -> tuple[TypeSummary, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(_summarize(item, repr_head=repr_head, repr_head_len=repr_head_len) for item in value)
    return (_summarize(value, repr_head=repr_head, repr_head_len=repr_head_len),)


def _failed_error(exc: Exception, records: tuple[NodeCallRecord, ...]) -> dict[str, Any]:
    error_def = ERROR_CATALOG[3001]
    failed_record = next((record for record in reversed(records) if record.status == "failed"), None)
    call_id = failed_record.call_id if failed_record is not None else "unknown"
    if isinstance(exc, RdeError) and isinstance(exc.code, int):
        code = exc.code
        catalog_entry = ERROR_CATALOG.get(code, error_def)
        name = exc.name
        message = exc.message
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


def _summarize(value: Any, *, repr_head: str, repr_head_len: int) -> TypeSummary:
    return TypeSummary(
        type_name=_type_name(value),
        repr_head=_safe_repr_head(value, enabled=repr_head == "on", length=repr_head_len),
    )


def _type_name(value: Any) -> str:
    target = type(value)
    if target is type(None):
        return "None"
    if target.__module__ == "builtins":
        return target.__qualname__
    return f"{target.__module__}.{target.__qualname__}"


def _safe_repr_head(value: Any, *, enabled: bool, length: int) -> str | None:
    if not enabled:
        return None
    try:
        return repr(value)[:length]
    except Exception:  # noqa: BLE001
        return None


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
