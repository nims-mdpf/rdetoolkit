"""Tests for ``rdetoolkit nodes`` (list/describe/lint) (Session E1,
TC-CLI-NODES-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e1.md
Conflicts #4-#9, Known Traps 6-9.

Registry-isolation note (tdd-enforcer resolution of a gap not explicitly
closed by session_e1.md's Conflict #7): ``core/registry.py`` has no reset
function and persists for the whole pytest process (Conflict #7). Every
``@node``/``@flow`` fixture defined WITHOUT an explicit ``id=`` inside a
test method automatically gets a ``<locals>``-qualified default id, which
``nodes lint``'s E2005 check (Conflict #7's own precedent) will flag --
meaning essentially every in-process test in this file permanently "dirties"
the shared registry for the rest of the pytest session. TC-CLI-NODES-EP-006
and TC-CLI-NODES-EP-010 require a CLEAN (zero-violation) registry to make a
meaningful assertion, which is unachievable in-process once any other test
in this file (or collected before it) has run. These two cases are
therefore written as subprocess-isolated invocations (a fresh Python
interpreter, per-test) rather than via the in-process ``typer.testing.
CliRunner`` used by every other case in this file -- the only reliable way
to observe a genuinely empty/clean registry. All other list/describe/lint
cases only assert PRESENCE of specific ids, never absence or an exact
count, per Conflict #7's own instruction.

Binding API-shape pin: ``rdetoolkit.cli.nodes_cmd.find_duplicate_node_ids
(specs: Sequence[NodeSpec]) -> Sequence[str]`` is a pure function (Conflict
#5) checked directly by TC-CLI-NODES-UNIT-001 against hand-built
``NodeSpec`` instances -- this exact name/signature is this file's
contract for that helper (session_e1.md's Conflict #5 mandates the
pattern but does not itself pin a name).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.types import InputPaths

_NODE_SPEC_FIELDS = {
    "id",
    "name",
    "input_schema",
    "output_schema",
    "tags",
    "version",
    "idempotent",
    "source_location",
}


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _run_isolated_lint(register_snippet: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``rdetoolkit nodes lint`` in a brand-new Python process whose
    registry contains only what ``register_snippet`` registers (or nothing
    at all, for an empty snippet) -- see this module's docstring for why
    in-process isolation is not achievable here."""
    script = textwrap.dedent(
        f"""
        import sys
        from rdetoolkit.core.node import node
        from rdetoolkit.core.flow import flow
        from rdetoolkit.types import InputPaths
        {textwrap.indent(textwrap.dedent(register_snippet), "        ")}
        from rdetoolkit.cli.app import app
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["nodes", "lint"])
        sys.stdout.write(result.output)
        sys.exit(result.exit_code)
        """,
    )
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60, check=False)


class TestNodesList:
    """TC-CLI-NODES-EP-001/002, TC-CLI-NODES-BV-001 (list half)."""

    def test_list_shows_locally_registered_node_id__tc_cli_nodes_ep_001(self, cli_runner: CliRunner) -> None:
        @node
        def _fixture_node_ep001(paths: InputPaths) -> None:
            return None

        result = cli_runner.invoke(app, ["nodes", "list"])

        assert result.exit_code == 0
        assert _fixture_node_ep001.__node_spec__.id in result.output

    def test_list_json_is_valid_json__tc_cli_nodes_ep_002(self, cli_runner: CliRunner) -> None:
        @node
        def _fixture_node_ep002(paths: InputPaths) -> None:
            return None

        result = cli_runner.invoke(app, ["nodes", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        ids = {entry["id"] for entry in data}
        assert _fixture_node_ep002.__node_spec__.id in ids

    def test_list_does_not_crash_with_no_new_entries__tc_cli_nodes_bv_001(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["nodes", "list"])

        assert result.exit_code == 0


class TestNodesDescribe:
    """TC-CLI-NODES-EP-003/004/005."""

    def test_describe_shows_all_nodespec_fields__tc_cli_nodes_ep_003(self, cli_runner: CliRunner) -> None:
        @node(tags=["t1"], version="1.2.3", idempotent=True)
        def _fixture_node_ep003(paths: InputPaths, extra: int = 3) -> str:
            return "x"

        node_id = _fixture_node_ep003.__node_spec__.id
        result = cli_runner.invoke(app, ["nodes", "describe", node_id])

        assert result.exit_code == 0
        for field_name in _NODE_SPEC_FIELDS:
            assert field_name in result.output, f"describe output missing NodeSpec field {field_name!r}"

    def test_describe_json_round_trips_with_full_field_set__tc_cli_nodes_ep_004(self, cli_runner: CliRunner) -> None:
        @node
        def _fixture_node_ep004(paths: InputPaths) -> None:
            return None

        node_id = _fixture_node_ep004.__node_spec__.id
        result = cli_runner.invoke(app, ["nodes", "describe", node_id, "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert set(data.keys()) == _NODE_SPEC_FIELDS
        assert data["id"] == node_id

    def test_describe_unknown_id_exits_3__tc_cli_nodes_ep_005(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["nodes", "describe", "definitely.not.a.registered.node.id.e1"])

        assert result.exit_code == 3


class TestNodesLintCleanRegistry:
    """TC-CLI-NODES-EP-006, TC-CLI-NODES-EP-010: zero-violation and
    advisory-only cases -- subprocess-isolated, see module docstring."""

    def test_clean_registry_exits_0_zero_violations__tc_cli_nodes_ep_006(self) -> None:
        register_snippet = """
            @node(id="isolated_clean_node_ep006")
            def clean_node(paths: InputPaths) -> None:
                return None

            @flow(id="isolated_clean_flow_ep006")
            def clean_flow(paths: InputPaths) -> None:
                clean_node(paths)
        """

        proc = _run_isolated_lint(register_snippet)

        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_recommended_name_deviation_is_advisory_only__tc_cli_nodes_ep_010(self) -> None:
        # Fully annotated but non-canonical parameter name ("p" instead of
        # "paths") -- advisory-only, never a lint violation (R1).
        register_snippet = """
            @node(id="isolated_advisory_node_ep010")
            def advisory_node(p: InputPaths) -> None:
                return None
        """

        proc = _run_isolated_lint(register_snippet)

        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_advisory_output_never_raises_e2002_or_e2004__tc_cli_nodes_ep_010_negative_guard(self) -> None:
        register_snippet = """
            @node(id="isolated_advisory_node_ep010b")
            def advisory_node(p: InputPaths) -> None:
                return None
        """

        proc = _run_isolated_lint(register_snippet)

        combined = proc.stdout + proc.stderr
        assert "2002" not in combined
        assert "2004" not in combined


class TestNodesLintViolations:
    """TC-CLI-NODES-EP-007/008/009: each violation kind, in-process (only
    presence of a violation is asserted -- see module docstring on why
    "exit 3" assertions are safe without isolation, while "exit 0"
    assertions are not)."""

    def test_missing_annotation_is_a_violation__tc_cli_nodes_ep_007(self, cli_runner: CliRunner) -> None:
        @node
        def _fixture_node_ep007(x) -> None:  # noqa: ANN001
            return None

        result = cli_runner.invoke(app, ["nodes", "lint"])

        assert result.exit_code == 3
        assert _fixture_node_ep007.__node_spec__.id in result.output

    def test_unstable_id_e2005_is_a_violation__tc_cli_nodes_ep_008(self, cli_runner: CliRunner) -> None:
        @node
        def _fixture_node_ep008(paths: InputPaths) -> None:
            return None

        node_id = _fixture_node_ep008.__node_spec__.id
        assert "<locals>" in node_id, "sanity check: a nested function's default id must contain <locals>"

        result = cli_runner.invoke(app, ["nodes", "lint"])

        assert result.exit_code == 3
        assert node_id in result.output

    def test_duplicate_reserved_annotation_e2006_is_a_violation__tc_cli_nodes_ep_009(self, cli_runner: CliRunner) -> None:
        @flow
        def _fixture_flow_ep009(paths: InputPaths, paths2: InputPaths) -> None:
            return None

        result = cli_runner.invoke(app, ["nodes", "lint"])

        assert result.exit_code == 3
        assert "InputPaths" in result.output


class TestFindDuplicateNodeIdsPureFunction:
    """TC-CLI-NODES-UNIT-001 (Conflict #5): the underlying E2001 detector is
    testable only as a pure function against hand-built NodeSpec instances
    -- the live registry structurally cannot produce a duplicate (register_
    node already raises RdeRegistryError(2001) synchronously)."""

    def test_detects_duplicate_id_in_hand_built_specs__tc_cli_nodes_unit_001(self) -> None:
        from rdetoolkit.cli.nodes_cmd import find_duplicate_node_ids
        from rdetoolkit.core.node import NodeSpec

        def _spec(node_id: str, name: str) -> NodeSpec:
            return NodeSpec(
                id=node_id,
                name=name,
                input_schema={},
                output_schema=(),
                tags=(),
                version="0.0.0",
                idempotent=False,
                source_location=f"dummy:{name}",
            )

        specs = (_spec("dup-id", "a"), _spec("dup-id", "b"), _spec("unique-id", "c"))

        result = find_duplicate_node_ids(specs)

        assert set(result) == {"dup-id"}

    def test_no_duplicates_returns_empty__tc_cli_nodes_unit_001_negative(self) -> None:
        from rdetoolkit.cli.nodes_cmd import find_duplicate_node_ids
        from rdetoolkit.core.node import NodeSpec

        def _spec(node_id: str, name: str) -> NodeSpec:
            return NodeSpec(
                id=node_id,
                name=name,
                input_schema={},
                output_schema=(),
                tags=(),
                version="0.0.0",
                idempotent=False,
                source_location=f"dummy:{name}",
            )

        specs = (_spec("a", "a"), _spec("b", "b"))

        result = find_duplicate_node_ids(specs)

        assert len(result) == 0


class TestNodesLintTemplateExtension:
    """TC-CLI-NODES-EP-011..013 (Session F2, Conflict #8, Known Traps
    #1/#2): ``nodes lint --module <dotted>`` catches E2101-E2105
    import-time ``RdeRegistryError``s raised while loading a violating
    ``ProcessingTemplate`` module and reports them as clean lint messages
    (never a raw traceback); W1101 ``TemplateSelfStateUsage`` is a
    genuinely new, lint-time-only advisory check via source inspection.
    Fixture modules: ``tests/v2/templates/fixtures/e2101_violation_template.py``
    (import-time E2101) and ``tests/v2/templates/fixtures/self_state_template.py``
    (imports cleanly; W1101 only, via ``inspect.getsource``)."""

    def test_lint_module_with_e2101_violation_reports_clean_message_no_traceback__tc_cli_nodes_ep_011(
        self,
        cli_runner: CliRunner,
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["nodes", "lint", "--module", "tests.v2.templates.fixtures.e2101_violation_template"],
        )

        assert result.exit_code == 3
        # NOTE: do not assert on the bare substring "2101" -- the fixture
        # module's own dotted path ("e2101_violation_template") contains
        # that digit sequence, so a generic, un-caught ImportError from
        # load_modules() (pre-implementation: "No module named
        # 'rdetoolkit.templates'") would trivially satisfy a bare "2101"
        # check without the E2101 catch-and-report logic existing at all.
        # Require the catalog NAME instead, which cannot leak from the
        # module path, and require the generic import-failure prefix to be
        # ABSENT -- proving the new try/except replaces that message with
        # a catalogued diagnostic rather than merely surfacing the raw
        # import failure text.
        assert "TemplateSlotMissing" in result.output, result.output
        assert "Unable to import module" not in result.output, result.output
        assert "Traceback (most recent call last)" not in result.output

    def test_lint_module_with_self_state_usage_reports_w1101_advisory__tc_cli_nodes_ep_012(
        self,
        cli_runner: CliRunner,
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["nodes", "lint", "--module", "tests.v2.templates.fixtures.self_state_template"],
        )

        assert result.exit_code == 3
        assert "1101" in result.output
        assert "Traceback (most recent call last)" not in result.output

    def test_lint_e2101_wrapper_does_not_swallow_pre_existing_e2006_check__tc_cli_nodes_ep_013(
        self,
        cli_runner: CliRunner,
    ) -> None:
        # Given: a pre-existing E2006 violation (duplicate reserved-type
        # annotation) registered in-process, exactly like TC-CLI-NODES-EP-009.
        @flow
        def _fixture_flow_ep013(paths: InputPaths, paths2: InputPaths) -> None:
            return None

        # When: lint also loads a template-clean --module (self_state_template
        # imports without error; only its W1101 advisory should add to the
        # message list) -- the new E2101-catching try/except around
        # load_modules() must not shadow or swallow the existing,
        # already-registered E2006 check.
        result = cli_runner.invoke(
            app,
            ["nodes", "lint", "--module", "tests.v2.templates.fixtures.self_state_template"],
        )

        assert result.exit_code == 3
        assert "InputPaths" in result.output  # the pre-existing E2006 check must still fire
        assert "1101" in result.output  # AND the new W1101 advisory must still fire
