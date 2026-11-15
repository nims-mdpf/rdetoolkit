"""GA-11 (#692): opt-in golden artifact snapshots.

In-process tests drive ``RdeTestResult.assert_snapshot`` on real isolated
runs; the ``--rde-update-snapshots`` approval flow and its CI refusal are
observed in a pytest subprocess.

EP table
========

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-SNAP-EP-001 | file | golden equal to the artifact | passes |
| TC-SNAP-EP-002 | repeated runs | two identical runs, one golden | both pass |
| TC-SNAP-EP-003 | approval | plugin update mode (``--rde-update-snapshots``, CI unset) | golden created, update recorded, next compare passes |
| TC-SNAP-EP-004 | directory | golden directory equal to the artifact directory | passes |
| TC-SNAP-EP-005 | ignore_fields | run-specific JSON value at a listed pointer | ignored; golden stores the placeholder (redaction) |
| TC-SNAP-EP-006 | ignore_columns | timestamp CSV column | ignored; other columns still compared |
| TC-SNAP-EP-007 | ignore_files | log file in a directory snapshot | left out |
| TC-SNAP-EP-008 | allow_raw | snapshot of ``raw/`` with ``allow_raw=True`` | allowed |
| TC-SNAP-EP-009 | pytest option | ``--rde-update-snapshots`` locally | golden written, summary lists files |

BV / negative table
===================

| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-SNAP-BV-001 | directory | missing and unexpected files | both listed |
| TC-SNAP-BV-002 | CSV | changed scientific value | row and column named |
| TC-SNAP-BV-003 | JSON | changed value / null vs absent / bool vs int / int vs float | pointer named |
| TC-SNAP-BV-004 | repeated runs | a run that changes between runs | second compare fails |
| TC-SNAP-BV-005 | binary | one byte changed in a PNG | sha256 and sizes, no decoding |
| TC-SNAP-BV-006 | text | changed line | unified diff |
| TC-SNAP-BV-007 | CI | update mode on with CI truthy | refused, golden unchanged; falsy CI values allow |
| TC-SNAP-BV-008 | CI + option | ``--rde-update-snapshots`` with CI=true | usage error, nothing written |
| TC-SNAP-BV-009 | no golden | golden path absent | names the approval option |
| TC-SNAP-BV-010 | size | file above ``max_bytes`` | refused |
| TC-SNAP-BV-011 | symlink | symlinked artifact / file inside the directory | refused |
| TC-SNAP-BV-012 | raw data | ``inputdata`` / ``nonshared_raw`` snapshot | refused unless allow_raw |
| TC-SNAP-BV-013 | arguments | bad pointer / bare string / traversal | TypeError / ValueError |
| TC-SNAP-BV-014 | kind | file artifact vs golden directory | refused |
| TC-SNAP-BV-015 | ignored field | ignored pointer absent from the artifact | reported, not ignored |
| TC-SNAP-BV-016 | approval | golden file no longer produced | removed and recorded |
| TC-SNAP-BV-017 | pytest run | changed artifact without the option | FAILED listing the file and the option |
| TC-SNAP-BV-018 | approval API | ``update=True`` on the result or standalone | TypeError, no parameter, nothing written |
| TC-SNAP-BV-019 | golden symlink | golden file / root is a symlink (also dangling) | refused for compare and update, link target untouched |
| TC-SNAP-BV-020 | golden symlink | symlinked file / directory inside a golden directory | refused for compare and update, nothing written outside |
| TC-SNAP-BV-021 | artifact symlink | linked parent directory (to ``inputdata``) on the way to the artifact or below it | refused, even in update mode; nothing written |
| TC-SNAP-BV-022 | CSV | duplicate header / row wider or narrower than the header | cell named by position / row width reported |
| TC-SNAP-BV-023 | no golden | empty artifact directory, golden absent | fails naming the approval; approval creates the empty baseline |
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

from rdetoolkit import flow
from rdetoolkit.testing import RdeTestResult, RdeTestRunner, snapshot
from rdetoolkit.testing.snapshot import IGNORED_PLACEHOLDER, SnapshotError
from rdetoolkit.types import InputPaths, OutputContext

FIXTURE = Path(__file__).parent / "fixtures" / "rde_case" / "sample"
_PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256))

#: What the next run writes; tests change it to simulate a changed result.
_OUTPUT: dict[str, object] = {}


def _default_output() -> dict[str, object]:
    return {
        "csv": "time,value,timestamp\n0,1.25,2026-11-15T10:00:00\n1,2.50,2026-11-15T10:00:01\n",
        "json": {"run_id": "r-1", "custom": {"temperature": 300, "pressure": 1.0, "enabled": True, "note": None}},
        "text": "line one\nline two\n",
        "png": _PNG,
    }


@flow(id="tests.ga692.snapshot")
def _writes(paths: InputPaths, out: OutputContext) -> None:
    del paths
    out.write_bytes("struct", "result.csv", str(_OUTPUT["csv"]).encode())
    out.write_bytes("struct", "result.json", json.dumps(_OUTPUT["json"]).encode())
    out.write_bytes("struct", "notes.txt", str(_OUTPUT["text"]).encode())
    out.write_bytes("main_image", "plot.png", bytes(_OUTPUT["png"]))  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # CI may be set by the machine running this suite; each test decides.
    monkeypatch.delenv("CI", raising=False)
    _OUTPUT.clear()
    _OUTPUT.update(_default_output())
    snapshot.reset()
    yield
    snapshot.reset()


def _run(tmp_path: Path, label: str = "runs") -> RdeTestResult:
    result = RdeTestRunner(tmp_path / label).run(flow=_writes, project=FIXTURE)
    assert result.status == "success", result.failure_summary(expected_status="success")
    return result


def _approve(result: RdeTestResult, artifact: str, golden: Path, **options: object) -> None:
    """Compare as ``pytest --rde-update-snapshots`` does: approval comes only from the plugin's update mode.

    ``pytest_configure`` turns the mode on for ``--rde-update-snapshots`` (and
    refuses it under CI); here the same module state is set for one call.
    """
    snapshot.set_update_mode(True)
    try:
        result.assert_snapshot(artifact, golden, **options)  # type: ignore[arg-type]
    finally:
        snapshot.set_update_mode(False)


def _approved(tmp_path: Path, artifact: str, **options: object) -> tuple[RdeTestResult, Path]:
    """Run once and approve ``artifact`` as the golden copy."""
    result = _run(tmp_path, "approve")
    golden = tmp_path / "golden" / Path(artifact).name
    _approve(result, artifact, golden, **options)
    return result, golden


# ------------------------------------------------------------------------ EP


def test_equal_file_passes__tc_snap_ep_001(tmp_path: Path) -> None:
    """TC-SNAP-EP-001: an artifact equal to its golden copy passes."""
    # Given: a golden file copied from a reviewed run
    result = _run(tmp_path)
    golden = tmp_path / "result.csv"
    shutil.copyfile(result.artifact_path("structured/result.csv"), golden)
    # When / Then
    result.assert_snapshot("structured/result.csv", golden)
    assert snapshot.recorded_updates() == ()


def test_two_identical_runs_pass__tc_snap_ep_002(tmp_path: Path) -> None:
    """TC-SNAP-EP-002: the same inputs give the same snapshot on every run."""
    # Given
    _, golden = _approved(tmp_path, "structured")
    # When / Then: two further runs both match
    _run(tmp_path, "first").assert_snapshot("structured", golden)
    _run(tmp_path, "second").assert_snapshot("structured", golden)


def test_explicit_approval_creates_golden__tc_snap_ep_003(tmp_path: Path) -> None:
    """TC-SNAP-EP-003: the approval mode writes the golden file and records it."""
    # When
    result, golden = _approved(tmp_path, "structured/result.csv")
    # Then
    assert golden.read_bytes() == result.read_bytes("structured/result.csv")
    assert snapshot.recorded_updates() == (snapshot.SnapshotUpdate(golden, "created"),)
    assert snapshot.update_summary_lines() == [f"created: {golden}"]
    result.assert_snapshot("structured/result.csv", golden)


def test_approval_of_a_change_is_recorded_as_changed__tc_snap_ep_003(tmp_path: Path) -> None:
    """TC-SNAP-EP-003: approving a changed artifact rewrites the golden copy."""
    # Given
    _, golden = _approved(tmp_path, "structured/notes.txt")
    _OUTPUT["text"] = "line one\nline 2\n"
    changed = _run(tmp_path, "changed")
    # When
    _approve(changed, "structured/notes.txt", golden)
    # Then
    assert golden.read_text(encoding="utf-8") == "line one\nline 2\n"
    assert snapshot.recorded_updates()[-1].action == "changed"


def test_update_mode_default_comes_from_the_option(tmp_path: Path) -> None:
    """The plugin option's update mode is the only switch that approves."""
    # Given
    result = _run(tmp_path)
    golden = tmp_path / "golden.csv"
    # When
    snapshot.set_update_mode(True)
    assert snapshot.update_mode() is True
    result.assert_snapshot("structured/result.csv", golden)
    # Then
    assert golden.is_file()
    snapshot.reset()
    assert snapshot.update_mode() is False
    assert snapshot.recorded_updates() == ()


def test_directory_snapshot_passes__tc_snap_ep_004(tmp_path: Path) -> None:
    """TC-SNAP-EP-004: a directory snapshot holds every file below it."""
    # When
    result, golden = _approved(tmp_path, "structured")
    # Then
    assert sorted(path.name for path in golden.iterdir()) == ["notes.txt", "result.csv", "result.json"]
    result.assert_snapshot("structured", golden)


def test_ignored_json_field_is_redacted__tc_snap_ep_005(tmp_path: Path) -> None:
    """TC-SNAP-EP-005: only the listed pointer is ignored; the golden copy never holds its value."""
    # Given: a golden copy approved with the run id ignored
    _, golden = _approved(tmp_path, "structured/result.json", ignore_fields=("/run_id",))
    stored = json.loads(golden.read_text(encoding="utf-8"))
    assert stored["run_id"] == IGNORED_PLACEHOLDER
    assert "r-1" not in golden.read_text(encoding="utf-8")
    # When: the next run records another run id
    _OUTPUT["json"] = {**_default_output()["json"], "run_id": "r-2"}  # type: ignore[dict-item]
    rerun = _run(tmp_path, "rerun")
    # Then: it matches; without the ignore it does not
    rerun.assert_snapshot("structured/result.json", golden, ignore_fields=["/run_id"])
    with pytest.raises(AssertionError, match='/run_id: expected "<rde-snapshot:ignored>", got "r-2"'):
        rerun.assert_snapshot("structured/result.json", golden)


def test_wildcard_pointer_masks_every_element(tmp_path: Path) -> None:
    """A '*' segment matches every key or list index, and only there."""
    # Given
    _OUTPUT["json"] = {"items": [{"at": "t1", "v": 1}, {"at": "t2", "v": 2}], "a/b": {"~": 1}}
    _, golden = _approved(tmp_path, "structured/result.json", ignore_fields=("/items/*/at", "/a~1b/~0", "/items/9/x", "/items/0/v/deeper"))
    # Then
    assert json.loads(golden.read_text(encoding="utf-8")) == {
        "items": [{"at": IGNORED_PLACEHOLDER, "v": 1}, {"at": IGNORED_PLACEHOLDER, "v": 2}],
        "a/b": {"~": IGNORED_PLACEHOLDER},
    }


def test_ignored_csv_column_keeps_other_columns__tc_snap_ep_006(tmp_path: Path) -> None:
    """TC-SNAP-EP-006: the timestamp column is ignored, the scientific columns are not."""
    # Given
    _, golden = _approved(tmp_path, "structured/result.csv", ignore_columns=("timestamp",))
    assert "2026-11-15" not in golden.read_text(encoding="utf-8")
    # When: only the timestamps change
    _OUTPUT["csv"] = "time,value,timestamp\n0,1.25,2026-11-16T00:00:00\n1,2.50,2026-11-16T00:00:01\n"
    _run(tmp_path, "later").assert_snapshot("structured/result.csv", golden, ignore_columns=("timestamp",))
    # Then: a changed value is still caught
    _OUTPUT["csv"] = "time,value,timestamp\n0,1.25,x\n1,2.51,y\n"
    with pytest.raises(AssertionError, match="row 2, column 'value': expected '2.50', got '2.51'"):
        _run(tmp_path, "changed").assert_snapshot("structured/result.csv", golden, ignore_columns=("timestamp",))


def test_ignored_column_still_requires_the_header__tc_snap_ep_006(tmp_path: Path) -> None:
    """TC-SNAP-EP-006: ignoring a column never drops it: a removed column is a difference."""
    # Given
    _, golden = _approved(tmp_path, "structured/result.csv", ignore_columns=("timestamp",))
    _OUTPUT["csv"] = "time,value\n0,1.25\n1,2.50\n"
    # When / Then
    with pytest.raises(AssertionError, match=r"header: golden \['time', 'value', 'timestamp'\], actual \['time', 'value'\]"):
        _run(tmp_path, "dropped").assert_snapshot("structured/result.csv", golden, ignore_columns=("timestamp",))


def test_ignored_files_are_left_out__tc_snap_ep_007(tmp_path: Path) -> None:
    """TC-SNAP-EP-007: a file pattern listed in ignore_files is not part of the snapshot."""
    # Given: a directory golden copy without the notes file
    result, golden = _approved(tmp_path, "structured", ignore_files=("*.txt",))
    assert not (golden / "notes.txt").exists()
    # When / Then
    _OUTPUT["text"] = "changed"
    _run(tmp_path, "rerun").assert_snapshot("structured", golden, ignore_files=("*.txt",))
    with pytest.raises(AssertionError, match="unexpected \\(produced, not in golden\\): notes.txt"):
        result.assert_snapshot("structured", golden)


def test_raw_snapshot_needs_allow_raw__tc_snap_ep_008(tmp_path: Path) -> None:
    """TC-SNAP-EP-008 / BV-012: raw input data is refused unless explicitly allowed."""
    # Given
    result = _run(tmp_path)
    golden = tmp_path / "golden"
    # When / Then
    for artifact in ("inputdata", "nonshared_raw/sample.txt", "inputdata/sample.txt"):
        with pytest.raises(SnapshotError, match="raw input data"):
            _approve(result, artifact, golden / artifact)
    assert not golden.exists()
    _approve(result, "nonshared_raw", golden / "raw", allow_raw=True)
    assert (golden / "raw" / "sample.txt").is_file()


# ------------------------------------------------------------------------ BV


def test_directory_reports_missing_and_unexpected__tc_snap_bv_001(tmp_path: Path) -> None:
    """TC-SNAP-BV-001: both directions of a file-set difference are listed."""
    # Given: a golden directory with an extra file and without notes.txt
    result, golden = _approved(tmp_path, "structured")
    (golden / "notes.txt").unlink()
    (golden / "peaks.csv").write_text("q\n1\n", encoding="utf-8")
    # When
    with pytest.raises(AssertionError) as excinfo:
        result.assert_snapshot("structured", golden)
    # Then
    message = str(excinfo.value)
    assert f"artifact 'structured' differs from golden snapshot {golden}" in message
    assert "missing (in golden, not produced): peaks.csv" in message
    assert "unexpected (produced, not in golden): notes.txt" in message
    assert "--rde-update-snapshots" in message
    assert f"run report: {result.report_path}" in message


def test_changed_scientific_value_fails__tc_snap_bv_002(tmp_path: Path) -> None:
    """TC-SNAP-BV-002 (mutation check): altering one recorded value makes the snapshot RED."""
    # Given
    _, golden = _approved(tmp_path, "structured/result.csv")
    _OUTPUT["csv"] = str(_OUTPUT["csv"]).replace("1.25", "1.26")
    # When
    with pytest.raises(AssertionError) as excinfo:
        _run(tmp_path, "mutated").assert_snapshot("structured/result.csv", golden)
    # Then
    assert "changed: <file>" in str(excinfo.value)
    assert "row 1, column 'value': expected '1.25', got '1.26'" in str(excinfo.value)


def test_csv_with_equal_cells_but_other_bytes(tmp_path: Path) -> None:
    """Quoting or line-ending changes are reported, not ignored."""
    # Given
    _, golden = _approved(tmp_path, "structured/result.csv")
    _OUTPUT["csv"] = str(_OUTPUT["csv"]).replace("\n", "\r\n")
    # When / Then
    with pytest.raises(AssertionError, match="cells are equal but the bytes differ"):
        _run(tmp_path, "crlf").assert_snapshot("structured/result.csv", golden)


@pytest.mark.parametrize(
    ("custom", "line"),
    [
        pytest.param({"temperature": 301, "pressure": 1.0, "enabled": True, "note": None}, "/custom/temperature: expected 300, got 301", id="value"),
        pytest.param({"temperature": 300, "pressure": 1.0, "enabled": True}, "/custom/note: missing (expected null)", id="null-vs-absent"),
        pytest.param({"temperature": 300, "pressure": 1.0, "enabled": 1, "note": None}, "/custom/enabled: expected true, got 1", id="bool-vs-int"),
        pytest.param({"temperature": 300, "pressure": 1, "enabled": True, "note": None}, "/custom/pressure: expected 1.0, got 1", id="float-vs-int"),
        pytest.param({"temperature": 300, "pressure": 1.0, "enabled": True, "note": None, "x": 0}, "/custom/x: unexpected (got 0)", id="extra-key"),
    ],
)
def test_json_differences_by_pointer__tc_snap_bv_003(tmp_path: Path, custom: dict[str, object], line: str) -> None:
    """TC-SNAP-BV-003: JSON snapshots compare strict JSON types by pointer."""
    # Given
    _, golden = _approved(tmp_path, "structured/result.json")
    _OUTPUT["json"] = {"run_id": "r-1", "custom": custom}
    # When / Then
    with pytest.raises(AssertionError) as excinfo:
        _run(tmp_path, "changed").assert_snapshot("structured/result.json", golden)
    assert line in str(excinfo.value)


def test_invalid_json_falls_back_to_a_text_diff(tmp_path: Path) -> None:
    """A .json artifact that no longer parses is shown as a line diff."""
    # Given
    result, golden = _approved(tmp_path, "structured/result.json")
    result.artifact_path("structured/result.json").write_text("{broken\n", encoding="utf-8")
    # When / Then
    with pytest.raises(AssertionError, match=r"\+\{broken"):
        result.assert_snapshot("structured/result.json", golden)


def test_changing_run_fails_the_second_compare__tc_snap_bv_004(tmp_path: Path) -> None:
    """TC-SNAP-BV-004: a non-deterministic output is caught by a repeated run."""
    # Given: the first run approved
    _, golden = _approved(tmp_path, "structured")
    # When: the next run differs in one value
    _OUTPUT["json"] = {**_default_output()["json"], "custom": {"temperature": 299}}  # type: ignore[dict-item]
    # Then
    with pytest.raises(AssertionError, match="changed: result.json"):
        _run(tmp_path, "second").assert_snapshot("structured", golden)


def test_binary_is_compared_by_hash__tc_snap_bv_005(tmp_path: Path) -> None:
    """TC-SNAP-BV-005: images are compared as bytes (sha256), never decoded."""
    # Given
    result, golden = _approved(tmp_path, "main_image/plot.png")
    assert golden.read_bytes() == _PNG
    _OUTPUT["png"] = _PNG[:-1] + b"\x00"
    # When
    with pytest.raises(AssertionError) as excinfo:
        _run(tmp_path, "changed").assert_snapshot("main_image/plot.png", golden)
    # Then
    assert f"golden {len(_PNG)} bytes sha256" in str(excinfo.value)
    assert f"actual {len(_PNG)} bytes sha256" in str(excinfo.value)
    result.assert_snapshot("main_image/plot.png", golden)


def test_text_is_shown_as_a_diff__tc_snap_bv_006(tmp_path: Path) -> None:
    """TC-SNAP-BV-006: text artifacts produce a unified diff."""
    # Given
    _, golden = _approved(tmp_path, "structured/notes.txt")
    _OUTPUT["text"] = "line one\nline 2\n"
    # When / Then
    with pytest.raises(AssertionError) as excinfo:
        _run(tmp_path, "changed").assert_snapshot("structured/notes.txt", golden)
    assert "-line two" in str(excinfo.value)
    assert "+line 2" in str(excinfo.value)


def test_text_with_only_line_ending_changes(tmp_path: Path) -> None:
    """Line-ending-only changes are a difference, explained as such."""
    # Given
    _, golden = _approved(tmp_path, "structured/notes.txt")
    _OUTPUT["text"] = "line one\r\nline two\r\n"
    # When / Then
    with pytest.raises(AssertionError, match="lines are equal but the bytes differ"):
        _run(tmp_path, "crlf").assert_snapshot("structured/notes.txt", golden)


def test_long_text_diff_is_capped(tmp_path: Path) -> None:
    """A long diff stays readable."""
    # Given
    _OUTPUT["text"] = "".join(f"a{i}\n" for i in range(40))
    _, golden = _approved(tmp_path, "structured/notes.txt")
    _OUTPUT["text"] = "".join(f"b{i}\n" for i in range(40))
    # When / Then
    with pytest.raises(AssertionError, match=r"\.\.\. \d+ more diff line\(s\)"):
        _run(tmp_path, "changed").assert_snapshot("structured/notes.txt", golden)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "github-actions"])
def test_ci_refuses_update__tc_snap_bv_007(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """TC-SNAP-BV-007: a truthy CI never approves, even with the update mode already on."""
    # Given: an approved golden copy and a changed run
    _, golden = _approved(tmp_path, "structured/result.csv")
    before = golden.read_bytes()
    _OUTPUT["csv"] = "time,value,timestamp\n0,9,x\n"
    changed = _run(tmp_path, "changed")
    monkeypatch.setenv("CI", value)
    # When
    with pytest.raises(SnapshotError) as excinfo:
        _approve(changed, "structured/result.csv", golden)
    # Then
    assert "refusing to update snapshot" in str(excinfo.value)
    assert "changed: <file>" in str(excinfo.value)
    assert golden.read_bytes() == before


@pytest.mark.parametrize("value", ["", "0", "false", "No", "off"])
def test_falsy_ci_allows_update__tc_snap_bv_007(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """TC-SNAP-BV-007: CI set to a false value is a local run."""
    # Given
    monkeypatch.setenv("CI", value)
    # When
    _approved(tmp_path, "structured/result.csv")
    # Then
    assert snapshot.ci_is_active() is False
    assert snapshot.ci_is_active({"CI": "true"}) is True
    assert snapshot.ci_is_active({}) is False


def test_missing_golden_names_the_approval__tc_snap_bv_009(tmp_path: Path) -> None:
    """TC-SNAP-BV-009: an absent golden copy explains how to create it."""
    # Given
    result = _run(tmp_path)
    golden = tmp_path / "none.csv"
    # When
    with pytest.raises(AssertionError) as excinfo:
        result.assert_snapshot("structured/result.csv", golden)
    # Then
    assert f"golden snapshot {golden} for artifact 'structured/result.csv' does not exist" in str(excinfo.value)
    assert "pytest --rde-update-snapshots" in str(excinfo.value)
    assert not golden.exists()


def test_size_limit__tc_snap_bv_010(tmp_path: Path) -> None:
    """TC-SNAP-BV-010: giant files are refused on either side."""
    # Given
    result, golden = _approved(tmp_path, "structured/result.csv")
    # When / Then
    with pytest.raises(SnapshotError, match="above max_bytes=10"):
        result.assert_snapshot("structured/result.csv", golden, max_bytes=10)
    big_golden = tmp_path / "big.txt"
    big_golden.write_text("x" * 100, encoding="utf-8")
    with pytest.raises(SnapshotError, match=f"snapshot file {big_golden} is 100 bytes"):
        result.assert_snapshot("structured/notes.txt", big_golden, max_bytes=50)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinks_are_refused__tc_snap_bv_011(tmp_path: Path) -> None:
    """TC-SNAP-BV-011: a symlinked artifact could publish a file from outside the run."""
    # Given
    result = _run(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    result.artifact_path("structured/link.txt").symlink_to(secret)
    result.artifact_path("thumbnail").rmdir()
    result.artifact_path("thumbnail").symlink_to(result.artifact_path("structured"))
    # When / Then
    with pytest.raises(SnapshotError, match="symlinked file 'structured/link.txt'"):
        _approve(result, "structured", tmp_path / "golden")
    with pytest.raises(SnapshotError, match="symlinked artifact 'thumbnail'"):
        _approve(result, "thumbnail", tmp_path / "golden")
    assert not (tmp_path / "golden").exists()


def test_update_argument_is_not_accepted__tc_snap_bv_018(tmp_path: Path) -> None:
    """TC-SNAP-BV-018: only ``--rde-update-snapshots`` approves; no argument can bypass it."""
    # Given: a run whose golden copy does not exist yet
    result = _run(tmp_path)
    golden = tmp_path / "golden.csv"
    # Then: neither public assertion signature has an update parameter
    assert "update" not in inspect.signature(RdeTestResult.assert_snapshot).parameters
    assert "update" not in inspect.signature(snapshot.assert_snapshot).parameters
    # When / Then: passing one is a TypeError and writes nothing
    with pytest.raises(TypeError, match="update"):
        result.assert_snapshot("structured/result.csv", golden, update=True)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="update"):
        snapshot.assert_snapshot(result, "structured/result.csv", golden, update=True)  # type: ignore[call-arg]
    assert not golden.exists()
    assert snapshot.recorded_updates() == ()


def _outside(tmp_path: Path, content: bytes) -> Path:
    """A file outside every golden root, standing for a file the test must never touch."""
    target = tmp_path / "outside" / "target.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_golden_file_is_refused__tc_snap_bv_019(tmp_path: Path) -> None:
    """TC-SNAP-BV-019: a golden file that is a link is neither compared nor written through."""
    # Given: a golden path linking to an outside file holding the artifact's bytes
    result = _run(tmp_path)
    produced = result.read_bytes("structured/result.csv")
    target = _outside(tmp_path, produced)
    golden = tmp_path / "golden.csv"
    golden.symlink_to(target)
    # When / Then: comparing is refused although the content matches
    with pytest.raises(SnapshotError, match=f"snapshot refuses the symlinked golden path {golden}"):
        result.assert_snapshot("structured/result.csv", golden)
    # When / Then: approving a change is refused and the link target is untouched
    target.write_bytes(b"stale\n")
    with pytest.raises(SnapshotError, match="symlinked golden path"):
        _approve(result, "structured/result.csv", golden)
    assert target.read_bytes() == b"stale\n"
    assert golden.is_symlink()
    assert snapshot.recorded_updates() == ()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_dangling_golden_link_is_not_created_through__tc_snap_bv_019(tmp_path: Path) -> None:
    """TC-SNAP-BV-019: approving never creates the file a dangling golden link points to."""
    # Given: a golden link whose target does not exist
    result = _run(tmp_path)
    target = tmp_path / "outside" / "created.csv"
    target.parent.mkdir()
    golden = tmp_path / "golden.csv"
    golden.symlink_to(target)
    # When / Then
    with pytest.raises(SnapshotError, match=f"symlinked golden path {golden}"):
        _approve(result, "structured/result.csv", golden)
    with pytest.raises(SnapshotError, match="symlinked golden path"):
        result.assert_snapshot("structured/result.csv", golden)
    assert not target.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_golden_root_directory_is_refused__tc_snap_bv_019(tmp_path: Path) -> None:
    """TC-SNAP-BV-019: a golden directory that is itself a link is refused."""
    # Given: an approved golden directory reached through a link
    _, real = _approved(tmp_path, "structured")
    link = tmp_path / "linked-golden"
    link.symlink_to(real, target_is_directory=True)
    rerun = _run(tmp_path, "rerun")
    # When / Then
    with pytest.raises(SnapshotError, match=f"symlinked golden path {link}"):
        rerun.assert_snapshot("structured", link)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_file_inside_golden_directory_is_refused__tc_snap_bv_020(tmp_path: Path) -> None:
    """TC-SNAP-BV-020: one linked file in a golden directory refuses the whole snapshot."""
    # Given: an approved directory whose result.csv is replaced by a link to an outside copy
    result, golden = _approved(tmp_path, "structured")
    target = _outside(tmp_path, (golden / "result.csv").read_bytes())
    (golden / "result.csv").unlink()
    (golden / "result.csv").symlink_to(target)
    # When / Then: compare is refused
    with pytest.raises(SnapshotError, match=f"symlinked golden path {golden / 'result.csv'}"):
        result.assert_snapshot("structured", golden)
    # When / Then: an approval of a changed run is refused before anything is written
    _OUTPUT["csv"] = "time,value,timestamp\n0,9,x\n"
    _OUTPUT["text"] = "changed\n"
    before = (golden / "notes.txt").read_bytes()
    with pytest.raises(SnapshotError, match="symlinked golden path"):
        _approve(_run(tmp_path, "changed"), "structured", golden)
    assert target.read_bytes() == result.read_bytes("structured/result.csv")
    assert (golden / "notes.txt").read_bytes() == before
    assert snapshot.recorded_updates()[-1].action == "created"  # only the initial approval


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_directory_inside_golden_directory_is_refused__tc_snap_bv_020(tmp_path: Path) -> None:
    """TC-SNAP-BV-020: a linked sub-directory would let golden paths escape the golden root."""
    # Given: an approved directory with a linked sub-directory pointing outside
    result, golden = _approved(tmp_path, "structured")
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "kept.csv").write_text("q\n1\n", encoding="utf-8")
    (golden / "sub").symlink_to(outside_dir, target_is_directory=True)
    # When / Then: compare is refused
    with pytest.raises(SnapshotError, match=f"symlinked golden path {golden / 'sub'}"):
        result.assert_snapshot("structured", golden)
    # When / Then: approval (which would remove sub/kept.csv as no longer produced) is refused
    with pytest.raises(SnapshotError, match="symlinked golden path"):
        _approve(result, "structured", golden)
    assert (outside_dir / "kept.csv").read_text(encoding="utf-8") == "q\n1\n"


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_new_file_under_a_linked_golden_directory_is_not_written__tc_snap_bv_020(tmp_path: Path) -> None:
    """TC-SNAP-BV-020: an update never creates a file through a linked golden sub-directory."""
    # Given: the artifact gains structured/sub/new.csv, and golden/sub links outside (empty)
    result, golden = _approved(tmp_path, "structured")
    outside_dir = tmp_path / "outside-empty"
    outside_dir.mkdir()
    (golden / "sub").symlink_to(outside_dir, target_is_directory=True)
    result.artifact_path("structured/sub").mkdir()
    result.artifact_path("structured/sub/new.csv").write_text("a\n1\n", encoding="utf-8")
    # When / Then
    with pytest.raises(SnapshotError, match=f"symlinked golden path {golden / 'sub'}"):
        _approve(result, "structured", golden)
    assert list(outside_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("options", "error", "fragment"),
    [
        pytest.param({"ignore_fields": ("run_id",)}, ValueError, "JSON pointer starting with '/'", id="pointer"),
        pytest.param({"ignore_fields": "/run_id"}, TypeError, "iterable of strings", id="bare-string-fields"),
        pytest.param({"ignore_columns": "timestamp"}, TypeError, "iterable of strings", id="bare-string-columns"),
        pytest.param({"ignore_files": [""]}, TypeError, "non-empty strings", id="empty-pattern"),
        pytest.param({"ignore_files": [3]}, TypeError, "non-empty strings", id="pattern-type"),
    ],
)
def test_arguments_are_validated__tc_snap_bv_013(tmp_path: Path, options: dict[str, object], error: type[Exception], fragment: str) -> None:
    """TC-SNAP-BV-013: misconfigured ignores are refused, never silently widened."""
    # Given
    result = _run(tmp_path)
    # When / Then
    with pytest.raises(error, match=fragment):
        result.assert_snapshot("structured/result.csv", tmp_path / "g.csv", **options)  # type: ignore[arg-type]


@pytest.mark.parametrize("artifact", ["/etc", "../sample", "structured/../../x"])
def test_artifact_traversal_is_refused__tc_snap_bv_013(tmp_path: Path, artifact: str) -> None:
    """TC-SNAP-BV-013: the artifact must stay below the data root."""
    # When / Then
    with pytest.raises(ValueError, match="data root"):
        _approve(_run(tmp_path), artifact, tmp_path / "g")


def test_missing_artifact_is_refused(tmp_path: Path) -> None:
    """A missing artifact cannot be approved or compared."""
    # When / Then
    with pytest.raises(SnapshotError, match="snapshot artifact 'structured/none.csv' does not exist"):
        _approve(_run(tmp_path), "structured/none.csv", tmp_path / "g.csv")


def test_kind_mismatch__tc_snap_bv_014(tmp_path: Path) -> None:
    """TC-SNAP-BV-014: a file is not compared with a directory, or the reverse."""
    # Given
    result = _run(tmp_path)
    (tmp_path / "dir").mkdir()
    (tmp_path / "file").write_text("x", encoding="utf-8")
    # When / Then
    with pytest.raises(SnapshotError, match="artifact is a file but golden .* is a directory"):
        result.assert_snapshot("structured/result.csv", tmp_path / "dir")
    with pytest.raises(SnapshotError, match="artifact is a directory but golden .* is a file"):
        result.assert_snapshot("structured", tmp_path / "file")


def test_ignored_pointer_must_exist__tc_snap_bv_015(tmp_path: Path) -> None:
    """TC-SNAP-BV-015: ignoring a value never hides a removed field."""
    # Given
    _, golden = _approved(tmp_path, "structured/result.json", ignore_fields=("/run_id",))
    _OUTPUT["json"] = {"custom": _default_output()["json"]["custom"]}  # type: ignore[index]
    # When / Then
    with pytest.raises(AssertionError, match="/run_id: missing"):
        _run(tmp_path, "no-id").assert_snapshot("structured/result.json", golden, ignore_fields=("/run_id",))


def test_approval_removes_files_no_longer_produced__tc_snap_bv_016(tmp_path: Path) -> None:
    """TC-SNAP-BV-016: approving a directory makes the golden copy match it exactly."""
    # Given
    result, golden = _approved(tmp_path, "structured")
    stale = golden / "old" / "stale.csv"
    stale.parent.mkdir()
    stale.write_text("x\n", encoding="utf-8")
    # When
    _approve(result, "structured", golden)
    # Then
    assert not stale.exists()
    assert snapshot.recorded_updates()[-1] == snapshot.SnapshotUpdate(stale, "removed")
    result.assert_snapshot("structured", golden)


def test_approved_csv_with_ignored_column_is_normalized(tmp_path: Path) -> None:
    """The approved CSV keeps every column and row; only the ignored cells are replaced."""
    # When
    _, golden = _approved(tmp_path, "structured/result.csv", ignore_columns=("timestamp",))
    # Then
    assert golden.read_text(encoding="utf-8") == (
        f"time,value,timestamp\n0,1.25,{IGNORED_PLACEHOLDER}\n1,2.50,{IGNORED_PLACEHOLDER}\n"
    )


def test_undecodable_csv_and_text_are_compared_as_bytes(tmp_path: Path) -> None:
    """Invalid UTF-8 in a text-typed artifact is never decoded lossily."""
    # Given
    result, golden = _approved(tmp_path, "structured")
    result.artifact_path("structured/result.csv").write_bytes(b"\xff\xfe,\n")
    result.artifact_path("structured/notes.txt").write_bytes(b"\xff\n")
    # When
    with pytest.raises(AssertionError) as excinfo:
        result.assert_snapshot("structured", golden, ignore_columns=("value",))
    # Then
    assert str(excinfo.value).count("binary content differs") == 2


def test_approved_invalid_json_is_kept_verbatim(tmp_path: Path) -> None:
    """An unparsable .json artifact is approved byte for byte."""
    # Given
    result = _run(tmp_path)
    result.artifact_path("structured/result.json").write_bytes(b"{broken")
    golden = tmp_path / "g.json"
    # When
    _approve(result, "structured/result.json", golden, ignore_fields=("/x",))
    # Then
    assert golden.read_bytes() == b"{broken"


# ------------------------------------------------------- pytest subprocess

_SUITE = '''
import json
import os
from pathlib import Path

from rdetoolkit import flow
from rdetoolkit.testing import RdeTestRunner
from rdetoolkit.types import InputPaths, OutputContext

PROJECT = Path({project!r})
GOLDEN = Path(__file__).parent / "golden"


@flow(id="tests.ga692.subprocess_snapshot")
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    value = os.environ.get("GA692_VALUE", "1.25")
    out.write_bytes("struct", "result.csv", f"time,value\\n0,{{value}}\\n".encode())


def test_snapshot(rde_runner):
    run = rde_runner.run(flow=pipeline, project=PROJECT)
    run.assert_snapshot("structured", GOLDEN / "structured")
'''


def _suite(tmp_path: Path) -> Path:
    module = tmp_path / "suite" / "test_snap.py"
    module.parent.mkdir()
    module.write_text(textwrap.dedent(_SUITE.format(project=str(FIXTURE))), encoding="utf-8")
    return module


def _pytest(tmp_path: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environ = {key: value for key, value in os.environ.items() if key != "CI"}
    environ.update(env or {})
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-o", "addopts=", "--basetemp", str(tmp_path / "bt"), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env=environ,
    )


def test_option_approves_and_summarizes__tc_snap_ep_009(tmp_path: Path) -> None:
    """TC-SNAP-EP-009 / BV-017 / BV-008: the full local approval flow through pytest."""
    # Given: no golden copy yet
    module = _suite(tmp_path)
    golden = module.parent / "golden" / "structured" / "result.csv"

    # When: running without the option
    first = _pytest(tmp_path, str(module))
    # Then: it fails and nothing is written
    assert first.returncode == 1, first.stdout
    assert "does not exist" in first.stdout
    assert not golden.exists()

    # When: approving locally
    approved = _pytest(tmp_path, str(module), "--rde-update-snapshots")
    # Then: the golden file exists and the summary lists it
    assert approved.returncode == 0, approved.stdout
    assert golden.read_text(encoding="utf-8") == "time,value\n0,1.25\n"
    assert "rdetoolkit: snapshot updates" in approved.stdout
    assert f"created: {golden}" in approved.stdout

    # When: the scientific value changes, without the option
    changed = _pytest(tmp_path, str(module), env={"GA692_VALUE": "1.26"})
    # Then: FAILED, naming the file, the cell and the option
    assert changed.returncode == 1, changed.stdout
    assert "changed: result.csv" in changed.stdout
    assert "row 1, column 'value': expected '1.25', got '1.26'" in changed.stdout
    assert "--rde-update-snapshots" in changed.stdout

    # When: CI tries to approve it
    refused = _pytest(tmp_path, str(module), "--rde-update-snapshots", env={"GA692_VALUE": "1.26", "CI": "true"})
    # Then: a usage error before any test runs, golden unchanged
    assert refused.returncode == 4, refused.stdout + refused.stderr
    assert "--rde-update-snapshots is refused because the CI environment variable is set" in refused.stderr
    assert golden.read_text(encoding="utf-8") == "time,value\n0,1.25\n"

    # When: a repeated, unchanged run
    again = _pytest(tmp_path, str(module))
    # Then: passes with no update summary
    assert again.returncode == 0, again.stdout
    assert "rdetoolkit: snapshot updates" not in again.stdout


def test_option_is_documented_in_help(tmp_path: Path) -> None:
    """The option is listed in pytest --help."""
    # When
    completed = _pytest(tmp_path, "--help")
    # Then
    assert completed.returncode == 0
    assert "--rde-update-snapshots" in completed.stdout


# ------------------------------------------------------------ review fixes


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
@pytest.mark.parametrize("artifact", ["thumbnail/sample.txt", "thumbnail", "structured/raw/sample.txt", "structured"])
def test_linked_parent_directory_is_refused__tc_snap_bv_021(tmp_path: Path, artifact: str) -> None:
    """TC-SNAP-BV-021: a linked directory on the way to the artifact cannot smuggle raw data into a golden file."""
    # Given: thumbnail/ and structured/raw both link to inputdata/
    result = _run(tmp_path)
    inputdata = result.artifact_path("inputdata")
    result.artifact_path("thumbnail").rmdir()
    result.artifact_path("thumbnail").symlink_to(inputdata, target_is_directory=True)
    result.artifact_path("structured/raw").symlink_to(inputdata, target_is_directory=True)
    golden = tmp_path / "golden"
    # When / Then: refused even in update mode, and nothing is written
    with pytest.raises(SnapshotError, match="symlinked"):
        _approve(result, artifact, golden / "out")
    assert not golden.exists()


@pytest.mark.parametrize(
    ("golden_csv", "actual_csv", "line"),
    [
        pytest.param("x,x\n1,2\n", "x,x\n999,2\n", "row 1, column 1 'x': expected '1', got '999'", id="duplicate-header"),
        pytest.param("x,y\n1,2\n", "x,y\n1,2,3\n", "row 1: expected 2 cell(s), got 3", id="extra-cell"),
        pytest.param("x,y\n1,2\n", "x,y\n1\n", "row 1: expected 2 cell(s), got 1", id="missing-cell"),
    ],
)
def test_csv_cells_are_compared_by_position__tc_snap_bv_022(tmp_path: Path, golden_csv: str, actual_csv: str, line: str) -> None:
    """TC-SNAP-BV-022: duplicate headers and rows wider or narrower than the header are compared cell by cell."""
    # Given
    _OUTPUT["csv"] = golden_csv
    _, golden = _approved(tmp_path, "structured/result.csv")
    _OUTPUT["csv"] = actual_csv
    # When
    with pytest.raises(AssertionError) as excinfo:
        _run(tmp_path, "changed").assert_snapshot("structured/result.csv", golden)
    # Then
    assert line in str(excinfo.value)


def test_missing_golden_for_an_empty_directory__tc_snap_bv_023(tmp_path: Path) -> None:
    """TC-SNAP-BV-023: an empty artifact directory without a golden copy fails, and approval creates the baseline."""
    # Given: thumbnail/ is produced empty and has no golden copy
    result = _run(tmp_path)
    assert result.artifact_path("thumbnail").is_dir()
    assert not any(result.artifact_path("thumbnail").iterdir())
    golden = tmp_path / "golden" / "thumbnail"
    # When / Then: the comparison fails naming the approval
    with pytest.raises(AssertionError) as excinfo:
        result.assert_snapshot("thumbnail", golden)
    assert f"golden snapshot {golden} for artifact 'thumbnail' does not exist" in str(excinfo.value)
    assert not golden.exists()
    # When: approving
    _approve(result, "thumbnail", golden)
    # Then: the empty baseline exists, is recorded, and the next comparison passes
    assert golden.is_dir()
    assert not any(golden.iterdir())
    assert [(update.path, update.action) for update in snapshot.recorded_updates()] == [(golden, "created")]
    result.assert_snapshot("thumbnail", golden)
