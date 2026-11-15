from dataclasses import dataclass
from enum import Enum
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import ExecutionPlan
from rdetoolkit.types import RdeConfig

class ArtifactStage(str, Enum):
    thumbnail = "thumbnail"
    structured = "structured"
    magic = "magic"
    description = "description"

@dataclass(frozen=True, slots=True)
class StageSpec:
    name: ArtifactStage
    enabled: bool
    reason: str | None
    side_effects: tuple[str, ...]

DEFAULT_ARTIFACT_STAGE_ORDER: tuple[str, ...]

def mode_stage_order(mode: ModeKind) -> tuple[str, ...]: ...
def artifact_stage_order(plan: ExecutionPlan) -> tuple[str, ...]: ...
def plan_artifact_stages(plan: ExecutionPlan, *, has_rawfiles: bool | None = ..., precompleted: bool = ...) -> tuple[StageSpec, ...]: ...
def describe_artifact_stages(mode: ModeKind, config: RdeConfig, *, order: tuple[str, ...] | None = ..., has_rawfiles: bool | None = ..., precompleted: bool = ...) -> tuple[StageSpec, ...]: ...
