"""Lazy execution planning for the v2 Runner."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Any, Literal

from rdetoolkit.api.request import ExecutionTarget, RunRequest
from rdetoolkit.domain.invoice_service import InvoiceService, invoice_source_for
from rdetoolkit.modes.protocol import PlanningContext
from rdetoolkit.modes.registry import handler_for
from rdetoolkit.runner.iterator import iterate_tiles
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig


@dataclass(frozen=True, slots=True)
class TilePreparation:
    """What preparing one tile produced (ruling #2).

    ``prepare_invoice`` used to return the tile invoice alone and stash the
    SmartTable row dictionary in a module-global keyed by data root. Returning
    both by value is what makes the handoff run-private: a second Runner on the
    same root has nothing to erase (reviews F1/R4).

    Attributes:
        invoice: The prepared tile invoice, or ``None`` when the mode builds none.
        smarttable_row_data: The row dictionary a v1 callback receives as
            ``RdeOutputResourcePath.smarttable_row_data``, or ``None``.
    """

    invoice: InvoiceData | None = None
    smarttable_row_data: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class TilePlan:
    """Immutable execution material for one tile.

    ``precompleted`` is the mode-owned skip seam (Session I6-C). A mode sets it
    on a tile whose work its own ``prepare_invoice`` already finished — v1's
    SmartTable EarlyExit tile is the only case today — and the executor then
    records the iteration as completed without invoking the flow and without
    the post-invoke invoice stage. The default keeps every other tile identical.
    """

    iteration: IterationInfo
    paths: InputPaths
    out: OutputContext
    invoice: InvoiceData | None
    prepare_invoice: Callable[[], TilePreparation] | None = None
    precompleted: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Immutable run plan with lazily produced tile plans."""

    run_id: str
    target: ExecutionTarget
    mode: ModeKind
    config: RdeConfig
    root: Path
    error_policy: Literal["continue", "fail_fast"]
    tiles: Iterable[TilePlan]
    #: The single data root resolved by the Runner before anything was created
    #: (ruling #1). Every consumer reads it from here instead of re-deriving it.
    data_root: Path
    #: The run-level ``invoice_org`` chosen once by the v1 mode rule (ruling
    #: #3). Artifact publication, magic variables and the v1 callback all read
    #: this decision instead of re-deciding it from what exists on disk.
    invoice_source: Path


@dataclass(frozen=True, slots=True)
class TileMaterial:
    """Run-owned material one tile hands to its invoker (ruling #2/#3).

    This is deliberately *not* part of ``RunContext``: the reserved DI types
    are a public contract (Design §7), while this bundle is an internal
    Runner -> invoker channel. Carrying it by value replaces the module-global
    process-global row-data handoff, which two runs over one root could erase
    for each other (reviews F1/R4).

    Attributes:
        invoice_source: The run-level ``invoice_org`` the plan decided.
        smarttable_row_data: The row dictionary the SmartTable builder computed
            for this tile, or ``None`` for every other tile.
    """

    invoice_source: Path
    smarttable_row_data: Mapping[str, Any] | None = None


@dataclass(slots=True)
class _InvoiceSourceState:
    path: Path
    prepared: bool


PathProvider = Path | Callable[[], Path]


class RunPlanner:
    """Convert a normalized request into one lazy common execution plan."""

    def __init__(
        self,
        *,
        inputdata_path: PathProvider,
        unpacked_dir_path: PathProvider,
        run_id_factory: Callable[[], str],
        invoice_service: InvoiceService | None = None,
    ) -> None:
        """Create a planner.

        Args:
            inputdata_path: Current input directory or a lazy path provider.
            unpacked_dir_path: Current unpack directory or a lazy path provider.
            run_id_factory: Provider for the active Runner run identifier.
            invoice_service: Run-owned path-based invoice operations.
        """
        self._inputdata_path = inputdata_path
        self._unpacked_dir_path = unpacked_dir_path
        self._run_id_factory = run_id_factory
        self._invoice_service = invoice_service or InvoiceService()

    def create(
        self,
        request: RunRequest,
        *,
        config: RdeConfig,
        mode: ModeKind,
        data_root: Path,
    ) -> ExecutionPlan:
        """Create an execution plan without eagerly enumerating tiles.

        Args:
            request: Normalized run request.
            config: Effective canonical configuration.
            mode: Resolved internal mode.
            data_root: The single data root the Runner resolved for this run.

        Returns:
            Frozen plan whose ``tiles`` iterable performs existing tile discovery lazily.
        """
        context = PlanningContext(
            root=request.root,
            inputdata_path=_resolve_path(self._inputdata_path),
            unpacked_dir_path=_resolve_path(self._unpacked_dir_path),
            invoice_service=self._invoice_service,
            config=config,
            data_root=data_root,
        )
        handler = handler_for(mode)
        tiles: Iterable[TilePlan] = (
            create_common_tiles(mode, context) if handler is None else handler.create_tiles(context)
        )
        return ExecutionPlan(
            run_id=self._run_id_factory(),
            target=request.target,
            mode=mode,
            config=config,
            root=request.root,
            error_policy=config.execution.on_iteration_error,
            tiles=tiles,
            data_root=data_root,
            invoice_source=invoice_source_for(mode, data_root=data_root),
        )


def create_common_tiles(mode: ModeKind, context: PlanningContext) -> Iterator[TilePlan]:
    """Enumerate the common tile plans for one mode.

    This is the single tile-construction body shared by the planner fallback
    and the thin mode handlers installed in Session I5. Mode-specific
    behavior belongs in the handlers themselves (Session I6), not here.

    Args:
        mode: Resolved internal mode.
        context: Run-scoped paths and invoice operations.

    Yields:
        One immutable ``TilePlan`` per discovered tile.
    """
    inputdata_path = context.inputdata_path
    invoice_service = context.invoice_service
    # The Runner resolved this once, before anything existed (ruling #1).
    data_root = context.data_root
    invariant_invoice = _invariant_invoice(mode, data_root=data_root, invoice_service=invoice_service)
    # The source is decided by the v1 mode rule (ruling #3); ``backup`` below
    # only *creates* it, and the creation timing stays v1's.
    source = _InvoiceSourceState(
        path=invoice_source_for(mode, data_root=data_root),
        prepared=mode is not ModeKind.excelinvoice,
    )
    tiles = iter(
        iterate_tiles(
            mode,
            inputdata_path,
            context.unpacked_dir_path,
            data_root,
            context.config,
        ),
    )
    # v1 backs the invoice up AFTER check_files (workflows.py), so
    # data/temp/invoice_org.json does not exist while an input checker scans
    # the unpack directory. Pulling the first tile forces the checker's parse
    # (including unpacking) to finish first, which keeps the backup out of the
    # RDEFormat checker's data/temp/** glob.
    first = next(tiles, None)
    if mode in {ModeKind.multidatatile, ModeKind.rdeformat}:
        _run_invoice_source(
            mode,
            data_root=data_root,
            inputdata_path=inputdata_path,
            invoice_service=invoice_service,
        )
    if first is None:
        return
    for info, paths, out in chain((first,), tiles):
        yield TilePlan(
            iteration=info,
            paths=paths,
            out=out,
            invoice=None,
            prepare_invoice=partial(
                _prepare_tile_invoice,
                mode,
                data_root=data_root,
                inputdata_path=inputdata_path,
                paths=paths,
                invoice_dir=out.invoice,
                iteration_index=info.index,
                invariant_invoice=invariant_invoice,
                source=source,
                invoice_service=invoice_service,
            ),
        )


def _prepare_tile_invoice(
    mode: ModeKind,
    *,
    data_root: Path,
    inputdata_path: Path,
    paths: InputPaths,
    invoice_dir: Path,
    iteration_index: int,
    invariant_invoice: InvoiceData | None,
    source: _InvoiceSourceState,
    invoice_service: InvoiceService,
) -> TilePreparation:
    if not source.prepared:
        _run_invoice_source(
            mode,
            data_root=data_root,
            inputdata_path=inputdata_path,
            rawfiles=paths.rawfiles,
            invoice_service=invoice_service,
        )
        source.prepared = True
    return _tile_invoice(
        mode,
        paths=paths,
        invoice_dir=invoice_dir,
        iteration_index=iteration_index,
        invariant_invoice=invariant_invoice,
        invoice_org=source.path,
        invoice_service=invoice_service,
    )


def _invariant_invoice(
    mode: ModeKind,
    *,
    data_root: Path,
    invoice_service: InvoiceService | None = None,
) -> InvoiceData | None:
    return (invoice_service or InvoiceService()).invariant_invoice(mode, data_root=data_root)


def _tile_invoice(
    mode: ModeKind,
    *,
    paths: InputPaths,
    invoice_dir: Path,
    iteration_index: int,
    invariant_invoice: InvoiceData | None,
    invoice_org: Path,
    invoice_service: InvoiceService | None = None,
) -> TilePreparation:
    invoice, row_data = (invoice_service or InvoiceService()).prepare_tile(
        mode,
        paths=paths,
        invoice_dir=invoice_dir,
        iteration_index=iteration_index,
        invariant_invoice=invariant_invoice,
        invoice_source=invoice_org,
    )
    return TilePreparation(invoice=invoice, smarttable_row_data=row_data)


def _run_invoice_source(
    mode: ModeKind,
    *,
    data_root: Path,
    inputdata_path: Path,
    rawfiles: tuple[Path, ...] = (),
    invoice_service: InvoiceService | None = None,
) -> Path:
    """Return the v1-compatible run-level invoice source for a backup mode."""
    return (invoice_service or InvoiceService()).backup(
        mode,
        data_root=data_root,
        inputdata_path=inputdata_path,
        rawfiles=rawfiles,
    )


def _flat_layout_invoice_source(*, invoice_org: Path) -> Path:
    """Compatibility wrapper for the former flat-layout helper."""
    return InvoiceService().backup(
        ModeKind.rdeformat,
        data_root=invoice_org.parent.parent,
        inputdata_path=invoice_org.parent.parent / "inputdata",
    )


def _resolve_path(provider: PathProvider) -> Path:
    return provider() if callable(provider) else provider
