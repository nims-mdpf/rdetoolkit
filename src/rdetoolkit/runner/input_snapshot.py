"""Read-only input grouping shared by strict planning and explanation."""

from __future__ import annotations

import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from rdetoolkit.domain.mode_selection import ModeKind
from rdetoolkit.errors import ERROR_CATALOG, RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.impl._zip_encoding import extract_zip_with_encoding, resolve_filename
from rdetoolkit.impl.compressed_controller import SystemFilesCleaner
from rdetoolkit.invoicefile import ExcelInvoiceFile, SmartTableFile
from rdetoolkit.types import RdeConfig


@dataclass(frozen=True, slots=True)
class InputReference:
    """A source file or an unextracted member of one source archive."""

    source: Path
    member: str | None = None

    @property
    def name(self) -> str:
        """Return the display name without reading file contents."""
        return self.source.name if self.member is None else f"{self.source.name}!/{self.member}"

    def materialized_path(self, unpacked: Path) -> Path:
        """Resolve where this reference is read after materialization."""
        return self.source if self.member is None else unpacked / self.member


@dataclass(frozen=True, slots=True)
class InputGroup:
    """One registration tile's ordered files and optional table row."""

    files: tuple[InputReference, ...]
    source_row: int | None = None
    original_table: bool = False


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    """Immutable grouping that performs no extraction or artifact writes."""

    mode: ModeKind
    groups: tuple[InputGroup, ...]
    table_path: Path | None = None
    iteration_policy: str = "input_order"
    deterministic_order: bool = True
    archives: tuple[Path, ...] = ()


def _planning_error(reason: str, *, diagnostics: list[dict[str, Any]] | None = None) -> RdeValidationError:
    definition = ERROR_CATALOG[4006]
    return RdeValidationError(
        code=4006,
        message=f"{definition.message_template.format(reason=reason)} Remediation: {definition.remediation}",
        detail={"diagnostics": diagnostics} if diagnostics else None,
    )


def _input_files(inputdata: Path) -> list[Path]:
    cleaner = SystemFilesCleaner()
    return [path for path in inputdata.glob("*") if not cleaner.is_excluded(path)]


def archive_references(archives: list[Path]) -> tuple[InputReference, ...]:
    """Read safe, unique archive member names without extracting payloads.

    Args:
        archives: Source ZIP archives in their input order.

    Returns:
        Ordered references using the same filename decoder as extraction.

    Raises:
        RdeValidationError: If an archive has unreadable or colliding names.
    """
    result: list[InputReference] = []
    seen: set[str] = set()
    for archive in archives:
        for name in _archive_names(archive):
            key = name.casefold()
            if key in seen:
                reason = f"Duplicate or case-colliding member in {archive.name}"
                raise _planning_error(reason)
            seen.add(key)
            result.append(InputReference(archive, name))
    _reject_file_directory_collisions(result)
    return tuple(result)


def _archive_names(archive: Path) -> list[str]:
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = [(info, resolve_filename(info)) for info in zipped.infolist()]
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        reason = f"Unreadable archive {archive.name}"
        raise _planning_error(reason) from exc
    _validate_archive_layout(entries, archive)
    cleaner = SystemFilesCleaner()
    names: list[str] = []
    for info, name in entries:
        _validate_member_name(name, archive)
        if not info.is_dir() and not cleaner.is_excluded(Path(name)):
            names.append(str(PurePosixPath(name)))
    return names


def _validate_archive_layout(entries: list[tuple[zipfile.ZipInfo, str]], archive: Path) -> None:
    files = {str(PurePosixPath(name)).casefold() for info, name in entries if not info.is_dir()}
    directories: dict[str, str] = {}
    for info, name in entries:
        path = PurePosixPath(name)
        parents = (path, *path.parents) if info.is_dir() else tuple(path.parents)
        _validate_archive_directories(parents, files, directories, archive)


def _validate_archive_directories(parents: tuple[PurePosixPath, ...], files: set[str], directories: dict[str, str], archive: Path) -> None:
    for parent in parents:
        name = str(parent)
        key = name.casefold()
        if key in files or (key in directories and directories[key] != name):
            reason = f"Colliding archive directory names in {archive.name}"
            raise _planning_error(reason)
        directories[key] = name


def _validate_member_name(name: str, archive: Path) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        reason = f"Unsafe member name in {archive.name}"
        raise _planning_error(reason)


def _reject_file_directory_collisions(references: list[InputReference]) -> None:
    names = {str(ref.member).casefold() for ref in references}
    for ref in references:
        parents = PurePosixPath(str(ref.member)).parents
        if any(str(parent).casefold() in names for parent in parents):
            reason = f"Archive member is both a file and directory in {ref.source.name}"
            raise _planning_error(reason)


def _smarttable_groups(table: Path, refs: tuple[InputReference, ...], save_table: bool) -> tuple[InputGroup, ...]:
    groups = _smarttable_row_groups(table, refs)
    original = InputGroup((InputReference(table),), original_table=True)
    if not groups:
        return (original,) if save_table else ()
    original_groups = (original,) if save_table else ()
    return (groups[-1], *original_groups, *groups[:-1])


def _smarttable_row_groups(table: Path, refs: tuple[InputReference, ...]) -> list[InputGroup]:
    data = SmartTableFile(table).read_table()
    columns = [column for column in data.columns if column.startswith("inputdata")]
    groups: list[InputGroup] = []
    for index, (_, row) in enumerate(data.iterrows()):
        selected = [_table_reference(row[column], refs, index + 3, column) for column in columns]
        groups.append(InputGroup(tuple(ref for ref in selected if ref is not None), source_row=index + 3))
    return groups


def _table_reference(value: object, refs: tuple[InputReference, ...], row: int, column: str) -> InputReference | None:
    if _empty(value):
        return None
    normalized = str(value).strip("/\\").replace("\\", "/")
    matches = [ref for ref in refs if str(ref.member) == normalized or str(ref.member).endswith("/" + normalized)]
    if len(matches) != 1:
        reason = "missing_file_reference" if not matches else "ambiguous_file_reference"
        diagnostic = {"row": row, "column": column, "reason": reason, "expected_type": "unique archive member", "suggestion": "Use one complete relative archive path."}
        message = f"SmartTable row {row}, column {column}: {reason}"
        raise _planning_error(message, diagnostics=[diagnostic])
    return matches[0]


def _empty(value: object) -> bool:
    return value is None or str(value) in {"", "nan", "<NA>"}


def _excel_groups(table: Path, refs: tuple[InputReference, ...], *, has_archive: bool) -> tuple[InputGroup, ...]:
    data = ExcelInvoiceFile(table).dfexcelinvoice
    count = len(data)
    if not has_archive:
        return tuple(InputGroup((), source_row=index + 1) for index in range(count))
    if "data_file_names/name" in data.columns:
        return _excel_flat_groups(data, refs)
    groups = _excel_folder_groups(refs)
    if len(groups) == 1:
        groups *= count
    if len(groups) != count:
        reason = f"Workbook {table.name} row count does not match archive groups"
        raise _planning_error(reason)
    order = data.iloc[:, 0].to_list()
    groups.sort(key=lambda group: _excel_group_index(group, order))
    return tuple(InputGroup(group, source_row=index + 1) for index, group in enumerate(groups))


def _excel_folder_groups(refs: tuple[InputReference, ...]) -> list[tuple[InputReference, ...]]:
    buckets: dict[str, list[InputReference]] = defaultdict(list)
    for ref in sorted(refs, key=lambda ref: str(ref.member)):
        if PurePosixPath(str(ref.member)).name != "invoice_org.json":
            buckets[str(PurePosixPath(str(ref.member)).parent)].append(ref)
    return [tuple(group) for group in buckets.values()]


def _excel_group_index(group: tuple[InputReference, ...], order: list[Any]) -> int:
    parts = PurePosixPath(str(group[0].member)).parts if group else ()
    return next((index for index, item in enumerate(order) if item in parts), len(order))


def _excel_flat_groups(data: Any, refs: tuple[InputReference, ...]) -> tuple[InputGroup, ...]:
    groups: list[InputGroup] = []
    for index, name in enumerate(data["data_file_names/name"]):
        matches = [ref for ref in refs if PurePosixPath(str(ref.member)).name == name]
        if len(matches) != 1:
            reason = f"Workbook row {index + 1} requires one unique archive filename"
            raise _planning_error(reason)
        groups.append(InputGroup((matches[0],), source_row=index + 1))
    return tuple(groups)


def _rdeformat_groups(refs: tuple[InputReference, ...]) -> tuple[InputGroup, ...]:
    groups: dict[int, list[InputReference]] = defaultdict(list)
    for ref in refs:
        match = re.search(r"/(\d{4})/", "/" + str(ref.member))
        groups[int(match.group(1)) if match else 0].append(ref)
    return tuple(InputGroup(tuple(groups[key])) for key in sorted(groups)) or (InputGroup(()),)


def discover_input_snapshot(mode: ModeKind, inputdata: Path, config: RdeConfig) -> InputSnapshot:
    """Discover registration groups without creating files or directories.

    Args:
        mode: Already selected mode; detection is never repeated.
        inputdata: Run input directory.
        config: Effective normalized configuration.

    Returns:
        Shared immutable material for explanation and strict-v2 execution.

    Raises:
        RdeValidationError: If the snapshot has unsafe or ambiguous references.
    """
    try:
        return _discover_snapshot(mode, inputdata, config)
    except (StructuredError, OSError, ValueError, KeyError, IndexError, zipfile.BadZipFile) as exc:
        reason = f"Unreadable {mode.value} table or input layout"
        raise _planning_error(reason) from exc


def _discover_snapshot(mode: ModeKind, inputdata: Path, config: RdeConfig) -> InputSnapshot:
    files = _input_files(inputdata)
    if mode is ModeKind.invoice:
        return _invoice_snapshot(files)
    if mode is ModeKind.multidatatile:
        return _multidatatile_snapshot(files, config)
    archives = [path for path in files if path.suffix.lower() == ".zip"]
    members = archive_references(archives)
    if mode is ModeKind.rdeformat:
        return InputSnapshot(mode, _rdeformat_groups(members), iteration_policy="numeric_directory_archive_member", archives=tuple(archives))
    snapshot = _smarttable_snapshot(files, members, config) if mode is ModeKind.smarttable else _excel_snapshot(files, members, archives)
    return replace(snapshot, archives=tuple(archives))


def _invoice_snapshot(files: list[Path]) -> InputSnapshot:
    ordinary = [path for path in files if path.suffix.lower() != ".zip"]
    archives = [path for path in files if path.suffix.lower() == ".zip"]
    group = InputGroup(tuple(InputReference(path) for path in ordinary + archives))
    return InputSnapshot(ModeKind.invoice, (group,), iteration_policy="filesystem", deterministic_order=False)


def _multidatatile_snapshot(files: list[Path], config: RdeConfig) -> InputSnapshot:
    policy = config.multidata_tile.order
    ordered = files if policy == "filesystem" else sorted(files, key=str)
    groups = tuple(InputGroup((InputReference(path),)) for path in ordered) or (InputGroup(()),)
    return InputSnapshot(ModeKind.multidatatile, groups, iteration_policy=policy, deterministic_order=policy == "name")


def _smarttable_snapshot(files: list[Path], members: tuple[InputReference, ...], config: RdeConfig) -> InputSnapshot:
    tables = [path for path in files if path.name.startswith("smarttable_") and path.suffix.lower() in {".csv", ".tsv", ".xlsx"}]
    table = _single_table(tables, "SmartTable")
    return InputSnapshot(ModeKind.smarttable, _smarttable_groups(table, members, config.smarttable.save_table_file), table, "table_registration_order")


def _excel_snapshot(files: list[Path], members: tuple[InputReference, ...], archives: list[Path]) -> InputSnapshot:
    tables = [path for path in files if path.stem.endswith("_excel_invoice") and path.suffix.lower() in {".xls", ".xlsx"}]
    table = _single_table(tables, "ExcelInvoice")
    if any(path not in archives and path != table for path in files):
        reason = "ExcelInvoice accepts only its workbook and optional archive"
        raise _planning_error(reason)
    return InputSnapshot(ModeKind.excelinvoice, _excel_groups(table, members, has_archive=bool(archives)), table, "workbook_order")


def _single_table(tables: list[Path], format_name: str) -> Path:
    if len(tables) != 1:
        reason = f"{format_name} requires exactly one matching table"
        raise _planning_error(reason)
    return tables[0]


def materialize_input_snapshot(snapshot: InputSnapshot, unpacked: Path) -> tuple[tuple[tuple[Path, ...], Path | None], ...]:
    """Materialize exactly the groups selected by read-only discovery.

    Args:
        snapshot: Shared grouping produced before output publication.
        unpacked: Runner-owned extraction and row-CSV directory.

    Returns:
        Per-group raw files and optional generated SmartTable row CSV.
    """
    references = _snapshot_references(snapshot)
    archives = dict.fromkeys((*snapshot.archives, *(ref.source for ref in references if ref.member is not None)))
    for archive in archives:
        extract_zip_with_encoding(archive, unpacked)
    if archives:
        SystemFilesCleaner().clean_directory(unpacked)
    row_csvs = _materialize_table_rows(snapshot, unpacked, references, bool(archives))
    return tuple(_materialize_group(group, unpacked, row_csvs) for group in snapshot.groups)


def _snapshot_references(snapshot: InputSnapshot) -> tuple[InputReference, ...]:
    return tuple(dict.fromkeys(ref for group in snapshot.groups for ref in group.files))


def _materialize_table_rows(snapshot: InputSnapshot, unpacked: Path, references: tuple[InputReference, ...], has_archive: bool) -> dict[int, Path]:
    if snapshot.mode is not ModeKind.smarttable or snapshot.table_path is None:
        return {}
    available = [ref.materialized_path(unpacked) for ref in references if ref.member is not None]
    generated = SmartTableFile(snapshot.table_path).generate_row_csvs_with_file_mapping(unpacked, available if has_archive else None)
    return {index + 3: row[0] for index, row in enumerate(generated)}


def _materialize_group(group: InputGroup, unpacked: Path, row_csvs: dict[int, Path]) -> tuple[tuple[Path, ...], Path | None]:
    files = tuple(ref.materialized_path(unpacked) for ref in group.files)
    row_csv = None if group.source_row is None else row_csvs.get(group.source_row)
    return files, row_csv
