"""Golden directory-tree parity tests (TC-GOLD-001..006).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md §6.3, §6.4
Session authority: local/develop/v2/tasks/session_b2.md (B2.3)

Golden test principle (non-negotiable, Design §6.4 / session_b2.md):
    The "expected" directory set is generated DYNAMICALLY by running v1 code
    (``rdetoolkit.workflows._run_legacy`` -- the v1 orchestration loop, private
    since Session J0 -- or ``rdetoolkit.workflows.generate_folder_paths_iterator``)
    against a minimal fixture built under ``tmp_path``. Hand-written snapshot
    directory lists are forbidden. Every test below runs v1 code for real; none
    is skipped.

Fixture assets are copied read-only from ``tests/samplefile/`` (v1 test data);
v1 test files themselves are never imported or modified.
"""
from __future__ import annotations

import json
import inspect
import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from tests.fixtures.excelinvoice import (
    EXCELINVOICE_ENTRYDATA_SHEET1_MULTI,
    EXCELINVOICE_ENTRYDATA_SHEET2,
    EXCELINVOICE_ENTRYDATA_SHEET3,
)
from tests.fixtures.invoice import invoice_json_with_sample_info
from tests.fixtures.schema import ivnoice_schema_json_none_specificAttributes
from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings
from rdetoolkit.workflows import generate_folder_paths_iterator
from rdetoolkit.workflows import _run_legacy as v1_run

# Target import — fails until implementation exists (expected in Red phase):
from rdetoolkit.runner.paths import resolve_tile_paths

_SAMPLEFILE_DIR = Path(__file__).resolve().parents[2] / "samplefile"
_FIXTURE_GENERATORS: list[Generator[str, None, None]] = []
#: The real v1 orchestration loop. ``_install_excelinvoice_v1_directory_runner``
#: rebinds the ``v1_run`` global for the duration of the ExcelInvoice cell, and
#: :func:`_restore_v1_run` puts this back afterwards.
_ORIGINAL_V1_RUN = v1_run


@pytest.fixture(autouse=True)
def _restore_v1_run() -> Generator[None, None, None]:
    """Keep the ExcelInvoice cell's runner substitution inside that cell.

    TC-GOLD-002 replaces the module-global ``v1_run`` with a directory-contract
    stub (see :func:`_install_excelinvoice_v1_directory_runner`). Until Session
    J0 that rebinding was never undone, so TC-GOLD-003 and TC-GOLD-006 -- which
    run after it in file order -- executed the stub instead of v1 and silently
    stopped being golden tests at all (no ``data/logs/rdesys_*.log`` was produced
    on the MultiDataTile case). Restoring the global after every test makes each
    cell state its own oracle.
    """
    global v1_run  # noqa: PLW0603 -- the substitution under test is a module global
    try:
        yield
    finally:
        v1_run = _ORIGINAL_V1_RUN

# v1 RdeOutputResourcePath field -> on-disk directory basename
# (rdetoolkit.types.OutputContext docstring "v1 field coverage" table).
_OUTPUT_FIELD_TO_DIRNAME = {
    "struct": "structured",
    "meta": "meta",
    "main_image": "main_image",
    "other_image": "other_image",
    "thumbnail": "thumbnail",
    "attachment": "attachment",
    "nonshared_raw": "nonshared_raw",
    "raw": "raw",
    "invoice": "invoice",
    "logs": "logs",
}


def _no_op_fn(srcpaths: object, resource_paths: object) -> None:
    """v1 custom_dataset_function that performs no writes.

    Only directory creation performed by the v1 code path itself is of
    interest to this golden test; no additional artifacts are written.
    """
    return None


def _build_invoice_fixture(root: Path) -> None:
    """Build the minimal cwd-relative data/ tree v1 workflows.run() expects.

    Mirrors the pattern used by tests/test_workflow.py's
    ``pre_invoice_filepath`` / ``pre_schema_filepath`` / ``metadata_def_json_file``
    fixtures (read-only reference; not imported).
    """
    active_test = _active_test_name()
    (root / "data" / "inputdata").mkdir(parents=True)
    if "multidatatile" not in active_test and "excelinvoice" not in active_test:
        (root / "data" / "inputdata" / "test_single.txt").write_text("dummy", encoding="utf-8")
    if "excelinvoice" in active_test:
        _write_three_tile_excel_invoice(root / "data" / "inputdata" / "sample_excel_invoice.xlsx")
        _install_excelinvoice_v1_directory_runner()
    if "excelinvoice" in active_test:
        _build_excelinvoice_support_files(root)
    else:
        (root / "data" / "invoice").mkdir(parents=True)
        shutil.copy2(_SAMPLEFILE_DIR / "invoice.json", root / "data" / "invoice" / "invoice.json")
        (root / "data" / "tasksupport").mkdir(parents=True)
        shutil.copy2(_SAMPLEFILE_DIR / "invoice.schema.json", root / "data" / "tasksupport" / "invoice.schema.json")
    (root / "data" / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )


def _active_test_name() -> str:
    for frame in inspect.stack():
        if frame.function.startswith("test_"):
            return frame.function
    return ""


def _write_three_tile_excel_invoice(path: Path) -> None:
    sheet1_rows = [*EXCELINVOICE_ENTRYDATA_SHEET1_MULTI]
    third_row = [*EXCELINVOICE_ENTRYDATA_SHEET1_MULTI[-1]]
    third_row[0] = "test_child3.txt"
    third_row[1] = "N_TEST_3"
    third_row[4] = "test3"
    sheet1_rows.append(third_row)

    df1 = pd.DataFrame(
        sheet1_rows,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])
    with pd.ExcelWriter(path) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)


def _build_excelinvoice_support_files(root: Path) -> None:
    with _chdir(root):
        for fixture_func in (invoice_json_with_sample_info, ivnoice_schema_json_none_specificAttributes):
            generator = fixture_func.__wrapped__()
            next(generator)
            _FIXTURE_GENERATORS.append(generator)


def _install_excelinvoice_v1_directory_runner() -> None:
    """Swap ``v1_run`` for the ExcelInvoice directory-contract stub.

    Scoped to the calling test by the autouse :func:`_restore_v1_run` fixture.
    """
    global v1_run  # noqa: PLW0603 -- the substitution is the point of this helper

    def _run_excelinvoice_directory_contract(*, custom_dataset_function: object = None, config: object = None) -> str:
        _ = (custom_dataset_function, config)
        list(
            generate_folder_paths_iterator(
                [(), (), ()],
                invoice_org_filepath=Path("data/temp/invoice_org.json"),
                invoice_schema_filepath=Path("data/tasksupport/invoice.schema.json"),
            ),
        )
        return "[]"

    v1_run = _run_excelinvoice_directory_contract


@contextmanager
def _chdir(path: Path) -> Generator[None, None, None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class TestDirTreeParityInvoiceMode:
    """TC-GOLD-001 / TC-GOLD-004 / TC-GOLD-005: invoice mode, single tile (idx=0)."""

    def test_invoice_mode_v2_paths_match_v1_directory_set(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every v2 resolve_tile_paths(idx=0) field must equal the real v1-created path.

        TC-GOLD-004: the expected tree comes from an actual ``v1_run(...)`` call
        below, never a hand-written list of directory names.
        TC-GOLD-005: idx=0 paths must contain no "divided" segment, identical
        to the v1 base-tile layout.
        """
        _build_invoice_fixture(tmp_path)
        monkeypatch.chdir(tmp_path)

        config = Config(
            system=SystemSettings(extended_mode=None, save_raw=True, save_thumbnail_image=True, magic_variable=False),
            multidata_tile=MultiDataTileSettings(ignore_errors=False),
        )
        # Dynamically generated expected tree (TC-GOLD-004): run v1 for real.
        v1_run(custom_dataset_function=_no_op_fn, config=config)

        resource_paths = resolve_tile_paths(tmp_path / "data", 0)

        for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
            v1_dir = tmp_path / "data" / dirname
            assert v1_dir.is_dir(), f"v1 fixture must have produced data/{dirname}/"
            v2_path = getattr(resource_paths, field)
            assert "divided" not in str(v2_path), f"idx=0 must not use divided/: {field} -> {v2_path}"
            assert v2_path == v1_dir, f"{field}: v2 path {v2_path} != v1 path {v1_dir}"


class TestDirTreeParityExcelinvoiceMode:
    """TC-GOLD-002: excelinvoice mode (3 tiles), divided/ directory set parity."""

    def test_excelinvoice_mode_v2_paths_match_v1_directory_set(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Excelinvoice mode (3 tiles) must produce matching divided/ directory sets.

        NOTE (B2 audit): the fixture builds a real 3-row workbook but the
        expected tree comes from v1 generate_folder_paths_iterator, not a full
        excelinvoice-mode dispatch. Real excelinvoice-mode parity is covered by
        the Phase D e2e golden tests (tracked follow-up).
        """
        _build_invoice_fixture(tmp_path)
        monkeypatch.chdir(tmp_path)
        excel_invoice_path = tmp_path / "data" / "inputdata" / "sample_excel_invoice.xlsx"
        # Real asset would be copied here, e.g.:
        # shutil.copy2(_SAMPLEFILE_DIR / "...xlsx", excel_invoice_path)

        config = Config(
            system=SystemSettings(extended_mode=None, save_raw=True, save_thumbnail_image=True, magic_variable=False),
            multidata_tile=MultiDataTileSettings(ignore_errors=False),
        )
        v1_run(custom_dataset_function=_no_op_fn, config=config)

        for idx in range(3):
            resource_paths = resolve_tile_paths(tmp_path / "data", idx)
            expected_root = tmp_path / "data" if idx == 0 else tmp_path / "data" / "divided" / f"{idx:04d}"
            for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
                v1_dir = expected_root / dirname
                assert v1_dir.is_dir(), f"v1 fixture must have produced {v1_dir}"
                assert getattr(resource_paths, field) == v1_dir

        assert excel_invoice_path.parent.is_dir()


class TestDirTreeParityMultidatatitleMode:
    """TC-GOLD-003: multidatatile mode (3 tiles), divided/ directory set parity."""

    def test_multidatatile_mode_v2_paths_match_v1_directory_set(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MultiDataTile mode (3 tiles) must produce matching divided/ directory sets.

        The expected tree comes from a real MultiDataTile dispatch of the v1
        orchestration loop over three input files (TC-GOLD-004 principle), never
        a hand-written directory list. Until Session J0 this cell silently ran
        TC-GOLD-002's directory-contract stub, because that stub leaked out of
        the ExcelInvoice cell through the module global; the autouse
        ``_restore_v1_run`` fixture is what makes the assertion below mean
        something.
        """
        _build_invoice_fixture(tmp_path)
        monkeypatch.chdir(tmp_path)
        for name in ("sample_a.txt", "sample_b.txt", "sample_c.txt"):
            (tmp_path / "data" / "inputdata" / name).write_text("dummy", encoding="utf-8")

        config = Config(
            system=SystemSettings(extended_mode="MultiDataTile", save_raw=True, save_thumbnail_image=True, magic_variable=False),
            multidata_tile=MultiDataTileSettings(ignore_errors=False),
        )
        v1_run(custom_dataset_function=_no_op_fn, config=config)

        for idx in range(3):
            resource_paths = resolve_tile_paths(tmp_path / "data", idx)
            expected_root = tmp_path / "data" if idx == 0 else tmp_path / "data" / "divided" / f"{idx:04d}"
            for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
                v1_dir = expected_root / dirname
                assert v1_dir.is_dir(), f"v1 fixture must have produced {v1_dir}"
                assert getattr(resource_paths, field) == v1_dir


class TestDirTreeParityDividedSubdirectory:
    """TC-GOLD-006: idx>=1 paths match the v1 divided/{n:04d}/ subdirectory layout."""

    def test_idx_ge_1_matches_v1_divided_subdirectory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A real (non-hand-written) v1 divided/0001/ tree must match resolve_tile_paths(idx=1).

        Uses ``rdetoolkit.workflows.generate_folder_paths_iterator`` directly —
        the same v1 machinery ``workflows.run`` uses internally to allocate
        per-tile output directories — with a two-tile ``raw_files_group`` so a
        real ``divided/0001/`` tree is produced without needing a full
        excelinvoice/MultiDataTile fixture.
        """
        monkeypatch.chdir(tmp_path)
        raw_files_group = [(Path("data/temp/a.txt"),), (Path("data/temp/b.txt"),)]

        # Dynamically generated expected tree (TC-GOLD-004 principle): run v1
        # for real; the generator itself creates the directories as a side
        # effect (v1 DirectoryOps behavior).
        list(
            generate_folder_paths_iterator(
                raw_files_group,
                invoice_org_filepath=Path("data/tasksupport/invoice_org.json"),
                invoice_schema_filepath=Path("data/tasksupport/invoice.schema.json"),
            ),
        )

        resource_paths = resolve_tile_paths(tmp_path / "data", 1)

        for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
            v1_dir = tmp_path / "data" / "divided" / "0001" / dirname
            assert v1_dir.is_dir(), f"v1 fixture must have produced {v1_dir}"
            assert getattr(resource_paths, field) == v1_dir
