"""Privacy and size bounds of the agent diagnostics envelope (#670).

Secrets are planted where a careless serializer would pick them up: nested
input/output values, exception strings, file and directory names, config
values, environment variables and forged identifiers. None may reach stdout or
stderr of ``nodes lint --json``, ``doctor --format json`` or ``report diagnose``.

EP table:
| Partition | Expected | Test |
| --- | --- | --- |
| secrets in every free-text report field | absent; ids kept | test_diagnose_report_secrets |
| ids rdetoolkit could not have written | null + ``redacted``; never echoed | test_diagnose_report_secrets, test_identifier_filter |
| malformed / non-UTF-8 / deep / oversized report | fixed JSON error, exit 3, no echo | test_diagnose_invalid_input |
| secrets in config, invoice, file names, env | absent from doctor | test_doctor_secrets |
| secret defaults, docstrings, import errors | absent from lint | test_lint_secrets |
| every command | format/producer metadata, no socket | test_provenance_and_no_network |
| arbitrary text in nested report values | absent (Hypothesis) | test_arbitrary_report_text |
BV table:
| Boundary | Expected | Test |
| --- | --- | --- |
| report exactly 16 MiB / 16 MiB + 1 byte | accepted / rejected | test_report_size_boundary |
| MAX_ENTRIES / MAX_ENTRIES + 1 findings | complete / capped, ``truncated`` | test_envelope_cap, test_diagnose_caps_lists |
| identifier of MAX_IDENTIFIER_LENGTH / +1 chars | kept / redacted | test_identifier_filter |
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from referencing import Registry, Resource
from typer.testing import CliRunner

from rdetoolkit import __version__
from rdetoolkit.cli.app import app
from rdetoolkit.report.diagnostics import MAX_ENTRIES, MAX_IDENTIFIER_LENGTH, diagnostic, envelope, safe_identifier

SECRET = "sk-test-0f9e8d7c6b5a"
SCHEMAS = Path(__file__).resolve().parents[3] / "docs" / "usage"


def _validate_diagnosis(payload: dict[str, Any]) -> None:
    base = json.loads((SCHEMAS / "diagnostics.schema.json").read_text(encoding="utf-8"))
    report = json.loads((SCHEMAS / "diagnostics-report.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource("diagnostics.schema.json", Resource.from_contents(base))
    jsonschema.Draft202012Validator(report, registry=registry).validate(payload)


def _report_data(**changes: Any) -> dict[str, Any]:
    secret_error = {"code": 3001, "name": SECRET, "message": f"token={SECRET}", "stacktrace": SECRET, "detail": {"env": {"API_KEY": SECRET}}}
    data = {
        "schema_version": "2", "run_id": "run_privacy", "status": "partial", "flow_id": SECRET, "mode": SECRET,
        "started_at": SECRET, "duration_ms": 1, "config_digest": SECRET, "warnings": [{"message": SECRET}],
        "error": {"code": "3001", "name": SECRET, "message": SECRET},
        "iterations": [
            {
                "index": 0, "status": "failed", "target": f"/home/alice/{SECRET}/data",
                "error": {**secret_error, "call_id": "pkg.reader#1"},
                "node_calls": [{
                    "call_id": "pkg.reader#1", "node_id": "pkg.reader", "status": "failed",
                    "inputs": {"value": {"nested": [{"deeper": SECRET}]}}, "outputs": [SECRET], "error": secret_error,
                }],
            },
            {
                "index": 1, "status": "failed", "error": {"code": 999_999, "message": SECRET, "call_id": f"/home/alice/{SECRET}#2"},
                "node_calls": [{"call_id": f"/home/alice/{SECRET}#2", "node_id": f"api_key={SECRET}", "status": "failed"}],
            },
        ],
    }
    return {**data, **changes}


def _write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_diagnose_report_secrets(tmp_path: Path) -> None:
    # Given: a report whose free text, nested values and two ids carry a secret
    path = _write(tmp_path / "run_report_run_privacy.json", _report_data())
    # When: diagnosing it in both formats
    as_json = CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"])
    as_text = CliRunner().invoke(app, ["report", "diagnose", str(path)])
    # Then: the well-formed ids are kept, the others are null and flagged, no secret is printed
    assert as_json.exit_code == as_text.exit_code == 0, as_json.output
    for result in (as_json, as_text):
        assert SECRET not in result.stdout
        assert SECRET not in result.stderr
    payload = json.loads(as_json.stdout)
    _validate_diagnosis(payload)
    first, second = payload["failures"]
    assert (first["node_id"], first["call_id"], first["redacted"]) == ("pkg.reader", "pkg.reader#1", [])
    assert (second["node_id"], second["call_id"], second["redacted"]) == (None, None, ["call_id", "node_id"])
    assert (second["code"], second["name"]) == (999_999, "ExecutionError")
    assert "<redacted call id>" in as_text.stdout
    assert payload["source"] == {"format": "rdetoolkit.run-report", "schema_version": "2"}


@pytest.mark.parametrize(
    ("name", "contents"),
    [
        ("broken", f'{{"{SECRET}": invalid'.encode()),
        ("not-utf8", b"\xff" + SECRET.encode()),
        ("deep", b"[" * 100_000 + SECRET.encode()),
        ("huge-int", b'{"x": ' + b"9" * 5000 + b"}"),
        ("scalar", json.dumps([SECRET]).encode()),
        ("forged-run-id", json.dumps(_report_data(run_id=f"../{SECRET}")).encode()),
        ("shape", json.dumps(_report_data(iterations={SECRET: SECRET})).encode()),
        ("call-shape", json.dumps(_report_data(iterations=[{"index": 0, "status": "failed", "node_calls": [SECRET]}])).encode()),
    ],
)
def test_diagnose_invalid_input(tmp_path: Path, name: str, contents: bytes) -> None:
    # Given: an unreadable report whose file name and contents carry a secret
    path = tmp_path / f"{SECRET}-{name}.json"
    path.write_bytes(contents)
    for argv in (["report", "diagnose", str(path), "--json"], ["report", "diagnose", str(path)]):
        # When: diagnosing it
        result = CliRunner().invoke(app, argv)
        # Then: a fixed error, exit 3, and neither the path nor the contents are echoed
        assert result.exit_code == 3, result.output
        assert SECRET not in result.stdout
        assert SECRET not in result.stderr
    payload = json.loads(CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"]).stdout)
    assert [d["name"] for d in payload["diagnostics"]] == ["ReportInputInvalid"]
    assert "source" not in payload


@pytest.mark.parametrize(("padding", "exit_code"), [(0, 0), (1, 3)])
def test_report_size_boundary(tmp_path: Path, padding: int, exit_code: int) -> None:
    # Given: a valid report padded to exactly the 16 MiB input cap, or one byte over it
    contents = json.dumps(_report_data()).encode()
    path = tmp_path / "run_report_run_privacy.json"
    path.write_bytes(contents + b" " * (16 * 1024 * 1024 - len(contents) + padding))
    # When/Then: the cap is inclusive
    result = CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"])
    assert result.exit_code == exit_code, result.output


@pytest.mark.parametrize("count", [MAX_ENTRIES, MAX_ENTRIES + 1])
def test_envelope_cap(count: int) -> None:
    # Given: findings at and over the cap, the error sorted last
    findings = [diagnostic(code=None, severity="warning", name="W", message="m", remediation="r", subject=f"s{i:04d}") for i in range(count - 1)]
    findings.append(diagnostic(code=None, severity="error", name="E", message="m", remediation="r", subject="zzzz"))
    # When: wrapping them
    result = envelope(findings)
    # Then: at most MAX_ENTRIES are kept, the cut is flagged, and the status still sees every finding
    assert len(result["diagnostics"]) == min(count, MAX_ENTRIES)
    assert result["truncated"] is (count > MAX_ENTRIES)
    assert result["status"] == "failed"


def test_diagnose_caps_lists(tmp_path: Path) -> None:
    # Given: a report with more failed tiles than the cap
    iterations = [
        {"index": i, "status": "failed", "error": {"code": 3001, "call_id": f"n#{i}"},
         "node_calls": [{"call_id": f"n#{i}", "node_id": "n", "status": "failed"}]}
        for i in range(MAX_ENTRIES + 5)
    ]
    path = _write(tmp_path / "run_report_run_privacy.json", _report_data(iterations=iterations))
    # When: diagnosing it
    payload = json.loads(CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"]).stdout)
    # Then: every list is capped and the envelope says so
    assert payload["truncated"] is True
    assert len(payload["failures"]) == len(payload["evidence"]["iterations"]) == len(payload["diagnostics"]) == MAX_ENTRIES
    _validate_diagnosis(payload)


@pytest.mark.parametrize(
    ("value", "kept"),
    [
        ("pkg.mod.func", True), ("mod.f.<locals>.g#12", True), ("処理.関数#3", True), ("x" * MAX_IDENTIFIER_LENGTH, True),
        ("x" * (MAX_IDENTIFIER_LENGTH + 1), False), ("", False), ("a b", False), ("/home/u/x", False),
        ("C:\\x", False), ("token=abc", False), ("a\n", False), ('"q"', False), (None, False), (3, False),
    ],
)
def test_identifier_filter(value: object, kept: bool) -> None:
    # When/Then: only ids rdetoolkit could have formed pass, unchanged
    assert safe_identifier(value) == (value if kept else None)


def test_doctor_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: secrets nested in config values, the invoice, an input file name, metadata and the environment
    from tests.v2.cli.test_cli_report import _build_data_fixture

    _build_data_fixture(tmp_path)
    (tmp_path / "rdeconfig.yaml").write_text(
        f"custom:\n  nested:\n    tokens: [{SECRET}]\n    db: {{password: {SECRET}}}\n", encoding="utf-8",
    )
    (tmp_path / "data/invoice/invoice.json").write_text(json.dumps({"basic": {"dataName": {"x": [SECRET]}}}), encoding="utf-8")
    (tmp_path / f"data/inputdata/{SECRET}.dat").write_text(SECRET, encoding="utf-8")
    (tmp_path / "data/tasksupport/metadata-def.json").write_text(json.dumps({SECRET: {"name": SECRET}}), encoding="utf-8")
    monkeypatch.setenv("RDE_API_TOKEN", SECRET)
    # When: running doctor in both formats
    as_json = CliRunner().invoke(app, ["doctor", str(tmp_path), "--format", "json"])
    as_text = CliRunner().invoke(app, ["doctor", str(tmp_path)])
    # Then: findings are reported without any planted value or absolute path
    payload = json.loads(as_json.stdout)
    assert payload["checks"], as_json.output
    for result in (as_json, as_text):
        assert SECRET not in result.output
        assert str(tmp_path) not in result.stdout


def test_lint_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a node with a secret default value and docstring, and a module whose import error quotes it
    from rdetoolkit.core import registry

    for name in ("_node_specs", "_node_wrappers", "_node_functions"):
        monkeypatch.setattr(registry, name, dict(getattr(registry, name)))
    (tmp_path / "privacy_lint_nodes.py").write_text(
        "from rdetoolkit import node\n\n"
        f"@node(id='privacy_lint_nodes.read')\ndef read(path, token: str = {SECRET!r}) -> None:\n    '''{SECRET}'''\n",
        encoding="utf-8",
    )
    (tmp_path / "privacy_lint_broken.py").write_text(f"raise ImportError('api_key={SECRET}')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    # When: linting both as JSON
    result = CliRunner().invoke(app, ["nodes", "lint", "--json", "--module", "privacy_lint_nodes", "--module", "privacy_lint_broken"])
    # Then: the findings name the node and module, but not the secret
    payload = json.loads(result.stdout)
    assert {"MissingTypeAnnotation", "ModuleImportFailed"} <= {d["name"] for d in payload["diagnostics"]}
    assert SECRET not in result.output


@pytest.mark.parametrize("argv", [["nodes", "lint", "--json"], ["doctor", ".", "--format", "json"], ["report", "diagnose", "REPORT", "--json"]])
def test_provenance_and_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    # Given: a project, a report, and sockets that fail if anything connects
    from tests.v2.cli.test_cli_report import _build_data_fixture

    _build_data_fixture(tmp_path)
    report = _write(tmp_path / "run_report_run_privacy.json", _report_data())
    monkeypatch.chdir(tmp_path)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("diagnostics must stay local")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    # When: running the command
    result = CliRunner().invoke(app, [str(report) if arg == "REPORT" else arg for arg in argv])
    # Then: one JSON document that names its format and producer
    payload = json.loads(result.stdout)
    assert result.exit_code in {0, 1, 3}, result.output
    assert (payload["format"], payload["producer"]) == ("rdetoolkit.diagnostics", {"name": "rdetoolkit", "version": __version__})
    assert payload["truncated"] is False


_id_breakers = st.sampled_from([" ", "/", "=", "\\", ":", "\n", '"'])


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(value=st.text(min_size=1, max_size=40), breaker=_id_breakers)
def test_arbitrary_report_text(tmp_path_factory: pytest.TempPathFactory, value: str, breaker: str) -> None:
    # Given: arbitrary text in nested values, messages and names, and in ids made unwritable by one character
    secret = f"SECRET{breaker}{value}END"
    error = {"code": 3001, "name": secret, "message": secret, "detail": {secret: [secret]}, "call_id": secret}
    iteration = {"index": 0, "status": "failed", "target": secret, "error": error,
                 "node_calls": [{"call_id": secret, "node_id": secret, "status": "failed", "inputs": {secret: {"v": secret}}, "error": error}]}
    path = _write(tmp_path_factory.mktemp("report") / "run_report_run_privacy.json", _report_data(iterations=[iteration], error=error))
    # When: diagnosing it
    result = CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"])
    # Then: no printed string contains it
    assert result.exit_code == 0, result.output
    assert not [text for text in _strings(json.loads(result.stdout)) if secret in text]


def _strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [text for key, item in value.items() for text in (str(key), *_strings(item))]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return [value] if isinstance(value, str) else []
