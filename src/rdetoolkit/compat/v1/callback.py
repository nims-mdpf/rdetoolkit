"""V1 dataset-callback adapter for the unified Runner (Design §7, §3.4).

This module owns three things: converting one tile's v2 material into the v1
callback arguments, calling the user callback with the signature it expects, and
— since Session J1 (ADR-023 decision 5) — running that call as a *flow* so the
callback entry point produces the same execution history a ``@flow`` does. The
signature rules are a port of the v1 ``DatasetRunner``
(``processing/processors/datasets.py``), which stays the behavioral oracle.

The provenance semantics are deliberately thin: the callback is recorded as the
parent flow of the ``@node`` calls it makes, and nothing else inside it is
observable. That is a structural consequence of recording ``@node`` calls rather
than a limitation to work around (Design §3.4 addendum).
"""

from __future__ import annotations

import copy
import inspect
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from rdetoolkit.api.request import LegacyCallbackTarget
from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.flow import derive_flow_id, push_flow
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
from rdetoolkit.runner.execute import (
    ExecutionResult,
    TileExecutionError,
    _emit_node_events,
    _failed_error,
)

if TYPE_CHECKING:
    from rdetoolkit.api.request import ExecutionTarget
    from rdetoolkit.core.context import RunContext
    from rdetoolkit.report.events import EventSink
    from rdetoolkit.runner.planner import TileMaterial
    from rdetoolkit.types import RdeConfig


#: ``flow_id`` reported by a v1 run that supplies no ``custom_dataset_function``
#: at all. Dotted like every other flow id (Session J1 ruling #1): the colon
#: spelling would have made ``parent_flow == flow_id`` unverifiable.
NO_CALLBACK_FLOW_ID = "rdetoolkit.compat.v1.callback.none"

_LEGACY_ARG_COUNT = 2
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

    # v1 handed its callback CWD-relative paths (``StorageDir`` /
    # ``DirectoryOps("data")``); a template comparing ``rawfiles`` against
    # ``Path("data/...")`` relies on it (v1.7 #503 integration tests). The
    # unified Runner works on absolute paths, so the standard layout is
    # projected back here, exactly where the v1 surface is built.
    v1 = _V1PathForm.for_tile(paths.invoice.parent)
    input_paths = RdeInputDirPaths(
        inputdata=v1.path(paths.inputdata),
        invoice=v1.path(paths.invoice),
        tasksupport=v1.path(paths.tasksupport),
        config=to_legacy_config(context.config),
    )
    tile_root = out.invoice.parent
    # v1.7 (#503): the row CSV is carried explicitly by the tile, never
    # inferred from ``rawfiles``, and is handed over under the new name only —
    # the ``smarttable_rowfile=`` keyword would raise v1's DeprecationWarning.
    smarttable_rawfile = paths.smarttable_rawfile
    output_paths = RdeOutputResourcePath(
        raw=v1.path(out.raw),
        nonshared_raw=v1.path(out.nonshared_raw),
        rawfiles=tuple(v1.path(path) for path in paths.rawfiles),
        struct=v1.path(out.struct),
        main_image=v1.path(out.main_image),
        other_image=v1.path(out.other_image),
        meta=v1.path(out.meta),
        thumbnail=v1.path(out.thumbnail),
        logs=v1.path(out.logs),
        invoice=v1.path(out.invoice),
        invoice_schema_json=v1.path(paths.tasksupport / "invoice.schema.json"),
        invoice_org=v1.path(material.invoice_source),
        # OutputContext deliberately omits these two directories (Design §6.3
        # addendum), so the tile root they share with invoice/ resolves them.
        temp=v1.path(tile_root / "temp"),
        invoice_patch=v1.path(tile_root / "invoice_patch"),
        smarttable_rawfile=None if smarttable_rawfile is None else v1.path(smarttable_rawfile),
        smarttable_row_data=(
            dict(material.smarttable_row_data)
            if smarttable_rawfile is not None and material.smarttable_row_data is not None
            else None
        ),
        attachment=v1.path(out.attachment),
    )
    return RdeDatasetPaths(input_paths=input_paths, output_paths=output_paths)


class _V1PathForm:
    """Project Runner paths onto the form a v1 callback received.

    v1 built every path from the relative ``data`` directory, so its callback
    saw ``data/inputdata/...``, ``data/divided/0001/raw`` and so on, relative to
    the CWD. That holds for the standard layout only — the data root is
    ``<cwd>/data``, the same condition under which the callback entry keeps
    v1's ``StorageDir`` log seam (contracts.md §J-REVIEW-3). Any other root
    (alias-flat, or a Runner rooted elsewhere) has no v1 counterpart and keeps
    absolute paths.
    """

    def __init__(self, base: Path | None) -> None:
        self._base = base

    @classmethod
    def for_tile(cls, data_root: Path) -> _V1PathForm:
        """Return the projection for a tile below ``data_root``.

        Args:
            data_root: The run's data root (``InputPaths.invoice.parent``).

        Returns:
            A CWD-relative projection for the standard layout, else identity.
        """
        cwd = Path.cwd()
        return cls(cwd if data_root == cwd / "data" else None)

    def path(self, path: Path) -> Path:
        """Return ``path`` as v1 would have handed it to the callback.

        Args:
            path: An absolute Runner path.

        Returns:
            The CWD-relative path when the projection applies and ``path`` lies
            below the CWD; ``path`` unchanged otherwise.
        """
        if self._base is None or not path.is_relative_to(self._base):
            return path
        return path.relative_to(self._base)


def callback_flow_id(callback: Callable[..., Any] | None) -> str:
    """Return the flow identifier a v1 dataset callback is recorded under.

    The callback is treated as the flow it effectively is (ADR-023 decision 5),
    so it shares the single derivation with ``@flow`` and with
    ``RunReport.flow_id``. That is what makes the Design §3.4 invariant
    ``parent_flow == RunReport.flow_id`` hold on the v1 entry point too.

    Args:
        callback: User dataset callback, or ``None`` for a callback-free v1 run.

    Returns:
        The callback's dotted stable reference, or :data:`NO_CALLBACK_FLOW_ID`.
    """
    return NO_CALLBACK_FLOW_ID if callback is None else derive_flow_id(callback)


class LegacyCallbackInvoker:
    """Invoke a v1 dataset callback for one planned tile, recording it as a flow."""

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
        """Convert the tile material and call the v1 dataset callback as a flow.

        The call happens inside the same ``CallLogRecorder`` context ``run_tile``
        builds for a ``@flow``, with the callback's flow id pushed on the flow
        stack. Every ``@node`` the callback calls is therefore recorded in this
        tile's call log with ``parent_flow`` equal to the run's ``flow_id``, and
        bridged to ``node.*`` events — on success and on failure alike.

        Args:
            target: Normalized legacy callback target.
            context: Reserved values for the current tile.
            event_sink: Sink receiving the bridged node events.
            run_id: Active run identifier carried by those events.
            config: Effective run configuration owning the recorder's
                provenance and type-check settings.
            material: Run-owned tile material handed to the v1 bundle.

        Returns:
            A completed result carrying the tile's call log.

        Raises:
            TypeError: If the target is not a legacy callback target.
            ValueError: If the tile context has no iteration information.
            TileExecutionError: If the callback fails. The error carries the
                records observed before the failure — the same contract
                ``run_tile`` uses — and keeps the original exception as its
                ``__cause__`` so the tile boundary can restore a
                ``StructuredError``'s ``ecode``/``emsg`` (§I6-0).
        """
        if not isinstance(target, LegacyCallbackTarget):
            msg = "LegacyCallbackInvoker requires a LegacyCallbackTarget"
            raise TypeError(msg)

        iteration = context.iteration
        if iteration is None:
            msg = "RunContext.iteration is required for tile execution."
            raise ValueError(msg)

        callback = target.function
        # Argument conversion is pure adapter work, not user code: keeping it
        # outside the recorder context means a conversion defect stays an
        # ordinary framework failure instead of being reported as a tile's node
        # execution failure. A callback-free v1 run converts nothing.
        dataset_paths = None if callback is None else to_legacy_dataset_paths(context, material=material)
        recorder = CallLogRecorder(
            repr_head=config.provenance.repr_head,
            repr_head_len=config.provenance.repr_head_len,
            type_check=cast("Literal['off', 'warn', 'strict']", config.execution.type_check),
            iteration_index=iteration.index,
        )
        datatile_id = _datatile_id(context, iteration.index)
        try:
            # The recorder and the flow id are installed even for a callback-free
            # run, so this entry point has exactly one execution shape.
            with recorder, push_flow(callback_flow_id(callback)):
                # Both operands are the same condition; the second one is what
                # narrows ``dataset_paths`` for the type checker.
                if callback is not None and dataset_paths is not None:
                    _call_with_matching_signature(callback, dataset_paths)
        except Exception as exc:
            _emit_node_events(event_sink, run_id=run_id, records=recorder.records)
            failed = ExecutionResult(
                iteration_index=iteration.index,
                status="failed",
                call_records=recorder.records,
                outputs=(),
                error=_failed_error(exc, recorder.records),
                datatile_id=datatile_id,
                stacktrace=traceback.format_exc(),
            )
            raise TileExecutionError(failed, exc) from exc
        _emit_node_events(event_sink, run_id=run_id, records=recorder.records)
        # A v1 callback's return value is ignored by contract, so a tile of this
        # entry point never has outputs — only the call log it produced.
        return ExecutionResult(
            iteration_index=iteration.index,
            status="completed",
            call_records=recorder.records,
            outputs=(),
            datatile_id=datatile_id,
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

    ``RdeConfig.custom`` is restored as v1 ``Config`` *extra* fields (Session
    J-REVIEW ruling #1). ``ConfigNormalizer`` moves every unknown top-level key
    of a v1 configuration -- a structured program's own ``threshold`` and the
    like -- into ``custom``; a callback reads them back as
    ``srcpaths.config.<key>``, so the projection must put them where v1 had
    them. A key spelled like a v1 field is skipped: there the structured v1
    field is authoritative.

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
        **_legacy_extra_fields(config.custom),
    )


def _legacy_extra_fields(custom: dict[str, Any]) -> dict[str, Any]:
    """Return the ``custom`` entries that can be v1 ``Config`` extra fields.

    Deep-copied so a callback mutating its config cannot reach back into the
    run's effective configuration, which later steps still read.
    """
    return {
        key: copy.deepcopy(value)
        for key, value in custom.items()
        if key not in Config.model_fields
    }


def _datatile_id(context: RunContext, iteration_index: int) -> str:
    """Mirror the tile identifier rule used by the eager execution core."""
    paths = context.paths
    if paths is not None and paths.rawfiles:
        return paths.rawfiles[0].stem
    return str(iteration_index)
