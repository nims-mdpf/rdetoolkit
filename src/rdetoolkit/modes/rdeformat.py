"""RDEFormat-mode planning handler for the unified Runner."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from rdetoolkit.domain.service_errors import execution_error
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import create_common_tiles

if TYPE_CHECKING:
    from rdetoolkit.modes.protocol import PlanningContext, RawCopyStrategy
    from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
    from rdetoolkit.types import RdeConfig

#: Catalog code v1 raised (as ``RuntimeError``) when a raw copy failed.
_COPY_FAILED_CODE = 3001

#: Destination components in v1 ``RDEFormatFileCopier`` order
#: (``processing/processors/files.py``). The order is part of the contract: v1
#: takes the *first* component that appears in the input path and stops, so
#: ``raw`` preceding ``nonshared_raw`` and ``meta`` decides where an ambiguous
#: path such as ``temp/0000/meta/raw/x.txt`` lands.
_DESTINATION_COMPONENTS = (
    "raw",
    "main_image",
    "other_image",
    "meta",
    "structured",
    "logs",
    "nonshared_raw",
)

#: Post-invoke artifact stages the v1 RDEFormat pipeline actually runs, in
#: order. ``processing/factories.py::RDEFormatPipelineBuilder`` is
#: StandardInvoiceInitializer -> RDEFormatFileCopier -> DatasetRunner ->
#: ThumbnailGenerator -> DescriptionUpdater: it has neither
#: ``StructuredInvoiceSaver`` nor ``VariableApplier``.
_ARTIFACT_STAGE_ORDER = ("thumbnail", "description")


class RdeFormatRawCopyStrategy:
    """Publish raw inputs by path component, as v1 ``RDEFormatFileCopier`` does.

    RDEFormat inputs arrive already laid out in RDE's own directory shape
    (``temp/0000/raw/…``, ``temp/0000/meta/…``, …), so v1 does not copy a tile's
    files into ``raw/`` and ``nonshared_raw/`` at all: it dispatches each file to
    the output directory named by one of its path components, and it applies no
    configuration gate while doing so.
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
        """Copy each input to the tile directory its path names.

        Args:
            source_files: Unpacked RDEFormat inputs belonging to one tile.
            raw_dir: Tile ``raw`` destination, and the anchor for its siblings.
            nonshared_raw_dir: Tile ``nonshared_raw`` destination.
            config: Canonical run configuration. Unused: v1's
                ``RDEFormatFileCopier`` reads neither ``save_raw`` nor
                ``save_nonshared_raw``.
            smarttable: Unused. SmartTable input filtering is a different
                mode's rule and v1 never applies it to RDEFormat.
            data_root: The run's single resolved data root, which bounds the
                classification (ruling #7).
        """
        del config, smarttable
        destinations = _destinations(raw_dir=raw_dir, nonshared_raw_dir=nonshared_raw_dir)
        # Sorted for determinism: the copy order is not part of any contract,
        # but a stable one keeps a partial failure reproducible.
        for source in sorted(source_files):
            components = _classifiable_parts(source, data_root)
            for component, destination in destinations.items():
                if component in components:
                    _copy_one(source, destination)
                    break


def _classifiable_parts(source: Path, data_root: Path) -> tuple[str, ...]:
    """Return the path components that may classify one unpacked input.

    v1's ``RDEFormatFileCopier`` sees a CWD-relative ``data/temp/0000/raw/...``,
    so only directories *inside* the project can decide a destination. The v2
    Runner passes absolute paths, which additionally expose every ancestor of
    the project: a research share named ``raw`` silently rerouted structured
    output (review R1). Restricting the comparison to the part of the path
    below the data root restores v1's meaning.

    A source that the data root does not contain has no classifiable
    components at all, so it is left unpublished rather than guessed at.
    """
    try:
        relative = source.relative_to(data_root)
    except ValueError:
        return ()
    return relative.parts[:-1]


def _destinations(*, raw_dir: Path, nonshared_raw_dir: Path) -> dict[str, Path]:
    """Map each v1 destination component onto this tile's output directory.

    The ``RawCopyStrategy`` seam carries only the two raw directories, so the
    remaining five are resolved from the tile root they share
    (``runner/paths.py`` places all twelve tile directories side by side). The
    two directories the seam does pass are used verbatim rather than rebuilt,
    so a caller that redirects them stays in control.
    """
    tile_root = raw_dir.parent
    resolved = {component: tile_root / component for component in _DESTINATION_COMPONENTS}
    resolved["raw"] = raw_dir
    resolved["nonshared_raw"] = nonshared_raw_dir
    return resolved


def _copy_one(source: Path, destination: Path) -> None:
    """Copy one input, catalogueing failure the way the domain services do.

    Directory creation stays owned by the Runner (Design §6.4), so a missing
    destination is a real failure here instead of being papered over: v1 relied
    on ``StandardInvoiceInitializer`` having created the tree first.
    """
    target = destination / source.name
    try:
        shutil.copy(source, target)
    except Exception as exc:
        message = f"Failed to copy {source} --> {target}"
        raise execution_error(_COPY_FAILED_CODE, message) from exc


class RdeFormatModeHandler:
    """Plan RDEFormat-mode tiles and own its two v1-specific artifact rules."""

    kind = ModeKind.rdeformat

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        """Create RDEFormat-mode tile plans.

        Args:
            context: Run-scoped paths and invoice operations.

        Returns:
            Lazily iterable common tile plans for the executor.
        """
        return create_common_tiles(self.kind, context)

    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None:
        """Return the component-dispatching RDEFormat raw copy strategy.

        Args:
            plan: Immutable run execution plan.

        Returns:
            The RDEFormat strategy, replacing the generic ``RawArtifactService``.
        """
        _ = plan
        return RdeFormatRawCopyStrategy()

    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None:
        """Return only the artifact stages the v1 RDEFormat pipeline runs.

        Args:
            plan: Immutable run execution plan.

        Returns:
            The thumbnail and description stages, in order; the structured
            invoice export and the magic-variable substitution have no
            processor in this pipeline.
        """
        _ = plan
        return _ARTIFACT_STAGE_ORDER
