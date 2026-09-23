from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.report.events import EventSink
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.invoker import TargetInvoker
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan

DEFAULT_ARTIFACT_STAGE_ORDER: tuple[str, ...]

def artifact_stage_order(plan: ExecutionPlan) -> tuple[str, ...]: ...

class TileExecutor:
    def __init__(
        self,
        *,
        event_sink: EventSink,
        flow_invoker: TargetInvoker | None = None,
        raw_artifact_service: RawArtifactService | None = None,
        image_artifact_service: ImageArtifactService | None = None,
        invoice_service: InvoiceService | None = None,
    ) -> None: ...
    def execute(self, plan: ExecutionPlan, tile: TilePlan) -> ExecutionResult: ...
