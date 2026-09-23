"""Execution target adapters for the v2 Runner."""

from __future__ import annotations

from typing import Protocol

from typing import TYPE_CHECKING

from rdetoolkit.api.request import ExecutionTarget, FlowTarget, LegacyCallbackTarget
from rdetoolkit.core.context import RunContext
from rdetoolkit.report.events import EventSink
from rdetoolkit.runner.execute import ExecutionResult, run_tile
from rdetoolkit.types import RdeConfig

if TYPE_CHECKING:
    from rdetoolkit.runner.planner import TileMaterial


class TargetInvoker(Protocol):
    """Adapter contract for invoking one normalized execution target."""

    def invoke(
        self,
        target: ExecutionTarget,
        context: RunContext,
        *,
        event_sink: EventSink,
        run_id: str,
        config: RdeConfig,
        material: TileMaterial,
    ) -> ExecutionResult:
        """Invoke a normalized target for one tile."""
        ...


class FlowInvoker:
    """Invoke a flow target through the existing eager ``run_tile`` core."""

    def invoke(
        self,
        target: ExecutionTarget,
        context: RunContext,
        *,
        event_sink: EventSink,
        run_id: str,
        config: RdeConfig,
        material: TileMaterial,
    ) -> ExecutionResult:
        """Execute one flow tile without duplicating DI or call-log behavior.

        Args:
            target: Normalized flow target.
            context: Reserved values for the current tile.
            event_sink: Sink receiving node events.
            run_id: Active run identifier.
            config: Effective run configuration.
            material: Unused; a v2 flow reads its inputs from ``context``.

        Returns:
            Primary execution result returned by ``run_tile``.

        Raises:
            TypeError: If the target is not a flow target.
        """
        if not isinstance(target, FlowTarget):
            msg = "FlowInvoker requires a FlowTarget; a LegacyCallbackTarget belongs to LegacyCallbackInvoker"
            raise TypeError(msg)
        _ = material
        return run_tile(
            target.function,
            context,
            event_sink=event_sink,
            run_id=run_id,
            config=config,
            emit_iteration_events=False,
        )


class InvokerRegistry:
    """Select the invoker for a normalized execution target (Design §7).

    Choosing the adapter is Runner-side work, so the compat package never
    decides how a target is executed.
    """

    def __init__(
        self,
        *,
        flow_invoker: TargetInvoker | None = None,
        legacy_invoker: TargetInvoker | None = None,
    ) -> None:
        """Create a registry over the two supported entry points.

        Args:
            flow_invoker: Optional replacement for the v2 flow adapter.
            legacy_invoker: Optional replacement for the v1 callback adapter.
        """
        if legacy_invoker is None:
            from rdetoolkit.compat.v1.callback import LegacyCallbackInvoker  # noqa: PLC0415 -- keeps compat off the runner import cycle

            legacy_invoker = LegacyCallbackInvoker()
        self._flow_invoker = flow_invoker or FlowInvoker()
        self._legacy_invoker = legacy_invoker

    def for_target(self, target: ExecutionTarget) -> TargetInvoker:
        """Return the invoker registered for one normalized target.

        Args:
            target: Normalized flow or legacy callback target.

        Returns:
            The adapter that owns this target's execution.

        Raises:
            TypeError: If the target is not a supported execution target.
        """
        if isinstance(target, FlowTarget):
            return self._flow_invoker
        if isinstance(target, LegacyCallbackTarget):
            return self._legacy_invoker
        msg = f"Unsupported execution target: {type(target).__name__}"
        raise TypeError(msg)

    def invoke(
        self,
        target: ExecutionTarget,
        context: RunContext,
        *,
        event_sink: EventSink,
        run_id: str,
        config: RdeConfig,
        material: TileMaterial,
    ) -> ExecutionResult:
        """Dispatch one tile to the invoker registered for its target.

        Args:
            target: Normalized execution target.
            context: Reserved values for the current tile.
            event_sink: Sink receiving node events.
            run_id: Active run identifier.
            config: Effective run configuration.
            material: Run-owned tile material for the selected invoker.

        Returns:
            Primary execution result produced by the selected invoker.
        """
        return self.for_target(target).invoke(
            target,
            context,
            event_sink=event_sink,
            run_id=run_id,
            config=config,
            material=material,
        )
