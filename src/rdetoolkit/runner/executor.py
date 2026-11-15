"""Common tile execution for planned v2 Runner work."""

from __future__ import annotations

import contextlib
import traceback
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdetoolkit._interrupt import is_run_interrupted
from rdetoolkit.core.context import RunContext
from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.domain.invoice_service import (
    INVOICE_STEP_DESCRIPTION,
    INVOICE_STEP_MAGIC,
    INVOICE_STEP_STRUCTURED,
    InvoiceService,
    build_tile_dataset_paths,
)
from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.errors import ERROR_CATALOG
from rdetoolkit.domain.validation import validate_tile_outputs, wrap_validation_error
from rdetoolkit.modes.protocol import RawCopyStrategy
from rdetoolkit.modes.registry import handler_for
from rdetoolkit.report.events import Event, EventSink, _best_effort_stderr
from rdetoolkit.report.failure import FailureDiagnostic, FailurePhase, failure_diagnostic, node_argument_rejection
from rdetoolkit.runner.execute import ExecutionResult, TileExecutionError
from rdetoolkit.runner.finalize import processing_error_record, structured_error_record
from rdetoolkit.runner.invoker import FlowInvoker, TargetInvoker
from rdetoolkit.runner.planner import TileMaterial, TilePreparation


if TYPE_CHECKING:
    from rdetoolkit.runner.planner import ExecutionPlan, TilePlan


#: The image stage is owned by the executor, not by the invoice service, so it
#: is named in the same sequence to keep one ordering authority per mode.
_THUMBNAIL_STAGE = "thumbnail"

_ARTIFACT_PUBLICATION_FAILED_CODE = 3005
_INVOICE_ARTIFACT_FAILED_CODE = 3006
_METADATA_INVALID_CODE = 4002


class _BestEffortEventSink:
    """Runner-side guard that keeps event-log failures out of the run's outcome.

    The event log is diagnostics (Session K4-F3): a failing write must never
    replace a node's error, empty the call log, or fail a successful run. So
    ``open`` and ``emit`` swallow ordinary exceptions, write one best-effort
    stderr line, and mute the rest of that run's events -- a log with a hole
    in the middle would read as a complete record of a different run. The
    mute is keyed on the run id, so a long-lived executor that outlives one
    broken run records the next run again.

    ``emit_final`` and ``close`` deliberately stay strict: the F2 shutdown
    contract maps a failing ``run.completed`` write or close to 5001 once the
    report and ``job.failed`` are persisted, and the Runner owns that mapping.
    A catalogued run interruption (3004, raised by the SIGTERM handler while a
    write is in progress) always propagates.

    Args:
        inner: The sink receiving the events.
    """

    def __init__(self, inner: EventSink) -> None:
        self.inner = inner
        self._muted_run_id: str | None = None
        self._open_failed = False

    def open(self, run_id: str) -> None:
        """Open the inner sink; a failure means "no event log for this run".

        Args:
            run_id: Run identifier.
        """
        self._muted_run_id = None
        self._open_failed = False
        try:
            self.inner.open(run_id)
        except Exception as exc:  # noqa: BLE001
            if is_run_interrupted(exc):
                raise
            self._open_failed = True
            self._muted_run_id = run_id
            _best_effort_stderr(f"rdetoolkit: event log could not be opened; this run is not recorded in it (the run continues): {type(exc).__name__}: {exc}\n")

    def emit(self, event: Event) -> None:
        """Forward an event; a failure mutes the rest of this run's events.

        Args:
            event: Event to forward.
        """
        if event.run_id == self._muted_run_id:
            return
        try:
            self.inner.emit(event)
        except Exception as exc:  # noqa: BLE001
            if is_run_interrupted(exc):
                raise
            self._muted_run_id = event.run_id
            _best_effort_stderr(f"rdetoolkit: event log write failed; later events of this run are not recorded (the run continues): {type(exc).__name__}: {exc}\n")

    def emit_final(self, event: Event) -> None:
        """Forward the closing event strictly, unless this run's log is muted.

        Args:
            event: The ``run.completed`` event.
        """
        if event.run_id == self._muted_run_id:
            return
        self.inner.emit(event)

    def close(self) -> None:
        """Close the inner sink strictly, unless it never opened for this run."""
        if self._open_failed:
            return
        self.inner.close()


class TileExecutor:
    """Execute planned tiles through the invoker registered for their target."""

    def __init__(
        self,
        *,
        event_sink: EventSink,
        flow_invoker: TargetInvoker | None = None,
        raw_artifact_service: RawArtifactService | None = None,
        image_artifact_service: ImageArtifactService | None = None,
        invoice_service: InvoiceService | None = None,
    ) -> None:
        """Create a tile executor.

        Args:
            event_sink: Sink receiving node events from the eager execution core.
            flow_invoker: Optional flow adapter used by tests or alternate hosts.
            raw_artifact_service: Optional completed-tile raw publisher.
            image_artifact_service: Optional completed-tile image publisher.
            invoice_service: Run-owned invoice artifact operations.
        """
        # Wrapped here because every node / iteration event of a tile is
        # emitted below this executor (K4-F3 ruling R1); a sink the Runner
        # already wrapped is shared so both see the same mute state.
        self._event_sink = event_sink if isinstance(event_sink, _BestEffortEventSink) else _BestEffortEventSink(event_sink)
        self._flow_invoker = flow_invoker or FlowInvoker()
        self._raw_artifact_service = raw_artifact_service
        self._image_artifact_service = image_artifact_service
        self._invoice_service = invoice_service or InvoiceService()

    def execute(self, plan: ExecutionPlan, tile: TilePlan) -> ExecutionResult:
        """Execute one tile and normalize ordinary failures into a result.

        Args:
            plan: Immutable run execution plan.
            tile: Per-tile paths, iteration data, and invoice preparation.

        Returns:
            Completed or failed primary execution result.
        """
        invoice = tile.invoice
        preparation = TilePreparation(invoice=tile.invoice)
        # Which part of the tile a failure belongs to (#686). Node failures and
        # artifact-stage failures carry their own type; everything else that
        # fails before the flow body is tile preparation.
        phase: FailurePhase = "tile_prepare"
        try:
            if tile.prepare_invoice is not None:
                preparation = tile.prepare_invoice()
            invoice = preparation.invoice
            context = RunContext(
                paths=tile.paths,
                out=tile.out,
                config=plan.config,
                invoice=invoice,
                iteration=tile.iteration,
            )
            # v1 copies raw inputs BEFORE the dataset callback runs: FileCopier /
            # RDEFormatFileCopier / SmartTableFileCopier all precede DatasetRunner
            # in processing/factories.py. A tile that fails therefore still leaves
            # raw/ and nonshared_raw/ populated, exactly as v1 does.
            self._publish_raw(plan, tile)
            if tile.precompleted:
                # v1's EarlyExit validates the tile and only then skips the
                # rest of the pipeline, so the check belongs *before* the tile
                # is recorded as completed (ruling #6). Validating afterwards
                # let flows run that v1 never reached (review R5).
                phase = "post_validate"
                _validate_precompleted_tile(tile)
                # The mode already finished this tile. v1's SmartTable
                # EarlyExit is the case: it writes the tile invoice, lets the
                # raw stage above copy the table, and raises
                # SkipRemainingProcessorsError before the dataset callback.
                # Recording a completed iteration with an empty call log keeps
                # the tile visible in the RunReport while nothing after the raw
                # stage runs; Runner.post_validate still validates its invoice,
                # as v1's EarlyExit validated before skipping.
                return _with_legacy_metadata(
                    _precompleted_result(tile),
                    invoice=invoice,
                    rawfiles=tile.paths.rawfiles,
                    root=plan.root,
                )
            result = _with_legacy_metadata(
                self._flow_invoker.invoke(
                    plan.target,
                    context,
                    event_sink=self._event_sink,
                    run_id=plan.run_id,
                    config=plan.config,
                    material=_tile_material(plan, preparation),
                ),
                invoice=invoice,
                rawfiles=tile.paths.rawfiles,
                root=plan.root,
            )
        except Exception as exc:  # noqa: BLE001
            if is_run_interrupted(exc):
                raise
            if isinstance(exc, TileExecutionError):
                return _with_legacy_metadata(
                    self._diagnosed_node_failure(plan, _with_user_error(exc.result, exc.__cause__), exc),
                    invoice=invoice,
                    rawfiles=tile.paths.rawfiles,
                    root=plan.root,
                )
            error = _stage_record(exc) if isinstance(exc, _StagePublicationError) else _execution_error(exc)
            result = ExecutionResult(
                iteration_index=tile.iteration.index,
                status="failed",
                call_records=(),
                outputs=(),
                error=error,
                datatile_id=_datatile_id(tile.paths.rawfiles, tile.iteration.index),
                stacktrace=traceback.format_exc() if isinstance(exc, _StagePublicationError) else None,
                diagnostic=_tile_failure_diagnostic(plan, tile, exc, phase=phase, error=error),
            )
            return _with_legacy_metadata(
                result,
                invoice=invoice,
                rawfiles=tile.paths.rawfiles,
                root=plan.root,
            )

        # The v1 processors after DatasetRunner never run when the callback
        # raises, so the post-invoke stage is completed-tiles only.
        if result.status != "completed":
            return result
        try:
            self._publish_post_invoke(plan, tile)
        except _StagePublicationError as exc:
            return replace(
                result,
                status="failed",
                error=exc.record,
                stacktrace=traceback.format_exc(),
                target=_legacy_failed_target(tile.paths.rawfiles, root=plan.root),
                diagnostic=_tile_failure_diagnostic(plan, tile, exc, phase="artifact_publish", error=exc.record),
            )
        return result

    def _diagnosed_node_failure(self, plan: ExecutionPlan, result: ExecutionResult, exc: TileExecutionError) -> ExecutionResult:
        """Attach the diagnostic of a failed flow call, and announce an argument rejection.

        The diagnostic is built from the exception the flow raised (the
        wrapper's ``__cause__``), so its location is the user's source line.
        A strict-mode argument rejection (#688) is phase
        ``node_argument_validation``: the rejected node never ran, so no
        ``call_id`` is claimed for it and the call log is left untouched; an
        additive ``node.argument_rejected`` event names the node and
        parameter.

        Args:
            plan: Immutable run execution plan.
            result: The failed result, user error already restored.
            exc: The tile failure the invoker raised.

        Returns:
            ``result`` with its diagnostic.
        """
        origin = exc.__cause__ if exc.__cause__ is not None else exc
        rejection = node_argument_rejection(origin)
        call_id = _recorded_call_id(result)
        node_id = next((record.node_id for record in result.call_records if record.call_id == call_id), None)
        if rejection is not None:
            self._event_sink.emit(
                Event.node_argument_rejected(
                    run_id=plan.run_id,
                    node_id=str(rejection.get("node_id") or "unknown"),
                    iteration_index=result.iteration_index,
                    parameter=str(rejection.get("parameter", "")),
                    expected_type=str(rejection.get("expected_type", "")),
                    actual_type=str(rejection.get("actual_type", "")),
                ),
            )
        diagnostic = _guarded_diagnostic(
            lambda: failure_diagnostic(
                origin,
                phase="node_argument_validation" if rejection is not None else "node_execution",
                error=result.error,
                root=plan.root,
                iteration_index=result.iteration_index,
                node_id=node_id,
                call_id=None if rejection is not None else call_id,
            ),
        )
        return replace(result, diagnostic=diagnostic)

    def _publish_post_invoke(self, plan: ExecutionPlan, tile: TilePlan) -> None:
        """Publish the artifacts v1 produces after the dataset callback.

        The sequence is mode-owned (Session I-REVIEW-A ruling #5). v1's invoice
        pipeline is ThumbnailGenerator -> StructuredInvoiceSaver ->
        VariableApplier -> DescriptionUpdater, while MultiDataTile and
        ExcelInvoice expand magic variables first; running one fixed order for
        every mode changes which artifacts a failing tile leaves behind
        (review R3).
        """
        dataset_paths = build_tile_dataset_paths(
            paths=tile.paths,
            out=tile.out,
            invoice_org=plan.invoice_source,
        )
        for step in artifact_stage_order(plan):
            if step == _THUMBNAIL_STAGE:
                self._publish_images(plan, tile)
                continue
            self._publish_invoice_step(plan, step, dataset_paths)

    def _publish_raw(self, plan: ExecutionPlan, tile: TilePlan) -> None:
        """Copy raw inputs through the mode strategy, or the generic service."""
        with _publication_guard(_publication_error):
            strategy = _raw_copy_strategy(plan)
            service: RawCopyStrategy | None = strategy if strategy is not None else self._raw_artifact_service
            if service is None:
                return
            service.copy(
                tile.paths.rawfiles,
                raw_dir=tile.out.raw,
                nonshared_raw_dir=tile.out.nonshared_raw,
                config=plan.config,
                smarttable=plan.mode.value == "smarttable",
                data_root=plan.data_root,
            )

    def _publish_images(self, plan: ExecutionPlan, tile: TilePlan) -> None:
        """Generate the configured thumbnail artifacts for a completed tile."""
        with _publication_guard(_publication_error):
            if self._image_artifact_service is None:
                return
            self._image_artifact_service.generate(
                main_image_dir=tile.out.main_image,
                thumbnail_dir=tile.out.thumbnail,
                config=plan.config,
            )

    def _publish_invoice_step(
        self,
        plan: ExecutionPlan,
        step: str,
        dataset_paths: RdeDatasetPaths,
    ) -> None:
        """Apply one structured / magic-variable / description invoice step."""
        with _publication_guard(_invoice_stage_error):
            self._invoice_service.apply_step(
                step,
                config=plan.config,
                dataset_paths=dataset_paths,
            )


def _guarded_diagnostic(build: Callable[[], FailureDiagnostic]) -> FailureDiagnostic | None:
    """Build a diagnostic; a defect in diagnosing never changes the tile outcome."""
    try:
        return build()
    except Exception as exc:  # noqa: BLE001
        if is_run_interrupted(exc):
            raise
        _best_effort_stderr(f"rdetoolkit: a tile failure could not be diagnosed (the outcome is unchanged): {type(exc).__name__}\n")
        return None


def _recorded_call_id(result: ExecutionResult) -> str | None:
    """Return the executed call the tile error names, or ``None`` when there is none."""
    call_id = (result.error or {}).get("call_id")
    return call_id if isinstance(call_id, str) and call_id and call_id != "unknown" else None


def _tile_failure_diagnostic(
    plan: ExecutionPlan,
    tile: TilePlan,
    exc: Exception,
    *,
    phase: FailurePhase,
    error: dict[str, Any],
) -> FailureDiagnostic | None:
    """Diagnose a tile failure outside the flow body (#686).

    An artifact-stage failure is diagnosed from the I/O error the stage
    wrapped, so its location is not the guard that attributed it.

    Args:
        plan: Immutable run execution plan.
        tile: The failed tile.
        exc: The failure.
        phase: Phase reached when it failed.
        error: The published tile error record.

    Returns:
        The diagnostic, or ``None`` if diagnosing itself failed.
    """
    origin: BaseException = exc
    if isinstance(exc, _StagePublicationError):
        phase = "artifact_publish"
        origin = exc.__cause__ if exc.__cause__ is not None else exc
    artifact_path = _validated_artifact(plan, tile, error) if phase == "post_validate" else None
    return _guarded_diagnostic(
        lambda: failure_diagnostic(
            origin,
            phase=phase,
            error=error,
            root=plan.root,
            iteration_index=tile.iteration.index,
            artifact_path=artifact_path,
        ),
    )


def _validated_artifact(plan: ExecutionPlan, tile: TilePlan, error: dict[str, Any]) -> str:
    """Name the tile artifact a per-tile validation code is about, data-root relative."""
    path = tile.out.meta / "metadata.json" if error.get("code") == _METADATA_INVALID_CODE else tile.out.invoice / "invoice.json"
    with contextlib.suppress(ValueError):
        return path.relative_to(plan.data_root).as_posix()
    return path.name


def _validate_precompleted_tile(tile: TilePlan) -> None:
    """Apply the per-tile artifact contract to a mode-completed tile.

    Args:
        tile: Tile the mode marked as pre-completed.

    Raises:
        RdeValidationError: If the tile's invoice or metadata does not validate.
            The tile boundary turns it into an ordinary iteration failure, so
            ``fail_fast`` aborts the run exactly where v1 did.
    """
    try:
        validate_tile_outputs(
            invoice_path=tile.out.invoice / "invoice.json",
            schema_path=tile.paths.tasksupport / "invoice.schema.json",
            metadata_path=tile.out.meta / "metadata.json",
        )
    except Exception as exc:  # noqa: BLE001
        # A stopped run is not an invalid tile: keep 3004 (review rc1 F01).
        if is_run_interrupted(exc):
            raise
        raise wrap_validation_error(exc) from exc


def _tile_material(plan: ExecutionPlan, preparation: TilePreparation) -> TileMaterial:
    """Bundle the run-owned material one tile hands to its invoker.

    Carrying it by value is what replaced the module-global row-data handoff
    and the filesystem-probing invoice-source resolver (rulings #2 and #3).
    """
    return TileMaterial(
        invoice_source=plan.invoice_source,
        smarttable_row_data=preparation.smarttable_row_data,
        call_sequence=plan.call_sequence,
    )


def _precompleted_result(tile: TilePlan) -> ExecutionResult:
    """Return the result of a tile the mode completed without the flow.

    Args:
        tile: Tile the mode marked as pre-completed.

    Returns:
        A completed result with no call records and no outputs, because no
        flow — and therefore no node — ran for this tile.
    """
    return ExecutionResult(
        iteration_index=tile.iteration.index,
        status="completed",
        call_records=(),
        outputs=(),
        error=None,
        datatile_id=_datatile_id(tile.paths.rawfiles, tile.iteration.index),
    )


class _StagePublicationError(Exception):
    """Carry a catalogued artifact-stage failure to the tile boundary."""

    def __init__(self, record: dict[str, Any]) -> None:
        super().__init__(str(record.get("message", "")))
        self.record = record


@contextlib.contextmanager
def _publication_guard(error_factory: Callable[[Exception], dict[str, Any]]) -> Iterator[None]:
    """Attribute failures of one artifact stage to that stage's error class.

    Guards are never nested: each stage wraps exactly one body, so an already
    attributed failure cannot reach a second guard.
    """
    try:
        yield
    except Exception as exc:
        if is_run_interrupted(exc):
            raise
        raise _StagePublicationError(error_factory(exc)) from exc


def _stage_record(exc: _StagePublicationError) -> dict[str, Any]:
    return exc.record


def _raw_copy_strategy(plan: ExecutionPlan) -> RawCopyStrategy | None:
    """Return the mode-owned raw copy strategy, when one is installed."""
    handler = handler_for(plan.mode)
    provider = getattr(handler, "raw_copy_strategy", None)
    if provider is None:
        return None
    return provider(plan)


#: The v1 invoice/SmartTable pipeline order, used when a mode declares none.
DEFAULT_ARTIFACT_STAGE_ORDER: tuple[str, ...] = (
    _THUMBNAIL_STAGE,
    INVOICE_STEP_STRUCTURED,
    INVOICE_STEP_MAGIC,
    INVOICE_STEP_DESCRIPTION,
)


def artifact_stage_order(plan: ExecutionPlan) -> tuple[str, ...]:
    """Return the ordered post-invoke artifact stages this mode runs.

    The sequence — not a set — is the contract (ruling #5): v1's MultiDataTile
    and ExcelInvoice pipelines run ``VariableApplier`` before the thumbnail and
    structured stages, and RDEFormat runs neither the structured export nor the
    magic expansion at all. The capability stays optional and is read through
    ``getattr``, so a handler that declares only ``kind``/``create_tiles``
    remains valid at runtime *and* in the type system (ruling #8).

    Args:
        plan: Immutable run execution plan.

    Returns:
        The ordered stage names, defaulting to the v1 invoice pipeline's.
    """
    handler = handler_for(plan.mode)
    provider = getattr(handler, "artifact_stage_order", None)
    if provider is None:
        return DEFAULT_ARTIFACT_STAGE_ORDER
    order = provider(plan)
    return DEFAULT_ARTIFACT_STAGE_ORDER if order is None else tuple(order)


#: Fields the passthrough record owns. ``remediation`` is included because it
#: is derived from the catalog code being replaced, so keeping the wrapper's
#: 3001 remediation would describe an error the run no longer reports.
_PASSTHROUGH_OWNED_KEYS = frozenset({"code", "name", "message", "remediation"})


def _with_user_error(result: ExecutionResult, cause: BaseException | None) -> ExecutionResult:
    """Restore a ``StructuredError``'s ``ecode``/``emsg`` on a wrapped result.

    ``run_tile`` catalogues every flow failure as 3001 before raising, so the
    raised code would otherwise be lost at the tile boundary. Only the
    catalogued fields are replaced: recorder context such as ``call_id`` stays
    on the record so the failing call remains identifiable.
    """
    passthrough = structured_error_record(cause)
    if passthrough is None:
        return result
    preserved = {key: value for key, value in (result.error or {}).items() if key not in _PASSTHROUGH_OWNED_KEYS}
    return replace(result, error={**preserved, **passthrough})


def _publication_error(exc: Exception) -> dict[str, Any]:
    """Attribute a raw/thumbnail publication failure to the framework (#8b).

    These stages only move files, so a failure is an output-side I/O problem
    and the remediation must point there instead of at the user's node.
    """
    return _catalogued_stage_error(_ARTIFACT_PUBLICATION_FAILED_CODE, exc)


def _invoice_stage_error(exc: Exception) -> dict[str, Any]:
    """Attribute an invoice artifact-stage failure.

    The structured / magic-variable / description steps run v1 invoice helpers
    that raise ``StructuredError`` for genuine data problems (an unresolvable
    magic variable, for example). v1 surfaced those verbatim through
    ``catch_exception_with_message``, so the I6-0 passthrough applies. Anything
    else is a framework failure of the invoice stage itself, which is a
    different remediation from a raw-copy I/O error.
    """
    passthrough = structured_error_record(exc)
    if passthrough is not None:
        return passthrough
    return _catalogued_stage_error(_INVOICE_ARTIFACT_FAILED_CODE, exc)


def _catalogued_stage_error(code: int, exc: Exception) -> dict[str, Any]:
    error_def = ERROR_CATALOG[code]
    return {
        "code": code,
        "name": error_def.name,
        "message": error_def.message_template.format(reason=f"{type(exc).__name__}: {exc}"),
        "remediation": error_def.remediation,
    }


def _execution_error(exc: Exception) -> dict[str, Any]:
    # A StructuredError carries ecode/emsg, not code/message (Design §6.3);
    # a ProcessingError carries its own remediation (#634).
    passthrough = structured_error_record(exc) or processing_error_record(exc)
    if passthrough is not None:
        return passthrough
    code = getattr(exc, "code", 3001)
    error_def = ERROR_CATALOG.get(code) if isinstance(code, int) else None
    return {
        "code": code,
        "name": getattr(exc, "name", error_def.name if error_def is not None else type(exc).__name__),
        "message": getattr(exc, "message", str(exc)),
        **({"remediation": error_def.remediation} if error_def is not None else {}),
    }


def _datatile_id(rawfiles: tuple[Path, ...], iteration_index: int) -> str:
    return rawfiles[0].stem if rawfiles else str(iteration_index)


def _with_legacy_metadata(
    result: ExecutionResult,
    *,
    invoice: Any,
    rawfiles: tuple[Path, ...],
    root: Path,
) -> ExecutionResult:
    """Attach compatibility inputs while they are available at the tile boundary.

    A failed tile names its raw files rather than their directory: v1's
    ``workflows._create_error_status`` wrote ``",".join(rawfiles)`` as the
    failed status's ``target``, and a v1 ``ignore_errors`` run *returns* those
    statuses, so the shape is observable v1 contract (Session J-REVIEW ruling
    #2, decision A). A completed tile keeps the directory form v1 reported.
    """
    title = result.datatile_id
    if invoice is not None:
        basic = invoice.raw.get("basic")
        if isinstance(basic, dict) and isinstance(basic.get("dataName"), str):
            title = basic["dataName"]
    target: str | None = (
        _legacy_failed_target(rawfiles, root=root) if result.status == "failed" else _legacy_target(rawfiles, root=root)
    )
    return replace(result, title=title, target=target)


def _legacy_failed_target(rawfiles: tuple[Path, ...], *, root: Path) -> str:
    """Return v1's failed-status target: every raw file, comma-joined."""
    return ",".join(_root_relative(path, root=root) for path in rawfiles)


def _root_relative(path: Path, *, root: Path) -> str:
    with contextlib.suppress(ValueError):
        path = path.relative_to(root)
    return path.as_posix()


def _legacy_target(rawfiles: tuple[Path, ...], *, root: Path) -> str:
    """Return v1's completed-status target, ``ProcessingContext.basedir``.

    v1 reports ``""`` for a tile without user files. Before v1.7 no SmartTable
    tile was ever empty (the row CSV sat in ``rawfiles``); since #503 a row
    that references no file has empty ``rawfiles`` and v1 publishes ``""``.
    """
    if not rawfiles:
        return ""
    basedir = rawfiles[0].parent
    with contextlib.suppress(ValueError):
        basedir = basedir.relative_to(root)
    return basedir.as_posix()
