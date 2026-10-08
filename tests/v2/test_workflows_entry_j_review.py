"""PR #542 review response: the public v1 callback entry vs live ``_run_legacy``.

Session J-REVIEW (contracts.md §J-REVIEW) answers the interrogate review of
2026-10-05. Every scenario the review reproduced is re-run here against a
**live** ``workflows._run_legacy`` oracle, in-process, over the same static
contract inputs (``tests/v2/contract/fixtures/_generate.py``), so a difference
between the v1 API and the unified Runner shows up as an unequal pair of
observations rather than as a hand-written expectation.

EP / BV table:

| TC-ID              | Class    | Input                                                         | Expected                                         |
|--------------------|----------|---------------------------------------------------------------|--------------------------------------------------|
| TC-JREV-P1-001     | EP valid | ``RdeConfig.custom`` scalar + nested                          | restored as v1 ``Config`` extras, deep-copied     |
| TC-JREV-P1-002     | EP inval | custom keys named like v1 top-level fields                    | not restored; structured v1 fields win            |
| TC-JREV-P1-003     | BV empty | empty ``custom`` / ``None`` config                            | ``model_extra == {}``                             |
| TC-JREV-P1-004     | EP valid | explicit v1 ``Config(threshold=0.5)`` through ``run()``       | callback sees ``0.5`` exactly as ``_run_legacy``  |
| TC-JREV-P1-005     | EP valid | tasksupport ``rdeconfig.yaml`` with top-level ``threshold``   | callback sees ``0.5`` exactly as ``_run_legacy``  |
| TC-JREV-P2-001     | EP valid | MDT, ``ignore_errors=True``, every tile fails, public entry   | statuses all failed, exit 0, no job.failed = v1   |
| TC-JREV-P2-002     | EP valid | same, ``Runner.run(LegacyCallbackTarget)``                    | ``report.status == "partial"``                    |
| TC-JREV-P2-003     | EP inval | same, ``ignore_errors=False`` (fail-fast)                     | ``SystemExit(1)`` + job.failed = v1               |
| TC-JREV-P2-004     | EP inval | same continue config, ``FlowTarget``                          | ``failed`` + job.failed (Design §7.2 unchanged)   |
| TC-JREV-P2-005..7  | BV       | ``_run_status`` with the legacy flag at 0 / some / fail-fast  | partial / partial / failed                        |
| TC-JREV-P2-008     | EP valid | MDT, ``ignore_errors=True``, middle of three tiles fails      | full statuses JSON (mixed shapes) = v1            |
| TC-JREV-P2-009..12 | EP/BV   | failed-entry shape: 5 labels, no error, unknown mode, target  | v1 ``_create_error_status`` shape                 |
| TC-JREV-P3-001     | EP valid | alias-flat root, public entry                                 | callback runs, no ``<root>/data``, log in root    |
| TC-JREV-P3-002     | BV       | the CWD itself is named ``data``                              | log in ``<cwd>/logs``, no ``data/data``           |
| TC-JREV-P3-003     | EP inval | alias-flat root with ``StorageDir`` sabotaged                 | ``StorageDir`` never consulted                    |
| TC-JREV-P3-004     | EP valid | standard layout with ``StorageDir`` redirected (v1 seam)      | the redirect is honoured                          |
| TC-JREV-F1 (×4)    | EP inval | non-MDT, ``ignore_errors=True``, every tile fails             | exit 1 / job.failed / 1 call = ``_run_legacy``    |
| TC-JREV-F2 (×3)    | EP inval | non-MDT ≥2 tiles, ``ignore_errors=True``, tile 0 fails        | v1 stops at tile 0: exit 1, 1 call = v1           |
| TC-JREV-F1-005..7  | EP/BV    | planner policy: callback × mode × configured policy           | continue only for callback + MDT; flow unchanged  |
| TC-JREV-F3-001     | EP inval | callback succeeds, post-invoke stage fails                    | failed entry target = raw-file list               |
| TC-JREV-C-001      | EP inval | malformed tasksupport YAML, standard layout                   | job.failed 999 text and exit 1 = ``_run_legacy``  |
| TC-JREV-C-002      | EP inval | malformed tasksupport YAML, alias-flat root                   | job.failed under the data root, no ``data/``      |
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from rdetoolkit import workflows
from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.compat.v1.callback import to_legacy_config
from rdetoolkit.core.flow import flow
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.config import Config
from rdetoolkit.runner.lifecycle import Runner, _run_status
from rdetoolkit.types import IterationInfo, RdeConfig
from tests.v2.contract.fixtures import _generate

#: v1 ``handle_generic_error``'s fixed ``job.failed`` text (``errors.py``).
_V1_GENERIC_JOB_FAILED = "ErrorCode=999\nErrorMessage=Error: Please check the logs and code, then try again.\n"

#: The review's all-tiles-failed callback error (P2 reproduction).
_ALL_FAILED_MESSAGE = "all failed"


def _invoke(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: Callable[[Any, Any], Any],
    callback: Any,
    config: Any,
) -> tuple[Any, int]:
    """Run one entry point with ``root`` as the CWD and capture its exit status.

    Both v1 and the unified entry read their inputs from the CWD and report a
    failure through ``sys.exit(1)``, so the pair is observed identically.
    """
    monkeypatch.chdir(root)
    try:
        return entry(callback, config), 0
    except SystemExit as error:
        return None, int(error.code or 0)


def _legacy_entry(callback: Any, config: Any) -> Any:
    return workflows._run_legacy(callback, config)  # noqa: SLF001 -- the live v1 oracle


def _public_entry(callback: Any, config: Any) -> Any:
    return workflows.run(custom_dataset_function=callback, config=config)


def _statuses(result: Any, root: Path) -> Any:
    """Normalize a legacy JSON payload exactly as the contract observations do."""
    if result is None:
        return None
    return _generate.normalize_snapshot(json.loads(result), roots=(root,))


def _job_failed(root: Path) -> str | None:
    path = root / "data" / "job.failed"
    return path.read_text(encoding="utf-8") if path.exists() else None


def _runner(root: Path) -> Runner:
    """Build the Runner exactly as ``workflows._run_callback_entry`` does."""
    return Runner(root=root, inputdata_path=root / "data" / "inputdata", unpacked_dir_path=root / "data" / "temp")


def _config_with_extras(mode: str, *, ignore_errors: bool = False, **extras: Any) -> Config:
    """Return the oracle v1 ``Config`` carrying user-defined top-level fields."""
    base = _generate.oracle_config(mode, ignore_errors=ignore_errors)
    return Config(**base.model_dump(), **extras)


class _ThresholdProbe:
    """v1 callback recording what ``srcpaths.config`` exposes for custom fields."""

    def __init__(self) -> None:
        self.seen: list[tuple[Any, Any]] = []

    def __call__(self, srcpaths: Any, resource_paths: Any) -> None:
        del resource_paths
        self.seen.append(
            (
                getattr(srcpaths.config, "threshold", "MISSING"),
                getattr(srcpaths.config, "nested", "MISSING"),
            ),
        )


def _all_tiles_fail(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths
    raise StructuredError(_ALL_FAILED_MESSAGE, ecode=999)


# ---------------------------------------------------------------------------
# P1 -- RdeConfig.custom survives the trip back to the v1 Config
# ---------------------------------------------------------------------------


class TestToLegacyConfigRestoresCustom:
    """TC-JREV-P1-001..003: ``to_legacy_config`` restores ``custom`` as v1 extras."""

    def test_custom_keys_become_v1_extra_fields__tc_jrev_p1_001(self) -> None:
        """TC-JREV-P1-001: custom keys become v1 extra fields."""
        # Given: a canonical config carrying a scalar and a nested custom key
        nested = {"a": 1}
        config = RdeConfig(custom={"threshold": 0.5, "nested": nested})

        # When: projecting it back onto the v1 Config contract
        legacy = to_legacy_config(config)

        # Then: both keys are ordinary v1 extra fields, visible as attributes
        assert legacy.threshold == 0.5  # type: ignore[attr-defined]
        assert legacy.nested == {"a": 1}  # type: ignore[attr-defined]
        assert legacy.model_extra == {"threshold": 0.5, "nested": {"a": 1}}
        # And: model_dump carries them top-level, as v1 Config(threshold=...) did
        dumped = legacy.model_dump()
        assert dumped["threshold"] == 0.5
        assert dumped["nested"] == {"a": 1}

        # And: the projection is a deep copy -- a callback mutating its config
        # cannot reach back into the run's effective configuration
        legacy.nested["a"] = 2  # type: ignore[attr-defined]
        assert config.custom["nested"] == {"a": 1}

    @pytest.mark.parametrize("colliding", ["system", "multidata_tile", "smarttable", "traceback"])
    def test_custom_keys_colliding_with_v1_fields_are_not_restored__tc_jrev_p1_002(
        self,
        colliding: str,
    ) -> None:
        """TC-JREV-P1-002: custom keys colliding with v1 fields are not restored."""
        # Given: a custom key spelled like a v1 top-level field
        config = RdeConfig(
            system={"extended_mode": "MultiDataTile"},
            execution={"on_iteration_error": "continue"},
            custom={colliding: {"bogus": True}, "threshold": 1},
        )

        # When: projecting it back
        legacy = to_legacy_config(config)

        # Then: the structured v1 field wins and the colliding key is dropped
        assert legacy.model_extra == {"threshold": 1}
        assert legacy.system.extended_mode == "MultiDataTile"
        assert legacy.multidata_tile is not None
        assert legacy.multidata_tile.ignore_errors is True
        assert legacy.traceback is None

    @pytest.mark.parametrize("config", [RdeConfig(), None], ids=["empty-custom", "none"])
    def test_no_custom_keys_means_no_extras__tc_jrev_p1_003(self, config: RdeConfig | None) -> None:
        """TC-JREV-P1-003: no custom keys means no extras."""
        # Given / When: a config with nothing to restore
        legacy = to_legacy_config(config)

        # Then: no extra field appears
        assert legacy.model_extra == {}


class TestCustomConfigRoundTripMatchesLegacy:
    """TC-JREV-P1-004/005: the review's P1 reproduction against live ``_run_legacy``."""

    def test_explicit_v1_config_custom_fields_reach_the_callback__tc_jrev_p1_004(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P1-004: explicit v1 config custom fields reach the callback."""
        # Given: the same invoice input and an explicit v1 Config with extras
        observations = {}
        for side, entry in (("legacy", _legacy_entry), ("public", _public_entry)):
            root = tmp_path / side
            _generate.materialize_sut_case("invoice", root)
            probe = _ThresholdProbe()

            # When: each entry point runs it
            result, exit_code = _invoke(
                root,
                monkeypatch,
                entry,
                probe,
                _config_with_extras("invoice", threshold=0.5, nested={"a": 1}),
            )
            observations[side] = (probe.seen, exit_code, _statuses(result, root))

        # Then: the callback saw the user's own fields, as v1 delivered them
        assert observations["legacy"][0] == [(0.5, {"a": 1})]
        assert observations["public"] == observations["legacy"]

    def test_tasksupport_custom_fields_reach_the_callback__tc_jrev_p1_005(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P1-005: tasksupport custom fields reach the callback."""
        # Given: a tasksupport rdeconfig.yaml with top-level custom keys
        observations = {}
        for side, entry in (("legacy", _legacy_entry), ("public", _public_entry)):
            root = tmp_path / side
            _generate.materialize_sut_case("invoice", root)
            (root / "data" / "tasksupport" / "rdeconfig.yaml").write_text(
                yaml.safe_dump({"system": {"save_raw": True}, "threshold": 0.5, "nested": {"a": 1}}),
                encoding="utf-8",
            )
            probe = _ThresholdProbe()

            # When: each entry point runs with config=None
            result, exit_code = _invoke(root, monkeypatch, entry, probe, None)
            observations[side] = (probe.seen, exit_code, _statuses(result, root))

        # Then: both delivered the file's custom keys to the callback
        assert observations["legacy"][0] == [(0.5, {"a": 1})]
        assert observations["public"] == observations["legacy"]


# ---------------------------------------------------------------------------
# P2 -- ignore_errors=True with every tile failing (contracts.md §J-REVIEW D9)
# ---------------------------------------------------------------------------


class TestAllTilesFailedUnderIgnoreErrors:
    """TC-JREV-P2-001..004: v1 API parity for the callback, §7.2 for the flow."""

    def test_public_entry_matches_legacy_when_every_tile_fails__tc_jrev_p2_001(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P2-001: public entry matches legacy when every tile fails."""
        # Given: the two-tile MultiDataTile family under ignore_errors=True
        observations = {}
        for side, entry in (("legacy", _legacy_entry), ("public", _public_entry)):
            root = tmp_path / side
            _generate.materialize_sut_case("multidatatile", root)

            # When: every callback raises StructuredError("all failed", 999)
            result, exit_code = _invoke(
                root,
                monkeypatch,
                entry,
                _all_tiles_fail,
                _generate.oracle_config("multidatatile", ignore_errors=True),
            )
            observations[side] = {
                "exit_code": exit_code,
                "statuses": _statuses(result, root),
                "job_failed": _job_failed(root),
            }

        # Then: v1 returned every failed status normally and wrote no marker
        legacy = observations["legacy"]
        assert legacy["exit_code"] == 0
        assert legacy["job_failed"] is None
        assert [status["status"] for status in legacy["statuses"]["statuses"]] == ["failed", "failed"]
        # And: the unified entry point is indistinguishable from it
        assert observations["public"] == legacy

    def test_public_entry_matches_legacy_on_a_mixed_partial_run__tc_jrev_p2_008(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The success and failed entry shapes side by side, against the oracle."""
        # Given: the MultiDataTile family grown to three tiles, ignore_errors=True
        observations = {}
        for side, entry in (("legacy", _legacy_entry), ("public", _public_entry)):
            root = tmp_path / side
            _generate.materialize_sut_case("multidatatile", root)
            (root / "data" / "inputdata" / "tile_02.txt").write_text("third tile\n", encoding="utf-8")
            calls: list[int] = []

            def _middle_tile_fails(srcpaths: Any, resource_paths: Any, calls: list[int] = calls) -> None:
                del srcpaths, resource_paths
                calls.append(len(calls))
                if len(calls) == 2:
                    raise StructuredError(_ALL_FAILED_MESSAGE, ecode=777)

            # When: only the middle tile fails
            result, exit_code = _invoke(
                root,
                monkeypatch,
                entry,
                _middle_tile_fails,
                _generate.oracle_config("multidatatile", ignore_errors=True),
            )
            observations[side] = {
                "exit_code": exit_code,
                "statuses": _statuses(result, root),
                "job_failed": _job_failed(root),
                "calls": list(calls),
            }

        # Then: v1 returned success / failed / success and exited normally
        legacy = observations["legacy"]
        assert legacy["exit_code"] == 0
        assert legacy["job_failed"] is None
        assert [status["status"] for status in legacy["statuses"]["statuses"]] == ["success", "failed", "success"]
        # And: every field of every entry is identical on the unified entry
        assert observations["public"] == legacy

    def test_runner_reports_partial_for_the_legacy_target__tc_jrev_p2_002(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P2-002: runner reports partial for the legacy target."""
        # Given: the same family and policy, driven through the Runner directly
        root = tmp_path / "runner"
        _generate.materialize_sut_case("multidatatile", root)
        monkeypatch.chdir(root)

        # When: every tile of the legacy callback target fails
        report = _runner(root).run(
            RunRequest(
                root=root,
                target=LegacyCallbackTarget(function=_all_tiles_fail),
                config_source=_generate.oracle_config("multidatatile", ignore_errors=True),
            ),
        )

        # Then: the run is partial -- in v1 a tile failure is not a run failure
        assert report.status == "partial"
        assert [iteration["status"] for iteration in report.iterations] == ["failed", "failed"]
        assert report.error is None
        assert report.warnings == [{"code": 3001, "message": "2 iteration(s) failed", "failed_count": 2}]
        # And: finalize published no job-failure marker
        assert not (root / "data" / "job.failed").exists()

    def test_fail_fast_legacy_target_still_fails_like_legacy__tc_jrev_p2_003(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P2-003: fail fast legacy target still fails like legacy."""
        # Given: the same family under v1's default fail-fast policy
        observations = {}
        for side, entry in (("legacy", _legacy_entry), ("public", _public_entry)):
            root = tmp_path / side
            _generate.materialize_sut_case("multidatatile", root)

            # When: every callback fails
            result, exit_code = _invoke(
                root,
                monkeypatch,
                entry,
                _all_tiles_fail,
                _generate.oracle_config("multidatatile", ignore_errors=False),
            )
            observations[side] = (exit_code, result, _job_failed(root))

        # Then: both exited 1 without a payload after writing the same marker
        assert observations["legacy"][0] == 1
        assert observations["legacy"][1] is None
        assert observations["legacy"][2] == f"ErrorCode=999\nErrorMessage={_ALL_FAILED_MESSAGE}\n"
        assert observations["public"] == observations["legacy"]

    def test_flow_target_with_continue_all_failed_stays_failed__tc_jrev_p2_004(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Design §7.2 for flows is untouched: no implicit partial success."""
        root = tmp_path / "flow"
        _generate.materialize_sut_case("multidatatile", root)
        monkeypatch.chdir(root)

        @flow
        def _all_fail_flow(iteration: IterationInfo) -> None:
            raise StructuredError(_ALL_FAILED_MESSAGE, ecode=999)

        # Given: the very same v1 continue configuration, but a flow target
        report = _runner(root).run(
            RunRequest(
                root=root,
                target=FlowTarget(function=_all_fail_flow),
                config_source=_generate.oracle_config("multidatatile", ignore_errors=True),
            ),
        )

        # Then: a flow whose every tile failed is a failed run with a marker
        assert report.status == "failed"
        assert [iteration["status"] for iteration in report.iterations] == ["failed", "failed"]
        job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
        assert job_failed.splitlines()[0] == "ErrorCode=999"


class TestRunStatusLegacyRule:
    """TC-JREV-P2-005..007: the classification rule behind D9."""

    def test_all_failed_is_partial_only_with_the_legacy_flag__tc_jrev_p2_005(self) -> None:
        """TC-JREV-P2-005: all failed is partial only with the legacy flag."""
        assert _run_status(completed_count=0, failed_count=2, all_failed_is_partial=True) == "partial"
        assert _run_status(completed_count=0, failed_count=2) == "failed"

    def test_some_failed_is_partial_either_way__tc_jrev_p2_006(self) -> None:
        """TC-JREV-P2-006: some failed is partial either way."""
        assert _run_status(completed_count=1, failed_count=1, all_failed_is_partial=True) == "partial"
        assert _run_status(completed_count=0, failed_count=0, all_failed_is_partial=True) == "success"

    def test_fail_fast_overrides_the_legacy_flag__tc_jrev_p2_007(self) -> None:
        """TC-JREV-P2-007: fail fast overrides the legacy flag."""
        assert _run_status(completed_count=0, failed_count=1, fail_fast=True, all_failed_is_partial=True) == "failed"


# ---------------------------------------------------------------------------
# P3 -- the rdesys log must not change the data root
# ---------------------------------------------------------------------------


def _materialize_alias_flat(root: Path, *, extra_inputs: dict[str, str] | None = None) -> None:
    """Materialize the invoice contract input with its RDE markers below ``root``."""
    stage = root.parent / f"{root.name}-stage"
    _generate.materialize_sut_case("invoice", stage)
    shutil.copytree(stage / "data", root)
    shutil.rmtree(stage)
    for name, text in (extra_inputs or {}).items():
        (root / "inputdata" / name).write_text(text, encoding="utf-8")


class _CallRecorder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, srcpaths: Any, resource_paths: Any) -> None:
        del srcpaths, resource_paths
        self.calls += 1


class TestCallbackEntryLogLocation:
    """TC-JREV-P3-001..004: the log ritual is decided after ``resolve_data_root``."""

    def test_alias_flat_root_runs_without_creating_data__tc_jrev_p3_001(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P3-001: alias flat root runs without creating data."""
        # Given: inputdata/ invoice/ tasksupport/ directly below the root, and a
        # tasksupport config declaring MultiDataTile over two input files
        root = tmp_path / "flat"
        _materialize_alias_flat(root, extra_inputs={"second.txt": "second\n"})
        (root / "tasksupport" / "rdeconfig.yaml").write_text(
            yaml.safe_dump({"system": {"extended_mode": "MultiDataTile"}}),
            encoding="utf-8",
        )
        recorder = _CallRecorder()

        # When: the public entry point runs there with config=None
        result, exit_code = _invoke(root, monkeypatch, _public_entry, recorder, None)

        # Then: the run succeeded and the callback ran once per tile
        assert exit_code == 0
        statuses = json.loads(result)["statuses"]
        assert [status["status"] for status in statuses] == ["success", "success"]
        # And: the mode came from <root>/tasksupport, not from v2 defaults
        assert [status["mode"] for status in statuses] == ["MultiDataTile", "MultiDataTile"]
        assert recorder.calls == 2
        # And: no data/ child was created, so the data root never moved
        assert not (root / "data").exists()
        # And: the rdesys log lives below the resolved data root
        assert len(sorted((root / "logs").glob("rdesys_*.log"))) == 1
        assert not (root / "job.failed").exists()

    def test_cwd_named_data_logs_below_itself__tc_jrev_p3_002(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P3-002: cwd named data logs below itself."""
        # Given: the CWD is the data directory itself
        project = tmp_path / "project"
        _generate.materialize_sut_case("invoice", project)
        root = project / "data"
        recorder = _CallRecorder()

        # When: the public entry runs from inside data/
        result, exit_code = _invoke(root, monkeypatch, _public_entry, recorder, None)

        # Then: the run worked against data/ and logged into data/logs
        assert exit_code == 0
        assert recorder.calls == 1
        assert json.loads(result)["statuses"][0]["status"] == "success"
        assert len(sorted((root / "logs").glob("rdesys_*.log"))) == 1
        # And: v1's StorageDir ritual would have produced data/data/logs
        assert not (root / "data").exists()

    def test_alias_flat_root_never_consults_storagedir__tc_jrev_p3_003(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P3-003: alias flat root never consults storagedir."""
        from rdetoolkit.rde2util import StorageDir

        # Given: an alias-flat root and a StorageDir that must not be reached
        root = tmp_path / "flat"
        _materialize_alias_flat(root)

        def _forbidden(*args: Any, **kwargs: Any) -> Path:
            msg = "StorageDir creates <cwd>/data and would move an alias-flat data root"
            raise AssertionError(msg)

        monkeypatch.setattr(StorageDir, "get_specific_outputdir", staticmethod(_forbidden))
        recorder = _CallRecorder()

        # When: the public entry runs
        _, exit_code = _invoke(root, monkeypatch, _public_entry, recorder, None)

        # Then: it completed without touching the v1 helper
        assert exit_code == 0
        assert recorder.calls == 1
        assert not (root / "data").exists()

    def test_standard_layout_keeps_the_storagedir_seam__tc_jrev_p3_004(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-P3-004: standard layout keeps the storagedir seam."""
        from rdetoolkit.rde2util import StorageDir

        # Given: a standard layout and a v1 test's StorageDir redirect
        root = tmp_path / "standard"
        _generate.materialize_sut_case("invoice", root)
        redirected = tmp_path / "redirected"
        requested: list[tuple[bool, str]] = []

        def _redirect(is_mkdir: bool, dir_basename: str, idx: int = 0) -> Path:
            requested.append((is_mkdir, dir_basename))
            target = redirected / dir_basename
            target.mkdir(parents=True, exist_ok=True)
            return target

        monkeypatch.setattr(StorageDir, "get_specific_outputdir", staticmethod(_redirect))

        # When: the public entry runs
        _, exit_code = _invoke(root, monkeypatch, _public_entry, _CallRecorder(), None)

        # Then: the log path came through the seam, once, as v1's did
        assert exit_code == 0
        assert requested == [(True, "logs")]
        assert len(sorted((redirected / "logs").glob("rdesys_*.log"))) == 1


# ---------------------------------------------------------------------------
# Consider -- a malformed tasksupport configuration (closes §J2-3)
# ---------------------------------------------------------------------------


class TestMalformedTasksupportConfig:
    """TC-JREV-C-001/002: the loader failure takes v1's generic failure route."""

    def test_malformed_yaml_matches_legacy__tc_jrev_c_001(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-C-001: malformed yaml matches legacy."""
        # Given: the same input with an unparseable data/tasksupport/rdeconfig.yaml
        observations = {}
        for side, entry in (("legacy", _legacy_entry), ("public", _public_entry)):
            root = tmp_path / side
            _generate.materialize_sut_case("invoice", root)
            (root / "data" / "tasksupport" / "rdeconfig.yaml").write_text("system: [broken\n", encoding="utf-8")
            recorder = _CallRecorder()

            # When: each entry point runs with config=None
            result, exit_code = _invoke(root, monkeypatch, entry, recorder, None)
            observations[side] = (exit_code, result, _job_failed(root), recorder.calls)

        # Then: v1 exited 1 with its generic marker and never ran the callback
        assert observations["legacy"] == (1, None, _V1_GENERIC_JOB_FAILED, 0)
        # And: the unified entry point is identical, marker text included
        assert observations["public"] == observations["legacy"]

    def test_malformed_yaml_in_alias_flat_root_writes_below_the_data_root__tc_jrev_c_002(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """TC-JREV-C-002: malformed yaml in alias flat root writes below the data root."""
        # Given: an alias-flat root with a malformed tasksupport config
        root = tmp_path / "flat"
        _materialize_alias_flat(root)
        (root / "tasksupport" / "rdeconfig.yaml").write_text("system: [broken\n", encoding="utf-8")

        # When: the public entry runs
        result, exit_code = _invoke(root, monkeypatch, _public_entry, _CallRecorder(), None)

        # Then: exit 1 with the generic marker below the resolved data root
        assert (exit_code, result) == (1, None)
        assert (root / "job.failed").read_text(encoding="utf-8") == _V1_GENERIC_JOB_FAILED
        assert not (root / "data").exists()
        # And: the operator was told on stderr, as v1's handler did
        assert capsys.readouterr().err.strip() != ""
        # And: the failure reached the rdesys log
        logs = sorted((root / "logs").glob("rdesys_*.log"))
        assert len(logs) == 1
        assert "ERROR" in logs[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# P2 (decision A) -- v1's failed-entry shape, unit level
# ---------------------------------------------------------------------------


def _failed_report(mode: str, error: dict[str, Any] | None) -> Any:
    from rdetoolkit.report.run_report import RunReport

    return RunReport(
        run_id="run-uuid",
        status="partial",
        flow_id="legacy:cb",
        mode=mode,
        started_at="<DATE>",
        duration_ms=0.0,
        config_digest="sha256:<X>",
        iterations=[
            {"index": 0, "datatile_id": "t0", "status": "completed", "title": "seed", "target": "data/inputdata"},
            {"index": 1, "datatile_id": "t1", "status": "failed", "title": "seed", "error": error, "target": "a,b"},
        ],
        warnings=[],
        error=None,
    )


class TestLegacyFailedEntryShape:
    """TC-JREV-P2-009..012: failed entries take v1's ``_create_error_status`` shape."""

    @pytest.mark.parametrize(
        ("mode", "label"),
        [
            ("invoice", "Invoice"),
            ("excelinvoice", "Excelinvoice"),
            ("multidatatile", "MultiDataTile"),
            ("rdeformat", "rdeformat"),
            ("smarttable", "SmartTableInvoice"),
        ],
    )
    def test_failed_entry_title_and_message__tc_jrev_p2_009(self, mode: str, label: str) -> None:
        """TC-JREV-P2-009: failed entry title and message."""
        # Given / When: a report with one completed and one failed tile
        statuses = json.loads(_failed_report(mode, {"code": 777, "message": "boom"}).to_legacy_statuses())["statuses"]

        # Then: the completed entry keeps its title, the failed one is v1-shaped
        assert statuses[0]["title"] == "seed"
        assert statuses[0]["error_message"] is None
        assert statuses[1]["title"] == f"Structured Process Failed: {label}"
        assert statuses[1]["error_message"] == "Error: boom"
        assert statuses[1]["error_code"] == 777
        assert statuses[1]["target"] == "a,b"

    def test_failed_entry_without_any_error_has_no_message__tc_jrev_p2_010(self) -> None:
        """TC-JREV-P2-010: failed entry without any error has no message."""
        # Given: a failed iteration carrying no error record at all
        statuses = json.loads(_failed_report("invoice", None).to_legacy_statuses())["statuses"]

        # Then: no "Error: None" is invented
        assert statuses[1]["error_message"] is None
        assert statuses[1]["error_code"] is None

    def test_unknown_mode_label_passes_through__tc_jrev_p2_011(self) -> None:
        """TC-JREV-P2-011: unknown mode label passes through."""
        statuses = json.loads(_failed_report("unknown", {"code": 1, "message": "m"}).to_legacy_statuses())["statuses"]

        assert statuses[1]["title"] == "Structured Process Failed: unknown"

    def test_failed_target_joins_every_raw_file__tc_jrev_p2_012(self, tmp_path: Path) -> None:
        """TC-JREV-P2-012: failed target joins every raw file."""
        from rdetoolkit.runner.executor import _legacy_failed_target

        # Given: two raw files below the root and one outside it
        inside = (tmp_path / "data" / "inputdata" / "a.txt", tmp_path / "data" / "inputdata" / "b.txt")
        outside = Path("/elsewhere/c.txt")

        # Then: root-relative POSIX paths, comma-joined in tile order; a path
        # outside the root is kept as-is; no raw file is an empty target
        assert _legacy_failed_target(inside, root=tmp_path) == "data/inputdata/a.txt,data/inputdata/b.txt"
        assert _legacy_failed_target((*inside, outside), root=tmp_path).endswith(",/elsewhere/c.txt")
        assert _legacy_failed_target((), root=tmp_path) == ""


# ---------------------------------------------------------------------------
# F1 / F2 -- v1 honours ignore_errors only in MultiDataTile
# ---------------------------------------------------------------------------

#: Non-MultiDataTile modes and the tile count of their contract input family.
_NON_MDT_TILE_COUNTS = {"invoice": 1, "excelinvoice": 2, "rdeformat": 2, "smarttable": 3}


class _TileScript:
    """v1 callback failing the tiles named in ``failing`` and counting calls."""

    def __init__(self, failing: set[int] | None) -> None:
        self.failing = failing
        self.calls = 0

    def __call__(self, srcpaths: Any, resource_paths: Any) -> None:
        del srcpaths, resource_paths
        index = self.calls
        self.calls += 1
        if self.failing is None or index in self.failing:
            raise StructuredError(_ALL_FAILED_MESSAGE, ecode=999)


def _observe_ignore_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    failing: set[int] | None,
) -> dict[str, Any]:
    """Run one mode with ``ignore_errors=True`` on both entry points."""
    observations: dict[str, Any] = {}
    for side, entry in (("legacy", _legacy_entry), ("public", _public_entry)):
        root = tmp_path / side
        _generate.materialize_sut_case(mode, root)
        script = _TileScript(failing)
        result, exit_code = _invoke(
            root,
            monkeypatch,
            entry,
            script,
            _generate.oracle_config(mode, ignore_errors=True),
        )
        observations[side] = {
            "exit_code": exit_code,
            "statuses": _statuses(result, root),
            "job_failed": _job_failed(root),
            "calls": script.calls,
        }
    return observations


class TestIgnoreErrorsIsMultiDataTileOnly:
    """TC-JREV-F1-001..004 / TC-JREV-F2-001..003: non-MDT stays fail-fast, as v1."""

    @pytest.mark.parametrize("mode", list(_NON_MDT_TILE_COUNTS))
    def test_every_tile_failing_exits_1_like_legacy__tc_jrev_f1(
        self,
        mode: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-F1: every tile failing exits 1 like legacy."""
        # Given / When: ignore_errors=True and a callback failing every tile
        observations = _observe_ignore_errors(tmp_path, monkeypatch, mode, failing=None)

        # Then: v1 ignored the flag outside MultiDataTile -- exit 1 after one call
        legacy = observations["legacy"]
        assert legacy["exit_code"] == 1
        assert legacy["calls"] == 1
        assert legacy["job_failed"] == f"ErrorCode=999\nErrorMessage={_ALL_FAILED_MESSAGE}\n"
        # And: the unified entry point agrees on every observable
        assert observations["public"] == legacy

    @pytest.mark.parametrize("mode", [mode for mode, count in _NON_MDT_TILE_COUNTS.items() if count >= 2])
    def test_first_tile_failing_stops_the_run_like_legacy__tc_jrev_f2(
        self,
        mode: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-F2: first tile failing stops the run like legacy."""
        # Given / When: ignore_errors=True, tile 0 fails and the rest would succeed
        observations = _observe_ignore_errors(tmp_path, monkeypatch, mode, failing={0})

        # Then: v1 stopped at the first failure -- no later tile ran
        legacy = observations["legacy"]
        assert legacy["exit_code"] == 1
        assert legacy["calls"] == 1
        assert legacy["job_failed"] is not None
        # And: the unified entry point did not keep going
        assert observations["public"] == legacy


class TestLegacyTargetErrorPolicy:
    """TC-JREV-F1-005..007: the planner derives v1 iteration semantics for callbacks."""

    @staticmethod
    def _plan(target: Any, mode: Any, policy: str) -> Any:
        from rdetoolkit.runner.planner import RunPlanner

        # Tiles are produced lazily, so planning touches no filesystem path.
        root = Path("/nonexistent")
        config = RdeConfig(execution={"on_iteration_error": policy})
        request = RunRequest(root=root, target=target, config_source=config)
        planner = RunPlanner(
            inputdata_path=root / "data" / "inputdata",
            unpacked_dir_path=root / "data" / "temp",
            run_id_factory=lambda: "plan-unit",
        )
        return planner.create(request, config=config, mode=mode, data_root=root / "data")

    def test_callback_continue_outside_multidatatile_is_fail_fast__tc_jrev_f1_005(self) -> None:
        """TC-JREV-F1-005: callback continue outside multidatatile is fail fast."""
        from rdetoolkit.runner.mode_resolver import ModeKind

        # Given: continue requested for a callback target in invoice mode
        plan = self._plan(LegacyCallbackTarget(function=_all_tiles_fail), ModeKind.invoice, "continue")

        # Then: v1 iteration semantics win -- fail_fast
        assert plan.error_policy == "fail_fast"

    def test_flow_continue_outside_multidatatile_stays_continue__tc_jrev_f1_006(self) -> None:
        """TC-JREV-F1-006: flow continue outside multidatatile stays continue."""
        from rdetoolkit.runner.mode_resolver import ModeKind

        @flow
        def _noop(iteration: IterationInfo) -> None:
            return None

        # Given / Then: a flow keeps the configured policy (Design §7.2)
        plan = self._plan(FlowTarget(function=_noop), ModeKind.invoice, "continue")
        assert plan.error_policy == "continue"

    @pytest.mark.parametrize(("policy", "expected"), [("continue", "continue"), ("fail_fast", "fail_fast")])
    def test_callback_in_multidatatile_follows_the_config__tc_jrev_f1_007(self, policy: str, expected: str) -> None:
        """TC-JREV-F1-007: callback in multidatatile follows the config."""
        from rdetoolkit.runner.mode_resolver import ModeKind

        plan = self._plan(LegacyCallbackTarget(function=_all_tiles_fail), ModeKind.multidatatile, policy)
        assert plan.error_policy == expected


class TestPostInvokeFailureTarget:
    """TC-JREV-F3-001: a post-invoke stage failure names the tile's raw files."""

    def test_post_invoke_failure_target_is_the_raw_file_list__tc_jrev_f3_001(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-JREV-F3-001: post invoke failure target is the raw file list."""
        # Given: a succeeding callback and a structured destination that cannot
        # receive the invoice copy (a directory where the file must go)
        root = tmp_path / "root"
        _generate.materialize_sut_case("invoice", root)
        blocked = root / "data" / "structured" / "invoice.json"
        (blocked / blocked.name).mkdir(parents=True)
        base = _generate.oracle_config("invoice")
        config = Config(**{**base.model_dump(), "system": {**base.system.model_dump(), "save_invoice_to_structured": True}})
        recorder = _CallRecorder()
        monkeypatch.chdir(root)

        # When: the Runner runs the legacy target
        report = _runner(root).run(
            RunRequest(root=root, target=LegacyCallbackTarget(function=recorder), config_source=config),
        )

        # Then: the callback ran, the post-invoke stage failed the tile
        assert recorder.calls == 1
        assert [iteration["status"] for iteration in report.iterations] == ["failed"]
        # And: the failed entry's target is v1's raw-file list, not the directory
        assert report.iterations[0]["target"] == "data/inputdata/invoice_input.txt"
        statuses = json.loads(report.to_legacy_statuses())["statuses"]
        assert statuses[0]["target"] == "data/inputdata/invoice_input.txt"
