"""Tests for ``rdetoolkit run`` v2 extensions (Session E1, TC-CLI-RUN-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e1.md
(Conflicts #1-#12, Known Traps 1-12), local/develop/v2/Design.md v2.1 §10/
§9.3/§11.

Binding API-shape pins asserted by this file (precision standard):
- ``rdetoolkit run --flow <dotted.module:attr> [--validate-only] [--config
  PATH]`` is the existing ``cli/app.py:run()`` command extended in place;
  ``target`` becomes an optional positional argument.
- ``--flow`` resolves ONLY a dotted ``pkg.mod`` path via
  ``importlib.import_module`` + single-``:``-separated ``getattr`` (no
  file-path support) -- Conflict #11. Fixture flows therefore live in the
  real, dotted-importable package ``tests.v2.cli.fixtures.run_flows``.
- Exit codes: 0 = RunReport.status == "success"; 2 = "partial"; 1 =
  "failed"; 3 = usage error (bad target string/mutual-exclusivity/module
  resolution/`--config` load failure) raised via ``typer.Exit(code=3)``,
  never ``typer.BadParameter`` (Known Trap 4 -- BadParameter's Click
  default exit code, 2, would collide with "partial").
- ``--validate-only`` (only meaningful combined with ``--flow``) must never
  invoke ``rdetoolkit.workflows.run`` -- this file monkeypatches
  ``rdetoolkit.workflows.run`` directly (not
  ``rdetoolkit.cli.run_cmd.<alias>``), which requires ``cli/run_cmd.py`` to
  perform a LATE/dynamic attribute lookup of ``workflows.run`` at call time
  (e.g. ``from rdetoolkit import workflows`` at module scope, then
  ``workflows.run(...)`` inside the function body) rather than
  ``from rdetoolkit.workflows import run`` bound once at import time --
  mirroring the existing legacy-target branch's own
  ``cli_module.workflows.run`` late-lookup pattern in ``cli/app.py``. This
  is a binding contract of this test file, not incidental monkeypatch
  mechanics.

Fixture data-directory convention: mirrors
``tests/v2/e2e/test_run_flow.py``'s ``_build_data_fixture`` shape but uses
``data/temp`` (not ``data/unpacked``) as the unpacked-dir, because
``workflows.run(flow=...)`` uses ``unpacked_dir_path=data_root / "temp"`` --
this is the "explicit data/temp convention" Known Trap 3 requires
``--validate-only``'s own manually constructed ``Runner(...)`` to match. Since
Session I-REVIEW-A both derive ``data_root`` from
``runner.paths.resolve_data_root`` instead of hardcoding ``<root>/data``, which
the alias-flat cells below pin. Self-contained (no ``tests.v2.e2e`` import),
per that file's own "no cross-file test helper imports" rule.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from tests.v2.cli.fixtures import legacy_targets

FIXTURE_MODULE = "tests.v2.cli.fixtures.run_flows"
LEGACY_MODULE = "tests.v2.cli.fixtures.legacy_targets"

_SEED_INVOICE_JSON: dict = {
    "datasetId": "seed-dataset",
    "basic": {
        "dateSubmitted": "2026-07-11",
        "dataOwnerId": "0" * 56,
        "dataName": "seed",
    },
}


def _build_data_fixture(root: Path, *, input_files: dict[str, str] | None = None) -> None:
    """Build a ``data/{inputdata,invoice,tasksupport,temp}`` tree matching
    ``workflows.run(flow=...)``'s actual dispatch convention."""
    inputdata = root / "data" / "inputdata"
    inputdata.mkdir(parents=True)
    resolved_input_files = {"test_single.txt": "dummy"} if input_files is None else input_files
    for name, content in resolved_input_files.items():
        (inputdata / name).write_text(content, encoding="utf-8")
    (root / "data" / "invoice").mkdir(parents=True)
    (root / "data" / "invoice" / "invoice.json").write_text(json.dumps(_SEED_INVOICE_JSON), encoding="utf-8")
    (root / "data" / "tasksupport").mkdir(parents=True)
    (root / "data" / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (root / "data" / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (root / "data" / "temp").mkdir(parents=True)


def _build_alias_flat_fixture(root: Path) -> None:
    """Build the same project with the RDE markers directly below ``root``.

    ``resolve_data_root`` contracts that such a root *is* the data root
    (Session I-REVIEW-A ruling #1). ``--validate-only`` hardcoded
    ``<cwd>/data``, so on this layout it validated a tree that does not exist.
    """
    inputdata = root / "inputdata"
    inputdata.mkdir(parents=True)
    (inputdata / "test_single.txt").write_text("dummy", encoding="utf-8")
    (root / "invoice").mkdir(parents=True)
    (root / "invoice" / "invoice.json").write_text(json.dumps(_SEED_INVOICE_JSON), encoding="utf-8")
    (root / "tasksupport").mkdir(parents=True)
    (root / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (root / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (root / "temp").mkdir(parents=True)


def _write_rdeconfig(root: Path, data: dict) -> None:
    (root / "rdeconfig.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _write_tasksupport_rdeconfig(root: Path, data: dict) -> None:
    """Write the v1 configuration a structured program actually ships.

    The legacy target rejects ``--config`` (Design §10), so the only way to
    configure TC-CLI-RUN-EP-018's continue policy is the v1 location the public
    entry point reads with v1's own loader.
    """
    tasksupport = root / "data" / "tasksupport"
    tasksupport.mkdir(parents=True, exist_ok=True)
    (tasksupport / "rdeconfig.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _legacy_payload(output: str) -> dict:
    """Return the legacy statuses JSON the CLI echoed.

    ``CliRunner`` mixes stderr into ``output`` and the Runner writes its failure
    count line there, so the payload is selected by shape rather than by
    position.

    Args:
        output: Captured CLI output.

    Returns:
        The decoded ``{"statuses": [...]}`` document.
    """
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.startswith('{"statuses"'):
            return cast(dict, json.loads(candidate))
    msg = f"no legacy statuses payload in CLI output: {output!r}"
    raise AssertionError(msg)


def _write_excel_invoice_workbook(path: Path) -> None:
    """Write the smallest workbook ``selected_input_checker`` detects.

    Only the ``*_excel_invoice.xlsx`` name and an ``invoice_form`` sheet matter
    for mode detection, which is all TC-CLI-RUN-EP-019 needs: the run never
    reaches the point of reading rows.
    """
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([["invoiceList_format_id"], [""]]).to_excel(
            writer,
            sheet_name="invoice_form",
            index=False,
            header=False,
        )


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def workflows_run_spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Spy on ``rdetoolkit.workflows.run`` at its module-level definition
    site. See this file's module docstring for why this requires
    ``cli/run_cmd.py`` to do a late attribute lookup."""
    calls: list[tuple] = []

    def _spy(**kwargs: object) -> object:
        calls.append((kwargs,))
        msg = "rdetoolkit.workflows.run must not be called on this path"
        raise AssertionError(msg)

    monkeypatch.setattr("rdetoolkit.workflows.run", _spy)
    return calls


class TestRunFlowExitCodes:
    """TC-CLI-RUN-EP-001..003: RunReport.status -> exit-code mapping."""

    def test_all_tiles_succeed_exits_0__tc_cli_run_ep_001(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:success_pipeline"])

        assert result.exit_code == 0
        assert "success" in result.output.lower()

    def test_some_tiles_fail_continue_policy_exits_2__tc_cli_run_ep_002(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        _build_data_fixture(isolated_root, input_files={"a.txt": "a", "b.txt": "b"})
        _write_rdeconfig(isolated_root, {"system": {"extended_mode": "MultiDataTile"}})

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:second_tile_fails_pipeline"])

        assert result.exit_code == 2
        assert "partial" in result.output.lower()

    def test_all_tiles_fail_exits_1__tc_cli_run_ep_003(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:failing_pipeline"])

        assert result.exit_code == 1
        assert "failed" in result.output.lower()


class TestRunFlowResolutionUsageErrors:
    """TC-CLI-RUN-EP-004..008: --flow string resolution failures and
    mutual-exclusivity are usage errors, exit code 3, and never reach
    workflows.run."""

    def test_unimportable_module_exits_3__tc_cli_run_ep_004(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        workflows_run_spy: list[tuple],
    ) -> None:
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(app, ["run", "--flow", "tests.v2.cli.fixtures.totally_nonexistent_module:pipeline"])

        assert result.exit_code == 3
        assert workflows_run_spy == []

    def test_missing_attribute_exits_3__tc_cli_run_ep_005(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        workflows_run_spy: list[tuple],
    ) -> None:
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:does_not_exist"])

        assert result.exit_code == 3
        assert workflows_run_spy == []

    def test_class_target_exits_3__tc_cli_run_ep_006(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        workflows_run_spy: list[tuple],
    ) -> None:
        """UPDATE (session_f2.md Conflict #9): the pre-F2 OR-condition
        (``"phase f" in output or "template" in output``) is replaced by a
        single precise assertion. Phase F now exists, so "not supported
        until Phase F" is a factually stale message; the OR-condition
        would perversely still pass on that stale wording alone. The new
        assertion checks the class is specifically rejected for NOT being
        a ``ProcessingTemplate`` subclass -- a real semantic distinction,
        not a temporal one -- which is strictly stronger: it can only pass
        for the right reason, never the old (now-wrong) one."""
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:NotAFunctionTarget"])

        assert result.exit_code == 3
        assert "processingtemplate" in result.output.lower()
        assert workflows_run_spy == []

    def test_target_and_flow_both_given_exits_3__tc_cli_run_ep_007(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        workflows_run_spy: list[tuple],
    ) -> None:
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(
            app,
            ["run", "legacy_target::attr", "--flow", f"{FIXTURE_MODULE}:success_pipeline"],
        )

        assert result.exit_code == 3
        assert workflows_run_spy == []

    def test_neither_target_nor_flow_exits_3__tc_cli_run_ep_008(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        workflows_run_spy: list[tuple],
    ) -> None:
        result = cli_runner.invoke(app, ["run"])

        assert result.exit_code == 3
        assert workflows_run_spy == []


class TestRunValidateOnly:
    """TC-CLI-RUN-EP-009..011: --validate-only structurally never calls the
    resolved flow (Conflict #3), proven via the module-level side-effect
    sentinel in tests.v2.cli.fixtures.run_flows."""

    def test_valid_fixture_validate_only_exits_0_never_calls_flow__tc_cli_run_ep_009(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        from tests.v2.cli.fixtures import run_flows

        before = len(run_flows.VALIDATE_ONLY_SENTINEL)
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"])

        assert result.exit_code == 0
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before

    def test_invalid_fixture_validate_only_exits_1_never_calls_flow__tc_cli_run_ep_010(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        from tests.v2.cli.fixtures import run_flows

        before = len(run_flows.VALIDATE_ONLY_SENTINEL)
        _build_data_fixture(isolated_root)
        # Malformed rdeconfig.yaml: an unknown top-level key is rejected by
        # RdeConfig's extra="forbid" model config, so Runner.load_config
        # raises during the validate-only path's first step.
        _write_rdeconfig(isolated_root, {"nonexistent_top_level_key": True})

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"])

        assert result.exit_code == 1
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before

    def test_alias_flat_root_validates_its_own_tree__tc_cli_run_ep_009b(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        """TC-CLI-RUN-EP-009b: --validate-only follows the resolved data root.

        Session I-REVIEW-A F-1: the path hardcoded ``<cwd>/data``, so an
        alias-flat project was validated against a non-existent tree. The
        negative half of the pin is below: removing the invoice the resolved
        root really owns must turn the exit code into 1.
        """
        from tests.v2.cli.fixtures import run_flows

        # Given: an alias-flat project with a valid invoice and schema
        before = len(run_flows.VALIDATE_ONLY_SENTINEL)
        _build_alias_flat_fixture(isolated_root)

        # When: validating without executing the flow
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"])

        # Then: the real tree validated, and the flow never ran
        assert result.exit_code == 0, result.output
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before
        assert not (isolated_root / "data").exists()

    def test_alias_flat_root_reports_its_own_invalid_tree__tc_cli_run_ep_010b(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        """TC-CLI-RUN-EP-010b: the alias-flat pin is not satisfied by any tree."""
        # Given: an alias-flat project whose own invoice is missing
        _build_alias_flat_fixture(isolated_root)
        (isolated_root / "invoice" / "invoice.json").unlink()

        # When: validating without executing the flow
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"])

        # Then: validation fails on the resolved root's own artifacts
        assert result.exit_code == 1
        assert "Validation failed" in result.output

    def test_alias_flat_root_drives_mode_resolution__tc_cli_run_ep_009c(
        self,
        isolated_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-CLI-RUN-EP-009c: the input paths follow the resolved data root.

        This is a construction-level pin, deliberately: with the old
        ``<cwd>/data`` hardcode the *validation* result was unchanged (the
        Runner resolves its own data root for ``pre_validate``), but
        ``resolve_mode`` scanned a non-existent ``<root>/data/inputdata`` and
        silently answered ``invoice`` for every alias-flat project -- including
        ExcelInvoice and SmartTable ones. ``--validate-only`` prints no mode, so
        the only honest observable is which directories the Runner is given.

        UPDATED (Session J2 ruling #4): ``validate_only`` now takes the resolved
        flow and drives one ``Runner.run(RunRequest(validate_only=True))`` call
        instead of three step-by-step Runner methods, so the call is adapted and
        the pin is **extended** -- the request the Runner receives is captured
        too, and it must carry ``validate_only=True`` with the flow as its
        target. The directory expectation is unchanged, and the step-by-step
        API's inability to publish W1001 (noted here before J2) is now its own
        regression cell, TC-CLI-RUN-EP-019.
        """
        from rdetoolkit.api.request import FlowTarget, RunRequest
        from rdetoolkit.cli import run_cmd
        from tests.v2.cli.fixtures import run_flows

        # Given: an alias-flat project carrying a plain input file
        before = len(run_flows.VALIDATE_ONLY_SENTINEL)
        _build_alias_flat_fixture(isolated_root)
        constructed: list[dict[str, Path]] = []
        requests: list[RunRequest] = []
        real_runner = run_cmd.Runner

        class _RecordingRunner(real_runner):  # type: ignore[misc, valid-type]
            def __init__(self, **kwargs: object) -> None:
                constructed.append(
                    {
                        "root": cast(Path, kwargs["root"]),
                        "inputdata_path": cast(Path, kwargs["inputdata_path"]),
                        "unpacked_dir_path": cast(Path, kwargs["unpacked_dir_path"]),
                    },
                )
                super().__init__(**kwargs)  # type: ignore[arg-type]

            def run(self, request: RunRequest, **overrides: object) -> object:
                requests.append(request)
                return super().run(request, **overrides)

        monkeypatch.setattr(run_cmd, "Runner", _RecordingRunner)

        # When: running the validate-only path
        run_cmd.validate_only(run_flows.validate_only_pipeline, None)

        # Then: the Runner scans the directories the resolved data root owns
        assert constructed == [
            {
                "root": isolated_root,
                "inputdata_path": isolated_root / "inputdata",
                "unpacked_dir_path": isolated_root / "temp",
            },
        ]

        # And: it is driven by exactly one validate-only request naming the flow
        assert len(requests) == 1
        assert requests[0].validate_only is True
        assert requests[0].root == isolated_root
        assert requests[0].target == FlowTarget(function=run_flows.validate_only_pipeline)

        # And: resolving the flow is not calling it
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before

    def test_validate_only_without_flow_exits_3__tc_cli_run_ep_011(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        result = cli_runner.invoke(app, ["run", "legacy_target::attr", "--validate-only"])

        assert result.exit_code == 3

    def test_validate_only_failure_writes_no_job_failed__tc_cli_run_ep_020(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        """TC-CLI-RUN-EP-020: a failed pre-flight leaves no job-failure marker.

        Routing ``--validate-only`` through ``Runner.run`` (Session J2 ruling
        #4) put its failures on the ordinary ``_failed_report`` + ``finalize``
        path, which writes ``data/job.failed``. The pre-J2 step-by-step helper
        wrote nothing at all, and the RDE platform reads that file as *the*
        job-failure marker -- a pre-flight check must not claim the job failed.
        The amended ruling: a validate-only run never writes ``job.failed``
        under any outcome, while still reporting exit 1 to its caller.

        The run report *is* written: it is a log, not a marker, and asserting
        its presence keeps this cell from passing for the wrong reason (a
        ``finalize`` that was skipped wholesale).
        """
        from tests.v2.cli.fixtures import run_flows

        # Given: a project whose own invoice is missing, so pre_validate fails
        # after the §J0-3 unpack directory has been prepared
        before = len(run_flows.VALIDATE_ONLY_SENTINEL)
        _build_data_fixture(isolated_root)
        (isolated_root / "data" / "invoice" / "invoice.json").unlink()

        # When: validating without executing the flow
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"])

        # Then: the caller is told it failed, and the flow never ran
        assert result.exit_code == 1
        assert "Validation failed" in result.output
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before

        # And: no job-failure marker was left behind
        assert not (isolated_root / "data" / "job.failed").exists(), (
            "a validate-only pre-flight must not write the RDE job-failure marker"
        )

        # And: the run report was still written, so the skip is specific
        assert list((isolated_root / "data" / "logs").glob("run_report_*.json")), (
            "the run report is a log and is still expected"
        )

        # And: the unpack directory v1 prepared before parsing is still there
        # (contracts.md §J0-3), the same layout TC-CLI-RUN-EP-009b validates
        assert (isolated_root / "data" / "temp").is_dir()

    def test_mode_override_publishes_w1001__tc_cli_run_ep_019(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        """TC-CLI-RUN-EP-019: --validate-only publishes the W1001 override event.

        Regression cell for §I-REVIEW-A debt 5, closed by Session J2 ruling #4.
        The pre-J2 path built the first three lifecycle steps by hand *before*
        any run id existed, so ``resolve_mode``'s W1001 warning was emitted with
        ``run_id=""`` and could not be published to a sink at all. Driving the
        same work through ``Runner.run(RunRequest(validate_only=True))`` gives it
        a real run id.

        The fixture declares ``extended_mode: invoice`` while shipping an
        ExcelInvoice workbook, which is exactly the "file detection overrode an
        explicitly configured mode" condition W1001 exists for.
        """
        from rdetoolkit.api.request import build_run_request
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.lifecycle import Runner
        from rdetoolkit.runner.paths import resolve_data_root
        from tests.v2.cli.fixtures import run_flows

        # Given: a project whose declared mode loses to its ExcelInvoice input
        before = len(run_flows.VALIDATE_ONLY_SENTINEL)
        _build_data_fixture(isolated_root, input_files={"test_single.txt": "dummy"})
        _write_excel_invoice_workbook(isolated_root / "data" / "inputdata" / "sample_excel_invoice.xlsx")
        _write_rdeconfig(isolated_root, {"system": {"extended_mode": "invoice"}})

        # When: validating through the CLI
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"])

        # Then: validation succeeds without running the flow
        assert result.exit_code == 0, result.output
        assert "Validation succeeded" in result.output
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before

        # And: the same request publishes W1001 with a real run id. The CLI owns
        # no sink, so the event is observed by replaying the one request the CLI
        # builds through a Runner that does.
        data_root = resolve_data_root(isolated_root)
        sink = MemoryEventSink()
        report = Runner(
            root=isolated_root,
            inputdata_path=data_root / "inputdata",
            unpacked_dir_path=data_root / "temp",
            event_sink=sink,
        ).run(
            build_run_request(
                flow=run_flows.validate_only_pipeline,
                custom_dataset_function=None,
                config=None,
                root=isolated_root,
                validate_only=True,
            ),
        )
        assert report.status == "success"
        assert report.iterations == []
        warnings_published = [
            event for event in sink.events if event.name == "warning" and event.payload.get("code") == 1001
        ]
        assert len(warnings_published) == 1
        assert warnings_published[0].run_id == report.run_id
        assert warnings_published[0].run_id != "", "W1001 was unpublishable while run_id was empty"
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before


class TestRunLegacyTargetExitCodes:
    """TC-CLI-RUN-EP-016..018: the legacy target maps onto §9.3's 0/1/2/3.

    The v1 *Python* contract keeps ``SystemExit(1)`` for a failed run and a
    normal return for a partial one; the CLI is uniform across every ``run``
    form (Session J2 ruling #3). These three cells drive the public entry point
    for real -- no stub -- so the mapping is measured end to end.
    """

    def test_legacy_target_success_exits_0__tc_cli_run_ep_016(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        # Given: a one-tile project and a callback that succeeds
        _build_data_fixture(isolated_root)

        # When: running it as a legacy target
        result = cli_runner.invoke(app, ["run", f"{LEGACY_MODULE}::succeeds"])

        # Then: exit 0, and the legacy JSON payload reached stdout
        assert result.exit_code == 0, result.output
        assert legacy_targets.call_count(isolated_root) == 1
        payload = _legacy_payload(result.output)
        assert [status["status"] for status in payload["statuses"]] == ["success"]

    def test_legacy_target_failure_exits_1__tc_cli_run_ep_017(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        # Given: a one-tile project and a callback that raises
        _build_data_fixture(isolated_root)

        # When: running it as a legacy target
        result = cli_runner.invoke(app, ["run", f"{LEGACY_MODULE}::always_fails"])

        # Then: the entry point's SystemExit(1) becomes CLI exit 1, not a
        # traceback escaping through ``except Exception``
        assert result.exit_code == 1
        assert legacy_targets.call_count(isolated_root) == 1

        # And: the v1 failure artifact carries the user's own ecode
        job_failed = (isolated_root / "data" / "job.failed").read_text(encoding="utf-8")
        assert job_failed.splitlines()[0] == f"ErrorCode={legacy_targets.FAILURE_CODE}"

    def test_legacy_target_partial_exits_2__tc_cli_run_ep_018(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        # Given: a two-tile MultiDataTile project with v1's continue policy,
        # declared in data/tasksupport because a legacy target rejects --config
        _build_data_fixture(isolated_root, input_files={"a.txt": "a", "b.txt": "b"})
        _write_tasksupport_rdeconfig(
            isolated_root,
            {
                "system": {"extended_mode": "MultiDataTile"},
                "multidata_tile": {"ignore_errors": True},
            },
        )

        # When: tile 1 fails while tile 0 succeeds
        result = cli_runner.invoke(app, ["run", f"{LEGACY_MODULE}::second_tile_fails"])

        # Then: a partial run is exit 2 -- the v1 API returned normally, so the
        # code can only come from the returned statuses
        assert result.exit_code == 2, result.output
        assert legacy_targets.call_count(isolated_root) == 2
        payload = _legacy_payload(result.output)
        assert [status["status"] for status in payload["statuses"]] == ["success", "failed"]

        # And: a partial run leaves no job.failed, exactly as v1 measured
        assert not (isolated_root / "data" / "job.failed").exists()

    def test_legacy_target_all_tiles_failed_under_ignore_errors_exits_2__tc_cli_run_ep_021(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        """contracts.md §J-REVIEW D9: v1's continue policy never fails the run.

        With ``ignore_errors: true`` v1 returned every failed status normally,
        even when no tile succeeded, so the public entry point returns its
        payload and the CLI maps a payload carrying ``failed`` to partial.
        """
        # Given: a two-tile MultiDataTile project with v1's continue policy
        _build_data_fixture(isolated_root, input_files={"a.txt": "a", "b.txt": "b"})
        _write_tasksupport_rdeconfig(
            isolated_root,
            {
                "system": {"extended_mode": "MultiDataTile"},
                "multidata_tile": {"ignore_errors": True},
            },
        )

        # When: every tile fails
        result = cli_runner.invoke(app, ["run", f"{LEGACY_MODULE}::always_fails"])

        # Then: exit 2, not 1 -- the entry point returned instead of exiting
        assert result.exit_code == 2, result.output
        assert legacy_targets.call_count(isolated_root) == 2
        payload = _legacy_payload(result.output)
        assert [status["status"] for status in payload["statuses"]] == ["failed", "failed"]

        # And: no job.failed, exactly as v1 measured for this policy
        assert not (isolated_root / "data" / "job.failed").exists()


class TestRunConfigOverride:
    """TC-CLI-RUN-EP-012, TC-CLI-RUN-BV-001/002: --config semantics
    (Conflict #10)."""

    def test_config_override_changes_observable_outcome__tc_cli_run_ep_012(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        _build_data_fixture(isolated_root, input_files={"a.txt": "a", "b.txt": "b"})
        _write_rdeconfig(isolated_root, {"system": {"extended_mode": "MultiDataTile"}})

        baseline = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:second_tile_fails_pipeline"])
        assert baseline.exit_code == 2, "baseline (no --config): continue policy -> partial -> exit 2"

        override_path = isolated_root / "override.yaml"
        override_path.write_text(yaml.safe_dump({"execution": {"on_iteration_error": "fail_fast"}}), encoding="utf-8")

        overridden = cli_runner.invoke(
            app,
            ["run", "--flow", f"{FIXTURE_MODULE}:second_tile_fails_pipeline", "--config", str(override_path)],
        )
        assert overridden.exit_code == 1, "--config override to fail_fast must flip the outcome to failed -> exit 1"

    def test_config_path_does_not_exist_exits_3__tc_cli_run_bv_001(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(
            app,
            ["run", "--flow", f"{FIXTURE_MODULE}:success_pipeline", "--config", str(isolated_root / "does_not_exist.yaml")],
        )

        assert result.exit_code == 3

    def test_config_combined_with_legacy_target_exits_3__tc_cli_run_bv_002(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        config_path = isolated_root / "override.yaml"
        config_path.write_text(yaml.safe_dump({"execution": {"on_iteration_error": "fail_fast"}}), encoding="utf-8")

        result = cli_runner.invoke(app, ["run", "legacy_target::attr", "--config", str(config_path)])

        assert result.exit_code == 3


@pytest.fixture
def workflows_run_recording_spy(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Spy on ``rdetoolkit.workflows.run`` that DELEGATES to the real
    implementation (unlike ``workflows_run_spy`` above, which raises to
    prove a path never calls it) -- TC-CLI-RUN-EP-014 needs to observe a
    real, successful call, not merely that a call was attempted. Uses the
    same late-attribute-lookup contract as ``workflows_run_spy`` (see this
    file's module docstring)."""
    from rdetoolkit import workflows as workflows_module

    calls: list[dict] = []
    original = workflows_module.run

    def _spy(**kwargs: object) -> object:
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr("rdetoolkit.workflows.run", _spy)
    return calls


class TestRunFlowTemplateClassAcceptance:
    """TC-CLI-RUN-EP-014 (UPDATE table net-new row, session_f2.md Conflict
    #9): a genuinely valid ``ProcessingTemplate`` subclass target resolves
    via ``--flow`` and runs end-to-end -- proving Design §5.2.3's
    Runner/CLI dual-acceptance clause and Conflict #3's flow_id-identity
    ruling (RunReport.flow_id must identify the concrete fixture class,
    not the skeleton it derives from)."""

    def test_valid_template_class_target_runs__tc_cli_run_ep_014(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        workflows_run_recording_spy: list[dict],
    ) -> None:
        _build_data_fixture(isolated_root)

        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:ValidTemplateTarget"])

        assert result.exit_code == 0, result.output
        assert len(workflows_run_recording_spy) == 1

        report = json.loads(result.output)
        assert report["status"] == "success"
        assert report["flow_id"].endswith("ValidTemplateTarget"), report["flow_id"]
        assert "_Ep014Skeleton" not in report["flow_id"]

    def test_depth1_skeleton_target_is_rejected__tc_cli_run_ep_015(
        self,
        cli_runner: CliRunner,
    ) -> None:
        # Given: a CLI reference to the registered depth-1 fixture skeleton
        flow_ref = f"{FIXTURE_MODULE}:_Ep014Skeleton"

        # When: run --flow resolves that class under the existing error conversion
        result = cli_runner.invoke(app, ["run", "--flow", flow_ref])

        # Then: it fails and retains the remediation-bearing TypeError
        assert result.exit_code == 1
        assert isinstance(result.exception, TypeError)
        message = str(result.exception).lower()
        assert "skeleton" in message
        assert "subclass" in message
        assert "slot" in message
