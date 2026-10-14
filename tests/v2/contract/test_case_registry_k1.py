"""Session K1: the generator's case registry and the static frozen-corpus access.

Ruling #1 made every frozen v1 observation a registered ``OracleCase``; ruling
#2 added per-case observation extras (pending until the freeze ritual through
``observe.PENDING_FREEZE_KEYS``); ruling #3 made a not-yet-frozen snapshot skip
-- never pass -- through ``frozen.require_snapshot``, and ``--check`` report it
as "pending freeze" rather than as an error, both only while
``_generate.ALLOW_PENDING_SNAPSHOTS`` holds.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| registry | every registered case | unique id, stem ``<outcome>[__<variant>]``, inventory derived from it | TC-K1-REG-EP-001 |
| ``_case_record`` | every snapshot frozen before K1 | equals the frozen ``case`` block byte for byte | TC-K1-REG-EP-002 |
| ``case_config`` | overrides / extras / tasksupport | deep-merged v1 Config, extras kept, ``None`` | TC-K1-REG-EP-003 |
| ``require_snapshot`` | frozen snapshot carrying the keys | the parsed payload | TC-K1-REG-EP-004 |
| ``_narrow_pending_keys`` | pending key the frozen file lacks | dropped from the candidate | TC-K1-REG-EP-005 |

Negative / boundary table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``oracle_case`` | unregistered id | ``KeyError`` | TC-K1-REG-EV-006 |
| ``case_config`` | canary without a run root | ``ValueError`` | TC-K1-REG-EV-007 |
| ``require_snapshot`` | snapshot missing, pending allowed | skip ``pending freeze: <path>`` | TC-K1-REG-EV-008 |
| ``require_snapshot`` | snapshot missing, pending off (K1-b) | fail | TC-K1-REG-EV-009 |
| ``require_snapshot`` | pending key missing / non-pending key missing | skip / fail | TC-K1-REG-EV-010 |
| ``_narrow_pending_keys`` | non-pending extra key, pending key present in frozen | both kept (mismatch surfaces) | TC-K1-REG-EV-011 |
| ``_run_check`` | pending only / a real mismatch | exit 0 listing pending / exit 1 | TC-K1-REG-EV-012 |
| ``_snapshot_message`` | file exists, or pending off | the mismatch, not "pending" | TC-K1-REG-EV-013 |
| ``_path_fields`` / ``_config_extras`` | non-dataclass / no config | ``{}`` | TC-K1-REG-BV-014 |
| ``execute_case`` | entry exits 1 / returns a non-str | exit code recorded / ``legacy_return`` null | TC-K1-REG-BV-015 |
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from tests.v2.contract import frozen
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import PENDING_FREEZE_KEYS


def _point_registry_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make snapshot lookups resolve below ``tmp_path`` instead of the real corpus."""
    expected_root = tmp_path / "tests" / "expected" / "v1"
    monkeypatch.setattr(_generate, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(_generate, "EXPECTED_ROOT", expected_root)
    return expected_root


def _write_snapshot(path: Path, observed: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": {}, "case": {}, "observed": observed}), encoding="utf-8")


def test_registry_ids_are_unique_and_derive_the_inventory__tc_k1_reg_ep_001() -> None:
    """TC-K1-REG-EP-001: one id per case; the inventory is the registry."""
    # Given: every registered synthetic and canary case
    cases = (*_generate.ORACLE_CASES, *_generate.CANARY_CASES)

    # When: deriving ids, stems and the declared snapshot inventory
    ids = [case.case_id for case in cases]
    stems = [case.stem for case in _generate.ORACLE_CASES]

    # Then: ids are unique, stems follow the ruling-#1 form, and the
    # inventory functions are exactly the registry's snapshot paths
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z_]+(__[a-z0-9_]+)?", stem) for stem in stems)
    assert _generate.expected_snapshot_paths() == [case.snapshot_path() for case in _generate.ORACLE_CASES]
    assert _generate.canary_snapshot_paths() == [case.snapshot_path() for case in _generate.CANARY_CASES]
    assert all(_generate.oracle_case(case.case_id) is case for case in cases)


def test_case_record_keeps_every_frozen_case_block__tc_k1_reg_ep_002() -> None:
    """TC-K1-REG-EP-002: the registry changes no frozen ``case`` value."""
    # Given: every snapshot that is frozen today
    frozen_cases = [
        case for case in (*_generate.ORACLE_CASES, *_generate.CANARY_CASES) if case.snapshot_path().exists()
    ]
    assert len(frozen_cases) >= 21

    # When / Then: the generated case block equals the frozen one exactly
    for case in frozen_cases:
        payload = json.loads(case.snapshot_path().read_text(encoding="utf-8"))
        assert _generate._case_record(case) == payload["case"], case.case_id  # noqa: SLF001


def test_case_config_merges_overrides_and_extras__tc_k1_reg_ep_003() -> None:
    """TC-K1-REG-EP-003: overrides deep-merge into the oracle Config."""
    # Given: an ignore_errors case, a config-extras case and a tasksupport case
    ignore = _generate.oracle_case("v1/multidatatile/usererr__ignore_errors")
    extras = _generate.oracle_case("v1/invoice/ok__config_extras")
    tasksupport = _generate.oracle_case("v1/invoice/ok__tasksupport_extras")

    # When: resolving their configuration objects
    ignore_config = _generate.case_config(ignore)
    extras_config = _generate.case_config(extras)

    # Then: the override changed only its own leaf
    assert ignore_config.multidata_tile.ignore_errors is True
    assert ignore_config.system == _generate.oracle_config("multidatatile").system
    # And: user extras survive as v1 Config extras
    assert extras_config.model_extra == {"threshold": 0.5, "nested": {"a": 1}}
    # And: a tasksupport case hands the entry no configuration at all
    assert _generate.case_config(tasksupport) is None


def test_require_snapshot_returns_a_frozen_payload__tc_k1_reg_ep_004() -> None:
    """TC-K1-REG-EP-004: a frozen snapshot is returned as parsed."""
    # Given / When: a snapshot frozen before K1
    payload = frozen.require_snapshot("v1/invoice/ok", keys=("exit_code", "output_tree"))

    # Then: it is the file's content
    path = _generate.oracle_case("v1/invoice/ok").snapshot_path()
    assert payload == json.loads(path.read_text(encoding="utf-8"))
    assert frozen.frozen_observed("v1/invoice/ok") == payload["observed"]


def test_narrow_pending_keys_drops_only_missing_pending_keys__tc_k1_reg_ep_005(tmp_path: Path) -> None:
    """TC-K1-REG-EP-005: a not-yet-frozen extra does not fail ``--check``."""
    # Given: a frozen snapshot without the pending extra
    path = tmp_path / "ok.json"
    _write_snapshot(path, {"exit_code": 0})
    pending_key = PENDING_FREEZE_KEYS[0]

    # When: narrowing a candidate carrying the extra
    narrowed = _generate._narrow_pending_keys(path, {"observed": {"exit_code": 0, pending_key: []}})  # noqa: SLF001

    # Then: only the pending extra is gone
    assert narrowed == {"observed": {"exit_code": 0}}


def test_unregistered_case_is_a_key_error__tc_k1_reg_ev_006() -> None:
    """TC-K1-REG-EV-006: a typo cannot silently select another case."""
    with pytest.raises(KeyError):
        _generate.oracle_case("v1/invoice/ok__no_such_variant")


def test_canary_config_needs_its_run_root__tc_k1_reg_ev_007() -> None:
    """TC-K1-REG-EV-007: the canary YAML is read from the assembled run root."""
    case = _generate.oracle_case("canary/invoice/ok")
    with pytest.raises(ValueError, match="canary configuration"):
        _generate.case_config(case)


def test_missing_snapshot_is_pending_while_allowed__tc_k1_reg_ev_008(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K1-REG-EV-008: a registered, unfrozen snapshot skips -- never passes."""
    # Given: an empty corpus and the K1-a pending switch
    _point_registry_at(tmp_path, monkeypatch)
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", True)

    # When / Then: the lookup skips naming the missing path
    with pytest.raises(pytest.skip.Exception, match=r"pending freeze: tests/expected/v1/invoice/plainerr\.json"):
        frozen.require_snapshot("v1/invoice/plainerr")


def test_missing_snapshot_fails_once_pending_is_off__tc_k1_reg_ev_009(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K1-REG-EV-009: after the freeze (K1-b) a missing snapshot is a failure."""
    # Given: an empty corpus with pending snapshots disallowed
    _point_registry_at(tmp_path, monkeypatch)
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", False)

    # When / Then: the lookup fails instead of skipping
    with pytest.raises(pytest.fail.Exception, match="missing frozen snapshot"):
        frozen.require_snapshot("v1/invoice/plainerr")


@pytest.mark.parametrize(
    ("key", "outcome"),
    [
        pytest.param(PENDING_FREEZE_KEYS[0], pytest.skip.Exception, id="pending-key-skips"),
        pytest.param("legacy_return", pytest.fail.Exception, id="frozen-key-fails"),
    ],
)
def test_missing_observed_key_skips_only_when_pending__tc_k1_reg_ev_010(
    key: str,
    outcome: type[BaseException],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K1-REG-EV-010: only a pending extra may be absent from a frozen snapshot."""
    # Given: a frozen snapshot lacking the requested key
    expected_root = _point_registry_at(tmp_path, monkeypatch)
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", True)
    _write_snapshot(expected_root / "invoice" / "ok.json", {"exit_code": 0})

    # When / Then: a pending extra skips, an already-frozen key is a defect
    with pytest.raises(outcome):
        frozen.require_snapshot("v1/invoice/ok", keys=(key,))


def test_narrow_pending_keys_keeps_everything_else__tc_k1_reg_ev_011(tmp_path: Path) -> None:
    """TC-K1-REG-EV-011: a new non-pending key, or a frozen extra, is still compared."""
    # Given: a frozen snapshot that already carries one pending extra
    path = tmp_path / "ok.json"
    pending_key = PENDING_FREEZE_KEYS[0]
    _write_snapshot(path, {"exit_code": 0, pending_key: []})
    candidate = {"observed": {"exit_code": 0, pending_key: ["changed"], "unexpected": 1}}

    # When: narrowing
    narrowed = _generate._narrow_pending_keys(path, candidate)  # noqa: SLF001

    # Then: nothing was dropped, so a comparison sees both differences
    assert narrowed == candidate


@pytest.mark.parametrize(
    ("messages", "exit_code"),
    [
        pytest.param([f"{_generate.PENDING_FREEZE_PREFIX}tests/x.json"], 0, id="pending-only"),
        pytest.param([f"{_generate.PENDING_FREEZE_PREFIX}tests/x.json", "invoice/ok: snapshot differs: ok.json"], 1, id="mismatch"),
    ],
)
def test_check_mode_separates_pending_from_mismatch__tc_k1_reg_ev_012(
    messages: list[str],
    exit_code: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K1-REG-EV-012: ``--check`` lists pending snapshots; only a mismatch fails."""
    # Given: clean provenance, no input drift, and the given comparison messages
    monkeypatch.setattr(_generate, "source_revision_errors", lambda **_: [])
    monkeypatch.setattr(_generate, "source_revision_warnings", lambda **_: [])
    monkeypatch.setattr(_generate, "check_static_input_drift", lambda: ([], "note"))
    monkeypatch.setattr(_generate, "freeze_expected_outputs", lambda *, check: list(messages))

    # When: running check mode
    result = _generate._run_check()  # noqa: SLF001

    # Then: pending snapshots are listed on stdout and never fail the gate
    captured = capsys.readouterr()
    assert result == exit_code
    assert "1 registered snapshot(s) await the freeze ritual" in captured.out
    assert ("snapshot differs" in captured.err) is (exit_code == 1)


def test_snapshot_message_is_a_mismatch_unless_pending__tc_k1_reg_ev_013(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K1-REG-EV-013: an existing file, or pending off, reports the mismatch itself."""
    # Given: an existing and a missing snapshot below the repository root
    monkeypatch.setattr(_generate, "REPOSITORY_ROOT", tmp_path)
    existing = tmp_path / "ok.json"
    existing.write_text("{}", encoding="utf-8")
    missing = tmp_path / "pending.json"

    # When / Then: only a missing file while pending is allowed is "pending"
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", True)
    assert _generate._snapshot_message(existing, "invoice/ok", "differs") == "invoice/ok: differs"  # noqa: SLF001
    assert _generate._snapshot_message(missing, "invoice/x", "missing") == (  # noqa: SLF001
        f"{_generate.PENDING_FREEZE_PREFIX}pending.json"
    )
    monkeypatch.setattr(_generate, "ALLOW_PENDING_SNAPSHOTS", False)
    assert _generate._snapshot_message(missing, "invoice/x", "missing") == "invoice/x: missing"  # noqa: SLF001


def test_recorders_tolerate_foreign_arguments__tc_k1_reg_bv_014() -> None:
    """TC-K1-REG-BV-014: non-dataclass arguments and no config record nothing."""
    assert _generate._path_fields(object()) == {}  # noqa: SLF001
    assert _generate._config_extras(object()) == {}  # noqa: SLF001


def test_execute_case_records_exit_code_and_string_returns_only__tc_k1_reg_bv_015(tmp_path: Path) -> None:
    """TC-K1-REG-BV-015: ``sys.exit`` and a non-``str`` return are observed like v1's."""
    # Given: a materialized invoice case and two stub entry points
    case = _generate.oracle_case("v1/invoice/ok")
    exiting_root = tmp_path / "exiting"
    returning_root = tmp_path / "returning"
    for root in (exiting_root, returning_root):
        _generate.materialize_case(case, root)

    def _exiting_entry(**_: Any) -> Any:
        raise SystemExit(1)

    def _object_entry(**_: Any) -> Any:
        return object()

    # When: each runs through the shared observation path
    exited = _generate.execute_case(case, exiting_root, _exiting_entry)
    returned = _generate.execute_case(case, returning_root, _object_entry)

    # Then: the exit status is recorded and only a legacy JSON string is a return
    assert exited["exit_code"] == 1
    assert exited["legacy_return"] is None
    assert returned["exit_code"] == 0
    assert returned["legacy_return"] is None
    assert returned["callback_count"] == 0
