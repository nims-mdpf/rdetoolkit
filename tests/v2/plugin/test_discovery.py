"""Session F3 plugin discovery acceptance tests.

EP table
========

==========================  ========================  =====================================  ====================
API                         Partition                 Expected                               Test ID
==========================  ========================  =====================================  ====================
``discover_plugins``        valid three-kind plugin   provenance and handlers returned       TC-PLUGIN-EP-001
``discover_plugins``        repeated discovery        identical result; no duplicate error   TC-PLUGIN-EP-002
``discover_plugins``        load failure              remediation warning and skip            TC-PLUGIN-EP-003
``discover_plugins``        invalid handler contract  remediation warning and skip            TC-PLUGIN-EP-004
plugin public surface       forbidden hooks           no hook registration API                TC-PLUGIN-EP-005
plugin CLI                  valid plugin               all three discovery commands expose it TC-PLUGIN-EP-006
plugin CLI                  broken plugin              exit zero and warn                     TC-PLUGIN-EP-007
``discover_plugins``        provider pre-imported      provenance remains non-empty            TC-PLUGIN-EP-008
plugin CLI                  module loaded before scan  plugin node remains listed              TC-PLUGIN-EP-009
==========================  ========================  =====================================  ====================

BV table
========

======================  ==================  ============================  ====================
API                     Boundary            Expected                      Test ID
======================  ==================  ============================  ====================
``discover_plugins``    zero entry points   empty tuple                   TC-PLUGIN-BV-001
``FormatHandler``       two extensions      order and values preserved    TC-PLUGIN-BV-002
======================  ==================  ============================  ====================
"""

from __future__ import annotations

import importlib
import json
import sys
from importlib.metadata import EntryPoint
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.core import registry as node_registry
from rdetoolkit.templates import registry as template_registry

PLUGIN_MODULE = "tests.v2.fixtures.plugin_pkg.demo"


@pytest.fixture(autouse=True)
def isolate_plugin_registries() -> Any:
    """Restore process-global registries and fixture imports after each test."""
    node_maps = tuple(
        getattr(node_registry, name).copy()
        for name in ("_node_specs", "_node_wrappers", "_node_functions")
    )
    template_maps = tuple(
        getattr(template_registry, name).copy()
        for name in ("_template_specs", "_template_classes")
    )
    concrete = list(getattr(template_registry, "_concrete_classes"))
    sys.modules.pop(PLUGIN_MODULE, None)
    yield
    for name, saved in zip(
        ("_node_specs", "_node_wrappers", "_node_functions"),
        node_maps,
        strict=True,
    ):
        target = getattr(node_registry, name)
        target.clear()
        target.update(saved)
    for name, saved in zip(("_template_specs", "_template_classes"), template_maps, strict=True):
        target = getattr(template_registry, name)
        target.clear()
        target.update(saved)
    getattr(template_registry, "_concrete_classes").clear()
    getattr(template_registry, "_concrete_classes").extend(concrete)
    sys.modules.pop(PLUGIN_MODULE, None)


def _entry_point(name: str = "fixture-plugin") -> EntryPoint:
    return EntryPoint(name=name, value=PLUGIN_MODULE, group="rdetoolkit.plugins")


def _patch_entries(monkeypatch: pytest.MonkeyPatch, *entries: EntryPoint) -> None:
    discovery = importlib.import_module("rdetoolkit.plugin.discovery")
    monkeypatch.setattr(discovery.metadata, "entry_points", lambda *, group: entries)
    cache = discovery.__dict__.get("_discovered")
    if isinstance(cache, dict):
        cache.clear()


class TestPluginDiscovery:
    def test_discovers_nodes_formats_and_templates__tc_plugin_ep_001_bv_002(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-PLUGIN-EP-001/BV-002: one plugin exposes exactly three supported kinds."""
        # Given: a module entry point declaring a node, template, and two-extension handler
        _patch_entries(monkeypatch, _entry_point())
        from rdetoolkit.plugin import discover_plugins

        # When: plugin discovery loads the entry point
        plugins = discover_plugins()

        # Then: provider introspection and declarative handlers retain provenance
        assert len(plugins) == 1
        plugin = plugins[0]
        assert plugin.name == "fixture-plugin"
        assert plugin.node_ids == ("fixture.plugin.read",)
        assert len(plugin.template_ids) == 1
        assert plugin.template_ids[0].endswith("FixtureTemplate")
        assert plugin.format_handlers[0].extensions == (".fixture", ".fx")

    def test_preimported_provider_retains_provenance__tc_plugin_ep_008(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Given: the provider has already been imported and registered before discovery
        importlib.import_module(PLUGIN_MODULE)
        _patch_entries(monkeypatch, _entry_point())
        from rdetoolkit.plugin import discover_plugins

        # When: discovery loads the already-cached module
        plugin = discover_plugins()[0]

        # Then: provenance comes from the provider object rather than registry deltas
        assert plugin.node_ids == ("fixture.plugin.read",)
        assert any(template_id.endswith("FixtureTemplate") for template_id in plugin.template_ids)

    def test_discovery_is_idempotent__tc_plugin_ep_002(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-PLUGIN-EP-002: repeated discovery returns the same provenance."""
        # Given: a valid plugin entry point
        _patch_entries(monkeypatch, _entry_point())
        from rdetoolkit.plugin import discover_plugins

        # When: discovery is performed twice
        first = discover_plugins()
        second = discover_plugins()

        # Then: the result is stable and duplicate registration is avoided
        assert second == first

    def test_load_failure_warns_with_remediation_and_skips__tc_plugin_ep_003(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """TC-PLUGIN-EP-003: a broken third-party package cannot break discovery."""
        # Given: an entry point whose module cannot be imported
        broken = EntryPoint(
            name="broken-plugin",
            value="tests.v2.fixtures.plugin_pkg.does_not_exist",
            group="rdetoolkit.plugins",
        )
        _patch_entries(monkeypatch, broken)
        from rdetoolkit.plugin import discover_plugins

        # When: discovery attempts to load it
        plugins = discover_plugins()

        # Then: it is skipped and the warning tells the user what to do next
        assert plugins == ()
        warning = capsys.readouterr().err
        assert "broken-plugin" in warning
        assert "Remediation:" in warning

    def test_invalid_handler_warns_and_skips__tc_plugin_ep_004(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """TC-PLUGIN-EP-004: incompatible FORMAT_HANDLERS is rejected safely."""
        # Given: an entry point object with a malformed handler declaration
        bad_object = SimpleNamespace(FORMAT_HANDLERS=("not-a-handler",))

        class _BadEntryPoint:
            name = "invalid-plugin"
            value = "invalid:plugin"

            def load(self) -> object:
                return bad_object

        discovery = importlib.import_module("rdetoolkit.plugin.discovery")
        monkeypatch.setattr(discovery.metadata, "entry_points", lambda *, group: (_BadEntryPoint(),))

        # When: discovery validates the declaration
        plugins = discovery.discover_plugins()

        # Then: the entire incompatible plugin is skipped with remediation
        assert plugins == ()
        warning = capsys.readouterr().err
        assert "invalid-plugin" in warning
        assert "Remediation:" in warning

    def test_public_surface_has_no_lifecycle_hooks__tc_plugin_ep_005(self) -> None:
        """TC-PLUGIN-EP-005: plugins cannot register Runner lifecycle callbacks."""
        # Given: the public plugin module
        import rdetoolkit.plugin as plugin

        # When: its explicitly exported names are inspected
        exported = set(plugin.__all__)

        # Then: only the three-kind declarative discovery contract is exposed
        assert exported == {"DiscoveredPlugin", "FormatHandler", "discover_plugins"}
        assert not exported & {"on_run", "on_tile", "on_start", "on_finish", "register_hook", "add_hook"}

    def test_empty_entry_point_set_returns_empty_tuple__tc_plugin_bv_001(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-PLUGIN-BV-001: an installation with no plugins is valid."""
        # Given: no rdetoolkit plugin entry points
        _patch_entries(monkeypatch)
        from rdetoolkit.plugin import discover_plugins

        # When/Then: discovery returns an immutable empty collection
        assert discover_plugins() == ()


class TestPluginCli:
    def test_commands_surface_all_plugin_kinds__tc_plugin_ep_006(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-PLUGIN-EP-006: formats, nodes, and templates expose plugin entries."""
        # Given: a valid three-kind plugin
        _patch_entries(monkeypatch, _entry_point())
        runner = CliRunner()

        # When: each plugin-aware listing command is invoked
        formats_result = runner.invoke(app, ["formats", "list", "--json"])
        nodes_result = runner.invoke(app, ["nodes", "list", "--plugin", "--json"])
        templates_result = runner.invoke(app, ["templates", "list", "--json"])

        # Then: each command succeeds and reports plugin provenance
        assert formats_result.exit_code == 0, formats_result.output
        assert json.loads(formats_result.output)[0]["plugin"] == "fixture-plugin"
        assert nodes_result.exit_code == 0, nodes_result.output
        node_entries = json.loads(nodes_result.output)
        assert [(entry["id"], entry["plugin"]) for entry in node_entries] == [
            ("fixture.plugin.read", "fixture-plugin"),
        ]
        assert templates_result.exit_code == 0, templates_result.output
        assert any(entry["id"].endswith("FixtureTemplate") for entry in json.loads(templates_result.output))

    def test_broken_plugin_cli_warns_and_exits_zero__tc_plugin_ep_007(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-PLUGIN-EP-007: plugin CLI remains available when one package is broken."""
        # Given: one broken entry point
        broken = EntryPoint(
            name="broken-plugin",
            value="tests.v2.fixtures.plugin_pkg.missing",
            group="rdetoolkit.plugins",
        )
        _patch_entries(monkeypatch, broken)

        # When: a plugin-aware command runs
        result = CliRunner().invoke(app, ["formats", "list"])

        # Then: it warns, skips, and succeeds
        assert result.exit_code == 0
        assert "broken-plugin" in result.output
        assert "Remediation:" in result.output

    def test_nodes_list_plugin_after_module_preload__tc_plugin_ep_009(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Given: the CLI will preload the same provider module before plugin discovery
        _patch_entries(monkeypatch, _entry_point())

        # When: exercising the review-reported load_modules -> discover_plugins order
        result = CliRunner().invoke(
            app,
            ["nodes", "list", "--plugin", "--module", PLUGIN_MODULE, "--json"],
        )

        # Then: the provider node remains attributed and visible
        assert result.exit_code == 0, result.output
        entries = json.loads(result.output)
        assert [(entry["id"], entry["plugin"]) for entry in entries] == [
            ("fixture.plugin.read", "fixture-plugin"),
        ]
