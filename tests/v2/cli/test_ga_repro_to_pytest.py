"""``rdetoolkit repro to-pytest``: an editable regression test from a repro archive (#700).

The command reads a full ``repro export`` archive (checked like ``repro
inspect``), imports the explicit ``--ref`` flow without calling it, and writes
a pytest module that declares the archived run as an ``rde_case``. The
expected status defaults to ``"success"`` -- the behaviour expected *after* the
fix -- and is never copied from the archived failure unless the developer
passes ``--expect-status``. Raw inputs are copied only with ``--stage-inputs``;
otherwise ``--project`` names an existing project whose inputs and config must
match the archive's digests.

EP/BV table:

| ID | Class | Input | Expected | Test |
|----|-------|-------|----------|------|
| EP-001 | valid | failed v3 archive, ``--stage-inputs`` | exit 0, rde_case source, post-fix ``success`` | test_valid_minimal_repro_generates_a_case |
| EP-002 | valid | ``--project`` = imported project | exit 0, nothing staged, relative PROJECT | test_imported_project_is_referenced_not_copied |
| EP-003 | valid | ``--expect-status failed`` (explicit opt-in) | failed + archived code | test_explicit_expect_status_opt_in |
| EP-004 | valid | dotted attribute ``mod:Holder.pipeline`` | attribute access on the import | test_dotted_attribute_reference |
| EP-005 | valid | v3 provenance known / version differs | listed; difference warned | test_provenance_is_listed_and_differences_warned |
| EP-006 | valid | v1 archive + ``--stage-inputs`` | exit 0, "provenance unavailable" noted | test_legacy_archive_stages_with_provenance_unavailable |
| EP-007 | valid | ``--force`` over an existing file | replaced | test_force_replaces_existing_output |
| NEG-001 | invalid | ``--ref`` absent | exit 2 | test_ref_is_required |
| NEG-002 | invalid | unimportable module / missing attribute | exit 3, no output | test_missing_flow_is_refused |
| NEG-003 | invalid | malformed or keyword ``--ref`` | exit 3 before import | test_malformed_ref_is_refused_before_import |
| NEG-004 | invalid | neither / both of ``--project`` and ``--stage-inputs`` | exit 2 | test_project_source_must_be_chosen_once |
| NEG-005 | invalid | modified member (valid CRC) | exit 3, no output, nothing staged | test_mismatched_archive_is_refused |
| NEG-006 | invalid | manifest-only archive | exit 3 actionable | test_manifest_only_archive_is_refused |
| NEG-007 | invalid | ``--project`` with changed / extra / missing input, other config | exit 3 naming it | test_project_that_differs_from_archive_is_refused |
| NEG-008 | invalid | v1 archive + ``--project`` | exit 3 (no per-file digests) | test_legacy_archive_cannot_verify_a_project |
| NEG-009 | invalid | existing output without ``--force`` / directory / link / not ``.py`` | exit 3, untouched | test_output_refusals |
| NEG-010 | invalid | traversal / absolute member names | exit 3, nothing written | test_path_traversal_member_is_refused |
| NEG-011 | invalid | non-empty ``--stage-inputs`` directory | exit 3 | test_stage_inputs_target_must_be_empty |
| NEG-012 | invalid | secrets in report, config, file names | absent from the generated source | test_secrets_are_not_copied_into_the_source |
| NEG-013 | invalid | generation | flow never called, no bytecode written | test_generation_never_calls_the_flow |
| BV-001 | boundary | ``pytest --collect-only`` + ruff on the output | collected, clean, no side effects | test_generated_source_collects_without_side_effects |
| BV-002 | boundary | real failed run, before and after the fix | RED before, GREEN after | test_post_fix_positive_assertion_end_to_end |
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit import __version__
from rdetoolkit.cli._repro_pytest import ArchivedRun, archived_run, project_expression, project_problems, provenance_notes, render_test, summarize
from rdetoolkit.cli.app import app
from rdetoolkit.testing import RdeTestRunner
from tests.v2.cli.test_cli_repro_security_671 import PAYLOAD, SECRET, _entries, _export, _import, _project, _rewrite

_FIXTURE = Path(__file__).parents[1] / "testing" / "fixtures" / "rde_case" / "sample"

_FLOW_SOURCE = '''
from pathlib import Path

from rdetoolkit import flow
from rdetoolkit.types import InputPaths

SENTINEL = Path(__file__).with_name("{name}.called")


@flow(id="tests.ga700.{name}")
def pipeline(paths: InputPaths) -> None:
    SENTINEL.write_text("flow executed", encoding="utf-8")
    if not Path(__file__).with_name("{name}.fixed").exists():
        raise ValueError("defect not fixed yet")


class Holder:
    pipeline = staticmethod(pipeline)
'''


@pytest.fixture(autouse=True)
def _no_enclosing_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


@pytest.fixture
def flow_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A uniquely named flow module importable from the working directory (tmp_path)."""
    name = f"ga700_flow_{uuid.uuid4().hex[:12]}"
    (tmp_path / f"{name}.py").write_text(_FLOW_SOURCE.format(name=name), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    yield name
    sys.modules.pop(name, None)


def _to_pytest(*args: str):
    return CliRunner().invoke(app, ["repro", "to-pytest", *args])


def _archive(tmp_path: Path) -> Path:
    _, report = _project(tmp_path)
    archive = tmp_path / "full.zip"
    result = _export(report, archive)
    assert result.exit_code == 0, result.output
    return archive


def _manifest(archive: Path) -> dict:
    with zipfile.ZipFile(archive) as opened:
        return json.loads(opened.read("repro_manifest.json"))


def _with_manifest(archive: Path, target: Path, manifest: dict) -> Path:
    entries = _entries(archive)
    entries["repro_manifest.json"] = json.dumps(manifest).encode()
    return _rewrite(target, entries)


def _generate(tmp_path: Path, flow_module: str, archive: Path, *options: str) -> tuple[object, Path]:
    output = tmp_path / "tests" / "test_regression.py"
    result = _to_pytest(str(archive), "--ref", f"{flow_module}:pipeline", "-o", str(output), *options)
    return result, output


# --------------------------------------------------------------------------- valid


def test_valid_minimal_repro_generates_a_case(tmp_path: Path, flow_module: str) -> None:
    # Given: a v3 archive of a failed run (error 3001)
    archive = _archive(tmp_path)
    stage = tmp_path / "tests" / "cases" / "repro"
    # When: generating a scaffold that stages the archived inputs (explicit opt-in)
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(stage))
    # Then: readable pytest source with the explicit flow, the case and the post-fix expectation
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == str(output)
    source = output.read_text(encoding="utf-8")
    compile(source, str(output), "exec")
    assert f"from {flow_module} import pipeline as flow_under_test\n" in source
    assert "from rdetoolkit.testing import RdeTestResult, rde_case\n" in source
    assert 'PROJECT = Path(__file__).parent / "cases/repro"\n' in source
    assert "@rde_case(\n    flow=flow_under_test,\n    project=PROJECT,\n" in source
    assert '    expect_status="success",\n' in source
    assert "expect_error_code" not in source.split("@rde_case(")[1]
    assert "def test_regression_security(rde_run: RdeTestResult) -> None:\n" in source
    assert '    assert rde_run.status == "success"\n' in source
    assert "Archived run: security, status 'failed', error code 3001." in source
    assert "behaviour expected after the fix" in source
    # And: the inputs were staged (verified, the opt-in target only) and the staging is announced
    assert (stage / "data" / "inputdata" / f"{SECRET}.dat").read_bytes() == PAYLOAD
    assert "raw input" in result.stderr
    assert "Review expect_status" in result.stderr


def test_imported_project_is_referenced_not_copied(tmp_path: Path, flow_module: str) -> None:
    # Given: the archive imported by the developer with 'repro import'
    archive = _archive(tmp_path)
    replay = tmp_path / "replay"
    assert _import(archive, replay).exit_code == 0
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    # When
    result, output = _generate(tmp_path, flow_module, archive, "--project", str(replay))
    # Then: the case points at that project, relative to the test file, and nothing else was written
    assert result.exit_code == 0, result.output
    source = output.read_text(encoding="utf-8")
    assert 'PROJECT = Path(__file__).parent / "../replay"\n' in source
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert sorted(set(after) - set(before)) == ["tests", "tests/test_regression.py"]
    assert "raw input" not in result.stderr


@pytest.mark.parametrize(("status", "code_line"), [("failed", "    expect_error_code=3001,\n"), ("success", None)])
def test_explicit_expect_status_opt_in(tmp_path: Path, flow_module: str, status: str, code_line: str | None) -> None:
    # Given: a failed archive
    archive = _archive(tmp_path)
    # When: the developer states the expected status explicitly
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "stage"), "--expect-status", status)
    # Then: that status (and, for a failure, the archived code) is written, marked as developer-provided
    assert result.exit_code == 0, result.output
    source = output.read_text(encoding="utf-8")
    assert f'    expect_status="{status}",\n' in source
    assert f'    assert rde_run.status == "{status}"\n' in source
    assert "given with --expect-status" in source
    if code_line is None:
        assert "expect_error_code" not in source.split("@rde_case(")[1]
    else:
        assert code_line in source


def test_dotted_attribute_reference(tmp_path: Path, flow_module: str) -> None:
    # Given: a flow reached through a class attribute
    archive = _archive(tmp_path)
    output = tmp_path / "test_dotted.py"
    # When
    result = _to_pytest(str(archive), "--ref", f"{flow_module}:Holder.pipeline", "-o", str(output), "--stage-inputs", str(tmp_path / "s"))
    # Then
    assert result.exit_code == 0, result.output
    source = output.read_text(encoding="utf-8")
    assert f"from {flow_module} import Holder as flow_under_test\n" in source
    assert "    flow=flow_under_test.pipeline,\n" in source


def test_provenance_is_listed_and_differences_warned(tmp_path: Path, flow_module: str) -> None:
    # Given: a v3 archive, once as exported and once claiming another rdetoolkit version
    archive = _archive(tmp_path)
    manifest = _manifest(archive)
    manifest["provenance"]["rdetoolkit"]["version"] = "0.0.1"
    other = _with_manifest(archive, tmp_path / "other.zip", manifest)
    # When
    same, same_output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "a"))
    differs = _to_pytest(str(other), "--ref", f"{flow_module}:pipeline", "-o", str(tmp_path / "test_b.py"), "--stage-inputs", str(tmp_path / "b"))
    # Then: provenance is listed as comments; the unavailable attributes are named; a difference is warned
    assert same.exit_code == 0, same.output
    source = same_output.read_text(encoding="utf-8")
    assert f"# rdetoolkit: {__version__}\n" in source
    assert "# Unavailable in the archive: " in source
    assert "source_code" in source
    assert "differs" not in same.stderr
    assert differs.exit_code == 0, differs.output
    assert f"rdetoolkit 0.0.1, this environment has {__version__}" in differs.stderr
    assert f"# WARNING: archived with rdetoolkit 0.0.1, this environment has {__version__}\n" in (tmp_path / "test_b.py").read_text(encoding="utf-8")


def test_legacy_archive_stages_with_provenance_unavailable(tmp_path: Path, flow_module: str) -> None:
    # Given: an archive written before #699 (schema_version "1": no files list, no provenance)
    archive = _archive(tmp_path)
    digest = _manifest(archive)["config_digest"]
    legacy = _with_manifest(archive, tmp_path / "legacy.zip", {"schema_version": "1", "config_included": True, "config_digest": digest})
    # When: staging its inputs (verified by import: CRCs and config digest)
    result, output = _generate(tmp_path, flow_module, legacy, "--stage-inputs", str(tmp_path / "stage"))
    # Then: generated, and both the source and stderr say what could not be verified
    assert result.exit_code == 0, result.output
    assert "Provenance unavailable" in result.stderr
    source = output.read_text(encoding="utf-8")
    assert "# Per-file checksums: unavailable (manifest schema_version 1)\n" in source
    assert "predates provenance" in source


def test_force_replaces_existing_output(tmp_path: Path, flow_module: str) -> None:
    # Given: an existing test file
    archive = _archive(tmp_path)
    output = tmp_path / "tests" / "test_regression.py"
    output.parent.mkdir()
    output.write_text("old\n", encoding="utf-8")
    # When: --force is given
    result, _ = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "stage"), "--force")
    # Then
    assert result.exit_code == 0, result.output
    assert "@rde_case(" in output.read_text(encoding="utf-8")
    assert sorted(path.name for path in output.parent.iterdir()) == ["test_regression.py"]


# --------------------------------------------------------------------------- invalid


def test_ref_is_required(tmp_path: Path) -> None:
    # Given/When: no --ref (the flow is never inferred from the archived flow_id)
    archive = _archive(tmp_path)
    result = _to_pytest(str(archive), "-o", str(tmp_path / "test_x.py"), "--stage-inputs", str(tmp_path / "s"))
    # Then
    assert result.exit_code == 2
    assert "--ref" in result.output
    assert not (tmp_path / "test_x.py").exists()
    assert not (tmp_path / "s").exists()


@pytest.mark.parametrize("ref", ["ga700_missing_module:pipeline", "{module}:no_such_flow"])
def test_missing_flow_is_refused(tmp_path: Path, flow_module: str, ref: str) -> None:
    # Given
    archive = _archive(tmp_path)
    output = tmp_path / "test_x.py"
    # When
    result = _to_pytest(str(archive), "--ref", ref.format(module=flow_module), "-o", str(output), "--stage-inputs", str(tmp_path / "s"))
    # Then: the import problem is named, nothing is written or staged
    assert result.exit_code == 3
    assert "Unable to resolve flow" in result.stderr
    assert not output.exists()
    assert not (tmp_path / "s").exists()


@pytest.mark.parametrize(
    "ref",
    ["pipeline", ":pipeline", "mod:", "a b:c", "mod:x;import os", "mod:class", "for.mod:pipeline", "mod:a:b", "mod:x()", "1mod:x"],
)
def test_malformed_ref_is_refused_before_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ref: str) -> None:
    # Given: a reference that is not module.path:attribute.path made of identifiers
    archive = _archive(tmp_path)
    monkeypatch.chdir(tmp_path)
    imported: list[str] = []
    monkeypatch.setattr("rdetoolkit.cli.run_cmd.import_project_module", lambda name: imported.append(name))
    output = tmp_path / "test_x.py"
    # When
    result = _to_pytest(str(archive), "--ref", ref, "-o", str(output), "--stage-inputs", str(tmp_path / "s"))
    # Then: refused without importing anything, so it can never reach the generated source
    assert result.exit_code == 3
    assert "Invalid --ref" in result.stderr
    assert imported == []
    assert not output.exists()


@pytest.mark.parametrize("options", [[], ["--project", "p", "--stage-inputs", "s"]])
def test_project_source_must_be_chosen_once(tmp_path: Path, flow_module: str, options: list[str]) -> None:
    # Given/When
    archive = _archive(tmp_path)
    result, output = _generate(tmp_path, flow_module, archive, *options)
    # Then
    assert result.exit_code == 2
    assert "exactly one of --project or --stage-inputs" in result.output
    assert not output.exists()


def test_mismatched_archive_is_refused(tmp_path: Path, flow_module: str) -> None:
    # Given: one input changed after export (the zip CRC is valid, the manifest digest is not)
    archive = _archive(tmp_path)
    entries = _entries(archive)
    entries[f"data/inputdata/{SECRET}.dat"] = PAYLOAD[::-1]
    tampered = _rewrite(tmp_path / "tampered.zip", entries)
    # When
    result, output = _generate(tmp_path, flow_module, tampered, "--stage-inputs", str(tmp_path / "stage"))
    # Then
    assert result.exit_code == 3
    assert "differ from repro_manifest.json" in result.stderr
    assert "rdetoolkit repro inspect" in result.stderr
    assert not output.exists()
    assert not (tmp_path / "stage").exists()


def test_manifest_only_archive_is_refused(tmp_path: Path, flow_module: str) -> None:
    # Given
    _, report = _project(tmp_path)
    archive = tmp_path / "meta.zip"
    assert _export(report, archive, "--manifest-only").exit_code == 0
    # When
    result, output = _generate(tmp_path, flow_module, archive, "--project", str(tmp_path / "project"))
    # Then
    assert result.exit_code == 3
    assert "--manifest-only archive" in result.stderr
    assert "full archive" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("changed", f"data/inputdata/{SECRET}.dat differs from the archive"),
        ("extra", "data/inputdata/sub/extra.dat is not in the archive"),
        ("missing", "data/invoice/invoice.json is missing"),
        ("config", "config_digest"),
    ],
)
def test_project_that_differs_from_archive_is_refused(tmp_path: Path, flow_module: str, mutation: str, message: str) -> None:
    # Given: an imported project the developer then modified
    archive = _archive(tmp_path)
    replay = tmp_path / "replay"
    assert _import(archive, replay).exit_code == 0
    if mutation == "changed":
        (replay / "data" / "inputdata" / f"{SECRET}.dat").write_bytes(b"other")
    elif mutation == "extra":
        (replay / "data" / "inputdata" / "sub").mkdir()
        (replay / "data" / "inputdata" / "sub" / "extra.dat").write_bytes(b"x")
    elif mutation == "missing":
        (replay / "data" / "invoice" / "invoice.json").unlink()
    else:
        (replay / "rdeconfig.yaml").write_text("custom:\n  sample: changed\n", encoding="utf-8")
    # When
    result, output = _generate(tmp_path, flow_module, archive, "--project", str(replay))
    # Then
    assert result.exit_code == 3
    assert message in result.stderr
    assert "--stage-inputs" in result.stderr
    assert not output.exists()


def test_legacy_archive_cannot_verify_a_project(tmp_path: Path, flow_module: str) -> None:
    # Given: a v1 archive and an imported project
    archive = _archive(tmp_path)
    digest = _manifest(archive)["config_digest"]
    legacy = _with_manifest(archive, tmp_path / "legacy.zip", {"schema_version": "1", "config_included": True, "config_digest": digest})
    replay = tmp_path / "replay"
    assert _import(legacy, replay).exit_code == 0
    # When
    result, output = _generate(tmp_path, flow_module, legacy, "--project", str(replay))
    # Then
    assert result.exit_code == 3
    assert "per-file checksums" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("kind", ["exists", "directory", "symlink", "suffix"])
def test_output_refusals(tmp_path: Path, flow_module: str, kind: str) -> None:
    # Given
    archive = _archive(tmp_path)
    output = tmp_path / "tests" / ("test_regression.txt" if kind == "suffix" else "test_regression.py")
    output.parent.mkdir()
    if kind == "exists":
        output.write_text("keep\n", encoding="utf-8")
    elif kind == "directory":
        output.mkdir()
    elif kind == "symlink":
        (tmp_path / "elsewhere.py").write_text("keep\n", encoding="utf-8")
        output.symlink_to(tmp_path / "elsewhere.py")
    # When: even with --force for the directory and the link
    options = ["--force"] if kind in {"directory", "symlink"} else []
    result = _to_pytest(str(archive), "--ref", f"{flow_module}:pipeline", "-o", str(output), "--stage-inputs", str(tmp_path / "s"), *options)
    # Then: refused before anything is staged; the existing paths are untouched
    assert result.exit_code == 3, result.output
    assert not (tmp_path / "s").exists()
    if kind == "exists":
        assert output.read_text(encoding="utf-8") == "keep\n"
        assert "--force" in result.stderr
    if kind == "symlink":
        assert (tmp_path / "elsewhere.py").read_text(encoding="utf-8") == "keep\n"
    if kind == "suffix":
        assert ".py" in result.stderr


@pytest.mark.parametrize("name", ["../escape.py", "data/inputdata/../../escape.py", "/abs/escape.py"])
def test_path_traversal_member_is_refused(tmp_path: Path, flow_module: str, name: str) -> None:
    # Given: an archive with an unsafe extra member
    archive = _archive(tmp_path)
    entries = _entries(archive)
    entries[name] = b"print('escaped')"
    unsafe = _rewrite(tmp_path / "unsafe.zip", entries)
    # When
    result, output = _generate(tmp_path, flow_module, unsafe, "--stage-inputs", str(tmp_path / "stage"))
    # Then
    assert result.exit_code == 3
    assert "Unsafe archive member name" in result.stderr
    assert not output.exists()
    assert not (tmp_path / "stage").exists()
    assert not (tmp_path / "escape.py").exists()


def test_stage_inputs_target_must_be_empty(tmp_path: Path, flow_module: str) -> None:
    # Given
    archive = _archive(tmp_path)
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "keep.txt").write_text("keep", encoding="utf-8")
    # When
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(stage))
    # Then
    assert result.exit_code == 3
    assert "not empty" in result.stderr
    assert sorted(path.name for path in stage.iterdir()) == ["keep.txt"]
    assert not output.exists()


def test_secrets_are_not_copied_into_the_source(tmp_path: Path, flow_module: str) -> None:
    # Given: a report whose flow_id, timestamps, warnings and error message, the config and an input name hold a secret
    archive = _archive(tmp_path)
    # When
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "tests" / "stage"))
    # Then: neither the secret, the input bytes nor an absolute local path reach the source or stdout
    assert result.exit_code == 0, result.output
    source = output.read_text(encoding="utf-8")
    assert SECRET not in source
    assert PAYLOAD.decode() not in source
    assert str(tmp_path) not in source
    assert SECRET not in result.stdout


def test_generation_never_calls_the_flow(tmp_path: Path, flow_module: str) -> None:
    # Given
    archive = _archive(tmp_path)
    # When
    result, _ = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "stage"))
    # Then: imported (validated) but never called, and no bytecode cache was written for it
    assert result.exit_code == 0, result.output
    assert flow_module in sys.modules
    assert not (tmp_path / f"{flow_module}.called").exists()
    assert not (tmp_path / "__pycache__").exists()


# --------------------------------------------------------------------------- boundary: the generated module


def _pytest(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--strict-markers", "-o", "addopts=", "-rA",
         "--basetemp", str(tmp_path / "basetemp"), *args],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=300,
        env={**os.environ, "PYTHONPATH": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_generated_source_collects_without_side_effects(tmp_path: Path, flow_module: str) -> None:
    # Given: a generated module
    archive = _archive(tmp_path)
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "tests" / "stage"))
    assert result.exit_code == 0, result.output
    # When: collecting it, and running the formatter and linter over it
    collected = _pytest(tmp_path, "--collect-only", "-q", str(output))
    ruff = shutil.which("ruff") or str(Path(sys.executable).with_name("ruff"))
    lint = subprocess.run([ruff, "check", "--isolated", str(output)], capture_output=True, text=True, check=False)  # noqa: S603
    fmt = subprocess.run([ruff, "format", "--isolated", "--check", str(output)], capture_output=True, text=True, check=False)  # noqa: S603
    # Then: one test collected, the flow never ran, nothing was staged, and the source is clean
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert "tests/test_regression.py::test_regression_security" in collected.stdout
    assert not (tmp_path / f"{flow_module}.called").exists()
    assert not list(tmp_path.rglob("rde_runner"))
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert fmt.returncode == 0, fmt.stdout + fmt.stderr


def test_post_fix_positive_assertion_end_to_end(tmp_path: Path, flow_module: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a real run of the defective flow, exported as a full archive
    monkeypatch.syspath_prepend(str(tmp_path))
    module = __import__(flow_module)
    run = RdeTestRunner(tmp_path / "original").run(flow=module.pipeline, project=_FIXTURE)
    assert run.status == "failed"
    assert run.report_path is not None
    archive = tmp_path / "failure.zip"
    assert _export(run.report_path, archive).exit_code == 0
    (tmp_path / f"{flow_module}.called").unlink()
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "tests" / "cases" / "failure"))
    assert result.exit_code == 0, result.output
    # When: running the generated test before the fix
    before = _pytest(tmp_path, str(output))
    # Then: it fails, because the default expectation is the post-fix success
    assert before.returncode == 1, before.stdout + before.stderr
    assert "expected 'success'" in before.stdout
    # When: the defect is fixed
    (tmp_path / f"{flow_module}.fixed").write_text("", encoding="utf-8")
    after = _pytest(tmp_path, str(output))
    # Then: the same generated test passes, without editing it
    assert after.returncode == 0, after.stdout + after.stderr
    assert "1 passed" in after.stdout


# --------------------------------------------------------------------------- further refusals


def _replace_member(archive: Path, target: Path, name: str, content: bytes | None) -> Path:
    """Rewrite one member (None removes it) and keep the manifest listing consistent."""
    entries = _entries(archive)
    manifest = json.loads(entries["repro_manifest.json"])
    manifest["files"] = [item for item in manifest["files"] if item["path"] != name]
    if content is None:
        del entries[name]
    else:
        entries[name] = content
        manifest["files"].append({"path": name, "byte_count": len(content), "sha256": "sha256:" + hashlib.sha256(content).hexdigest()})
    entries["repro_manifest.json"] = json.dumps(manifest).encode()
    return _rewrite(target, entries)


@pytest.mark.parametrize("content", [b"{}", b"not json", None])
def test_unreadable_or_missing_report_is_refused(tmp_path: Path, flow_module: str, content: bytes | None) -> None:
    # Given: a consistent archive whose run report is unreadable or absent
    archive = _replace_member(_archive(tmp_path), tmp_path / "noreport.zip", "data/logs/run_report_security.json", content)
    # When
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "stage"))
    # Then
    assert result.exit_code == 3
    assert "exactly one readable run report" in result.stderr
    assert not output.exists()
    assert not (tmp_path / "stage").exists()


def test_not_a_zip_is_refused(tmp_path: Path, flow_module: str) -> None:
    # Given
    archive = tmp_path / "broken.zip"
    archive.write_bytes(b"not a zip")
    # When
    result, output = _generate(tmp_path, flow_module, archive, "--stage-inputs", str(tmp_path / "stage"))
    # Then
    assert result.exit_code == 3
    assert "Unable to read archive" in result.stderr
    assert not output.exists()


def test_invalid_expect_status_is_a_command_line_error(tmp_path: Path, flow_module: str) -> None:
    # Given/When
    result, output = _generate(tmp_path, flow_module, _archive(tmp_path), "--stage-inputs", str(tmp_path / "s"), "--expect-status", "passed")
    # Then
    assert result.exit_code == 2
    assert "--expect-status must be one of success, partial, failed" in result.stderr
    assert not output.exists()


def test_module_that_raises_on_import_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a module whose top-level code raises something other than ImportError
    name = f"ga700_raises_{uuid.uuid4().hex[:12]}"
    (tmp_path / f"{name}.py").write_text("raise RuntimeError('broken module')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    archive = _archive(tmp_path)
    output = tmp_path / "test_x.py"
    path_before = list(sys.path)
    # When
    result = _to_pytest(str(archive), "--ref", f"{name}:pipeline", "-o", str(output), "--stage-inputs", str(tmp_path / "s"))
    # Then: one usage error naming the exception; sys.path is restored
    assert result.exit_code == 3
    assert "Unable to resolve flow" in result.stderr
    assert "RuntimeError: broken module" in result.stderr
    assert sys.path == path_before
    assert not output.exists()
    sys.modules.pop(name, None)


def test_project_must_be_a_directory(tmp_path: Path, flow_module: str) -> None:
    # Given/When
    result, output = _generate(tmp_path, flow_module, _archive(tmp_path), "--project", str(tmp_path / "missing"))
    # Then
    assert result.exit_code == 3
    assert "--project is not a directory" in result.stderr
    assert not output.exists()


def test_unwritable_output_is_refused(tmp_path: Path, flow_module: str) -> None:
    # Given: an output whose parent is a regular file
    (tmp_path / "file").write_text("", encoding="utf-8")
    output = tmp_path / "file" / "test_x.py"
    # When
    result = _to_pytest(str(_archive(tmp_path)), "--ref", f"{flow_module}:pipeline", "-o", str(output), "--stage-inputs", str(tmp_path / "s"))
    # Then: refused before the inputs are staged
    assert result.exit_code == 3
    assert "Unable to write" in result.stderr
    assert "is not a directory" in result.stderr
    assert not (tmp_path / "s").exists()


def test_write_failure_is_reported(tmp_path: Path, flow_module: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the file system refuses the write itself (full disk, permissions)
    def refuse(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("denied")

    monkeypatch.setattr("rdetoolkit.cli.repro_cmd.tempfile.NamedTemporaryFile", refuse)
    output = tmp_path / "test_x.py"
    output.write_text("keep\n", encoding="utf-8")
    # When: replacing with --force
    result = _to_pytest(str(_archive(tmp_path)), "--ref", f"{flow_module}:pipeline", "-o", str(output), "--stage-inputs", str(tmp_path / "s"), "--force")
    # Then
    assert result.exit_code == 3
    assert "Unable to write" in result.stderr
    assert output.read_text(encoding="utf-8") == "keep\n"


def test_output_created_meanwhile_is_not_overwritten(tmp_path: Path, flow_module: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the output appears after the early check (simulated by skipping it)
    output = tmp_path / "test_x.py"
    output.write_text("keep\n", encoding="utf-8")
    monkeypatch.setattr("rdetoolkit.cli.repro_cmd._check_output", lambda *_args, **_kwargs: None)
    # When
    result = _to_pytest(str(_archive(tmp_path)), "--ref", f"{flow_module}:pipeline", "-o", str(output), "--stage-inputs", str(tmp_path / "s"))
    # Then: the exclusive create refuses it
    assert result.exit_code == 3
    assert "Output already exists" in result.stderr
    assert output.read_text(encoding="utf-8") == "keep\n"


def test_project_without_relative_path_is_named_absolutely(tmp_path: Path, flow_module: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: no relative path between the test file and the project (another Windows drive)
    def no_relative_path(*_args: object) -> str:
        raise ValueError("path is on mount 'D:', start on mount 'C:'")

    monkeypatch.setattr("rdetoolkit.cli._repro_pytest.os.path.relpath", no_relative_path)
    stage = tmp_path / "stage"
    # When
    result, output = _generate(tmp_path, flow_module, _archive(tmp_path), "--stage-inputs", str(stage))
    # Then: generated with the absolute path, and the developer is told
    assert result.exit_code == 0, result.output
    assert f"PROJECT = Path({json.dumps(stage.resolve().as_posix())})\n" in output.read_text(encoding="utf-8")
    assert "has no path relative to" in result.stderr


# --------------------------------------------------------------------------- unit: rendering helpers


def _report(**fields: object) -> str:
    base = {
        "schema_version": "2", "run_id": "run-1", "status": "failed", "flow_id": "f", "mode": "invoice", "started_at": "t",
        "duration_ms": 0, "config_digest": "sha256:" + "0" * 64, "iterations": [], "warnings": [], "error": None,
    }
    return json.dumps({**base, **fields})


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"error": {"code": 3001}}, ArchivedRun("run-1", "failed", 3001)),
        ({"iterations": [{"index": 0}, {"index": 1, "error": {"code": 3002}}]}, ArchivedRun("run-1", "failed", 3002)),
        ({"error": {"code": True}, "iterations": ["not a mapping"]}, ArchivedRun("run-1", "failed", None)),
        ({"status": "exploded", "run_id": "bad id\n"}, ArchivedRun(None, None, None)),
    ],
)
def test_archived_run_quotes_only_validated_facts(fields: dict, expected: ArchivedRun) -> None:
    # Given/When/Then: codes come from the run or the first failed tile; anything unusable is None
    assert archived_run(_report(**fields)) == expected


@pytest.mark.parametrize(
    ("run_id", "name"),
    [("security", "test_regression_security"), ("20261115-AB.c<1>", "test_regression_20261115_ab_c_1"), (None, "test_regression_archived_run"), ("___", "test_regression_archived_run")],
)
def test_test_name_is_an_identifier(run_id: str | None, name: str) -> None:
    # Given/When
    source = render_test(module="m", attributes=("f",), project="Path(__file__).parent", run=ArchivedRun(run_id, None, None), expect_status=None, notes=())
    # Then
    assert f"def {name}(rde_run: RdeTestResult) -> None:\n" in source
    assert "status not recorded" in source
    assert "has no recorded status" in source
    compile(source, "generated.py", "exec")


def test_project_expression_for_the_test_directory(tmp_path: Path) -> None:
    # Given/When/Then: a project next to the test file is its directory
    assert project_expression(tmp_path, tmp_path / "test_x.py") == ("Path(__file__).parent", False)


def test_project_expression_escapes_unprintable_names(tmp_path: Path) -> None:
    # Given: a directory name with a control character
    expression, absolute = project_expression(tmp_path / "a\tb", tmp_path / "test_x.py")
    # Then: a valid, single-line literal
    assert (expression, absolute) == ('Path(__file__).parent / "a\\tb"', False)


def test_provenance_notes_describe_git_and_python_differences() -> None:
    # Given: a manifest recording a dirty git checkout and another Python minor version
    commit = "a" * 40
    manifest = {
        "schema_version": "3",
        "provenance": {
            "captured_at": "export",
            "python": {"status": "known", "implementation": "CPython", "version": "2.7.18"},
            "git": {"status": "known", "commit": commit, "dirty": True},
        },
    }
    # When
    lines, warnings = provenance_notes(manifest, 3)
    # Then
    assert f"# git: {commit} (tracked files changed)" in lines
    assert "# Per-file checksums: 3 files verified against repro_manifest.json" in lines
    assert warnings == [f"archived with Python 2.7.18, this environment has {platform.python_version()}"]


@pytest.mark.parametrize("kind", ["config", "link", "unreadable", "no_inputs"])
def test_project_problems_beyond_content(tmp_path: Path, kind: str) -> None:
    # Given: an imported project with a broken config, a linked or unreadable input, or no input directories
    archive = _archive(tmp_path)
    replay = tmp_path / "replay"
    assert _import(archive, replay).exit_code == 0
    manifest = _manifest(archive)
    files = {item["path"]: (item["byte_count"], item["sha256"]) for item in manifest["files"]}
    target = replay / "data" / "inputdata" / f"{SECRET}.dat"
    if kind == "config":
        (replay / "rdeconfig.yaml").write_text("system: [unclosed\n", encoding="utf-8")
    elif kind == "link":
        moved = tmp_path / "outside.dat"
        target.rename(moved)
        target.symlink_to(moved)
    elif kind == "unreadable":
        if os.geteuid() == 0:
            pytest.skip("root reads files regardless of their mode")
        target.chmod(0)
    else:
        for name in ("inputdata", "invoice", "tasksupport"):
            shutil.rmtree(replay / "data" / name)
    # When
    problems = project_problems(replay, files, manifest["config_digest"])
    # Then
    if kind == "config":
        assert problems == [f"the project's effective config does not reproduce the archived config_digest {manifest['config_digest']}"]
    elif kind == "no_inputs":
        assert problems == [f"data/inputdata/{SECRET}.dat is missing", "data/invoice/invoice.json is missing"]
    else:
        assert problems == [f"data/inputdata/{SECRET}.dat differs from the archive"]
    if kind == "unreadable":
        target.chmod(0o644)


def test_summarize_caps_the_listing() -> None:
    # Given/When
    text = summarize([f"p{index}" for index in range(7)])
    # Then
    assert text.splitlines() == ["  p0", "  p1", "  p2", "  p3", "  p4", "  ... and 2 more"]


@pytest.mark.parametrize("status", [[], {}, 1])
def test_non_string_provenance_status_is_unavailable(tmp_path: Path, flow_module: str, status: object) -> None:
    # Given: an archive whose provenance status values are not strings
    archive = _archive(tmp_path)
    manifest = _manifest(archive)
    for name in ("git", "rdetoolkit"):
        manifest["provenance"][name] = {"status": status}
    broken = _with_manifest(archive, tmp_path / "broken.zip", manifest)
    stage = tmp_path / "stage"
    # When
    result, output = _generate(tmp_path, flow_module, broken, "--stage-inputs", str(stage))
    # Then: the test is generated and lists both attributes as unavailable
    assert result.exit_code == 0, result.output
    source = output.read_text(encoding="utf-8")
    unavailable = next(line for line in source.splitlines() if line.startswith("# Unavailable in the archive: "))
    assert "git" in unavailable and "rdetoolkit" in unavailable
