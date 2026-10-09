"""End-to-end integration tests for Issue #503.

These tests exercise the *real* :func:`rdetoolkit.workflows.run` entry point
(SmartTableChecker -> generate_folder_paths_iterator -> the SmartTableInvoice
pipeline) to verify that a structured-processing template written for
invoice mode -- one that inspects ``resource_paths.rawfiles`` using
extension/count/``rawfiles[0]`` assumptions -- runs unmodified when the same
inputs are processed in SmartTable mode. Unlike the other unit/mock-based
tests added for Issue #503, this module never mocks
``SmartTableChecker``/``generate_folder_paths_iterator``/the pipeline: it
drives the whole wiring so that any mismatch between those components would
be caught here.

Equivalence Partitioning:
| API    | Input/State Partition                                    | Rationale                                             | Expected Outcome                                                  | Test ID    |
| ------ | --------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------ | ---------- |
| ``run``| SmartTable mode, ``save_table_file=False``, N data rows   | Representative invoice-mode template, no row-CSV leak   | callback sees only user files; ``smarttable_rawfile`` is canonical | TC-EP-001  |
| ``run``| SmartTable mode, ``save_table_file=True``, N data rows    | Original file must register at ``divided/0001``        | divided/0001 = original file; invoice seeded from invoice_org      | TC-EP-002  |

Boundary Value:
| API    | Boundary                                                   | Rationale                                               | Expected Outcome                                                    | Test ID    |
| ------ | ----------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------- | ---------- |
| ``run``| ``system.save_raw`` / ``save_nonshared_raw`` both True       | Row CSV must never leak into persisted artifacts          | no ``fsmarttable_*.csv`` under any ``raw``/``nonshared_raw`` folder   | TC-BV-001  |

Validation commands:
    Direct: ``uv run pytest tests/test_smarttable_workflow_integration.py -q``
    Tox: ``tox -e py312-module -- tests/test_smarttable_workflow_integration.py``

Note:
    Each test runs inside its own ``tmp_path`` (via ``monkeypatch.chdir``)
    because ``rdetoolkit.workflows.generate_folder_paths_iterator`` builds
    the RDE output tree via ``rdetoolkit.core.DirectoryOps("data")``, a
    literal path relative to the process's current working directory.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.workflows import run

SAMPLEFILE_DIR = Path(__file__).parent / "samplefile"


def _write_zip(zip_path: Path, file_contents: dict[str, str]) -> None:
    """Create a zip archive containing the given files at its root."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in file_contents.items():
            zf.writestr(name, content)


def _setup_smarttable_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    csv_rows: list[tuple[str, str, str]],
    save_table_file: bool,
    save_raw: bool = True,
) -> None:
    """Build a real RDE ``data/`` workspace with a SmartTable input for ``run()``.

    Mirrors the on-disk layout ``rdetoolkit init`` generates
    (``data/inputdata``, ``data/invoice``, ``data/tasksupport``), then adds a
    SmartTable source file (two header rows: display names, then mapping
    keys) plus a zip bundling the user data files referenced by its
    ``inputdata1`` column, exactly as SmartTableFile/SmartTableChecker expect
    (files referenced from the table are only resolved against the contents
    of an uploaded zip; see ``SmartTableFile._find_file_by_relative_path``).

    Args:
        tmp_path: pytest temporary directory; used as the process cwd.
        monkeypatch: fixture used to ``chdir`` into ``tmp_path`` (the change
            is automatically reverted at teardown).
        csv_rows: ``(file_name, data_name, sample3_value)`` triples. Each
            becomes one SmartTable data row, referencing one distinct user
            file bundled in the zip.
        save_table_file: value written to ``smarttable.save_table_file``.
        save_raw: value written to both ``system.save_raw`` and
            ``system.save_nonshared_raw``.
    """
    monkeypatch.chdir(tmp_path)

    for name in ("inputdata", "invoice", "tasksupport"):
        Path("data", name).mkdir(parents=True, exist_ok=True)

    shutil.copy2(SAMPLEFILE_DIR / "invoice.schema.json", Path("data/tasksupport/invoice.schema.json"))
    shutil.copy2(SAMPLEFILE_DIR / "invoice.json", Path("data/invoice/invoice.json"))

    save_raw_str = str(save_raw).lower()
    save_table_file_str = str(save_table_file).lower()
    rdeconfig = (
        "system:\n"
        "  extended_mode: null\n"
        f"  save_raw: {save_raw_str}\n"
        f"  save_nonshared_raw: {save_raw_str}\n"
        "  save_thumbnail_image: false\n"
        "  magic_variable: false\n"
        "smarttable:\n"
        f"  save_table_file: {save_table_file_str}\n"
    )
    Path("data/tasksupport/rdeconfig.yml").write_text(rdeconfig, encoding="utf-8")

    zip_contents = {file_name: f"content of {file_name}" for file_name, _, _ in csv_rows}
    _write_zip(Path("data/inputdata/files.zip"), zip_contents)

    display_row = ",".join(["Display"] * 3)
    key_row = "inputdata1,basic/dataName,custom/sample3"
    data_rows = "\n".join(f"{file_name},{data_name},{sample3}" for file_name, data_name, sample3 in csv_rows)
    csv_content = f"{display_row}\n{key_row}\n{data_rows}\n"
    Path("data/inputdata/smarttable_test.csv").write_text(csv_content, encoding="utf-8")


def _invoice_style_custom_dataset_factory(
    calls: list[dict[str, Any]],
) -> Any:
    """Build a callback representative of an invoice-mode structured-processing template.

    The returned callback deliberately makes the assumptions a template
    written for invoice mode commonly makes: ``rawfiles`` holds only the
    user's data file(s), ``rawfiles[0]`` is meaningful, and every entry has
    the expected extension. None of this is SmartTable-aware; if a
    ``fsmarttable_*.csv`` row file ever leaked into ``rawfiles``, these
    assertions would fail.
    """

    def _callback(
        srcpaths: RdeInputDirPaths,
        resource_paths: RdeOutputResourcePath,
    ) -> None:
        calls.append(
            {
                "rawfiles": resource_paths.rawfiles,
                "smarttable_rawfile": resource_paths.smarttable_rawfile,
            },
        )

        # Assumptions typical of invoice-mode templates.
        assert len(resource_paths.rawfiles) >= 1
        first_file = resource_paths.rawfiles[0]
        assert first_file.suffix == ".txt"  # would fail if fsmarttable_*.csv leaked in as rawfiles[0]
        for f in resource_paths.rawfiles:
            assert f.suffix == ".txt"
            assert not f.name.startswith("fsmarttable_")

    return _callback


def test_invoice_style_template_runs_unmodified_under_smarttable_mode(tmp_path, monkeypatch):
    """TC-EP-001 / Issue #503 primary acceptance criterion.

    A representative invoice-mode template (extension/count/``rawfiles[0]``
    assumptions) must run unmodified under SmartTable mode: ``rawfiles``
    contains only user data files in every tile, and ``smarttable_rawfile``
    is the sole, canonical way to reach the per-tile row CSV.
    """
    csv_rows = [
        ("sample1.txt", "Experiment_1", "25"),
        ("sample2.txt", "Experiment_2", "26"),
        ("sample3.txt", "Experiment_3", "27"),
    ]
    _setup_smarttable_workspace(
        tmp_path,
        monkeypatch,
        csv_rows=csv_rows,
        save_table_file=False,
        save_raw=True,
    )

    calls: list[dict[str, Any]] = []
    invoice_style_custom_dataset = _invoice_style_custom_dataset_factory(calls)

    result = json.loads(run(custom_dataset_function=invoice_style_custom_dataset))

    # The callback ran once per data row, and every tile succeeded.
    assert len(calls) == 3
    assert all(status["status"] == "success" for status in result["statuses"])
    assert all(status["mode"] == "SmartTableInvoice" for status in result["statuses"])

    # Registration order (per SmartTableChecker.parse docstring): the LAST
    # table row registers last (data/ root), earlier rows fill divided/000N
    # in table order.
    assert calls[0]["rawfiles"] == (Path("data/temp/sample3.txt"),)
    assert calls[1]["rawfiles"] == (Path("data/temp/sample1.txt"),)
    assert calls[2]["rawfiles"] == (Path("data/temp/sample2.txt"),)

    # smarttable_rawfile is set to the per-tile row CSV in every call.
    for call in calls:
        assert call["smarttable_rawfile"] is not None
        assert call["smarttable_rawfile"].name.startswith("fsmarttable_")
        assert call["smarttable_rawfile"].suffix == ".csv"

    # Filesystem-level guarantee: the row CSV is never copied into raw/
    # nonshared_raw, regardless of system.save_raw / save_nonshared_raw.
    for raw_dir_name in ("raw", "nonshared_raw"):
        raw_dirs = list(Path("data").glob(f"**/{raw_dir_name}"))
        assert raw_dirs, f"expected at least one {raw_dir_name} directory to have been created"
        for raw_dir in raw_dirs:
            copied_names = {p.name for p in raw_dir.iterdir()}
            assert not any(name.startswith("fsmarttable_") for name in copied_names)
            # Sanity check: the directories are not empty/unused by accident.
            assert copied_names


def test_row_csv_not_copied_to_raw_with_single_row(tmp_path, monkeypatch):
    """TC-BV-001 boundary: a single data row still keeps the row CSV out of raw storage."""
    csv_rows = [("only.txt", "Experiment_only", "1")]
    _setup_smarttable_workspace(
        tmp_path,
        monkeypatch,
        csv_rows=csv_rows,
        save_table_file=False,
        save_raw=True,
    )

    calls: list[dict[str, Any]] = []
    invoice_style_custom_dataset = _invoice_style_custom_dataset_factory(calls)

    result = json.loads(run(custom_dataset_function=invoice_style_custom_dataset))

    assert len(calls) == 1
    assert result["statuses"][0]["status"] == "success"
    assert calls[0]["rawfiles"] == (Path("data/temp/only.txt"),)
    assert calls[0]["smarttable_rawfile"].name.startswith("fsmarttable_")

    for raw_dir_name in ("raw", "nonshared_raw"):
        raw_dir = Path("data", raw_dir_name)
        assert raw_dir.exists()
        copied_names = {p.name for p in raw_dir.iterdir()}
        assert copied_names == {"only.txt"}


def test_save_table_file_true_original_file_registers_first_at_divided_0001(tmp_path, monkeypatch):
    """Verify save_table_file=true registers the original file at divided/0001.

    With save_table_file=true, the original file should occupy
    divided/0001 (registered first) and data rows should keep their
    row1..rowN registration order, with the last row at data/ root.

    The divided/0001 tile has no pre-existing invoice.json, so
    SmartTableEarlyExitProcessor seeds it from invoice_org before updating
    dataName (regression coverage for the bug found in Issue #503 Task 06).
    """
    csv_rows = [
        ("sample1.txt", "Experiment_1", "25"),
        ("sample2.txt", "Experiment_2", "26"),
    ]
    _setup_smarttable_workspace(
        tmp_path,
        monkeypatch,
        csv_rows=csv_rows,
        save_table_file=True,
        save_raw=True,
    )

    calls: list[dict[str, Any]] = []
    invoice_style_custom_dataset = _invoice_style_custom_dataset_factory(calls)

    run(custom_dataset_function=invoice_style_custom_dataset)

    # Desired behavior: the callback runs once per DATA ROW only (the
    # original-file tile early-exits and never reaches DatasetRunner).
    assert len(calls) == 2

    # idx=0 -> data/ root: last row (Experiment_2), registered last.
    root_invoice = json.loads(Path("data/invoice/invoice.json").read_text(encoding="utf-8"))
    assert root_invoice["basic"]["dataName"] == "Experiment_2"

    # idx=1 -> divided/0001: the ORIGINAL SmartTable file, registered first.
    divided_1_invoice = json.loads(Path("data/divided/0001/invoice/invoice.json").read_text(encoding="utf-8"))
    assert divided_1_invoice["basic"]["dataName"] == "smarttable_test.csv"

    # idx=2 -> divided/0002: first row (Experiment_1).
    divided_2_invoice = json.loads(Path("data/divided/0002/invoice/invoice.json").read_text(encoding="utf-8"))
    assert divided_2_invoice["basic"]["dataName"] == "Experiment_1"

    # The row CSV must still never reach raw/nonshared_raw for the rows that
    # do complete successfully.
    for raw_dir_name in ("raw", "nonshared_raw"):
        for raw_dir in Path("data").glob(f"**/{raw_dir_name}"):
            copied_names = {p.name for p in raw_dir.iterdir()}
            assert not any(name.startswith("fsmarttable_") for name in copied_names)
