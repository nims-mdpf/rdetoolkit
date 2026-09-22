"""Narrow contract for mode-owned execution planning."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from rdetoolkit.domain.invoice_service import InvoiceService
    from rdetoolkit.runner.mode_resolver import ModeKind
    from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
    from rdetoolkit.types import RdeConfig


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """Explicit run material available to a mode handler.

    Args:
        root: Project or flat data root for the run.
        inputdata_path: Directory containing run inputs.
        unpacked_dir_path: Directory used for unpacked inputs.
        invoice_service: Run-owned invoice operations used while creating tiles.
        config: Effective run configuration consumed by legacy input checkers.
        data_root: The single data root the Runner resolved for this run
            (ruling #1). A handler must never re-derive it from ``root``.
    """

    root: Path
    inputdata_path: Path
    unpacked_dir_path: Path
    invoice_service: InvoiceService
    data_root: Path
    config: RdeConfig | None = None


class RawCopyStrategy(Protocol):
    """Publish one tile's raw inputs.

    ``RawArtifactService`` is the generic implementation; a mode installs its
    own strategy when v1 copies raw files by a different rule (RDEFormat
    dispatches by path component, for example).
    """

    def copy(
        self,
        source_files: tuple[Path, ...],
        *,
        raw_dir: Path,
        nonshared_raw_dir: Path,
        config: RdeConfig,
        smarttable: bool = False,
        data_root: Path,
    ) -> None:
        """Copy the configured raw artifacts for one tile.

        ``data_root`` is the run's single resolved data root. A strategy that
        classifies inputs by path component must interpret them *relative* to
        it (Session I-REVIEW-A ruling #7): the absolute path reaches outside
        the project, so an ancestor directory named ``raw`` would otherwise
        decide where an unpacked file lands (review R1).
        """
        ...


@runtime_checkable
class ModeHandler(Protocol):
    """The minimum contract every mode handler satisfies.

    Deliberately just identity and tile creation (Session I-REVIEW-A ruling
    #8). The executor reads the artifact capabilities below through ``getattr``
    and works without them, so declaring them here made the type system reject
    handlers the runtime accepts (reviews F6/R6).
    """

    kind: ModeKind

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        """Create tile plans from explicit planning material.

        Args:
            context: Run-scoped paths and invoice operations.

        Returns:
            Lazily iterable common tile plans for the executor.
        """
        ...


@runtime_checkable
class RawCopyStrategyProvider(Protocol):
    """Optional capability: own how a mode publishes one tile's raw inputs."""

    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None:
        """Return the mode-specific raw copy strategy, if any.

        Args:
            plan: Immutable run execution plan.

        Returns:
            Mode-owned strategy, or ``None`` for the generic service.
        """
        ...


@runtime_checkable
class ArtifactStageProvider(Protocol):
    """Optional capability: own the post-invoke artifact stage sequence."""

    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None:
        """Return the ordered post-invoke artifact stages this mode runs.

        ``None`` selects the v1 invoice pipeline's order (``thumbnail`` ->
        ``structured`` -> ``magic`` -> ``description``). A mode whose v1
        pipeline reorders or omits a processor returns its own sequence; the
        order is part of the contract because it decides which artifacts a
        failing tile leaves behind (ruling #5).

        Args:
            plan: Immutable run execution plan.

        Returns:
            Ordered stage names, or ``None`` for the default sequence.
        """
        ...
