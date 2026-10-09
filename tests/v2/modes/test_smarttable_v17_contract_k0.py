"""Session K0-iii: the v1.7.1 SmartTable contract on the unified Runner.

v1.7 (#503) changed what a SmartTable tile *is*: ``SmartTableChecker.parse``
returns ``(row_csv | None, user_files)`` pairs, ``rawfiles`` carries only the
user's data files, the generated row CSV is reachable only through
``smarttable_rawfile`` (``smarttable_rowfile`` is a deprecated alias), the row
CSV is never copied to ``raw/`` or ``nonshared_raw/``, and with
``save_table_file: true`` the original table registers first at
``divided/0001`` with an invoice seeded from ``invoice_org``. #496 made a
``meta/`` column without ``tasksupport/metadata-def.json`` an error, and #515
(v1.7.1) decodes cp932 zip member names.

No expectation here is hand-written where an oracle exists: every end-to-end
cell runs the **live** ``workflows._run_legacy`` (the v1.7.1 code path) and the
unified public entry on byte-identical workspaces and compares the
observations. ``expected/**``, ``_generate.py`` and ``observe.py`` are not used
to produce expectations and are untouched.

Equivalence partitions (EP):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``run(custom_dataset_function=)`` | 3 rows, ``save_table_file=False`` | #503 callback material | ``rawfiles``/``smarttable_rawfile`` per call = ``_run_legacy`` | TC-K0-EP-001 |
| ``run(custom_dataset_function=)`` | ``save_raw``/``save_nonshared_raw`` on | #503 row CSV never copied | raw listings = ``_run_legacy``, no ``fsmarttable_*`` | TC-K0-EP-002 |
| ``run(custom_dataset_function=)`` | ``save_table_file=True``, 2 rows | #503 ``divided/0001`` first + seed | invoices/raw/calls = ``_run_legacy`` | TC-K0-EP-003 |
| ``iterate_tiles`` | SmartTable mode | ruling #1 tile material | ``rawfiles``/``raw``/``smarttable_rawfile`` = v1 iterator | TC-K0-EP-011 |
| ``run(custom_dataset_function=)`` | cp932 zip member name | #515 through v1 helper | callback file name = ``_run_legacy`` | TC-K0-EP-013 |
| ``run(flow=)`` | SmartTable flow | v2 reserved type carries the row CSV | ``paths.smarttable_rawfile`` set, ``rawfiles`` user only | TC-K0-EP-015 |

Negative / boundary partitions (EV / BV):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``run(custom_dataset_function=)`` | ``save_table_file=True``, 0 data rows | table alone occupies ``data/`` | observations = ``_run_legacy`` | TC-K0-BV-004 |
| ``run(custom_dataset_function=)`` | 1 row | smallest table | ``raw`` = ``{"only.txt"}`` = ``_run_legacy`` | TC-K0-BV-005 |
| ``run(custom_dataset_function=)`` | ``meta/`` column, no metadata-def.json | #496 | exit 1 + ``job.failed`` = ``_run_legacy`` | TC-K0-EV-006 |
| ``run(custom_dataset_function=)`` | any SmartTable run | ruling #2: new name only | no ``smarttable_rowfile`` DeprecationWarning | TC-K0-EV-007 |
| ``Runner.run`` | tile preparation raises a plain exception | ruling #6 | ``3001`` (not ``1002``) in report and ``job.failed`` | TC-K0-EV-008 |
| ``Runner.run`` | tile preparation raises ``StructuredError`` | v1 passthrough kept | ``job.failed`` carries its ``ecode``/``emsg`` | TC-K0-EV-009 |
| ``iterate_tiles`` | a row referencing no file | empty user files | ``rawfiles == ()``, ``raw is None`` = v1 iterator | TC-K0-BV-012 |
| ``InputPaths`` | field omitted | append-only default | ``smarttable_rawfile is None`` | TC-K0-BV-014 |
| ``iterate_tiles`` | invoice mode | other modes unchanged | ``smarttable_rawfile is None`` | TC-K0-BV-016 |
| ``iterate_tiles`` | checker group of the wrong shape | runtime-only distinction | ``TypeError`` naming the tile | TC-K0-EV-017 |
| ``InvoiceService.prepare_tile`` | SmartTable row tile without a row CSV | no ``rawfiles[0]`` fallback | v1's ``StructuredError`` message | TC-K0-EV-018 |
| ``to_legacy_dataset_paths`` | data root is not ``<cwd>/data`` | no v1 counterpart | absolute paths kept | TC-K0-BV-019 |
| ``run(custom_dataset_function=)`` | standard layout | v1 path form (``StorageDir``) | every path field verbatim = ``_run_legacy`` | TC-K0-EP-020 |
"""

from __future__ import annotations

import dataclasses
import io
import json
import shutil
import struct
import warnings
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import workflows
from rdetoolkit.compat.v1.callback import to_legacy_dataset_paths
from rdetoolkit.core.context import RunContext
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.impl.input_controller import SmartTableChecker
from rdetoolkit.runner import planner as planner_module
from rdetoolkit.runner.iterator import iterate_tiles
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import TileMaterial
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig

_SAMPLEFILE_DIR = Path(__file__).resolve().parents[2] / "samplefile"
_TABLE_NAME = "smarttable_test.csv"
_ROWS = (("sample1.txt", "Experiment_1", "25"), ("sample2.txt", "Experiment_2", "26"), ("sample3.txt", "Experiment_3", "27"))

Rows = tuple[tuple[str, str, str], ...]


# ---------------------------------------------------------------------------
# Workspace construction (mirrors the v1.7 integration tests' layout)
# ---------------------------------------------------------------------------


def _write_cp932_zip(path: Path, members: dict[str, str]) -> None:
    """Write a STORED zip whose member names are cp932 bytes without the UTF-8 flag.

    ``zipfile`` always flags non-ASCII names as UTF-8, so a legacy Japanese
    Windows archive can only be reproduced by writing the records by hand.
    """
    buf = io.BytesIO()
    entries = [(name.encode("cp932"), content.encode("utf-8")) for name, content in members.items()]
    offsets: list[int] = []
    for name, data in entries:
        offsets.append(buf.tell())
        crc = zlib.crc32(data) & 0xFFFFFFFF
        buf.write(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, 0, 0, 0, crc, len(data), len(data), len(name), 0))
        buf.write(name)
        buf.write(data)
    central_start = buf.tell()
    for (name, data), offset in zip(entries, offsets, strict=True):
        crc = zlib.crc32(data) & 0xFFFFFFFF
        buf.write(
            struct.pack(
                "<IHHHHHHIIIHHHHHII",
                0x02014B50, 20, 20, 0, 0, 0, 0, crc, len(data), len(data), len(name), 0, 0, 0, 0, 0, offset,
            ),
        )
        buf.write(name)
    central_size = buf.tell() - central_start
    buf.write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entries), len(entries), central_size, central_start, 0))
    path.write_bytes(buf.getvalue())


def _workspace(
    root: Path,
    *,
    rows: Rows = _ROWS,
    save_table_file: bool = False,
    meta_column: bool = False,
    cp932_zip: bool = False,
    with_file_column: bool = True,
) -> Path:
    """Build one ``data/`` workspace with a SmartTable input under ``root``."""
    data = root / "data"
    for name in ("inputdata", "invoice", "tasksupport"):
        (data / name).mkdir(parents=True, exist_ok=True)
    shutil.copy2(_SAMPLEFILE_DIR / "invoice.schema.json", data / "tasksupport" / "invoice.schema.json")
    shutil.copy2(_SAMPLEFILE_DIR / "invoice.json", data / "invoice" / "invoice.json")
    (data / "tasksupport" / "rdeconfig.yml").write_text(
        "system:\n"
        "  extended_mode: null\n"
        "  save_raw: true\n"
        "  save_nonshared_raw: true\n"
        "  save_thumbnail_image: false\n"
        "  magic_variable: false\n"
        "smarttable:\n"
        f"  save_table_file: {str(save_table_file).lower()}\n",
        encoding="utf-8",
    )
    members = {file_name: f"content of {file_name}" for file_name, _, _ in rows}
    if cp932_zip:
        _write_cp932_zip(data / "inputdata" / "files.zip", members)
    elif with_file_column and members:
        with zipfile.ZipFile(data / "inputdata" / "files.zip", "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)

    keys = ["basic/dataName", "custom/sample3"]
    if with_file_column:
        keys.insert(0, "inputdata1")
    if meta_column:
        keys.append("meta/comment")
    lines = [",".join(["Display"] * len(keys)), ",".join(keys)]
    for file_name, data_name, sample3 in rows:
        cells = [data_name, sample3]
        if with_file_column:
            cells.insert(0, file_name)
        if meta_column:
            cells.append("memo")
        lines.append(",".join(cells))
    (data / "inputdata" / _TABLE_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return data


def _relative(path: Path | None, root: Path) -> str | None:
    """Return a root-relative POSIX path, whichever form the entry handed over."""
    if path is None:
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        candidate = candidate.resolve().relative_to(root.resolve())
    return candidate.as_posix()


class _Recorder:
    """v1 callback recording the SmartTable material it receives."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[dict[str, Any]] = []

    def __call__(self, srcpaths: Any, resource_paths: Any) -> None:
        del srcpaths
        self.calls.append(
            {
                "rawfiles": [_relative(path, self.root) for path in resource_paths.rawfiles],
                "smarttable_rawfile": _relative(resource_paths.smarttable_rawfile, self.root),
            },
        )


def _legacy_entry(callback: Any) -> Any:
    return workflows._run_legacy(callback)  # noqa: SLF001 -- the live v1.7.1 oracle


def _public_entry(callback: Any) -> Any:
    return workflows.run(custom_dataset_function=callback)


def _tile_dirs(data: Path) -> list[Path]:
    divided = data / "divided"
    tiles = [data]
    if divided.is_dir():
        tiles.extend(sorted(path for path in divided.iterdir() if path.is_dir()))
    return tiles


def _observe(
    root: Path,
    entry: Callable[[Any], Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Run one entry with ``root`` as the CWD and collect the #503 observables."""
    monkeypatch.chdir(root)
    recorder = _Recorder(root)
    exit_code = 0
    try:
        entry(recorder)
    except SystemExit as error:
        exit_code = int(error.code or 0)
    data = root / "data"
    invoices: dict[str, Any] = {}
    raw: dict[str, dict[str, list[str]]] = {}
    for tile in _tile_dirs(data):
        key = tile.relative_to(data).as_posix()
        invoice_path = tile / "invoice" / "invoice.json"
        if invoice_path.exists():
            invoices[key] = json.loads(invoice_path.read_text(encoding="utf-8"))
        raw[key] = {
            name: sorted(path.name for path in (tile / name).iterdir()) if (tile / name).is_dir() else []
            for name in ("raw", "nonshared_raw")
        }
    job_failed = data / "job.failed"
    return {
        "exit_code": exit_code,
        "calls": recorder.calls,
        "invoices": invoices,
        "raw": raw,
        "job_failed": (
            job_failed.read_text(encoding="utf-8").replace(str(root.resolve()), "<ROOT>").replace(str(root), "<ROOT>")
            if job_failed.exists()
            else None
        ),
    }


def _pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **workspace: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Observe ``_run_legacy`` and the unified public entry on identical inputs."""
    legacy_root = tmp_path / "legacy"
    unified_root = tmp_path / "unified"
    _workspace(legacy_root, **workspace)
    _workspace(unified_root, **workspace)
    legacy = _observe(legacy_root, _legacy_entry, monkeypatch)
    unified = _observe(unified_root, _public_entry, monkeypatch)
    return legacy, unified


# ---------------------------------------------------------------------------
# End-to-end parity with the live v1.7.1 oracle
# ---------------------------------------------------------------------------


def test_callback_material_matches_v171__tc_k0_ep_001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K0-EP-001: rawfiles hold user files only; the row CSV is smarttable_rawfile."""
    # Given: a three-row SmartTable with save_table_file disabled
    # When: both entries process identical workspaces
    legacy, unified = _pair(tmp_path, monkeypatch)

    # Then: the callback saw exactly what v1.7.1 handed over, tile by tile
    assert unified["calls"] == legacy["calls"]
    assert unified["exit_code"] == legacy["exit_code"] == 0
    # And: the v1.7 contract itself holds (guards against both sides regressing)
    assert [call["rawfiles"] for call in unified["calls"]] == [
        ["data/temp/sample3.txt"],
        ["data/temp/sample1.txt"],
        ["data/temp/sample2.txt"],
    ]
    for call in unified["calls"]:
        assert Path(call["smarttable_rawfile"]).name.startswith("fsmarttable_")
        assert not any(Path(name).name.startswith("fsmarttable_") for name in call["rawfiles"])


def test_row_csv_never_reaches_raw_storage__tc_k0_ep_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K0-EP-002: raw/ and nonshared_raw/ never receive the generated row CSV."""
    # Given: save_raw and save_nonshared_raw both enabled
    # When: both entries run
    legacy, unified = _pair(tmp_path, monkeypatch)

    # Then: every tile's raw listings equal v1.7.1's
    assert unified["raw"] == legacy["raw"]
    # And: no listing names a row CSV, and every tile still published its user file
    for listings in unified["raw"].values():
        for names in listings.values():
            assert names
            assert not any(name.startswith("fsmarttable_") for name in names)


def test_save_table_file_registers_the_table_first__tc_k0_ep_003(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K0-EP-003: save_table_file puts the table at divided/0001 with a seeded invoice."""
    # Given: a two-row SmartTable with save_table_file enabled
    # When: both entries run
    legacy, unified = _pair(tmp_path, monkeypatch, rows=_ROWS[:2], save_table_file=True)

    # Then: invoices, raw listings, callback material and exit status equal v1.7.1
    assert unified["invoices"] == legacy["invoices"]
    assert unified["raw"] == legacy["raw"]
    assert unified["calls"] == legacy["calls"]
    assert unified["exit_code"] == legacy["exit_code"] == 0
    # And: the original table owns divided/0001; the rows keep their order around it
    assert unified["invoices"]["divided/0001"]["basic"]["dataName"] == _TABLE_NAME
    assert unified["invoices"]["."]["basic"]["dataName"] == "Experiment_2"
    assert unified["invoices"]["divided/0002"]["basic"]["dataName"] == "Experiment_1"
    assert unified["raw"]["divided/0001"]["raw"] == [_TABLE_NAME]
    assert len(unified["calls"]) == 2


def test_table_without_data_rows_occupies_the_data_root__tc_k0_bv_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K0-BV-004: save_table_file with zero rows registers the table alone at data/."""
    # Given: a header-only SmartTable with save_table_file enabled
    # When: both entries run
    legacy, unified = _pair(tmp_path, monkeypatch, rows=(), save_table_file=True)

    # Then: the whole observation equals v1.7.1's
    assert unified == legacy
    # And: the table is the only tile, at the data root, and no callback ran
    assert list(unified["invoices"]) == ["."]
    assert unified["invoices"]["."]["basic"]["dataName"] == _TABLE_NAME
    assert unified["calls"] == []


def test_single_row_keeps_raw_to_the_user_file__tc_k0_bv_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K0-BV-005: the smallest table still copies only the user file."""
    # Given: a one-row SmartTable
    # When: both entries run
    legacy, unified = _pair(tmp_path, monkeypatch, rows=(("only.txt", "Experiment_only", "1"),))

    # Then: v1.7.1 parity, and raw storage holds exactly the user file
    assert unified == legacy
    assert unified["raw"]["."] == {"raw": ["only.txt"], "nonshared_raw": ["only.txt"]}


def test_meta_column_without_definition_fails_like_v171__tc_k0_ev_006(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K0-EV-006: a meta/ column without metadata-def.json is a StructuredError (#496)."""
    # Given: a SmartTable with a meta/comment column and no metadata-def.json
    # When: both entries run
    legacy, unified = _pair(tmp_path, monkeypatch, meta_column=True)

    # Then: the run fails exactly as v1.7.1 does
    assert unified["exit_code"] == legacy["exit_code"] == 1
    assert unified["job_failed"] == legacy["job_failed"]
    assert unified["calls"] == legacy["calls"] == []
    # And: the marker names the missing definition, not a silent skip
    assert unified["job_failed"] is not None
    assert "metadata-def.json not found" in unified["job_failed"]


def test_unified_entry_emits_no_rowfile_deprecation__tc_k0_ev_007(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K0-EV-007: the v2 path uses smarttable_rawfile only (ruling #2)."""
    # Given: a SmartTable workspace, with save_table_file covering the EarlyExit tile too
    root = tmp_path / "unified"
    _workspace(root, save_table_file=True)

    # When: the unified entry runs with every warning recorded
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        observed = _observe(root, _public_entry, monkeypatch)

    # Then: the run succeeded and no deprecated alias was touched on the way
    assert observed["exit_code"] == 0
    assert not [warning for warning in caught if "smarttable_rowfile" in str(warning.message)]


def _runner(root: Path) -> Runner:
    data = root / "data"
    return Runner(root=root, inputdata_path=data / "inputdata", unpacked_dir_path=data / "temp")


def _failing_iterate_tiles(exc: Exception) -> Callable[..., Any]:
    def _iterate(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise exc

    return _iterate


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Accept any tile without producing artifacts."""
    del paths


def test_tile_preparation_failure_is_an_execution_error__tc_k0_ev_008(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K0-EV-008: a plain exception while preparing tiles is 3001, never 1002."""
    # Given: tile discovery that crashes with a plain exception (the shape of the
    # pre-K0 tuple-as-Path defect)
    root = tmp_path / "unified"
    _workspace(root)
    monkeypatch.setattr(planner_module, "iterate_tiles", _failing_iterate_tiles(AttributeError("tile boom")))
    monkeypatch.chdir(root)

    # When: the Runner executes the run
    report = _runner(root).run(RunRequest(root=root, target=FlowTarget(function=_noop_flow)))

    # Then: the failure is attributed to execution with the catalogue entry
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 3001
    assert report.error["name"] == "NodeExecutionFailed"
    assert "tile boom" in report.error["message"]
    # And: job.failed publishes the same code, not the configuration code
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.startswith("ErrorCode=3001\n")
    assert "ErrorCode=1002" not in job_failed


def test_tile_preparation_structured_error_passes_through__tc_k0_ev_009(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K0-EV-009: a StructuredError while preparing tiles keeps its ecode/emsg."""
    # Given: tile discovery raising a v1 StructuredError
    root = tmp_path / "unified"
    _workspace(root)
    error = StructuredError("checker refused the table", ecode=42)
    monkeypatch.setattr(planner_module, "iterate_tiles", _failing_iterate_tiles(error))
    monkeypatch.chdir(root)

    # When: the Runner executes the run
    report = _runner(root).run(RunRequest(root=root, target=FlowTarget(function=_noop_flow)))

    # Then: the v1 passthrough is untouched by the execution mapping
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 42
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed == "ErrorCode=42\nErrorMessage=checker refused the table\n"


# ---------------------------------------------------------------------------
# Tile material (ruling #1) against the merged v1.7 iterator
# ---------------------------------------------------------------------------


def _v1_tile_material(data: Path, *, save_table_file: bool) -> list[tuple[list[str], str | None]]:
    """Return what v1.7's checker + ``generate_folder_paths_iterator`` hand each tile."""
    checker = SmartTableChecker(data / "temp", save_table_file=save_table_file)
    (data / "temp").mkdir(parents=True, exist_ok=True)
    groups, _table = checker.parse(data / "inputdata")
    resources = workflows.generate_folder_paths_iterator(
        groups,
        data / "invoice" / "invoice.json",
        data / "tasksupport" / "invoice.schema.json",
        smarttable_mode=True,
    )
    root = data.parent
    return [
        ([_relative(path, root) or "" for path in resource.rawfiles], _relative(resource.smarttable_rawfile, root))
        for resource in resources
    ]


def _v2_tile_material(data: Path, *, save_table_file: bool) -> list[InputPaths]:
    config = RdeConfig(smarttable={"save_table_file": save_table_file})
    return [
        paths
        for _info, paths, _out in iterate_tiles(ModeKind.smarttable, data / "inputdata", data / "temp", data, config)
    ]


@pytest.mark.parametrize("save_table_file", [False, True], ids=["rows-only", "with-table"])
def test_iterator_carries_the_v17_tile_material__tc_k0_ep_011(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    save_table_file: bool,
) -> None:
    """TC-K0-EP-011: iterate_tiles splits each pair exactly like v1.7's iterator."""
    # Given: identical workspaces for the v1 iterator and the v2 iterator
    legacy_data = _workspace(tmp_path / "legacy", save_table_file=save_table_file)
    unified_data = _workspace(tmp_path / "unified", save_table_file=save_table_file)
    monkeypatch.chdir(tmp_path / "legacy")

    # When: both enumerate their tiles
    expected = _v1_tile_material(legacy_data, save_table_file=save_table_file)
    observed = _v2_tile_material(unified_data, save_table_file=save_table_file)

    # Then: rawfiles and the row CSV are the v1.7 values, tile by tile
    root = tmp_path / "unified"
    assert [
        ([_relative(path, root) for path in paths.rawfiles], _relative(paths.smarttable_rawfile, root)) for paths in observed
    ] == expected
    # And: raw is the single user file, as for every other mode
    for paths in observed:
        assert paths.raw == (paths.rawfiles[0] if len(paths.rawfiles) == 1 else None)


def test_row_without_file_reference_has_no_raw_input__tc_k0_bv_012(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K0-BV-012: a row that references no file yields empty user files."""
    # Given: a SmartTable without any inputdata column
    legacy_data = _workspace(tmp_path / "legacy", with_file_column=False)
    unified_data = _workspace(tmp_path / "unified", with_file_column=False)
    monkeypatch.chdir(tmp_path / "legacy")

    # When: both enumerate their tiles
    expected = _v1_tile_material(legacy_data, save_table_file=False)
    observed = _v2_tile_material(unified_data, save_table_file=False)

    # Then: no tile has user files, every tile still has its row CSV
    assert [(list(paths.rawfiles), paths.smarttable_rawfile is not None) for paths in observed] == [
        (rawfiles, rowfile is not None) for rawfiles, rowfile in expected
    ]
    assert all(paths.raw is None and paths.rawfiles == () for paths in observed)


def test_cp932_member_names_reach_the_callback__tc_k0_ep_013(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K0-EP-013: #515 cp932 zip names are decoded on the unified path too."""
    # Given: a zip written by a Japanese Windows tool (cp932 names, no UTF-8 flag)
    rows = (("測定データ.txt", "Experiment_jp", "5"),)

    # When: both entries run
    legacy, unified = _pair(tmp_path, monkeypatch, rows=rows, cp932_zip=True)

    # Then: the callback saw the decoded name, exactly as v1.7.1 did
    assert unified["calls"] == legacy["calls"]
    assert unified["calls"][0]["rawfiles"] == ["data/temp/測定データ.txt"]
    assert unified["raw"] == legacy["raw"]


def test_input_paths_row_csv_defaults_to_none__tc_k0_bv_014() -> None:
    """TC-K0-BV-014: the appended InputPaths field is optional and frozen."""
    # Given / When: InputPaths built without the new field
    paths = InputPaths(inputdata=Path("in"), invoice=Path("inv"), tasksupport=Path("ts"))

    # Then: it defaults to None and cannot be reassigned
    assert paths.smarttable_rawfile is None
    with pytest.raises(AttributeError):
        paths.smarttable_rawfile = Path("x.csv")  # type: ignore[misc]


_FLOW_SEEN: list[tuple[tuple[str, ...], str | None]] = []


@flow
def _recording_flow(paths: InputPaths) -> None:
    """Record the SmartTable material a flow receives."""
    _FLOW_SEEN.append(
        (
            tuple(path.name for path in paths.rawfiles),
            paths.smarttable_rawfile.name if paths.smarttable_rawfile is not None else None,
        ),
    )


def test_flow_receives_the_row_csv_through_input_paths__tc_k0_ep_015(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K0-EP-015: a flow reaches the row CSV through InputPaths.smarttable_rawfile."""
    # Given: a three-row SmartTable workspace
    root = tmp_path / "unified"
    _workspace(root)
    monkeypatch.chdir(root)
    _FLOW_SEEN.clear()

    # When: the flow entry runs
    report = workflows.run(flow=_recording_flow)

    # Then: every tile saw user files only, and its own row CSV
    assert not isinstance(report, str)
    assert report.status == "success"
    assert [rawfiles for rawfiles, _row in _FLOW_SEEN] == [("sample3.txt",), ("sample1.txt",), ("sample2.txt",)]
    rows = [row for _rawfiles, row in _FLOW_SEEN]
    assert all(row is not None and row.startswith("fsmarttable_") for row in rows)
    assert len(set(rows)) == len(rows)


def test_other_modes_carry_no_row_csv__tc_k0_bv_016(tmp_path: Path) -> None:
    """TC-K0-BV-016: invoice-mode tiles keep smarttable_rawfile unset."""
    # Given: an invoice-mode workspace with one input file
    data = tmp_path / "data"
    for name in ("inputdata", "invoice", "tasksupport"):
        (data / name).mkdir(parents=True)
    shutil.copy2(_SAMPLEFILE_DIR / "invoice.json", data / "invoice" / "invoice.json")
    (data / "inputdata" / "measure.txt").write_text("x", encoding="utf-8")

    # When: the iterator enumerates the invoice-mode tile
    tiles = list(iterate_tiles(ModeKind.invoice, data / "inputdata", data / "temp", data))

    # Then: the tile carries its file and no SmartTable row CSV
    assert len(tiles) == 1
    _info, paths, _out = tiles[0]
    assert paths.rawfiles == (data / "inputdata" / "measure.txt",)
    assert paths.smarttable_rawfile is None



class _ShapeChecker:
    """Input checker returning one fixed, deliberately malformed group."""

    def __init__(self, group: object) -> None:
        self._group = group

    def parse(self, src_dir_input: Path) -> tuple[list[object], None]:
        del src_dir_input
        return [self._group], None


@pytest.mark.parametrize(
    ("mode", "group"),
    [
        pytest.param(ModeKind.smarttable, (Path("a.txt"),), id="smarttable-flat-tuple"),
        pytest.param(ModeKind.smarttable, (Path("row.csv"), [Path("a.txt")]), id="smarttable-list-user-files"),
        pytest.param(ModeKind.smarttable, ("row.csv", (Path("a.txt"),)), id="smarttable-str-row"),
        pytest.param(ModeKind.invoice, (None, (Path("a.txt"),)), id="invoice-pair"),
        pytest.param(ModeKind.invoice, Path("a.txt"), id="invoice-bare-path"),
    ],
)
def test_malformed_checker_group_is_rejected__tc_k0_ev_017(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: ModeKind,
    group: object,
) -> None:
    """TC-K0-EV-017: a group whose shape contradicts the mode fails loudly."""
    # Given: a checker returning a group of the wrong shape for the mode
    data = tmp_path / "data"
    monkeypatch.setattr(
        "rdetoolkit.runner.iterator.selected_input_checker",
        lambda *args, **kwargs: _ShapeChecker(group),
    )

    # When / Then: enumerating the tile raises a TypeError naming tile 0
    with pytest.raises(TypeError, match="tile 0"):
        list(iterate_tiles(mode, data / "inputdata", data / "temp", data))


def test_row_tile_without_row_csv_fails_like_v1__tc_k0_ev_018(tmp_path: Path) -> None:
    """TC-K0-EV-018: no row CSV means v1's StructuredError, never a rawfiles guess."""
    # Given: a SmartTable tile whose rawfiles look like a row CSV but carry no row CSV
    data = _workspace(tmp_path)
    impostor = data / "temp" / "fsmarttable_test_0000.csv"
    impostor.parent.mkdir(parents=True, exist_ok=True)
    impostor.write_text("basic/dataName\nx\n", encoding="utf-8")
    paths = InputPaths(
        inputdata=data / "inputdata",
        invoice=data / "invoice",
        tasksupport=data / "tasksupport",
        rawfiles=(impostor,),
    )

    # When / Then: preparing the tile fails with v1's initializer message
    with pytest.raises(StructuredError) as error:
        InvoiceService().prepare_tile(
            ModeKind.smarttable,
            paths=paths,
            invoice_dir=data / "invoice_out",
            iteration_index=0,
            invariant_invoice=None,
            invoice_source=data / "invoice" / "invoice.json",
        )
    assert error.value.emsg == "No SmartTable row CSV file found"
    assert error.value.ecode == 1
    # And: nothing was written for the tile
    assert not (data / "invoice_out" / "invoice.json").exists()


def _legacy_context(data: Path, *, row_csv: Path | None) -> RunContext:
    user_file = data / "temp" / "sample1.txt"
    return RunContext(
        paths=InputPaths(
            inputdata=data / "inputdata",
            invoice=data / "invoice",
            tasksupport=data / "tasksupport",
            raw=user_file,
            rawfiles=(user_file,),
            smarttable_rawfile=row_csv,
        ),
        out=OutputContext.from_resource_paths(resolve_tile_paths(data, 1)),
        config=RdeConfig(),
        iteration=IterationInfo(index=1, total=2, mode="smarttable"),
    )


@pytest.mark.parametrize("row_csv", [True, False], ids=["row-tile", "table-tile"])
def test_non_standard_root_keeps_absolute_paths__tc_k0_bv_019(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    row_csv: bool,
) -> None:
    """TC-K0-BV-019: only the standard layout is projected onto v1's relative form."""
    # Given: a data root that is not <cwd>/data (the CWD is elsewhere)
    data = tmp_path / "project" / "data"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(parents=True)
    monkeypatch.chdir(elsewhere)
    row = data / "temp" / "fsmarttable_test_0000.csv" if row_csv else None
    context = _legacy_context(data, row_csv=row)

    # When: projecting the tile onto the v1 callback arguments
    legacy = to_legacy_dataset_paths(context, material=TileMaterial(invoice_source=data / "invoice" / "invoice.json"))

    # Then: every path stays absolute, exactly as the Runner holds it
    output = legacy.output_paths
    assert output.rawfiles == (data / "temp" / "sample1.txt",)
    assert output.raw == data / "divided" / "0001" / "raw"
    assert output.invoice_org == data / "invoice" / "invoice.json"
    assert legacy.input_paths.inputdata == data / "inputdata"
    assert output.smarttable_rawfile == row


def _path_fields(value: Any) -> dict[str, Any]:
    """Return every Path-valued field of a v1 path bundle as strings."""
    observed: dict[str, Any] = {}
    for field in dataclasses.fields(value):
        item = getattr(value, field.name)
        if isinstance(item, Path):
            observed[field.name] = str(item)
        elif isinstance(item, tuple) and all(isinstance(part, Path) for part in item):
            observed[field.name] = [str(part) for part in item]
    return observed


def test_callback_path_form_matches_v171_verbatim__tc_k0_ep_020(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K0-EP-020: every path a v1 callback receives is v1's own string, unnormalized."""
    # Given: identical standard-layout workspaces and a callback recording raw strings
    observations: dict[str, list[dict[str, Any]]] = {}

    def _run(name: str, entry: Callable[[Any], Any]) -> None:
        root = tmp_path / name
        _workspace(root, rows=_ROWS[:2], save_table_file=True)
        seen: list[dict[str, Any]] = []

        def _callback(srcpaths: Any, resource_paths: Any) -> None:
            seen.append({"input": _path_fields(srcpaths), "output": _path_fields(resource_paths)})

        monkeypatch.chdir(root)
        entry(_callback)
        observations[name] = seen

    # When: both entries run
    _run("legacy", _legacy_entry)
    _run("unified", _public_entry)

    # Then: the strings are identical field by field, tile by tile
    assert observations["unified"] == observations["legacy"]
    assert observations["unified"]
    for seen in observations["unified"]:
        assert not any(Path(value).is_absolute() for value in seen["output"].values() if isinstance(value, str))
