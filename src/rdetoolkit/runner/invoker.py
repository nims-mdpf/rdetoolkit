"""Execution target adapters for the v2 Runner."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from typing import TYPE_CHECKING

from rdetoolkit.api.request import ExecutionTarget, FlowTarget, LegacyCallbackTarget
from rdetoolkit.core.context import RunContext
from rdetoolkit.report.events import EventSink
from rdetoolkit.runner.execute import ExecutionResult, run_tile
from rdetoolkit.types import RdeConfig

if TYPE_CHECKING:
    from rdetoolkit.runner.planner import TileMaterial


#: The failure list of the innermost active :func:`capture_target_failures`.
#: A context variable rather than Runner state: the v1 entry needs the exception
#: object of a failed tile, which ``TileExecutor`` normalizes into a JSON-ready
#: record, and a ContextVar keeps concurrent in-process runs apart.
_TARGET_FAILURES: ContextVar[list[Exception] | None] = ContextVar("rdetoolkit_target_failures", default=None)


@contextmanager
def capture_target_failures() -> Iterator[list[Exception]]:
    """Hold the latest exception an invoked target raised while the context is active.

    This is the seam the v1 entry (``workflows.run(custom_dataset_function=...)``)
    uses to obtain the primary exception of a failed tile, so it can write the
    stderr traceback v1.7.1 wrote. Execution is unaffected: every exception is
    still re-raised to ``TileExecutor`` exactly as before.

    Yields:
        A list holding at most one exception: the most recent failure. Earlier
        failures are dropped so their tracebacks are released.
    """
    failures: list[Exception] = []
    token = _TARGET_FAILURES.set(failures)
    try:
        yield failures
    finally:
        _TARGET_FAILURES.reset(token)


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
            material: Run-owned tile material. A v2 flow reads its inputs
                from ``context``; only the run's call counter is taken from
                here so ``seq`` stays run-global across tiles.

        Returns:
            Primary execution result returned by ``run_tile``.

        Raises:
            TypeError: If the target is not a flow target.
        """
        if not isinstance(target, FlowTarget):
            msg = "FlowInvoker requires a FlowTarget; a LegacyCallbackTarget belongs to LegacyCallbackInvoker"
            raise TypeError(msg)
        return run_tile(
            target.function,
            context,
            event_sink=event_sink,
            run_id=run_id,
            config=config,
            emit_iteration_events=False,
            sequence=material.call_sequence,
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
        try:
            return self.for_target(target).invoke(
                target,
                context,
                event_sink=event_sink,
                run_id=run_id,
                config=config,
                material=material,
            )
        except Exception as exc:
            failures = _TARGET_FAILURES.get()
            if failures is not None:
                # Keep only the latest failure: the v1 entry formats the last
                # one, and holding every tile's traceback (frames, locals) for
                # the whole run would keep large objects alive under continue.
                failures[:] = [exc]
            raise
