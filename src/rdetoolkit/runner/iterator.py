"""Tile iteration for the v2 Runner."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Protocol, cast

from rdetoolkit._interrupt import is_run_interrupted
from rdetoolkit.domain.input_checker import selected_input_checker
from rdetoolkit.errors import ERROR_CATALOG, RdeValidationError
from rdetoolkit.impl.compressed_controller import SystemFilesCleaner
from rdetoolkit.invoicefile import ExcelInvoiceFile
from rdetoolkit.models.config import Config
from rdetoolkit.models.rde2types import RdeInputDirPaths
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import TileOutputPaths, resolve_tile_paths
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig

#: Arity of a v1.7 ``SmartTableRawFiles`` element: ``(row_csv | None, user_files)``.
_SMARTTABLE_PAIR_LEN = 2


class EmptyExcelInvoiceError(RdeValidationError):
    """Input validation error for an Excel invoice with no registration rows."""

    def __init__(self) -> None:
        """Create the catalogued empty-input diagnostic."""
        definition = ERROR_CATALOG[4004]
        # The append-only v1 signature is narrower than the v2 runtime initializer.
        initialize = cast(Callable[..., None], super().__init__)
        initialize(code=4004, message=f"{definition.message_template} Remediation: {definition.remediation}")


def reject_empty_excelinvoice(mode: ModeKind, inputdata_path: Path) -> None:
    """Diagnose an Excel invoice with no data rows before pre-validation (#588).

    ``iterate_tiles`` already rejects a form whose checker finds no rows, but
    the Runner pre-validates ``invoice/invoice.json`` first. A blank form
    uploaded on its own -- typically a template whose data rows hold only
    formulas evaluating to ``""`` -- often comes without that invoice, so the
    run ended in 4003 RequiredArtifactMissing before the form was ever looked
    at. v1.7.1 never required the invoice for a form without rows and
    published 999; probing the form first restores the #568 outcome for it.

    "No data rows" is exactly what tile discovery sees: the rows the v1 sheet
    reader keeps, where a formula's ``""`` result is an empty cell. The probe
    only reads the workbook (no unpacking, no writes) and stays silent on
    anything it cannot judge -- another mode, zero or several candidate
    workbooks, or a workbook the reader rejects -- so those inputs keep their
    existing diagnostics.

    Args:
        mode: Effective Runner mode.
        inputdata_path: Directory containing input files.

    Raises:
        EmptyExcelInvoiceError: If the run's single Excel invoice has no data rows.
    """
    if mode is not ModeKind.excelinvoice:
        return
    workbook = _single_excel_invoice(inputdata_path)
    if workbook is None:
        return
    try:
        rows = ExcelInvoiceFile(workbook).dfexcelinvoice
    except Exception as exc:  # noqa: BLE001 -- unreadable input keeps the existing route
        if is_run_interrupted(exc):
            raise
        return
    if len(rows) == 0:
        raise EmptyExcelInvoiceError


def _single_excel_invoice(inputdata_path: Path) -> Path | None:
    """Return the one Excel invoice ``ExcelInvoiceChecker`` would select, if any."""
    if not inputdata_path.is_dir():
        return None
    cleaner = SystemFilesCleaner()
    candidates = [
        path
        for path in inputdata_path.glob("*")
        if not cleaner.is_excluded(path)
        and path.suffix.lower() in {".xls", ".xlsx"}
        and path.stem.endswith("_excel_invoice")
    ]
    return candidates[0] if len(candidates) == 1 else None


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
    groups, _special = checker.parse(inputdata_path)
    total = len(groups)
    if mode is ModeKind.excelinvoice and total == 0:
        raise EmptyExcelInvoiceError

    for idx, group in enumerate(groups):
        tile_paths = resolve_tile_paths(data_root, idx)
        _create_output_dirs(tile_paths)
        rawfiles, row_csv = _tile_files(mode, group, idx)
        yield (
            IterationInfo(index=idx, total=total, mode=mode.value),
            InputPaths(
                inputdata=inputdata_path,
                invoice=src_paths.invoice,
                tasksupport=src_paths.tasksupport,
                raw=rawfiles[0] if len(rawfiles) == 1 else None,
                rawfiles=rawfiles,
                smarttable_rawfile=row_csv,
            ),
            OutputContext.from_resource_paths(tile_paths),
        )


def _tile_files(mode: ModeKind, group: object, idx: int) -> tuple[tuple[Path, ...], Path | None]:
    """Split one checker group into the tile's user files and its row CSV.

    Since v1.7 (#503) the SmartTable checker returns ``(row_csv | None,
    user_files)`` pairs while every other checker returns flat path tuples.
    The split mirrors ``workflows.generate_folder_paths_iterator``: the row CSV
    never enters ``rawfiles`` (so it is never copied to raw storage and never
    becomes ``rawfiles[0]``) and travels only as ``smarttable_rawfile``.
    The shape is checked explicitly because the distinction is runtime-only;
    a flat tuple in SmartTable mode would otherwise surface far away, as the
    ``'tuple' object has no attribute ...`` failure this replaced.

    Args:
        mode: Effective Runner mode, which decides the group shape.
        group: One element of the checker's ``parse`` result.
        idx: Tile index, quoted in the shape error.

    Returns:
        The tile's user files and its row CSV (``None`` outside SmartTable).

    Raises:
        TypeError: If the group does not have the shape the mode implies.
    """
    if mode is not ModeKind.smarttable:
        if not isinstance(group, Sequence) or not all(isinstance(path, Path) for path in group):
            msg = f"{mode.value} tile {idx} must be a sequence of Path objects; got {group!r}"
            raise TypeError(msg)
        return tuple(group), None
    if (
        not isinstance(group, tuple)
        or len(group) != _SMARTTABLE_PAIR_LEN
        or not (group[0] is None or isinstance(group[0], Path))
        or not isinstance(group[1], tuple)
        or not all(isinstance(path, Path) for path in group[1])
    ):
        msg = f"smarttable tile {idx} must be a (row_csv | None, user_files) pair; got {group!r}"
        raise TypeError(msg)
    return group[1], group[0]


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
