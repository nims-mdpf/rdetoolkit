"""Tests for ``rdetoolkit flows`` (list/describe) (Session E1,
TC-CLI-FLOWS-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e1.md
Conflicts #4/#6/#7.

These commands mirror ``nodes list``/``nodes describe`` (test_cli_nodes.py)
using ``core/registry.list_flows()``/``get_flow()`` (Conflict #4's boundary
amendment for enumeration; ``get_flow`` itself already existed). No lint
counterpart exists for flows -- E2006 is checked as part of ``nodes lint``
(TC-CLI-NODES-EP-009), not a separate ``flows lint``. Every case here only
asserts PRESENCE of a locally-registered id, never an exact total count
(Conflict #7).
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.core.flow import flow
from rdetoolkit.types import InputPaths

_FLOW_SPEC_FIELDS = {"id", "name", "source_location"}


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


class TestFlowsList:
    """TC-CLI-FLOWS-EP-001/002."""

    def test_list_shows_locally_registered_flow_id__tc_cli_flows_ep_001(self, cli_runner: CliRunner) -> None:
        @flow
        def _fixture_flow_ep001(paths: InputPaths) -> None:
            return None

        result = cli_runner.invoke(app, ["flows", "list"])

        assert result.exit_code == 0
        assert _fixture_flow_ep001.__flow_spec__.id in result.output

    def test_list_json_is_valid_json__tc_cli_flows_ep_002(self, cli_runner: CliRunner) -> None:
        @flow
        def _fixture_flow_ep002(paths: InputPaths) -> None:
            return None

        result = cli_runner.invoke(app, ["flows", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        ids = {entry["id"] for entry in data}
        assert _fixture_flow_ep002.__flow_spec__.id in ids


class TestFlowsDescribe:
    """TC-CLI-FLOWS-EP-003/004/005."""

    def test_describe_shows_all_flowspec_fields__tc_cli_flows_ep_003(self, cli_runner: CliRunner) -> None:
        @flow
        def _fixture_flow_ep003(paths: InputPaths) -> None:
            return None

        flow_id = _fixture_flow_ep003.__flow_spec__.id
        result = cli_runner.invoke(app, ["flows", "describe", flow_id])

        assert result.exit_code == 0
        for field_name in _FLOW_SPEC_FIELDS:
            assert field_name in result.output, f"describe output missing FlowSpec field {field_name!r}"

    def test_describe_json_round_trips_with_full_field_set__tc_cli_flows_ep_004(self, cli_runner: CliRunner) -> None:
        @flow
        def _fixture_flow_ep004(paths: InputPaths) -> None:
            return None

        flow_id = _fixture_flow_ep004.__flow_spec__.id
        result = cli_runner.invoke(app, ["flows", "describe", flow_id, "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert set(data.keys()) == _FLOW_SPEC_FIELDS
        assert data["id"] == flow_id

    def test_describe_unknown_name_exits_3__tc_cli_flows_ep_005(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["flows", "describe", "definitely.not.a.registered.flow.id.e1"])

        assert result.exit_code == 3
