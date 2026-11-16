"""Read-only mode selection and explicit-intent policy (Design §6.2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Literal
from zipfile import BadZipFile, ZipFile, ZipInfo

from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.impl._zip_encoding import resolve_filename

if TYPE_CHECKING:
    from rdetoolkit.types import RdeConfig


class ModeKind(str, Enum):
    """Canonical registration modes accepted by the v2 configuration boundary."""

    invoice = "invoice"
    excelinvoice = "excelinvoice"
    multidatatile = "multidatatile"
    smarttable = "smarttable"
    rdeformat = "rdeformat"


_MODE_ALIASES = {mode.value: mode for mode in ModeKind} | {
    "Invoice": ModeKind.invoice,
    "MultiDataTile": ModeKind.multidatatile,
    "SmartTableInvoice": ModeKind.smarttable,
    "ExcelInvoice": ModeKind.excelinvoice,
    "RDEFormat": ModeKind.rdeformat,
}


def normalize_mode_name(value: object) -> ModeKind:
    """Validate an exact canonical mode name or a documented legacy alias.

    Args:
        value: Configured mode identifier.

    Returns:
        Canonical mode.

    Raises:
        RdeConfigError: For an unknown or non-string identifier (1002).
    """
    if isinstance(value, str) and value in _MODE_ALIASES:
        return _MODE_ALIASES[value]
    valid = ", ".join(mode.value for mode in ModeKind)
    raise RdeConfigError(code=1002, message=f"Invalid system.extended_mode. Valid names: {valid}. Legacy aliases: Invoice, MultiDataTile, SmartTableInvoice, ExcelInvoice, RDEFormat.")


def _normalize_mode_setting(value: object) -> str:
    mode = normalize_mode_name(value)
    # This alias means Invoice on the callback path until a flow target is known.
    return "RDEFormat" if value == "RDEFormat" else mode.value


@dataclass(frozen=True, slots=True)
class ModeEvidence:
    """A filename and format indicator, without input payloads."""

    mode: ModeKind
    filename: str
    indicator: str


@dataclass(frozen=True, slots=True)
class ModeDecision:
    """Immutable explanation of configured intent and observed input evidence."""

    configured_mode: ModeKind | None
    chosen_mode: ModeKind
    candidates: tuple[ModeKind, ...]
    evidence: tuple[ModeEvidence, ...]
    reason_codes: tuple[str, ...]
    ambiguous: bool = False
    warning_codes: tuple[int, ...] = ()
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible representation.

        Returns:
            Versioned decision containing names and reason identifiers only.
        """
        return {
            "schema_version": self.schema_version,
            "configured_mode": None if self.configured_mode is None else self.configured_mode.value,
            "chosen_mode": self.chosen_mode.value,
            "candidates": [mode.value for mode in self.candidates],
            "evidence": [{"mode": item.mode.value, "filename": item.filename, "indicator": item.indicator} for item in self.evidence],
            "reason_codes": list(self.reason_codes),
            "ambiguous": self.ambiguous,
            "warning_codes": list(self.warning_codes),
        }


def _input_evidence(inputdata_path: Path) -> tuple[ModeEvidence, ...]:
    evidence: list[ModeEvidence] = []
    for path in sorted(inputdata_path.glob("*"), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.name.startswith("smarttable_") and path.suffix.lower() in {".csv", ".tsv", ".xlsx"}:
            evidence.append(ModeEvidence(ModeKind.smarttable, path.name, "smarttable_filename"))
        if path.stem.endswith("_excel_invoice") and path.suffix.lower() in {".xls", ".xlsx"}:
            evidence.append(ModeEvidence(ModeKind.excelinvoice, path.name, "excelinvoice_filename"))
    return tuple(evidence)


def _mode_error(code: int, reason: str, *, evidence: tuple[ModeEvidence, ...] = ()) -> RdeConfigError:
    definition = ERROR_CATALOG[code]
    return RdeConfigError(
        code=code,
        message=f"{definition.message_template.format(reason=reason)} Remediation: {definition.remediation}",
        detail={"evidence": [{"mode": item.mode.value, "filename": item.filename, "indicator": item.indicator} for item in evidence]},
    )


def _archive_entries(archive: Path) -> list[tuple[ZipInfo, str]]:
    try:
        with ZipFile(archive) as opened:
            return [(item, resolve_filename(item)) for item in opened.infolist()]
    except (BadZipFile, OSError, ValueError) as exc:
        raise _mode_error(1008, f"Unreadable ZIP archive {archive.name}") from exc


def _archive_layout_problem(entries: list[tuple[ZipInfo, str]]) -> str | None:
    files = [str(PurePosixPath(name)).casefold() for info, name in entries if not info.is_dir()]
    if len(set(files)) != len(files):
        return "Duplicate or case-colliding ZIP members"
    directories: dict[str, str] = {}
    file_keys = set(files)
    for info, name in entries:
        problem = _archive_entry_problem(info, name, file_keys, directories)
        if problem is not None:
            return problem
    return None


def _archive_entry_problem(info: ZipInfo, name: str, files: set[str], directories: dict[str, str]) -> str | None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        return "Unsafe ZIP member paths"
    parents = (path, *path.parents) if info.is_dir() else tuple(path.parents)
    return _archive_directory_problem(parents, files, directories)


def _archive_directory_problem(parents: tuple[PurePosixPath, ...], files: set[str], directories: dict[str, str]) -> str | None:
    for parent in parents:
        name = str(parent)
        key = name.casefold()
        if key in files or (key in directories and directories[key] != name):
            return "Colliding archive directory names"
        directories[key] = name
    return None


def _validate_archive_members(archive: Path) -> None:
    problem = _archive_layout_problem(_archive_entries(archive))
    if problem is not None:
        raise _mode_error(1007, f"{problem} in {archive.name}")


def _special_archives(inputdata_path: Path) -> list[Path]:
    return sorted(path for path in inputdata_path.glob("*") if path.is_file() and path.suffix.lower() == ".zip")


def _validate_special_archives(mode: ModeKind, inputdata_path: Path) -> None:
    archives = _special_archives(inputdata_path)
    if mode is ModeKind.rdeformat and not archives:
        raise _mode_error(1008, "rdeformat requires one ZIP archive")
    if len(archives) > 1:
        raise _mode_error(1007, f"{mode.value} has multiple ZIP archives: {', '.join(path.name for path in archives)}")
    for archive in archives:
        _validate_archive_members(archive)


def _select_v2(configured: ModeKind | None, evidence: tuple[ModeEvidence, ...]) -> tuple[ModeKind, str]:
    if len(evidence) > 1:
        raise _mode_error(1007, f"Multiple special input files: {', '.join(item.filename for item in evidence)}", evidence=evidence)
    detected = evidence[0].mode if evidence else None
    _validate_requested_mode(configured, detected, evidence)
    if configured is not None:
        return configured, "explicit_mode"
    return (detected, "unique_file_evidence") if detected is not None else (ModeKind.invoice, "default_invoice")


def _validate_requested_mode(configured: ModeKind | None, detected: ModeKind | None, evidence: tuple[ModeEvidence, ...]) -> None:
    if configured is not None and detected is not None and configured is not detected:
        raise _mode_error(1005, f"system.extended_mode={configured.value} conflicts with {evidence[0].filename} ({detected.value})", evidence=evidence)
    if configured in {ModeKind.smarttable, ModeKind.excelinvoice} and detected is None:
        raise _mode_error(1008, f"system.extended_mode={configured.value} requires its matching special input file")


def _legacy_choice(raw_mode: str, evidence: tuple[ModeEvidence, ...]) -> ModeKind:
    legacy_mode = {"MultiDataTile": ModeKind.multidatatile, "multidatatile": ModeKind.multidatatile, "rdeformat": ModeKind.rdeformat}.get(raw_mode, ModeKind.invoice)
    detected = {item.mode for item in evidence}
    return next((mode for mode in (ModeKind.smarttable, ModeKind.excelinvoice) if mode in detected), legacy_mode)


def _candidate_modes(configured: ModeKind | None, chosen: ModeKind, evidence: tuple[ModeEvidence, ...]) -> tuple[ModeKind, ...]:
    modes = [] if configured is None else [configured]
    modes.extend(item.mode for item in evidence)
    modes.append(chosen)
    return tuple(dict.fromkeys(modes))


def decide_mode(config: RdeConfig, inputdata_path: Path, *, contract: Literal["v1", "v2"] = "v2") -> ModeDecision:
    """Select a mode from a read-only input snapshot.

    Args:
        config: Effective configuration, including its explicitly set fields.
        inputdata_path: Directory to inspect without extracting or writing.
        contract: Strict v2 policy or frozen callback precedence.

    Returns:
        Immutable decision with evidence, candidate modes, and warning codes.

    Raises:
        RdeConfigError: For invalid names, conflicts, ambiguity, or missing inputs.
    """
    explicit = "extended_mode" in config.system.model_fields_set
    raw_mode = config.system.extended_mode
    evidence = _input_evidence(inputdata_path)
    if contract == "v1":
        requested = _legacy_choice(raw_mode, ())
        configured = requested if explicit else None
        chosen = _legacy_choice(raw_mode, evidence)
        warnings = (1001,) if explicit and chosen is not requested else ()
        reason = "legacy_file_override" if warnings else "legacy_precedence"
    else:
        configured = normalize_mode_name(raw_mode) if explicit else None
        chosen, reason = _select_v2(configured, evidence)
        _validate_selected_inputs(chosen, inputdata_path)
        warnings = ()
    return ModeDecision(configured, chosen, _candidate_modes(configured, chosen, evidence), evidence, (reason,), len(evidence) > 1, warnings)


def _validate_selected_inputs(mode: ModeKind, inputdata_path: Path) -> None:
    if mode in {ModeKind.smarttable, ModeKind.excelinvoice, ModeKind.rdeformat}:
        _validate_special_archives(mode, inputdata_path)
