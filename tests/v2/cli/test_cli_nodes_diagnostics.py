"""Node lint JSON contract; EP/BV cases: docs/usage/diagnostics-lint.en.md."""
from __future__ import annotations

import inspect
import json
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.cli import nodes_cmd
from rdetoolkit.core.node import NodeSpec
from rdetoolkit.core.registry import FlowSpec
from rdetoolkit.errors import ERROR_CATALOG, RdeRegistryError


@pytest.fixture
def clean_lint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate inspected registries without resetting live runtime state."""
    from rdetoolkit.templates import registry as templates
    monkeypatch.setattr(nodes_cmd.registry, "list_nodes", lambda: ())
    monkeypatch.setattr(nodes_cmd.registry, "list_flows", lambda: ())
    monkeypatch.setattr(nodes_cmd.registry, "find_unstable_node_ids", lambda: ())
    monkeypatch.setattr(templates, "list_concrete_templates", lambda: ())


def invoke_json(*args: str):
    return CliRunner().invoke(app, ["nodes", "lint", "--json", *args])


def spec(node_id: str) -> NodeSpec:
    return NodeSpec(node_id, node_id, {}, (), (), "1", False, "project:callable")


def test_empty_registry__lint_001(clean_lint) -> None:
    # Given: an empty registry.
    # When: requesting the JSON contract.
    result = invoke_json()
    # Then: zero findings are represented explicitly.
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["schema_version"] == "1"
    assert data["status"] == "passed"
    assert data["diagnostics"] == []


def test_missing_annotation_and_explicit_any__lint_002(clean_lint, monkeypatch) -> None:
    # Given: one missing parameter annotation and one explicit Any.
    def fn(missing, present: Any) -> None:
        pass
    monkeypatch.setattr(nodes_cmd.registry, "list_nodes", lambda: (spec("sample"),))
    monkeypatch.setattr(nodes_cmd.registry, "get_node_function", lambda _: fn)
    # When: linting the signature.
    result = invoke_json()
    # Then: only the absent annotation has the documented non-catalog identifier.
    assert result.exit_code == 3
    findings = json.loads(result.stdout)["diagnostics"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["name"] == "MissingTypeAnnotation"
    assert finding["code"] is None
    assert finding["subject"] == "sample.missing"
    assert finding["remediation"]
    assert finding["severity"] == "error"


def test_unstable_node_id__lint_003(clean_lint, monkeypatch) -> None:
    # Given: an unstable node ID.
    monkeypatch.setattr(nodes_cmd.registry, "find_unstable_node_ids", lambda: ("project.<locals>.fn",))
    # When: linting it.
    result = invoke_json()
    # Then: the existing catalog is authoritative.
    finding = json.loads(result.stdout)["diagnostics"][0]
    assert result.exit_code == 3
    assert finding["code"] == 2005
    assert finding["name"] == ERROR_CATALOG[2005].name
    assert finding["remediation"] == ERROR_CATALOG[2005].remediation


def test_duplicate_node_ids__lint_004(clean_lint, monkeypatch) -> None:
    # Given: duplicate specs (the live registry rejects these during import).
    monkeypatch.setattr(nodes_cmd.registry, "list_nodes", lambda: (spec("dup"), spec("dup")))
    monkeypatch.setattr(nodes_cmd.registry, "get_node_function", lambda _: lambda: None)
    # When: linting the specs.
    result = invoke_json()
    # Then: the duplicate has E2001 rather than a message to parse.
    assert result.exit_code == 3
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == 2001


def test_duplicate_reserved_annotation__lint_005(clean_lint, monkeypatch) -> None:
    # Given: a flow with duplicate reserved annotations.
    from rdetoolkit.types import InputPaths
    monkeypatch.setattr(nodes_cmd.registry, "list_flows", lambda: (FlowSpec("pipeline", "pipeline", "project:pipeline"),))
    monkeypatch.setattr(nodes_cmd.registry, "get_flow_function", lambda _: lambda: None)
    monkeypatch.setattr(nodes_cmd, "find_duplicate_reserved_annotations", lambda _: {InputPaths: ["left", "right"]})
    # When: linting the flow signature.
    result = invoke_json()
    # Then: E2006 identifies the affected flow.
    finding = json.loads(result.stdout)["diagnostics"][0]
    assert result.exit_code == 3
    assert finding["code"] == 2006
    assert finding["subject"] == "pipeline"


@pytest.mark.parametrize("code", [2001, 2101, 2102, 2103, 2104, 2105])
def test_catalog_import_failure__lint_006_011(clean_lint, monkeypatch, code) -> None:
    # Given: import-time registry validation fails.
    def failing_import(name):
        raise RdeRegistryError(code=code, name=ERROR_CATALOG[code].name, message="invalid declaration")
    monkeypatch.setattr(nodes_cmd, "import_project_module", failing_import)
    # When: requesting structured lint.
    result = invoke_json("--module", "project")
    # Then: catalog failures remain structured and never become raw tracebacks.
    assert result.exit_code == 3
    finding = json.loads(result.stdout)["diagnostics"][0]
    assert finding["code"] == code
    assert finding["name"] == ERROR_CATALOG[code].name
    assert "Traceback" not in result.stdout


def test_warning_only_exit_and_severity__lint_007(clean_lint, monkeypatch) -> None:
    # Given: a template method uses state absent from __init__.
    from rdetoolkit.templates import registry as templates
    def method(self) -> None:
        pass
    method.__node_spec__ = object()
    template = type("Template", (), {"slot": method})
    monkeypatch.setattr(templates, "list_concrete_templates", lambda: (template,))
    monkeypatch.setattr(nodes_cmd, "_self_attributes", lambda fn: {"hidden"} if fn is method else set())
    # When: linting the template.
    result = invoke_json()
    # Then: warnings preserve historical exit 3, while severity is explicit.
    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["status"] == "warning"
    finding = data["diagnostics"][0]
    assert finding["code"] == 1101
    assert finding["severity"] == "warning"
    assert finding["name"] == "TemplateSelfStateUsage"
    assert finding["remediation"]


@pytest.mark.parametrize("failure", [ModuleNotFoundError("absent"), ValueError("arbitrary user data")])
def test_module_import_failure__lint_008(clean_lint, monkeypatch, failure) -> None:
    # Given: a missing or broken module.
    def failing_import(name):
        raise failure
    monkeypatch.setattr(nodes_cmd, "import_project_module", failing_import)
    # When: importing for JSON lint.
    result = invoke_json("--module", "project")
    # Then: operational failure is distinguishable without inventing a code.
    assert result.exit_code == 3
    finding = json.loads(result.stdout)["diagnostics"][0]
    assert finding["name"] == "ModuleImportFailed"
    assert finding["code"] is None
    assert finding["subject"] == "project"
    assert "arbitrary user data" not in result.stdout


def test_import_stdout_utf8_and_side_effect__lint_009(clean_lint, monkeypatch, tmp_path) -> None:
    # Given: imports can print and write files.
    marker = tmp_path / "side-effect"
    def noisy_import(name):
        print("import notice 日本語")
        marker.write_text("executed", encoding="utf-8")
    monkeypatch.setattr(nodes_cmd, "import_project_module", noisy_import)
    # When: requesting machine output.
    result = invoke_json("--module", "project")
    # Then: JSON-only stdout coexists with documented import side effects.
    assert result.exit_code == 0
    assert json.loads(result.stdout)["diagnostics"] == []
    assert "import notice 日本語" in result.stderr
    assert marker.read_text(encoding="utf-8") == "executed"


def test_deterministic_order_and_utf8__lint_010(clean_lint, monkeypatch) -> None:
    # Given: registry order is independent from stable diagnostic order.
    ids = ["z.<locals>.日本語", "a.<locals>.fn"]
    monkeypatch.setattr(nodes_cmd.registry, "find_unstable_node_ids", lambda: tuple(ids))
    # When: registration order changes.
    first = invoke_json()
    ids.reverse()
    second = invoke_json()
    # Then: the serialized findings are stable and UTF-8.
    assert first.exit_code == second.exit_code == 3
    assert first.stdout == second.stdout
    assert "日本語" in first.stdout
    assert [item["subject"] for item in json.loads(first.stdout)["diagnostics"]] == ids


def test_text_missing_annotation_unchanged__lint_012(clean_lint, monkeypatch) -> None:
    # Given: the existing text-mode check.
    def fn(value) -> None:
        pass
    monkeypatch.setattr(nodes_cmd.registry, "list_nodes", lambda: (spec("sample"),))
    monkeypatch.setattr(nodes_cmd.registry, "get_node_function", lambda _: fn)
    # When: no output flag is supplied.
    result = CliRunner().invoke(app, ["nodes", "lint"])
    # Then: human-readable message and exit status are preserved.
    assert result.exit_code == 3
    assert result.stdout == "Missing type annotation: sample.value\n"


def test_text_import_failure_unchanged__lint_012(clean_lint, monkeypatch) -> None:
    # Given: a non-registry module error.
    def failing_import(name):
        raise ValueError("broken module")
    monkeypatch.setattr(nodes_cmd, "import_project_module", failing_import)
    # When: importing in text mode.
    result = CliRunner().invoke(app, ["nodes", "lint", "--module", "project"])
    # Then: the existing operational error is on stderr.
    assert result.exit_code == 3
    assert "Unable to import module project: broken module" in result.stderr


def test_text_unexpected_registry_error_propagates__lint_013(clean_lint, monkeypatch) -> None:
    # Given: a registry error outside the existing template-error handler.
    failure = RdeRegistryError(code=2001, name="DuplicateNodeId", message="duplicate")
    def failing_import(name):
        raise failure
    monkeypatch.setattr(nodes_cmd, "import_project_module", failing_import)
    # When: the existing text command imports it.
    result = CliRunner().invoke(app, ["nodes", "lint", "--module", "project"])
    # Then: the original exception contract stays intact.
    assert result.exception is failure


@pytest.mark.parametrize("failure", [OSError(), TypeError(), SyntaxError()])
def test_unavailable_template_source__lint_014(monkeypatch, failure) -> None:
    # Given: source inspection is unavailable.
    def no_source(value):
        raise failure
    monkeypatch.setattr(inspect, "getsource", no_source)
    # When: checking self attributes.
    found = nodes_cmd._self_attributes(object())
    # Then: no hidden state is fabricated.
    assert found == set()


def test_text_clean_registry__lint_001(clean_lint) -> None:
    # Given: no registered violations.
    # When: requesting default human-readable lint.
    result = CliRunner().invoke(app, ["nodes", "lint"])
    # Then: the existing success message remains unchanged.
    assert result.exit_code == 0
    assert result.stdout == "0 violations\n"


@pytest.mark.parametrize("code", [987654, "legacy-custom"])
def test_uncatalogued_registry_error__lint_008(clean_lint, monkeypatch, code) -> None:
    # Given: a third-party module raises an uncatalogued registry exception.
    def failing_import(name):
        raise RdeRegistryError(code=code, name="UnknownThirdPartyError", message="raw sensitive data")
    monkeypatch.setattr(nodes_cmd, "import_project_module", failing_import)
    # When: importing it for machine diagnostics.
    result = invoke_json("--module", "project")
    # Then: the CLI uses its documented fallback, never forwards invented codes.
    assert result.exit_code == 3
    finding = json.loads(result.stdout)["diagnostics"][0]
    assert finding["code"] is None
    assert finding["name"] == "ModuleImportFailed"
    assert "raw sensitive data" not in result.stdout


def test_source_attributes_are_observed__lint_014(monkeypatch) -> None:
    # Given: actual source references self, a bare name and another object's attribute.
    monkeypatch.setattr(inspect, "getsource", lambda _: "def method(self):\n    return self.hidden, other.attr, bare\n")
    # When: inspecting template self state.
    found = nodes_cmd._self_attributes(object())
    # Then: only the observed self attribute is reported.
    assert found == {"hidden"}


def test_catalog_import_error_omits_runtime_message__lint_008(clean_lint, monkeypatch) -> None:
    # Given: even a catalogued registry error can carry runtime secrets.
    def failing_import(name):
        raise RdeRegistryError(code=2001, name="DuplicateNodeId", message="TOPSECRET=credential")
    monkeypatch.setattr(nodes_cmd, "import_project_module", failing_import)
    # When: requesting machine-readable findings.
    result = invoke_json("--module", "project")
    # Then: only authoritative catalog wording is serialized.
    assert result.exit_code == 3
    finding = json.loads(result.stdout)["diagnostics"][0]
    assert finding["code"] == 2001
    assert finding["message"] == ERROR_CATALOG[2001].message_template
    assert "TOPSECRET" not in result.stdout
