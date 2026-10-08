"""``data/temp`` is created before input parsing, as v1 does (Session J0, debt 4).

v1 creates the unpack directory unconditionally *before* any input checker
runs: ``workflows.check_files_result`` opens with
``StorageDir.get_specific_outputdir(True, "temp")`` and only then calls
``selected_input_checker(...).parse(...)``. v2 created it lazily -- when a tile
was allocated or an archive was actually unpacked -- so every run that failed
*before* parsing succeeded left one directory less on disk than v1 did. That
was the whole content of the ``_UNPACK_DIRECTORY_GAP`` asymmetry the Session
I6-B seats bounded (``tests/v2/modes/test_{excelinvoice,multidatatile}_compat_i6_b.py``);
with the pre-creation in place those seats now assert an empty symmetric
difference.

The directory is resolved from the run's **data root**, not from
``unpacked_dir_path``: on an alias-flat project it is ``<root>/temp``.

Every case below is **discriminating**: it goes RED when the ``mkdir`` in
``Runner.run`` is removed. Asserting "``data/temp`` exists after a successful
run" would not, because the invoice backup creates that directory on its own
later in the run -- so the success case pins the *ordering* (the directory
exists by the time ``pre_validate`` is entered, which is before any parsing or
backup) instead of the mere existence.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-J0-TEMP-EP-001 | ordering, success path | a one-tile invoice project | ``data/temp`` already exists when ``pre_validate`` is entered |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-J0-TEMP-EV-002 | checker rejects | two ``*_excel_invoice.xlsx`` | run failed with no tile, ``data/temp`` still exists |
| TC-J0-TEMP-EV-003 | pre_validate rejects | schema-invalid invoice | run failed before any tile, ``data/temp`` still exists |
| TC-J0-TEMP-EV-004 | alias-flat, rejected early | markers below the root, no ``invoice.schema.json`` | ``<root>/temp`` exists and ``<root>/data`` does not |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"basic": {"type": "object", "properties": {"dataName": {"type": "string"}}}},
}

_OVERRIDES: dict[str, Any] = {
    "system": {
        "extended_mode": "invoice",
        "save_raw": True,
        "save_nonshared_raw": False,
        "save_thumbnail_image": False,
        "magic_variable": False,
    },
}


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Consume one tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()


def _invoice(*, valid: bool = True) -> dict[str, Any]:
    return {
        "datasetId": "j0-temp-precreation",
        "basic": {
            "dateSubmitted": "2026-09-28",
            "dataOwnerId": "0" * 56,
            # ``dataName`` must be a string, so an int violates the schema.
            "dataName": "j0" if valid else 1,
        },
    }


def _build(
    data_root: Path,
    *,
    valid_invoice: bool = True,
    input_files: dict[str, str] | None = None,
    with_schema: bool = True,
) -> None:
    """Materialize the RDE input directories directly below ``data_root``.

    Args:
        data_root: Directory that directly owns ``inputdata`` / ``invoice`` /
            ``tasksupport``.
        valid_invoice: Write an invoice that satisfies the schema.
        input_files: ``name -> content`` map written into ``inputdata``.
        with_schema: Write ``tasksupport/invoice.schema.json``. Omitting it makes
            ``pre_validate`` reject the run with catalog code 4003, before the
            input is parsed and before any tile or invoice backup exists.
    """
    inputdata = data_root / "inputdata"
    inputdata.mkdir(parents=True)
    for name, content in ({"a.txt": "a"} if input_files is None else input_files).items():
        (inputdata / name).write_text(content, encoding="utf-8")
    (data_root / "invoice").mkdir(parents=True)
    (data_root / "invoice" / "invoice.json").write_text(
        json.dumps(_invoice(valid=valid_invoice)),
        encoding="utf-8",
    )
    (data_root / "tasksupport").mkdir(parents=True)
    if with_schema:
        (data_root / "tasksupport" / "invoice.schema.json").write_text(json.dumps(_SCHEMA), encoding="utf-8")


def _nested_runner(root: Path) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )


def test_unpack_directory_exists_before_run_level_validation__tc_j0_temp_ep_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-J0-TEMP-EP-001: on the success path the directory exists *early enough*.

    Asserting that a successful run left ``data/temp`` behind proves nothing:
    the invoice backup creates it anyway, later. What v1 contracts is the
    *timing* -- the directory exists before anything parses the input -- so this
    case observes the earliest v2 step that follows the ``mkdir``,
    ``pre_validate``, and requires the directory to be there already.
    """
    # Given: a one-tile invoice project and a Runner whose pre_validate is observed
    root = tmp_path / "ok"
    _build(root / "data")
    monkeypatch.chdir(root)
    runner = _nested_runner(root)
    seen_at_pre_validate: list[bool] = []
    original_pre_validate = runner.pre_validate

    def _observing_pre_validate(config: Any) -> None:
        seen_at_pre_validate.append((root / "data" / "temp").is_dir())
        original_pre_validate(config)

    runner.pre_validate = _observing_pre_validate  # type: ignore[method-assign]

    # When: the run completes
    report = runner.run(_noop_flow, **_OVERRIDES)

    # Then: the directory was already on disk when run-level validation started
    assert report.status == "success", report.error
    assert seen_at_pre_validate == [True]
    assert (root / "data" / "temp").is_dir()


def test_checker_rejection_still_leaves_the_unpack_directory__tc_j0_temp_ev_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-J0-TEMP-EV-002: the input checker fails after v1 created ``data/temp``.

    Two ``*_excel_invoice.xlsx`` files make ``ExcelInvoiceChecker._validate_files``
    reject the input before it parses anything, which is exactly the shape where
    v2 used to publish one directory fewer than v1.
    """
    # Given: an ExcelInvoice project carrying two workbooks
    root = tmp_path / "rejected"
    _build(
        root / "data",
        input_files={"one_excel_invoice.xlsx": "not-a-workbook", "two_excel_invoice.xlsx": "not-a-workbook"},
    )
    monkeypatch.chdir(root)

    # When: the run is rejected by the checker
    report = _nested_runner(root).run(_noop_flow, **_OVERRIDES)

    # Then: no tile ran, yet the pre-parse directory is on disk
    assert report.status == "failed"
    assert report.iterations == []
    assert (root / "data" / "temp").is_dir()


def test_pre_validate_rejection_still_leaves_the_unpack_directory__tc_j0_temp_ev_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-J0-TEMP-EV-003: run-level validation fails after the directory exists.

    ``pre_validate`` has no v1 counterpart, so the earliest v1-observable state
    is "config loaded, ``data/temp`` created". A v2 run that aborts in
    ``pre_validate`` must therefore still have it.
    """
    # Given: a project whose invoice violates its schema
    root = tmp_path / "invalid"
    _build(root / "data", valid_invoice=False)
    monkeypatch.chdir(root)

    # When: run-level validation rejects the invoice
    report = _nested_runner(root).run(_noop_flow, **_OVERRIDES)

    # Then: the run failed before any tile and the directory is still there
    assert report.status == "failed"
    assert report.iterations == []
    assert (root / "data" / "temp").is_dir()


def test_alias_flat_root_gets_its_own_temp_directory__tc_j0_temp_ev_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-J0-TEMP-EV-004: the directory follows the data root, not ``unpacked_dir_path``.

    The project has no ``invoice.schema.json``, so ``pre_validate`` rejects the
    run before any tile or invoice backup can create a directory: a ``<root>/temp``
    can only have come from the pre-creation. The Runner also keeps its default
    ``<root>/unpacked`` unpack directory, so the name ``temp`` can only have come
    from the data-root rule.
    """
    # Given: an alias-flat project root that is rejected before parsing
    root = tmp_path / "flat"
    _build(root, with_schema=False)
    monkeypatch.chdir(root)

    # When: run-level validation rejects the missing schema
    report = Runner(root=root).run(_noop_flow, **_OVERRIDES)

    # Then: the data root -- the root itself -- owns the temp directory
    assert report.status == "failed"
    assert report.iterations == []
    assert (root / "temp").is_dir()
    assert not (root / "data").exists()
    assert not (root / "unpacked").exists()
