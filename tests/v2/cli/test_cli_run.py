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

import pytest
import yaml
from typer.testing import CliRunner

from rdetoolkit.cli.app import app

FIXTURE_MODULE = "tests.v2.cli.fixtures.run_flows"

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
        """
        from rdetoolkit.cli import run_cmd

        # Given: an alias-flat project
        #
        # (The fixture deliberately keeps a plain input file: a workbook here
        # would trigger the W1001 mode-override event, which this path emits
        # with an empty ``run_id`` and therefore cannot publish -- an unrelated
        # latent defect of the step-by-step API, recorded in contracts.md.)
        _build_alias_flat_fixture(isolated_root)
        constructed: list[dict[str, Path]] = []
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

        monkeypatch.setattr(run_cmd, "Runner", _RecordingRunner)

        # When: running the validate-only path
        run_cmd.validate_only(None)

        # Then: the Runner scans the directories the resolved data root owns
        assert constructed == [
            {
                "root": isolated_root,
                "inputdata_path": isolated_root / "inputdata",
                "unpacked_dir_path": isolated_root / "temp",
            },
        ]

    def test_validate_only_without_flow_exits_3__tc_cli_run_ep_011(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        result = cli_runner.invoke(app, ["run", "legacy_target::attr", "--validate-only"])

        assert result.exit_code == 3


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
