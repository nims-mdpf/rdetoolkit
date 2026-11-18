"""Versioned, read-only registration explanation for the current input snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdetoolkit.api.request import FlowTarget
from rdetoolkit.config.normalize import _find_tasksupport_config, _load_optional_mapping
from rdetoolkit.domain.invoice_service import invoice_source_for
from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, ResolutionDiagnostic, preview_invoice
from rdetoolkit.domain.magic_policy import options_from_config
from rdetoolkit.domain.magic_service import template_destinations, validate_templates
from rdetoolkit.domain.mode_selection import ModeDecision, ModeKind, decide_mode
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.fileops import readf_json
from rdetoolkit.modes.stages import ArtifactStage, StageSpec, artifact_stage_order, describe_artifact_stages
from rdetoolkit.runner.config_loader import load_run_config
from rdetoolkit.runner.input_snapshot import InputGroup, InputSnapshot, discover_input_snapshot
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.paths import TileOutputPaths, resolve_data_root, resolve_tile_paths
from rdetoolkit.runner.planner import ExecutionPlan
from rdetoolkit.types import RdeConfig


@dataclass(frozen=True, slots=True)
class PlannedTile:
    """Redacted tile membership and destination descriptions."""

    index: int
    input_names: tuple[str, ...]
    source_row: int | None
    invoice_origin: str
    output_paths: tuple[tuple[str, str], ...]
    invokes_flow: bool
    stages: tuple[StageSpec, ...]


_MAGIC_CHECKS = ("syntax", "source_resolution", "normalization", "output_limits")
_MAGIC_NOT_CHECKED = ("invoice_schema", "invoice_standard_checks", "flow_side_effects")
_SKIPPED_STAGE_REASONS = frozenset({"precompleted_tile", "omitted_by_mode"})


@dataclass(frozen=True, slots=True)
class MagicTilePreview:
    """Value-free interpolation outcome for one planned tile."""

    index: int
    status: str
    reason: str
    diagnostics: tuple[ResolutionDiagnostic, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the explain-schema representation."""
        return {"index": self.index, "status": self.status, "reason": self.reason, "diagnostics": [item.to_dict() for item in self.diagnostics]}


@dataclass(frozen=True, slots=True)
class MagicPreview:
    """What the pre-flow snapshot says about interpolation, and what it cannot say."""

    status: str
    reason: str
    tiles: tuple[MagicTilePreview, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the explain-schema representation."""
        return {
            "status": self.status,
            "reason": self.reason,
            "checks": list(_MAGIC_CHECKS),
            "not_checked": list(_MAGIC_NOT_CHECKED),
            "tiles": [tile.to_dict() for tile in self.tiles],
        }


@dataclass(frozen=True, slots=True)
class RegistrationPreview:
    """A deterministic explanation that contains no invoice or metadata values."""

    decision: ModeDecision
    tiles: tuple[PlannedTile, ...]
    stages: tuple[StageSpec, ...]
    config_source: str
    iteration_policy: str
    deterministic_order: bool
    warnings: tuple[str, ...]
    magic: MagicPreview
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned explain-schema representation.

        Returns:
            A JSON-compatible success envelope with redacted plan descriptions.
        """
        return {
            "schema_version": self.schema_version,
            "status": "success",
            "decision": self.decision.to_dict(),
            "tile_count": len(self.tiles),
            "tiles": [_tile_dict(tile) for tile in self.tiles],
            "stages": [_stage_dict(stage) for stage in self.stages],
            "config_source": self.config_source,
            "iteration_policy": self.iteration_policy,
            "deterministic_order": self.deterministic_order,
            "warnings": list(self.warnings),
            "preparation": {"status": "not_invoked", "reason": "current_input_snapshot_only"},
            "magic_preview": self.magic.to_dict(),
            "graph_preview": {"status": "unavailable", "reason": "graph_preview_api_pending"},
        }


def _stage_dict(stage: StageSpec) -> dict[str, Any]:
    return {"name": stage.name.value, "enabled": stage.enabled, "reason": stage.reason, "side_effects": list(stage.side_effects)}


def _tile_dict(tile: PlannedTile) -> dict[str, Any]:
    return {
        "index": tile.index,
        "input_names": list(tile.input_names),
        "source_row": tile.source_row,
        "invoice_origin": tile.invoice_origin,
        "output_paths": dict(tile.output_paths),
        "invokes_flow": tile.invokes_flow,
        "stages": [_stage_dict(stage) for stage in tile.stages],
    }


def _magic_stage(tile: PlannedTile) -> StageSpec | None:
    return next((stage for stage in tile.stages if stage.name is ArtifactStage.magic), None)


def _preview_tile(tile: PlannedTile, group: InputGroup, invoice: dict[str, Any], mode: ModeKind, options: MagicOptions) -> MagicTilePreview:
    stage = _magic_stage(tile)
    if stage is None:
        return MagicTilePreview(tile.index, "skipped", "omitted_by_mode")
    if stage.reason in _SKIPPED_STAGE_REASONS:
        return MagicTilePreview(tile.index, "skipped", str(stage.reason))
    if tile.source_row is not None:
        return MagicTilePreview(tile.index, "deferred", "row_invoice_built_at_runtime")
    rawfiles = tuple(Path(ref.member) if ref.member is not None else ref.source for ref in group.files)
    context = ResolutionContext.from_sources(
        original_invoice=invoice,
        current_invoice=invoice,
        metadata=None,
        rawfiles=rawfiles,
        iteration_index=tile.index,
        mode=mode.value,
    )
    result = preview_invoice(context, options=options, deferred_scopes=frozenset({"metadata"}))
    return MagicTilePreview(tile.index, "previewed", "pre_flow_snapshot", result.diagnostics)


def _magic_preview(mode: ModeKind, invoice: dict[str, Any], tiles: tuple[PlannedTile, ...], snapshot: InputSnapshot, options: MagicOptions) -> MagicPreview:
    if mode is ModeKind.rdeformat:
        return MagicPreview("not_applicable", "mode_has_no_magic_stage")
    previews = tuple(_preview_tile(tile, group, invoice, mode, options) for tile, group in zip(tiles, snapshot.groups, strict=True))
    if options.policy == "disabled":
        return MagicPreview("disabled", "policy_disabled", previews)
    if not template_destinations(invoice, options):
        return MagicPreview("no_templates", "no_eligible_templates", previews)
    return MagicPreview("previewed", "pre_flow_snapshot", previews)


def _preview_target() -> None:
    """Identify the strict validation contract without loading any user code."""


def _config_source(root: Path, data_root: Path, *, overrides: bool) -> str:
    source = "defaults"
    for candidate in (root / "rdeconfig.yaml", root / "pyproject.toml"):
        if candidate.exists() and _load_optional_mapping(candidate) is not None:
            source = candidate.relative_to(root).as_posix()
            break
    else:
        legacy = _find_tasksupport_config(data_root)
        if legacy is not None:
            source = legacy.relative_to(root).as_posix()
    return source + " + overrides" if overrides else source


def _output_description(paths: TileOutputPaths, data_root: Path) -> tuple[tuple[str, str], ...]:
    names = ("struct", "meta", "main_image", "other_image", "thumbnail", "attachment", "nonshared_raw", "raw", "invoice", "logs", "temp", "invoice_patch")
    return tuple((name, getattr(paths, name).relative_to(data_root).as_posix()) for name in names)


def _planned_tile(index: int, group: InputGroup, snapshot: InputSnapshot, data_root: Path, config: RdeConfig, order: tuple[str, ...], magic_options: MagicOptions) -> PlannedTile:
    origin = "invoice/invoice.json"
    if snapshot.table_path is not None and group.source_row is not None:
        origin = f"inputdata/{snapshot.table_path.name}#row={group.source_row}"
    return PlannedTile(
        index=index,
        input_names=tuple(ref.name for ref in group.files),
        source_row=group.source_row,
        invoice_origin=origin,
        output_paths=_output_description(resolve_tile_paths(data_root, index), data_root),
        invokes_flow=not group.original_table,
        stages=describe_artifact_stages(snapshot.mode, config, order=order, has_rawfiles=bool(group.files), precompleted=group.original_table, magic_options=magic_options),
    )


def _effective_stage_order(root: Path, data_root: Path, mode: ModeKind, config: RdeConfig) -> tuple[str, ...]:
    plan = ExecutionPlan(
        run_id="preview",
        target=FlowTarget(function=_preview_target),
        mode=mode,
        config=config,
        root=root,
        error_policy=config.execution.on_iteration_error,
        tiles=(),
        data_root=data_root,
        invoice_source=invoice_source_for(mode, data_root=data_root),
    )
    return artifact_stage_order(plan)


def _require_source_artifacts(data_root: Path) -> None:
    for relative in ("invoice/invoice.json", "tasksupport/invoice.schema.json"):
        if not (data_root / relative).exists():
            message = f"Required input artifact missing: {relative}. Provide it before validation."
            raise RdeValidationError(code=4003, message=message, detail={"artifact": relative})


def preview_registration(root: Path, *, overrides: Mapping[str, Any] | None = None) -> RegistrationPreview:
    """Validate and explain a registration without invoking or importing user code.

    Args:
        root: Project root or flat data directory.
        overrides: Optional configuration overrides using normal Runner precedence.

    Returns:
        Immutable selection, tile, stage, and optional-preview descriptions.

    Raises:
        RdeError: If configuration, source artifacts, template syntax, mappings,
            or grouping are invalid.
    """
    root = root.resolve()
    data_root = resolve_data_root(root)
    config = load_run_config(root, overrides=overrides)
    decision = decide_mode(config, data_root / "inputdata")
    _require_source_artifacts(data_root)
    runner = Runner(root=root, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp")
    runner._validate_inputs(FlowTarget(function=_preview_target), decision.chosen_mode, config)  # noqa: SLF001 -- same validation boundary without run publication
    magic_options = options_from_config(config)
    invoice: dict[str, Any] = {}
    if decision.chosen_mode is not ModeKind.rdeformat:
        invoice = readf_json(data_root / "invoice" / "invoice.json")
        validate_templates(invoice, magic_options)
    snapshot = discover_input_snapshot(decision.chosen_mode, data_root / "inputdata", config)
    order = _effective_stage_order(root, data_root, snapshot.mode, config)
    warnings = ["User preparation and flow are not invoked; this plan describes only the current input snapshot."]
    if not snapshot.deterministic_order:
        warnings.append("Filesystem ordering is not deterministic across filesystems.")
    tiles = tuple(_planned_tile(index, group, snapshot, data_root, config, order, magic_options) for index, group in enumerate(snapshot.groups))
    return RegistrationPreview(
        decision=decision,
        tiles=tiles,
        stages=describe_artifact_stages(snapshot.mode, config, order=order, magic_options=magic_options),
        config_source=_config_source(root, data_root, overrides=bool(overrides)),
        iteration_policy=snapshot.iteration_policy,
        deterministic_order=snapshot.deterministic_order,
        warnings=tuple(warnings),
        magic=_magic_preview(snapshot.mode, invoice, tiles, snapshot, magic_options),
    )
