"""Tests for ``rdetoolkit templates`` (list/describe) (Session F2,
TC-CLI-TEMPLATES-*).

Written before implementation (TDD Red phase). Authority:
local/develop/v2/tasks/session_f2.md Conflicts #1, #6; Design.md v2.1
§5.2.4, §9.3. Mirrors ``tests/v2/cli/test_cli_nodes.py``'s shape/CliRunner
conventions.

Binding API-shape pins asserted by this file (precision standard):
- ``rdetoolkit templates list [--json] [--module <dotted>]...`` and
  ``rdetoolkit templates describe <name> [--json] [--module <dotted>]...``
  exist as a new ``templates`` sub-app, mirroring ``nodes_cmd.py``'s
  ``--module`` convention exactly (repeatable option, no filesystem scan --
  a caller must ``import`` the providing module first, either inline
  before invoking the CLI in-process, or via ``--module``).
- The Template Registry holds ONLY depth-1 (skeleton) entries -- a depth-2
  concrete user class is NEVER listed, even when its module has been
  ``--module``-imported (Conflict #6's scope guard, Verification command
  #11, exercised here as an automated regression test).
- Exit-code contract matches E1/E2's existing CLI convention: 0 success
  (including an empty list -- absence of registrations is not an error,
  mirroring ``nodes list``'s precedent), 3 usage error (unknown
  ``describe`` name).
- ``templates list --json`` entries carry an ``"id"`` key (same minimal
  contract every other ``--json`` list command in this codebase already
  provides -- ``nodes list --json``, mirrored here since ``describe``
  needs some literal id string that ``list`` must supply).
- ``describe``'s exact ``TemplateSpec`` field names are intentionally NOT
  pinned here (Conflict #6 leaves the dataclass shape to Codex's choice,
  "mirror NodeSpec's spirit") -- this file only asserts that declared slot
  and hook NAMES are discoverable in ``describe``'s output, both text and
  ``--json`` forms.

Fixture module: ``tests.v2.templates.fixtures.xrd_like_template``
(``DemoSkeletonTemplate`` depth-1 / ``DemoConcreteProcessing`` depth-2),
real file-backed classes as required by ``--module`` resolution
(``importlib.import_module``, no file-path support).
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app

FIXTURE_MODULE = "tests.v2.templates.fixtures.xrd_like_template"


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


class TestTemplatesList:
    """TC-CLI-TEMPLATES-EP-001..003, TC-CLI-TEMPLATES-BV-001/002."""

    def test_list_shows_locally_defined_skeleton__tc_cli_templates_ep_001(self, cli_runner: CliRunner) -> None:
        # Given: a depth-1 skeleton defined inline (registered at
        # class-definition time, mirroring nodes list's in-process
        # convention -- no --module needed for a class already resident in
        # this process).
        from typing import final

        from rdetoolkit.templates import ProcessingTemplate, slot
        from rdetoolkit.types import InputPaths

        class _LocalSkeletonEp001(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        # When
        result = cli_runner.invoke(app, ["templates", "list"])

        # Then
        assert result.exit_code == 0
        assert "_LocalSkeletonEp001" in result.output

    def test_list_json_is_valid_json_and_contains_id__tc_cli_templates_ep_002(self, cli_runner: CliRunner) -> None:
        from typing import final

        from rdetoolkit.templates import ProcessingTemplate, slot
        from rdetoolkit.types import InputPaths

        class _LocalSkeletonEp002(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        result = cli_runner.invoke(app, ["templates", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        ids = {entry["id"] for entry in data}
        assert any("_LocalSkeletonEp002" in entry_id for entry_id in ids)

    def test_list_via_module_option_shows_fixture_skeleton__tc_cli_templates_ep_003(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["templates", "list", "--module", FIXTURE_MODULE])

        assert result.exit_code == 0
        assert "DemoSkeletonTemplate" in result.output

    def test_list_never_shows_depth2_user_class_even_via_module__tc_cli_templates_bv_001(
        self,
        cli_runner: CliRunner,
    ) -> None:
        # Regression-testable form of Verification command #11's manual
        # scope-guard check (Conflict #6): the depth-2 concrete class must
        # never appear, even though its module was --module-imported.
        result = cli_runner.invoke(app, ["templates", "list", "--module", FIXTURE_MODULE])

        assert result.exit_code == 0
        assert "DemoConcreteProcessing" not in result.output

    def test_list_does_not_crash_with_no_new_registrations__tc_cli_templates_bv_002(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["templates", "list"])

        assert result.exit_code == 0


class TestTemplatesDescribe:
    """TC-CLI-TEMPLATES-EP-004/005, TC-CLI-TEMPLATES-EP-006."""

    def _fixture_template_id(self, cli_runner: CliRunner) -> str:
        list_result = cli_runner.invoke(app, ["templates", "list", "--module", FIXTURE_MODULE, "--json"])
        assert list_result.exit_code == 0, list_result.output
        entries = json.loads(list_result.output)
        matches = [entry for entry in entries if "DemoSkeletonTemplate" in entry["id"]]
        assert matches, f"expected a DemoSkeletonTemplate entry in {entries!r}"
        return str(matches[0]["id"])

    def test_describe_shows_declared_slot_and_hook_names__tc_cli_templates_ep_004(self, cli_runner: CliRunner) -> None:
        template_id = self._fixture_template_id(cli_runner)

        result = cli_runner.invoke(app, ["templates", "describe", template_id])

        assert result.exit_code == 0
        assert "read" in result.output
        assert "extract_meta" in result.output
        assert "transform" in result.output

    def test_describe_json_flag_is_valid_json_and_contains_slot_names__tc_cli_templates_ep_005(
        self,
        cli_runner: CliRunner,
    ) -> None:
        template_id = self._fixture_template_id(cli_runner)

        result = cli_runner.invoke(app, ["templates", "describe", template_id, "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        rendered = json.dumps(data)
        assert "read" in rendered
        assert "extract_meta" in rendered

    def test_describe_unknown_name_exits_3__tc_cli_templates_ep_006(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["templates", "describe", "definitely.not.a.registered.template.f2"])

        assert result.exit_code == 3
