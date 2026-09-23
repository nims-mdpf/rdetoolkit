"""Minimal v1 dataset-callback adapter for the unified Runner (Design §7).

This module owns exactly two things: converting one tile's v2 material into the
v1 callback arguments, and calling the user callback with the signature it
expects. The signature rules are a port of the v1 ``DatasetRunner``
(``processing/processors/datasets.py``), which stays the behavioral oracle.

Anything beyond conversion and invocation — notably the execution history of
the callback entry point — is Session I8 work and is deliberately absent here.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdetoolkit.api.request import LegacyCallbackTarget
from rdetoolkit.models.config import (
    Config,
    MultiDataTileSettings,
    SmartTableSettings,
    SystemSettings,
)
from rdetoolkit.models.rde2types import (
    RdeDatasetPaths,
    RdeInputDirPaths,
    RdeOutputResourcePath,
)
from rdetoolkit.runner.execute import ExecutionResult

if TYPE_CHECKING:
    from rdetoolkit.api.request import ExecutionTarget
    from rdetoolkit.core.context import RunContext
    from rdetoolkit.report.events import EventSink
    from rdetoolkit.runner.planner import TileMaterial
    from rdetoolkit.types import RdeConfig


_LEGACY_ARG_COUNT = 2
# v1's own threshold (``workflows._select_smarttable_rowfile``): a row CSV stem
# splits into at least ["fsmarttable", "<index>"].
_SMARTTABLE_ROWFILE_MIN_PARTS = 2
# v1 ``Config.system.extended_mode`` accepts only these two spellings; every
# other v2 mode name (including the canonical default "invoice") is None in v1.
_V1_EXTENDED_MODES = frozenset({"rdeformat", "MultiDataTile"})
_ARITY_ERROR_KEYWORDS = (
    "required positional argument",
    "positional arguments but",
    "missing 1 required positional argument",
    "positional argument but",
)


def accepts_unified_argument(callback: Callable[..., Any]) -> bool | None:
    """Infer which v1 callback signature a callable expects.

    Args:
        callback: User-supplied dataset callback.

    Returns:
        ``True`` for the unified single-argument style, ``False`` for the
        legacy ``(srcpaths, resource_paths)`` pair, and ``None`` when the
        signature cannot decide (v1 then tries unified first and falls back).
    """
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return None

    parameters = list(signature.parameters.values())
    if any(parameter.kind is inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return None

    positional = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) >= _LEGACY_ARG_COUNT:
        return False
    if len(positional) == 1:
        return True
    return None


def to_legacy_dataset_paths(context: RunContext, *, material: TileMaterial) -> RdeDatasetPaths:
    """Convert one tile's v2 material into the v1 dataset path bundle.

    Args:
        context: Reserved values prepared by the Runner for the current tile.
        material: Run-owned tile material. It carries the ``invoice_org`` the
            plan decided (ruling #3) and this tile's SmartTable row dictionary
            (ruling #2), so this adapter neither re-decides the source from
            what happens to exist under ``temp/`` nor reads a process-global
            handoff a concurrent run could have erased.

    Returns:
        The unified v1 path bundle, which also exposes the legacy pair through
        ``as_legacy_args()``.

    Raises:
        ValueError: If the context lacks the input or output material that a v1
            callback requires.
    """
    paths = context.paths
    out = context.out
    if paths is None or out is None:
        msg = "RunContext.paths and RunContext.out are required to build v1 callback arguments."
        raise ValueError(msg)

    input_paths = RdeInputDirPaths(
        inputdata=paths.inputdata,
        invoice=paths.invoice,
        tasksupport=paths.tasksupport,
        config=to_legacy_config(context.config),
    )
    tile_root = out.invoice.parent
    smarttable_rowfile = _select_smarttable_rowfile(paths.rawfiles)
    output_paths = RdeOutputResourcePath(
        raw=out.raw,
        nonshared_raw=out.nonshared_raw,
        rawfiles=paths.rawfiles,
        struct=out.struct,
        main_image=out.main_image,
        other_image=out.other_image,
        meta=out.meta,
        thumbnail=out.thumbnail,
        logs=out.logs,
        invoice=out.invoice,
        invoice_schema_json=paths.tasksupport / "invoice.schema.json",
        invoice_org=material.invoice_source,
        # OutputContext deliberately omits these two directories (Design §6.3
        # addendum), so the tile root they share with invoice/ resolves them.
        temp=tile_root / "temp",
        invoice_patch=tile_root / "invoice_patch",
        smarttable_rowfile=smarttable_rowfile,
        smarttable_row_data=(
            dict(material.smarttable_row_data)
            if smarttable_rowfile is not None and material.smarttable_row_data is not None
            else None
        ),
        attachment=out.attachment,
    )
    return RdeDatasetPaths(input_paths=input_paths, output_paths=output_paths)


def _select_smarttable_rowfile(rawfiles: tuple[Path, ...]) -> Path | None:
    """Return the generated SmartTable row CSV, using the v1 selection rule.

    Ported from ``workflows._select_smarttable_rowfile``: only the first raw
    file is considered, and it must be an ``fsmarttable_*_<digits>.csv`` file
    produced by the SmartTable checker.

    Args:
        rawfiles: The tile's input files, in checker order.

    Returns:
        The row CSV, or ``None`` when this tile has none.
    """
    if not rawfiles:
        return None
    candidate = rawfiles[0]
    if candidate.suffix.lower() != ".csv":
        return None
    stem = candidate.stem
    if not stem.startswith("fsmarttable_"):
        return None
    parts = stem.split("_")
    if len(parts) < _SMARTTABLE_ROWFILE_MIN_PARTS:
        return None
    return candidate if parts[-1].isdigit() else None


class LegacyCallbackInvoker:
    """Invoke a v1 dataset callback for one planned tile."""

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
        """Convert the tile material and call the v1 dataset callback.

        Args:
            target: Normalized legacy callback target.
            context: Reserved values for the current tile.
            event_sink: Unused; iteration events stay Runner-owned.
            run_id: Unused; the callback entry point emits no node events.
            config: Unused; the effective config travels inside ``context``.
            material: Run-owned tile material handed to the v1 bundle.

        Returns:
            A completed result for the tile. Failures propagate so the common
            tile executor keeps owning failure normalization.

        Raises:
            TypeError: If the target is not a legacy callback target.
            ValueError: If the tile context has no iteration information.
        """
        if not isinstance(target, LegacyCallbackTarget):
            msg = "LegacyCallbackInvoker requires a LegacyCallbackTarget"
            raise TypeError(msg)
        _ = (event_sink, run_id, config)

        iteration = context.iteration
        if iteration is None:
            msg = "RunContext.iteration is required for tile execution."
            raise ValueError(msg)

        if target.function is not None:
            _call_with_matching_signature(
                target.function,
                to_legacy_dataset_paths(context, material=material),
            )

        # Positional fields are: iteration index, status, call log, outputs.
        # The v1 entry point contributes neither of the latter two in I5.
        return ExecutionResult(
            iteration.index,
            "completed",
            (),
            (),
            datatile_id=_datatile_id(context, iteration.index),
        )


def _call_with_matching_signature(
    callback: Callable[..., Any],
    dataset_paths: RdeDatasetPaths,
) -> None:
    """Call a v1 callback exactly as the v1 DatasetRunner does."""
    srcpaths, resource_paths = dataset_paths.as_legacy_args()
    unified = accepts_unified_argument(callback)
    if unified is True:
        callback(dataset_paths)
        return
    if unified is False:
        callback(srcpaths, resource_paths)
        return

    # Ambiguous callable: attempt the unified style with a guarded fallback so
    # a user's own TypeError is never mistaken for an arity mismatch.
    try:
        callback(dataset_paths)
    except TypeError as error:
        if not _looks_like_arity_mismatch(error):
            raise
        callback(srcpaths, resource_paths)


def _looks_like_arity_mismatch(error: TypeError) -> bool:
    """Return True when a TypeError looks like a wrong-arity call."""
    message = str(error)
    return any(keyword in message for keyword in _ARITY_ERROR_KEYWORDS)


def to_legacy_config(config: RdeConfig | None) -> Config:
    """Project the canonical v2 config back onto the v1 Config contract.

    Public because the Runner's tile iterator needs the same projection for the
    legacy input checkers, which read ``smarttable.save_table_file`` from a v1
    ``Config`` (``domain.mode.selected_input_checker``).

    Args:
        config: Effective canonical configuration, or ``None``.

    Returns:
        Equivalent v1 configuration.
    """
    if config is None:
        return Config()
    system = config.system
    extended_mode = system.extended_mode if system.extended_mode in _V1_EXTENDED_MODES else None
    return Config(
        system=SystemSettings(
            extended_mode=extended_mode,
            save_raw=system.save_raw,
            save_nonshared_raw=system.save_nonshared_raw,
            save_thumbnail_image=system.save_thumbnail_image,
            magic_variable=system.magic_variable,
            save_invoice_to_structured=system.save_invoice_to_structured,
            feature_description=system.feature_description,
        ),
        multidata_tile=MultiDataTileSettings(
            ignore_errors=config.execution.on_iteration_error == "continue",
        ),
        smarttable=SmartTableSettings(save_table_file=config.smarttable.save_table_file),
    )


def _datatile_id(context: RunContext, iteration_index: int) -> str:
    """Mirror the tile identifier rule used by the eager execution core."""
    paths = context.paths
    if paths is not None and paths.rawfiles:
        return paths.rawfiles[0].stem
    return str(iteration_index)
