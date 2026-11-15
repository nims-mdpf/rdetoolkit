"""EP/BV contract for the shared diagnostic envelope.

EP table: empty -> passed (test_empty); warning -> warning (test_severity);
error -> failed (test_severity); mixed -> failed (test_severity);
unknown -> explicit uncatalogued (test_unknown); location -> retained (test_location);
secrets planted in errors, config and inputs -> absent from every command's stdout (test_no_secret_*).
BV table: zero findings (test_empty), arbitrary finding permutations
(test_permutations), Unicode subject (test_unicode).
"""

import json
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from rdetoolkit.report.diagnostics import diagnostic, envelope


def finding(**kwargs):
    return diagnostic(code=None, name="Example", severity="error", message="Invalid input.", remediation="Fix input.", subject="project", **kwargs)


def test_empty():
    # Given/When: no findings are reported.
    result = envelope([])
    # Then: the versioned report passes and names its format and producer.
    from rdetoolkit import __version__

    assert result == {
        "schema_version": "1",
        "format": "rdetoolkit.diagnostics",
        "producer": {"name": "rdetoolkit", "version": __version__},
        "status": "passed",
        "diagnostics": [],
        "truncated": False,
    }
    assert envelope([], command="doctor")["command"] == "doctor"


@pytest.mark.parametrize("severities,status", [(["warning"], "warning"), (["error"], "failed"), (["warning", "error"], "failed"), (["info"], "passed")])
def test_severity(severities, status):
    # Given: findings of the specified severities.
    findings = [diagnostic(code=None, name="Example", severity=s, message="m", remediation="r", subject="s") for s in severities]
    # When/Then: severity controls the status independently of command exits.
    assert envelope(findings)["status"] == status


def test_unknown():
    # Given/When: an uncatalogued finding has no integer code.
    result = finding()
    # Then: its documented symbolic name is kept.
    assert result["code"] is None
    assert result["name"] == "Example"


def test_location():
    # Given/When: a finding has an affected path and JSON pointer.
    result = finding(location={"path": "tasksupport/invoice.schema.json", "pointer": "/required"})
    # Then: optional location data remains structured.
    assert result["location"]["pointer"] == "/required"


def test_unicode():
    # Given: a diagnostic containing Unicode identifiers.
    result = envelope([finding(location={"path": "設定.json"})])
    # When/Then: serialization round-trips without ASCII escaping.
    assert "設定" in json.dumps(result, ensure_ascii=False)


@given(st.permutations(["c", "a", "b"]))
def test_permutations(subjects):
    # Given: the same findings arrive in any order.
    findings = [diagnostic(code=None, name="Example", severity="error", message="m", remediation="r", subject=s) for s in subjects]
    # When/Then: the envelope has one deterministic order.
    assert [d["subject"] for d in envelope(findings)["diagnostics"]] == ["a", "b", "c"]


@pytest.mark.parametrize("command", [["nodes", "lint", "--json"], ["doctor", "--format", "json"], ["report", "diagnose", "missing.json", "--json"]])
def test_cli_outputs_follow_published_schema(tmp_path, monkeypatch, command):
    # Given: an empty project and the published envelope schema.
    import jsonschema
    from typer.testing import CliRunner
    from rdetoolkit.cli.app import app

    schema_path = Path(__file__).resolve().parents[3] / "docs" / "usage" / "diagnostics.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    monkeypatch.chdir(tmp_path)
    # When: invoking each command's machine-readable mode.
    result = CliRunner().invoke(app, command)
    # Then: even diagnostic failures use the published JSON contract.
    assert result.exit_code in {0, 1, 3}, result.output
    jsonschema.Draft202012Validator(schema).validate(json.loads(result.stdout))


SECRET = "planted-secret-7f3a9c"


def test_no_secret_in_nodes_lint_json(tmp_path, monkeypatch):
    # Given: modules whose import errors quote a secret
    from rdetoolkit.errors import RdeRegistryError
    from typer.testing import CliRunner
    from rdetoolkit.cli.app import app

    (tmp_path / "secret_lint_broken.py").write_text(f"raise ImportError({SECRET!r})\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    from rdetoolkit.cli import nodes_cmd

    real_import = nodes_cmd.import_project_module

    def import_or_fail(name):
        if name == "secret_lint_template":
            raise RdeRegistryError(code=2101, name="TemplateSlotMissing", message=f"slot {SECRET} missing")
        return real_import(name)

    monkeypatch.setattr(nodes_cmd, "import_project_module", import_or_fail)
    # When: linting them as JSON
    result = CliRunner().invoke(app, ["nodes", "lint", "--json", "--module", "secret_lint_broken", "--module", "secret_lint_template"])
    # Then: both are findings, and the secret appears nowhere on stdout
    payload = json.loads(result.stdout)
    assert result.exit_code == 3
    # (subset: other tests in this process may have registered nodes lint also reports)
    assert {"ModuleImportFailed", "TemplateSlotMissing"} <= {d["name"] for d in payload["diagnostics"]}
    assert SECRET not in result.stdout


def test_no_secret_in_doctor_json(tmp_path, monkeypatch):
    # Given: a secret in a config value, in an invoice the Runner rejects, and in a flow import error
    from typer.testing import CliRunner
    from rdetoolkit.cli.app import app
    from tests.v2.cli.test_cli_report import _build_data_fixture

    _build_data_fixture(tmp_path)
    (tmp_path / "rdeconfig.yaml").write_text(f"custom:\n  api_token: {SECRET}\n", encoding="utf-8")
    (tmp_path / "data/invoice/invoice.json").write_text(json.dumps({"basic": {"dataName": SECRET}}), encoding="utf-8")
    (tmp_path / "data/tasksupport/metadata-def.json").write_text("{}", encoding="utf-8")
    (tmp_path / "secret_doctor_flow.py").write_text(f"raise RuntimeError({SECRET!r})\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: running doctor in both formats
    as_json = CliRunner().invoke(app, ["doctor", "--format", "json", "--ref", "secret_doctor_flow:main"])
    as_text = CliRunner().invoke(app, ["doctor", "--ref", "secret_doctor_flow:main"])
    # Then: the failures are reported, but no planted value reaches either output
    payload = json.loads(as_json.stdout)
    assert as_json.exit_code == as_text.exit_code == 1
    failed = {d["check_id"] for d in payload["diagnostics"]}
    assert {"runner.preflight", "flow.import"} <= failed
    assert "config.effective" not in failed  # the secret-bearing config was loaded
    assert SECRET not in as_json.output
    assert SECRET not in as_text.output


def test_no_secret_in_report_diagnose(tmp_path, monkeypatch):
    # Given: a real run whose node raises with a secret and receives a secret argument
    from typer.testing import CliRunner
    from rdetoolkit.cli.app import app
    from rdetoolkit.core.flow import flow
    from rdetoolkit.core.node import node
    from rdetoolkit.runner.lifecycle import Runner
    from tests.v2.cli.test_cli_report import _build_data_fixture

    _build_data_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)

    @node(id="diagnostics_contract_secret_node")
    def leak(token: str) -> None:
        raise RuntimeError(f"bad token {token}")

    @flow(id="diagnostics_contract_secret_flow")
    def pipeline() -> None:
        leak(SECRET)

    report = Runner(root=tmp_path, run_id_factory=lambda: "secret_run").run(pipeline)
    path = tmp_path / "data/logs/run_report_secret_run.json"
    # The secret really is in the local artifacts (otherwise this test proves nothing)
    assert report.status == "failed"
    assert SECRET in path.read_text(encoding="utf-8")
    assert SECRET in (tmp_path / "data/logs/iterations/iteration_0.json").read_text(encoding="utf-8")
    # When: diagnosing the report in both formats
    as_json = CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"])
    as_text = CliRunner().invoke(app, ["report", "diagnose", str(path)])
    # Then: the failing node and call are identified without the secret
    payload = json.loads(as_json.stdout)
    assert as_json.exit_code == as_text.exit_code == 0
    assert payload["failures"][0]["node_id"] == "diagnostics_contract_secret_node"
    assert payload["evidence"]["iterations"][0]["iteration_detail"]["state"] == "verified"
    assert SECRET not in as_json.output
    assert SECRET not in as_text.output
