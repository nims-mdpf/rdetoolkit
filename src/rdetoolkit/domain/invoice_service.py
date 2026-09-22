"""Run-owned, path-based invoice operations shared by all modes."""

from __future__ import annotations

import contextlib
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdetoolkit.domain.invoice import (
    build_excelinvoice_tile_invoice,
    build_smarttable_tile_invoice,
    load_invoice,
    smarttable_invoice_builder,
)
from rdetoolkit.domain.service_errors import validation_error
from rdetoolkit.invoicefile import apply_magic_variable, update_description_with_features
from rdetoolkit.models.rde2types import RdeDatasetPaths, RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.types import InputPaths, InvoiceData, RdeConfig

if TYPE_CHECKING:
    from rdetoolkit.runner.mode_resolver import ModeKind


#: Modes whose v1 pipeline backs the original invoice up before processing.
#: Ported verbatim from ``invoicefile._description.backup_invoice_json_files``:
#: an ExcelInvoice workbook or ``mode in {rdeformat, multidatatile}`` selects
#: ``data/temp/invoice_org.json``; every other mode keeps the original.
_BACKUP_MODES = frozenset({"excelinvoice", "multidatatile", "rdeformat"})


class InvoiceService:
    """Own run-scoped invoice preparation with explicit filesystem paths."""

    def __init__(self) -> None:
        """Create an invoice service owning this run's SmartTable material."""
        self._smarttable_builder = smarttable_invoice_builder()

    def begin_run(self) -> None:
        """Release the SmartTable material of any previously executed run.

        Everything run-scoped now belongs to this instance: the base invoice
        snapshot lives on the builder, and the per-tile row dictionary is
        returned by value from :meth:`prepare_tile` (ruling #2). No root is
        accepted, because there is nothing keyed by one left to release --
        which is what stops a second run on the same root from erasing this
        run's material (reviews F1/R4).
        """
        self._smarttable_builder.reset()

    def end_run(self) -> None:
        """Release this run's retained SmartTable material.

        Runs are bounded, so the base invoice snapshot is released here as well
        as at ``begin_run``: a long-lived process that executes many runs never
        accumulates the material of the runs it already finished.
        """
        self._smarttable_builder.reset()

    def backup(
        self,
        mode: ModeKind,
        *,
        data_root: Path,
        inputdata_path: Path,
        rawfiles: tuple[Path, ...] = (),
    ) -> Path:
        """Return the run-level invoice source, backing it up when required.

        Args:
            mode: Effective Runner mode.
            data_root: The run's single resolved data root.
            inputdata_path: Explicit input directory used for Excel discovery.
            rawfiles: Current tile inputs, if already known.

        Returns:
            Original or backed-up invoice path.
        """
        invoice_source = data_root / "invoice" / "invoice.json"
        _ = inputdata_path, rawfiles
        if _mode_value(mode) not in _BACKUP_MODES:
            return invoice_source
        if not invoice_source.exists():
            return invoice_source
        backup_path = invoice_source_for(mode, data_root=data_root)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(invoice_source, backup_path)
        return backup_path

    def prepare_tile(
        self,
        mode: ModeKind,
        *,
        paths: InputPaths,
        invoice_dir: Path,
        iteration_index: int,
        invariant_invoice: InvoiceData | None,
        invoice_source: Path,
    ) -> tuple[InvoiceData | None, dict[str, Any] | None]:
        """Prepare one tile invoice without a legacy mode processor.

        Args:
            mode: Effective Runner mode.
            paths: Explicit input paths for the tile.
            invoice_dir: Explicit destination invoice directory.
            iteration_index: Zero-based tile index.
            invariant_invoice: Preloaded invoice shared by invariant modes.
            invoice_source: Run-level source or backup invoice.

        Returns:
            The prepared tile invoice (``None`` when the mode has no builder)
            and the SmartTable row dictionary for this tile (``None`` for every
            other mode). The row dictionary is returned instead of being
            retained anywhere, so it can only reach this tile's own invoker
            (ruling #2).
        """
        destination = invoice_dir / "invoice.json"
        if invariant_invoice is not None:
            _copy_invoice(invoice_source, destination)
            return invariant_invoice, None
        mode_value = _mode_value(mode)
        schema = paths.tasksupport / "invoice.schema.json"
        if mode_value == "excelinvoice":
            candidates = (*paths.rawfiles, *_directory_files(paths.inputdata))
            return (
                build_excelinvoice_tile_invoice(
                    excel_path=_first_matching(candidates, suffixes=(".xlsx", ".xlsm", ".xls")),
                    invoice_org=invoice_source,
                    invoice_schema_path=schema,
                    dist_path=destination,
                    idx=iteration_index,
                ),
                None,
            )
        if mode_value == "smarttable":
            return build_smarttable_tile_invoice(
                smarttable_rowfile=_first_matching(paths.rawfiles, prefixes=("fsmarttable_",), suffixes=(".csv",)),
                invoice_org=invoice_source,
                invoice_schema_path=schema,
                dist_path=destination,
                builder=self._smarttable_builder,
            )
        return None, None

    def invariant_invoice(self, mode: ModeKind, *, data_root: Path) -> InvoiceData | None:
        """Load the invariant invoice for modes that share one source.

        Args:
            mode: Effective Runner mode.
            data_root: The run's single resolved data root.

        Returns:
            Loaded invoice or None for per-tile invoice modes.
        """
        invoice_path = data_root / "invoice" / "invoice.json"
        mode_value = _mode_value(mode)
        if mode_value == "invoice":
            inputdata = data_root / "inputdata"
            if not invoice_path.exists() and inputdata.exists() and not tuple(sorted(inputdata.iterdir())):
                return None
            return load_invoice(invoice_path)
        if mode_value in {"multidatatile", "rdeformat"} and invoice_path.exists():
            return load_invoice(invoice_path)
        return None

    def apply_step(
        self,
        step: str,
        *,
        config: RdeConfig,
        dataset_paths: RdeDatasetPaths,
        feature_updater: Callable[[], None] | None = None,
    ) -> None:
        """Apply exactly one invoice artifact step.

        The caller owns the order (Session I-REVIEW-A ruling #5): v1's
        MultiDataTile and ExcelInvoice pipelines expand magic variables
        *before* exporting the structured invoice, and review R3 showed that
        the difference is observable as soon as one step fails. A ``frozenset``
        of enabled steps could not express that, so the sequence now comes from
        the mode and this method performs one named step at a time.

        The structured copy takes ``invoice_org`` — the run-level source
        invoice — exactly like v1's ``StructuredInvoiceSaver``; copying the
        tile invoice instead would publish magic-variable substitutions v1
        never writes there.

        The whole v1 dataset bundle is required — not just a few paths —
        because ``apply_magic_variable`` resolves ``${invoice:...}`` from
        ``dataset_paths.invoice_org`` and ``${metadata:...}`` from the tile's
        ``meta/metadata.json``, exactly as v1's ``VariableApplier`` does.

        Args:
            step: One of ``structured`` / ``magic`` / ``description``.
            config: Canonical run configuration.
            dataset_paths: v1 dataset bundle for the tile being finalized.
            feature_updater: Optional replacement for the description update.

        Raises:
            FileNotFoundError: If the structured copy is enabled but the source
                invoice is missing (v1 ``StructuredInvoiceSaver`` behavior).
            ValueError: If ``step`` is not a known invoice artifact step.
        """
        resource = dataset_paths.output_paths
        invoice_path = resource.invoice / "invoice.json"
        if step == INVOICE_STEP_STRUCTURED:
            if config.system.save_invoice_to_structured:
                self._save_structured_invoice(resource.invoice_org, resource.struct)
            return
        if step == INVOICE_STEP_MAGIC:
            if config.system.magic_variable and resource.rawfiles:
                apply_magic_variable(
                    invoice_path,
                    resource.rawfiles[0],
                    save_filepath=invoice_path,
                    dataset_paths=dataset_paths,
                )
            return
        if step == INVOICE_STEP_DESCRIPTION:
            if config.system.feature_description:
                updater = feature_updater or build_description_updater(dataset_paths)
                # v1's DescriptionUpdater suppresses every failure because the
                # description transfer is optional enrichment, not an artifact.
                with contextlib.suppress(Exception):
                    updater()
            return
        message = f"Unknown invoice artifact step: {step!r}"
        raise ValueError(message)

    @staticmethod
    def _save_structured_invoice(invoice_org: Path, structured_dir: Path) -> None:
        if not invoice_org.exists():
            msg = f"Original invoice not found for structured export: {invoice_org}"
            raise FileNotFoundError(msg)
        structured_dir.mkdir(parents=True, exist_ok=True)
        destination = structured_dir / "invoice.json"
        if invoice_org.resolve() != destination.resolve():
            shutil.copy2(invoice_org, destination)


def invoice_source_for(mode: ModeKind, *, data_root: Path) -> Path:
    """Return the run-level ``invoice_org`` this mode reads.

    The decision is the v1 mode branch and nothing else. Deriving it from the
    *presence* of ``data/temp/invoice_org.json`` — as this module did before
    Session I-REVIEW-A — let a backup left behind by an earlier run on the same
    root become the source of the next one (review R2): the structured export,
    the ``${invoice:...}`` magic variables and the v1 callback's ``invoice_org``
    all silently published an invoice this run never read.

    Args:
        mode: Effective Runner mode.
        data_root: The run's single resolved data root.

    Returns:
        Path of the run-level source invoice, whether or not it exists yet.
    """
    if _mode_value(mode) in _BACKUP_MODES:
        return data_root / "temp" / "invoice_org.json"
    return data_root / "invoice" / "invoice.json"


def build_tile_dataset_paths(
    *,
    paths: InputPaths,
    out: Any,
    invoice_org: Path,
) -> RdeDatasetPaths:
    """Build the v1 dataset bundle for one tile's invoice artifact stage.

    ``RdeDatasetPaths`` is a v1 primitive (``models.rde2types``) that the v1
    invoice helpers consume directly, so the domain layer constructs it here
    rather than importing the ``compat`` adapter. ``RdeInputDirPaths.config``
    keeps its v1 default: none of the invoice steps reads it.

    Args:
        paths: Runner input paths for the tile.
        out: Runner output context for the tile.
        invoice_org: Run-level source invoice.

    Returns:
        The v1 bundle expected by ``apply_magic_variable`` and
        ``update_description_with_features``.
    """
    resource = RdeOutputResourcePath(
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
        invoice_org=invoice_org,
        attachment=out.attachment,
    )
    return RdeDatasetPaths(
        input_paths=RdeInputDirPaths(
            inputdata=paths.inputdata,
            invoice=paths.invoice,
            tasksupport=paths.tasksupport,
        ),
        output_paths=resource,
    )


def build_description_updater(dataset_paths: RdeDatasetPaths) -> Callable[[], None]:
    """Build the v1 feature-description update operation for one tile.

    Args:
        dataset_paths: v1 dataset bundle for the tile.

    Returns:
        Callable performing the v1 ``update_description_with_features`` call.
    """

    def _update() -> None:
        update_description_with_features(
            dataset_paths.output_paths,
            dataset_paths.output_paths.invoice / "invoice.json",
            dataset_paths.tasksupport / "metadata-def.json",
        )

    return _update


#: Canonical names of the three invoice artifact steps a mode may run.
INVOICE_STEP_STRUCTURED = "structured"
INVOICE_STEP_MAGIC = "magic"
INVOICE_STEP_DESCRIPTION = "description"
INVOICE_STEPS = frozenset({INVOICE_STEP_STRUCTURED, INVOICE_STEP_MAGIC, INVOICE_STEP_DESCRIPTION})


def _directory_files(directory: Path) -> tuple[Path, ...]:
    return tuple(sorted(directory.iterdir())) if directory.exists() else ()


def _first_matching(
    paths: tuple[Path, ...],
    *,
    suffixes: tuple[str, ...],
    prefixes: tuple[str, ...] = (),
) -> Path:
    ordered = tuple(sorted(paths))
    for path in ordered:
        if path.suffix.lower() in suffixes and (not prefixes or path.name.startswith(prefixes)):
            return path
    for path in ordered:
        if path.suffix.lower() in suffixes:
            return path
    message = f"No input file matched suffixes {suffixes}"
    raise validation_error(4003, message)


def _copy_invoice(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def _mode_value(mode: Any) -> str:
    value = getattr(mode, "value", mode)
    return str(value)
