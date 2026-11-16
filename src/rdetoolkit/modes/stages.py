"""Validated, read-only artifact-stage specifications owned by registration modes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.modes.registry import handler_for

if TYPE_CHECKING:
    from rdetoolkit.runner.mode_resolver import ModeKind
    from rdetoolkit.runner.planner import ExecutionPlan
    from rdetoolkit.types import RdeConfig


class ArtifactStage(str, Enum):
    """Supported post-invoke artifact stages, in the default invoice order."""

    thumbnail = "thumbnail"
    structured = "structured"
    magic = "magic"
    description = "description"


@dataclass(frozen=True, slots=True)
class StageSpec:
    """Describe one artifact stage without executing it.

    Attributes:
        name: Stable stage identifier.
        enabled: Whether the stage can run for the supplied tile and configuration.
        reason: Stable reason for an omission or pending runtime inputs.
        side_effects: Relative artifact paths that the enabled stage may change.
    """

    name: ArtifactStage
    enabled: bool
    reason: str | None
    side_effects: tuple[str, ...]


DEFAULT_ARTIFACT_STAGE_ORDER: tuple[str, ...] = tuple(stage.value for stage in ArtifactStage)
_MAGIC_FIRST_ORDER = ("magic", "thumbnail", "structured", "description")
_MODE_ORDERS = {
    "multidatatile": _MAGIC_FIRST_ORDER,
    "excelinvoice": _MAGIC_FIRST_ORDER,
    "rdeformat": ("thumbnail", "description"),
}
_STAGE_CONFIG_FIELDS = {
    ArtifactStage.thumbnail: "save_thumbnail_image",
    ArtifactStage.structured: "save_invoice_to_structured",
    ArtifactStage.magic: "magic_variable",
    ArtifactStage.description: "feature_description",
}
_SIDE_EFFECTS = {
    ArtifactStage.thumbnail: ("thumbnail/",),
    ArtifactStage.structured: ("structured/invoice.json",),
    ArtifactStage.magic: ("invoice/invoice.json",),
    ArtifactStage.description: ("invoice/invoice.json",),
}


def mode_stage_order(mode: ModeKind) -> tuple[str, ...]:
    """Return the built-in mode's historical artifact order (Design §6.3).

    Args:
        mode: Effective registration mode.

    Returns:
        Ordered artifact stage identifiers before configuration gates.
    """
    return _MODE_ORDERS.get(mode.value, DEFAULT_ARTIFACT_STAGE_ORDER)


def artifact_stage_order(plan: ExecutionPlan) -> tuple[str, ...]:
    """Read the accepted stage order or validate a mode handler's declaration.

    The capability is optional. A missing provider or ``None`` selects the
    invoice default. A planner stores the result on ``artifact_stages`` once,
    so execution does not ask a mutable provider to decide again.

    Args:
        plan: Immutable execution plan, including an optional accepted sequence.

    Returns:
        Validated stage identifiers in execution order.

    Raises:
        RdeConfigError: If identifiers, uniqueness, or dependency order are invalid.
    """
    if plan.artifact_stages is not None:
        return plan.artifact_stages
    provider = getattr(handler_for(plan.mode), "artifact_stage_order", None)
    if provider is None:
        return DEFAULT_ARTIFACT_STAGE_ORDER
    if not callable(provider):
        reason = "artifact_stage_order must be callable"
        raise _stage_error(reason)
    return _validated_order(provider(plan))


def plan_artifact_stages(
    plan: ExecutionPlan,
    *,
    has_rawfiles: bool | None = None,
    precompleted: bool = False,
) -> tuple[StageSpec, ...]:
    """Describe the same handler-selected stages that execution consumes.

    Args:
        plan: Accepted execution plan or a read-only plan with no tile enumeration.
        has_rawfiles: Whether the tile has raw files, or ``None`` before discovery.
        precompleted: Whether the mode completed the tile before user invocation.

    Returns:
        Selected stages in execution order, followed by mode-omitted stages.
    """
    return describe_artifact_stages(
        plan.mode,
        plan.config,
        order=artifact_stage_order(plan),
        has_rawfiles=has_rawfiles,
        precompleted=precompleted,
    )


def describe_artifact_stages(
    mode: ModeKind,
    config: RdeConfig,
    *,
    order: tuple[str, ...] | None = None,
    has_rawfiles: bool | None = None,
    precompleted: bool = False,
) -> tuple[StageSpec, ...]:
    """Describe a mode's artifact plan without constructing an execution target.

    Args:
        mode: Effective registration mode.
        config: Normalized configuration supplying stage gates.
        order: Selected handler override, or ``None`` for the built-in mode order.
        has_rawfiles: Whether raw files exist, or ``None`` when not yet discovered.
        precompleted: Whether the original-table tile bypasses post-invoke work.

    Returns:
        Immutable stage descriptions. Paths are relative, and values are omitted.

    Raises:
        RdeConfigError: If an explicit stage sequence is invalid.
    """
    selected = tuple(ArtifactStage(name) for name in _validated_order(mode_stage_order(mode) if order is None else order))
    names = (*selected, *(stage for stage in ArtifactStage if stage not in selected))
    return tuple(_describe_stage(stage, stage in selected, config, has_rawfiles, precompleted) for stage in names)


def _validated_order(raw: object) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_ARTIFACT_STAGE_ORDER
    names = _stage_names(raw)
    if len(names) != len(set(names)):
        reason = "stage order contains duplicate identifiers"
        raise _stage_error(reason)
    if "description" in names and names[-1] != "description":
        reason = "description must follow every other selected stage"
        raise _stage_error(reason)
    return names


def _stage_names(raw: object) -> tuple[str, ...]:
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        reason = "stage order must be a sequence of stage identifiers"
        raise _stage_error(reason)
    names = tuple(raw)
    known = {stage.value for stage in ArtifactStage}
    if any(not isinstance(name, str) or name not in known for name in names):
        reason = "stage order contains an unsupported identifier"
        raise _stage_error(reason)
    return names


def _describe_stage(
    stage: ArtifactStage,
    selected: bool,
    config: RdeConfig,
    has_rawfiles: bool | None,
    precompleted: bool,
) -> StageSpec:
    reason = _omission_reason(stage, selected, config, has_rawfiles, precompleted)
    enabled = reason in {None, "runtime_inputs_pending"}
    return StageSpec(stage, enabled, reason, _SIDE_EFFECTS[stage])


def _omission_reason(
    stage: ArtifactStage,
    selected: bool,
    config: RdeConfig,
    has_rawfiles: bool | None,
    precompleted: bool,
) -> str | None:
    if not selected:
        return "omitted_by_mode"
    if precompleted:
        return "precompleted_tile"
    if not getattr(config.system, _STAGE_CONFIG_FIELDS[stage]):
        return "disabled_by_config"
    if stage is ArtifactStage.magic:
        return {False: "no_rawfiles", None: "runtime_inputs_pending", True: None}[has_rawfiles]
    return None


def _stage_error(reason: str) -> RdeConfigError:
    definition = ERROR_CATALOG[1006]
    message = definition.message_template.format(reason=reason)
    return RdeConfigError(
        code=1006,
        message=f"{message} Remediation: {definition.remediation}",
        detail={"reason": reason},
    )
