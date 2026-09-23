"""ExcelInvoice-mode planning handler for the unified Runner."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import create_common_tiles

if TYPE_CHECKING:
    from rdetoolkit.modes.protocol import PlanningContext, RawCopyStrategy
    from rdetoolkit.runner.planner import ExecutionPlan, TilePlan


#: v1 pipeline order for this mode (``processing/factories.py``):
#: VariableApplier -> ThumbnailGenerator -> StructuredInvoiceSaver ->
#: DescriptionUpdater.
_ARTIFACT_STAGE_ORDER = ("magic", "thumbnail", "structured", "description")


class ExcelInvoiceModeHandler:
    """Plan ExcelInvoice-mode tiles.

    Session I5 keeps this adapter deliberately thin: it owns the mode identity
    and nothing else, so the planned tiles stay identical to the pre-handler
    Runner. Empty-row and missing-row compatibility arrives in Session I6.
    """

    kind = ModeKind.excelinvoice

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        """Create ExcelInvoice-mode tile plans.

        Args:
            context: Run-scoped paths and invoice operations.

        Returns:
            Lazily iterable common tile plans for the executor.
        """
        return create_common_tiles(self.kind, context)

    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None:
        """Return no mode-specific raw copy strategy.

        Args:
            plan: Immutable run execution plan.

        Returns:
            ``None``, selecting the generic ``RawArtifactService``.
        """
        _ = plan
        return None

    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None:
        """Expand magic variables first, as this mode's v1 pipeline does.

        ``processing/factories.py`` builds this pipeline as VariableApplier ->
        ThumbnailGenerator -> StructuredInvoiceSaver -> DescriptionUpdater. The
        order is observable: when the magic expansion fails, v1 leaves no
        ``structured/invoice.json`` behind (review R3).

        Args:
            plan: Immutable run execution plan.

        Returns:
            The v1 sequence for this mode.
        """
        _ = plan
        return _ARTIFACT_STAGE_ORDER
