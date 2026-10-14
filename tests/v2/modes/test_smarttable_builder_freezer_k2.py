"""Session K2-0: the SmartTable builder freezer (``_freeze.py``) and its static access.

Ruling #1 froze v1's ``SmartTableInvoiceInitializer`` as a unit-level oracle;
ruling #4 put its snapshots under the K1 pending switch. These cells pin the
freezer's own contract with a stubbed observation -- no cell here runs v1.
Session K2-0b closed the window after the freeze ritual (3424839b): the
committed corpus itself must be complete (TC-K2-0-FRZ-EV-015).

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| registry | every registered case | unique ids, inventory derived, 47 ``i6c`` + 24 ``k2`` | TC-K2-0-FRZ-EP-001 |
| registry | the R3 port | every original TC id but TC-BV-002 is a ``k2`` case | TC-K2-0-FRZ-EP-002 |
| ``observe_case`` | multi-step case with a source mutation | the mutation lands between the steps; dist per step | TC-K2-0-FRZ-EP-003 |
| ``freeze`` | write mode | every snapshot written with the stamped provenance | TC-K2-0-FRZ-EP-004 |
| ``require_builder_snapshot`` | frozen snapshot of the same inputs | the parsed payload | TC-K2-0-FRZ-EP-005 |

Negative / boundary table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``require_write_tree_hygiene`` | a code path is dirty | ``RuntimeError`` | TC-K2-0-FRZ-EV-006 |
| ``require_write_tree_hygiene`` | only snapshot JSON dirty (builder or K1) | accepted | TC-K2-0-FRZ-BV-007 |
| ``freeze(check=True)`` | missing / pending allowed, pending off, differing | pending / mismatch / mismatch | TC-K2-0-FRZ-EV-008 |
| ``run_check`` | pending only / a mismatch / unauditable provenance | exit 0 / 1 / 1 | TC-K2-0-FRZ-EV-009 |
| ``require_builder_snapshot`` | missing (pending, off) / other inputs | skip / fail / fail | TC-K2-0-FRZ-EV-010 |
| ``observe_v1`` | the worker exits non-zero | ``RuntimeError`` | TC-K2-0-FRZ-EV-011 |
| ``jsonable_row_data`` / ``normalize_observation`` | NaN, None, non-scalar; root and resolved root; pydantic URL version | sentinel / null / repr; ``<ROOT>``; ``<ver>`` | TC-K2-0-FRZ-BV-012 |
| ``tests/v2`` imports | any module but ``_freeze.py`` | no ``rdetoolkit.processing`` import | TC-K2-0-FRZ-EV-013 |
| registry inputs | owner identities | synthetic 56-digit ids only | TC-K2-0-FRZ-EV-014 |
| committed corpus (K2-0b) | after the freeze ritual | pending off; all 71 snapshots frozen, no orphan, same inputs, one clean writer | TC-K2-0-FRZ-EV-015 |
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.v2.contract import frozen
from tests.v2.contract.fixtures import _generate
from tests.v2.modes.fixtures.smarttable_builder import _freeze

_TESTS_V2 = Path(__file__).resolve().parents[1]

#: The original TC ids of the two R3 files, spelled out (not derived).
_R3_IDS = frozenset(
    {
        *(f"TC-EP-{number:03d}" for number in range(1, 14)),
        *(f"TC-BV-{number:03d}" for number in range(1, 7)),
        *(f"TC-EP-429-{number:03d}" for number in (1, 2, 5, 6, 7, 8)),
    },
)


def _point_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Resolve builder snapshots below ``tmp_path`` instead of the real corpus."""
    fixture_root = tmp_path / "tests" / "fixtures" / "smarttable_builder"
    monkeypatch.setattr(_freeze, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(_freeze, "FIXTURE_ROOT", fixture_root)
    return fixture_root


def _stub_observation(case: _freeze.BuilderCase) -> dict[str, Any]:
    return {"steps": [{"row_data": None, "invoice": {"id": case.case_id}, "metadata": None}], "source_invoice": None}


def _write_snapshot(case: _freeze.BuilderCase, *, observed: Any, commit: str = "abcdef012345") -> None:
    _generate.write_json_snapshot(
        case.snapshot_path(),
        {"source": {"oracle": _freeze.ORACLE, "commit": commit}, "case": _freeze.case_record(case), "observed": observed},
    )


def test_registry_ids_are_unique_and_derive_the_inventory__tc_k2_0_frz_ep_001() -> None:
    """TC-K2-0-FRZ-EP-001: one snapshot per registered case, per family."""
    # Given: the registry
    cases = _freeze.BUILDER_CASES

    # When: deriving ids and the snapshot inventory
    ids = [case.case_id for case in cases]

    # Then: ids are unique, the inventory follows them, and the family sizes are declared
    assert len(ids) == len(set(ids))
    assert _freeze.snapshot_paths() == [case.snapshot_path() for case in cases]
    assert all(_freeze.builder_case(case_id).case_id == case_id for case_id in ids)
    assert sum(case.family == "i6c" for case in cases) == 47
    assert sum(case.family == "k2" for case in cases) == 24
    assert {case.family for case in cases} == set(_freeze.FAMILIES)
    with pytest.raises(KeyError):
        _freeze.builder_case("i6c/TC-UNREGISTERED")


def test_r3_port_registers_every_original_id__tc_k2_0_frz_ep_002() -> None:
    """TC-K2-0-FRZ-EP-002: all 25 R3 ids are ported; only TC-BV-002 has no frozen case."""
    # Given: the k2 family
    registered = {case.test_id for case in _freeze.BUILDER_CASES if case.family == "k2"}

    # Then: exactly the original ids minus the v2-only re-expression
    assert registered == _R3_IDS - {"TC-BV-002"}
    assert len(_R3_IDS) == 25


def test_multi_step_case_mutates_the_source_between_steps__tc_k2_0_frz_ep_003(tmp_path: Path) -> None:
    """TC-K2-0-FRZ-EP-003: steps run in order, each with its own row CSV and destination."""
    # Given: TC-EP-001 (row 0 into the source, ``sample.ownerId`` popped, row 1 into the tile)
    case = _freeze.builder_case("k2/TC-EP-001")
    seen: list[tuple[Path, Path, dict[str, Any]]] = []

    def _recording_runner(paths: _freeze.StepPaths) -> dict[str, Any] | None:
        assert paths.rowfile is not None
        source = json.loads(paths.invoice_org.read_text(encoding="utf-8"))
        seen.append((paths.rowfile, paths.dist_path, source["sample"]))
        return {"cell": float("nan")}

    # When: observing it with a recording runner
    observed = _freeze.observe_case(case, tmp_path, _recording_runner)

    # Then: step 0 targets the source, step 1 the tile, and the pop happened in between
    assert [rowfile.name for rowfile, _, _ in seen] == ["fsmarttable_case_0000.csv", "fsmarttable_case_0001.csv"]
    assert seen[0][1] == tmp_path / "invoice" / "invoice.json"
    assert seen[1][1] == tmp_path / "divided" / "0001" / "invoice" / "invoice.json"
    assert "ownerId" in seen[0][2]
    assert "ownerId" not in seen[1][2]
    assert [step["row_data"] for step in observed["steps"]] == [{"cell": _freeze.NAN_CELL}] * 2


def test_write_mode_writes_every_snapshot_with_provenance__tc_k2_0_frz_ep_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K2-0-FRZ-EP-004: write mode owns the whole inventory and stamps the revision."""
    # Given: the corpus redirected to tmp_path and a stamped revision
    _point_at(tmp_path, monkeypatch)
    monkeypatch.setattr(_generate, "_git_revision", lambda: "0123456789ab")

    # When: freezing with a stubbed observation
    messages = _freeze.freeze(check=False, observe=_stub_observation)

    # Then: every registered snapshot exists with oracle, revision, case record and observation
    assert messages == []
    for case in _freeze.BUILDER_CASES:
        payload = json.loads(case.snapshot_path().read_text(encoding="utf-8"))
        assert payload["source"] == {"oracle": _freeze.ORACLE, "commit": "0123456789ab"}
        assert payload["case"] == _freeze.case_record(case)
        assert payload["observed"] == _stub_observation(case)


def test_require_builder_snapshot_returns_a_frozen_payload__tc_k2_0_frz_ep_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K2-0-FRZ-EP-005: a snapshot of the registered inputs is returned as is."""
    # Given: one snapshot frozen from the registered inputs
    _point_at(tmp_path, monkeypatch)
    case = _freeze.builder_case("i6c/TC-I6-C-EP-001")
    _write_snapshot(case, observed={"steps": []})

    # When / Then: the payload comes back unchanged
    payload = frozen.require_builder_snapshot(case.case_id)
    assert payload["observed"] == {"steps": []}
    assert payload["case"] == _freeze.case_record(case)


def test_write_hygiene_rejects_code_dirtiness__tc_k2_0_frz_ev_006() -> None:
    """TC-K2-0-FRZ-EV-006: a dirty code path -- including the freezer itself -- refuses a freeze."""
    # Given: a source file, the freezer module and a builder JSON dirty together
    builder_root = Path("tests/v2/modes/fixtures/smarttable_builder")
    dirty = [
        Path("src/rdetoolkit/modes/smarttable.py"),
        builder_root / "_freeze.py",
        builder_root / "i6c" / "TC-I6-C-EP-001.json",
    ]

    # When / Then: the gate names both code paths and no snapshot
    with pytest.raises(RuntimeError, match="clean code tree") as error:
        _freeze.require_write_tree_hygiene(dirty)
    assert "src/rdetoolkit/modes/smarttable.py" in str(error.value)
    assert "_freeze.py" in str(error.value)
    assert "TC-I6-C-EP-001.json" not in str(error.value)


def test_write_hygiene_allows_only_snapshot_dirtiness__tc_k2_0_frz_bv_007() -> None:
    """TC-K2-0-FRZ-BV-007: builder snapshots and K1 snapshots may be dirty (one ritual)."""
    # Given: only snapshot JSON files are dirty
    dirty = [
        Path("tests/v2/modes/fixtures/smarttable_builder/k2/TC-EP-001.json"),
        Path("tests/v2/contract/fixtures/expected/v1/smarttable/ok__csv_table__save_table_file.json"),
        Path("tests/v2/contract/fixtures/expected/canary/invoice/ok.json"),
    ]

    # When / Then: the gate accepts the tree
    _freeze.require_write_tree_hygiene(dirty)


def test_check_mode_separates_pending_from_mismatch__tc_k2_0_frz_ev_008(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K2-0-FRZ-EV-008: missing is pending only while allowed; a difference never is."""
    # Given: one snapshot frozen with a different observation, all others missing
    _point_at(tmp_path, monkeypatch)
    differing = _freeze.BUILDER_CASES[0]
    _write_snapshot(differing, observed={"steps": "other"})

    # When: checking with the pending switch on and off
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", True)
    allowed = _freeze.freeze(check=True, observe=_stub_observation)
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", False)
    strict = _freeze.freeze(check=True, observe=_stub_observation)

    # Then: the difference is a mismatch both times; the missing ones are pending only when allowed
    assert f"{differing.case_id}: snapshot differs: {differing.stem}.json" in allowed
    pending = [message for message in allowed if message.startswith(_freeze.PENDING_FREEZE_PREFIX)]
    assert len(pending) == len(_freeze.BUILDER_CASES) - 1
    assert not any(message.startswith(_freeze.PENDING_FREEZE_PREFIX) for message in strict)
    assert len(strict) == len(_freeze.BUILDER_CASES)


def test_run_check_exit_codes__tc_k2_0_frz_ev_009(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K2-0-FRZ-EV-009: pending only -> 0 with a listing; a mismatch or bad provenance -> 1."""
    # Given: an empty corpus with the pending switch on
    _point_at(tmp_path, monkeypatch)
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", True)
    monkeypatch.setattr(_generate, "_git_revision", lambda: "0123456789ab")

    # When / Then: everything pending is exit 0 with the count and the list
    assert _freeze.run_check(observe=_stub_observation) == 0
    out = capsys.readouterr().out
    assert f"{len(_freeze.BUILDER_CASES)} registered snapshot(s) await the freeze ritual:" in out
    assert "tests/fixtures/smarttable_builder/k2/TC-EP-001.json" in out

    # When / Then: one differing snapshot is exit 1
    first = _freeze.BUILDER_CASES[0]
    _write_snapshot(first, observed={"steps": "other"})
    assert _freeze.run_check(observe=_stub_observation) == 1

    # When / Then: an unauditable recorded commit is exit 1 before any observation
    _write_snapshot(first, observed=_stub_observation(first), commit="0123456789ab-dirty")
    assert _freeze.run_check(observe=lambda case: pytest.fail("observed despite bad provenance")) == 1
    assert "unauditable" in capsys.readouterr().err


def test_require_builder_snapshot_pending_and_failures__tc_k2_0_frz_ev_010(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K2-0-FRZ-EV-010: skip while pending, fail when strict or when the inputs moved."""
    # Given: an empty corpus
    _point_at(tmp_path, monkeypatch)
    case = _freeze.builder_case("i6c/TC-I6-C-EP-001")

    # When / Then: missing + pending allowed skips with the path
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", True)
    with pytest.raises(pytest.skip.Exception, match=r"pending freeze: tests/fixtures/smarttable_builder/i6c/TC-I6-C-EP-001\.json"):
        frozen.require_builder_snapshot(case.case_id)

    # When / Then: missing + pending off fails
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", False)
    with pytest.raises(pytest.fail.Exception, match="missing frozen builder snapshot"):
        frozen.require_builder_snapshot(case.case_id)

    # When / Then: a snapshot observed from other inputs fails even while pending is allowed
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", True)
    record = _freeze.case_record(case)
    record["steps"][0]["csv_text"] = "basic/dataName\nother\n"
    _generate.write_json_snapshot(
        case.snapshot_path(),
        {"source": {"oracle": _freeze.ORACLE, "commit": "abc"}, "case": record, "observed": {}},
    )
    with pytest.raises(pytest.fail.Exception, match="observed from other inputs"):
        frozen.require_builder_snapshot(case.case_id)


def test_worker_failure_is_a_runtime_error__tc_k2_0_frz_ev_011(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K2-0-FRZ-EV-011: a worker that leaves no observation is an error, not an empty value."""
    # Given: a worker process that exits 1 without writing anything
    def _failed(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(_freeze.subprocess, "run", _failed)

    # When / Then: the observation raises with the case id and the stderr tail
    with pytest.raises(RuntimeError, match=r"v1 oracle worker failed for i6c/TC-I6-C-EP-001: exit=1; stderr=boom"):
        _freeze.observe_v1(_freeze.builder_case("i6c/TC-I6-C-EP-001"))


def test_row_data_and_root_normalization__tc_k2_0_frz_bv_012(tmp_path: Path) -> None:
    """TC-K2-0-FRZ-BV-012: NaN stays distinguishable from None; both root spellings normalize."""
    # Given: a row with a NaN, a None, a string and a non-scalar cell
    row = {"nan": float("nan"), "none": None, "text": "x", "other": object}

    # When: recording it, and normalizing a message quoting the root two ways
    recorded = _freeze.jsonable_row_data(row)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "real", target_is_directory=True)
    (tmp_path / "real").mkdir()
    message = f"{link}/a and {link.resolve()}/b"

    # Then: NaN -> sentinel, None -> null, other -> repr; both spellings -> <ROOT>
    assert recorded is not None
    assert recorded["nan"] == _freeze.NAN_CELL
    assert recorded["none"] is None
    assert recorded["text"] == "x"
    assert recorded["other"] == {"repr": repr(object)}
    assert _freeze.jsonable_row_data(None) is None
    assert _freeze.normalize_observation({"m": [message]}, link) == {"m": ["<ROOT>/a and <ROOT>/b"]}
    # And: pydantic's own version in an error URL is environment, not contract
    for version in ("2.12", "2.14", "10.0"):
        url = f"visit https://errors.pydantic.dev/{version}/v/missing"
        assert _freeze.normalize_observation(url, link) == "visit https://errors.pydantic.dev/<ver>/v/missing"


def _imports_processing(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("rdetoolkit.processing"):
            return True
        if isinstance(node, ast.Import) and any(alias.name.startswith("rdetoolkit.processing") for alias in node.names):
            return True
    return False


def test_only_the_freezer_imports_v1_processing__tc_k2_0_frz_ev_013() -> None:
    """TC-K2-0-FRZ-EV-013: ``rdetoolkit.processing`` is imported by ``_freeze.py`` alone.

    Docstrings may still name the module; only real ``import`` statements count.
    """
    # Given: every Python module below tests/v2
    modules = sorted(_TESTS_V2.rglob("*.py"))

    # When: collecting the ones that import rdetoolkit.processing
    importers = [path.relative_to(_TESTS_V2).as_posix() for path in modules if _imports_processing(path)]

    # Then: the freezer is the only one
    assert importers == ["modes/fixtures/smarttable_builder/_freeze.py"]


def test_registry_owner_identities_are_synthetic__tc_k2_0_frz_ev_014() -> None:
    """TC-K2-0-FRZ-EV-014: no real owner hash can reach the public builder corpus."""
    # Given: every JSON input and row CSV of every registered case
    values: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"dataOwnerId", "ownerId"} and isinstance(item, str) and item:
                    values.append(item)
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    for case in _freeze.BUILDER_CASES:
        collect([case.invoice, case.metadata, case.metadata_def])
        for step in case.steps:
            for line in (step.csv_text or "").splitlines()[1:]:
                values.extend(re.findall(r"\b[0-9a-f]{56}\b", line))

    # Then: every owner identity is a zero-padded synthetic id
    assert values
    assert [value for value in values if re.fullmatch(r"0{55}[0-9]", value) is None] == []


def test_the_builder_freeze_window_is_closed__tc_k2_0_frz_ev_015() -> None:
    """TC-K2-0-FRZ-EV-015: after the K2-0 freeze every builder snapshot is committed.

    Session K2-0b turned the single pending switch off: a missing builder
    snapshot is a failure, never a skip. The committed corpus is exactly the
    registry -- 47 ``i6c`` + 24 ``k2`` files, no orphan -- each observed from
    the registered inputs by v1's initializer at one clean revision.
    """
    # Given: the registry and the committed builder corpus
    registered = _freeze.snapshot_paths()
    on_disk = sorted(_freeze.FIXTURE_ROOT.rglob("*.json"))

    # Then: the window is closed and every registered snapshot is a frozen file
    assert _generate.ALLOW_PENDING_SNAPSHOTS is False
    assert len(registered) == 71
    assert [path.relative_to(_freeze.REPOSITORY_ROOT).as_posix() for path in registered if not path.is_file()] == []
    # And: nothing on disk is unregistered
    assert set(on_disk) == set(registered)
    # And: each snapshot records the registered inputs and an auditable writer
    commits: set[str] = set()
    for case in _freeze.BUILDER_CASES:
        payload = json.loads(case.snapshot_path().read_text(encoding="utf-8"))
        assert payload["case"] == _freeze.case_record(case), case.case_id
        assert payload["source"]["oracle"] == _freeze.ORACLE
        commits.add(payload["source"]["commit"])
    assert len(commits) == 1
    assert _freeze.provenance_errors() == []
