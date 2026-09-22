"""Common tile execution for planned v2 Runner work."""

from __future__ import annotations

import contextlib
import traceback
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError
from rdetoolkit.domain.validation import validate_tile_outputs, wrap_validation_error
from rdetoolkit.modes.protocol import RawCopyStrategy
from rdetoolkit.modes.registry import handler_for
from rdetoolkit.report.events import EventSink
from rdetoolkit.runner.execute import ExecutionResult, TileExecutionError
from rdetoolkit.runner.finalize import structured_error_record
from rdetoolkit.runner.invoker import FlowInvoker, TargetInvoker
from rdetoolkit.runner.planner import TileMaterial, TilePreparation


if TYPE_CHECKING:
    from rdetoolkit.runner.planner import ExecutionPlan, TilePlan


#: The image stage is owned by the executor, not by the invoice service, so it
#: is named in the same sequence to keep one ordering authority per mode.
_THUMBNAIL_STAGE = "thumbnail"

_RUN_INTERRUPTED_CODE = 3004
_ARTIFACT_PUBLICATION_FAILED_CODE = 3005
_INVOICE_ARTIFACT_FAILED_CODE = 3006


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
        self._event_sink = event_sink
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
            if _is_run_interrupted(exc):
                raise
            if isinstance(exc, TileExecutionError):
                return _with_legacy_metadata(
                    _with_user_error(exc.result, exc.__cause__),
                    invoice=invoice,
                    rawfiles=tile.paths.rawfiles,
                    root=plan.root,
                )
            result = ExecutionResult(
                iteration_index=tile.iteration.index,
                status="failed",
                call_records=(),
                outputs=(),
                error=_stage_record(exc) if isinstance(exc, _StagePublicationError) else _execution_error(exc),
                datatile_id=_datatile_id(tile.paths.rawfiles, tile.iteration.index),
                stacktrace=traceback.format_exc() if isinstance(exc, _StagePublicationError) else None,
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
            )
        return result

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
        raise wrap_validation_error(exc) from exc


def _tile_material(plan: ExecutionPlan, preparation: TilePreparation) -> TileMaterial:
    """Bundle the run-owned material one tile hands to its invoker.

    Carrying it by value is what replaced the module-global row-data handoff
    and the filesystem-probing invoice-source resolver (rulings #2 and #3).
    """
    return TileMaterial(
        invoice_source=plan.invoice_source,
        smarttable_row_data=preparation.smarttable_row_data,
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
        if _is_run_interrupted(exc):
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


def _is_run_interrupted(exc: Exception) -> bool:
    return isinstance(exc, RdeExecutionError) and exc.code == _RUN_INTERRUPTED_CODE


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
    # A StructuredError carries ecode/emsg, not code/message (Design §6.3).
    passthrough = structured_error_record(exc)
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
    """Attach compatibility inputs while they are available at the tile boundary."""
    title = result.datatile_id
    if invoice is not None:
        basic = invoice.raw.get("basic")
        if isinstance(basic, dict) and isinstance(basic.get("dataName"), str):
            title = basic["dataName"]
    target = _legacy_target(rawfiles, root=root)
    return replace(result, title=title, target=target)


def _legacy_target(rawfiles: tuple[Path, ...], *, root: Path) -> str | None:
    if not rawfiles:
        return None
    basedir = rawfiles[0].parent
    with contextlib.suppress(ValueError):
        basedir = basedir.relative_to(root)
    return basedir.as_posix()
