"""Tile iteration for the v2 Runner."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from rdetoolkit.domain.mode import selected_input_checker
from rdetoolkit.models.config import Config
from rdetoolkit.models.rde2types import RdeInputDirPaths
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import TileOutputPaths, resolve_tile_paths
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig


class TileIterator(Protocol):
    """Callable shape for producing per-tile Runner reserved values."""

    def __call__(
        self,
        mode: ModeKind,
        inputdata_path: Path,
        unpacked_dir_path: Path,
        data_root: Path,
        config: RdeConfig | None = None,
    ) -> Iterator[tuple[IterationInfo, InputPaths, OutputContext]]:
        """Yield per-tile ``IterationInfo``, ``InputPaths``, and ``OutputContext`` triples."""
        ...


def iterate_tiles(
    mode: ModeKind,
    inputdata_path: Path,
    unpacked_dir_path: Path,
    data_root: Path,
    config: RdeConfig | None = None,
) -> Iterator[tuple[IterationInfo, InputPaths, OutputContext]]:
    """Yield v1-compatible tile contexts for all Runner modes.

    Args:
        mode: Effective Runner mode.
        inputdata_path: Directory containing input files.
        unpacked_dir_path: Directory used by legacy input checkers.
        data_root: The run's single resolved data root. It anchors both the
            per-tile output directories and the ``invoice``/``tasksupport``
            input directories, so one run can never read its invoice from one
            root while writing its tiles below another (ruling #1).
        config: Effective run configuration. The legacy checkers consume
            ``smarttable.save_table_file`` from it; passing ``None`` keeps the
            v1 default behavior.

    Yields:
        Per-tile ``(IterationInfo, InputPaths, OutputContext)`` triples.
    """
    src_paths = RdeInputDirPaths(
        inputdata=inputdata_path,
        invoice=data_root / "invoice",
        tasksupport=data_root / "tasksupport",
    )
    checker = selected_input_checker(
        src_paths,
        unpacked_dir_path,
        _mode_for_checker(mode),
        config=_checker_config(config),
    )
    rawfiles_by_tile, _special = checker.parse(inputdata_path)
    total = len(rawfiles_by_tile)

    for idx, rawfiles in enumerate(rawfiles_by_tile):
        tile_paths = resolve_tile_paths(data_root, idx)
        _create_output_dirs(tile_paths)
        rawfiles_tuple = tuple(rawfiles)
        yield (
            IterationInfo(index=idx, total=total, mode=mode.value),
            InputPaths(
                inputdata=inputdata_path,
                invoice=src_paths.invoice,
                tasksupport=src_paths.tasksupport,
                raw=rawfiles_tuple[0] if len(rawfiles_tuple) == 1 else None,
                rawfiles=rawfiles_tuple,
            ),
            OutputContext.from_resource_paths(tile_paths),
        )


def _checker_config(config: RdeConfig | None) -> Config | None:
    """Project the canonical config onto the v1 contract the checkers read.

    Imported lazily because ``compat.v1`` imports Runner modules; a top-level
    import would close a runner -> compat -> runner cycle.
    """
    if config is None:
        return None
    from rdetoolkit.compat.v1.callback import to_legacy_config  # noqa: PLC0415

    return to_legacy_config(config)


def _mode_for_checker(mode: ModeKind) -> str | None:
    if mode is ModeKind.multidatatile:
        return "multidatatile"
    if mode is ModeKind.rdeformat:
        return "rdeformat"
    return None


def _create_output_dirs(tile_paths: TileOutputPaths) -> None:
    """Create the twelve v1-compatible directories owned by one tile.

    The set is the one v1 ``generate_folder_paths_iterator`` creates, including
    ``temp`` and ``invoice_patch`` (Design §6.3 addendum). Iterating the
    dataclass fields keeps this creation loop and the path bundle from drifting
    apart: a directory added to ``TileOutputPaths`` is created without a second
    edit here.
    """
    for name in TileOutputPaths.__dataclass_fields__:
        path: Path = getattr(tile_paths, name)
        path.mkdir(parents=True, exist_ok=True)
