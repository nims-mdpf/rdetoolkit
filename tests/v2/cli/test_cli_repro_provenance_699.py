"""Repro archive provenance, per-file checksums and ``repro inspect`` (#699).

Manifest ``schema_version`` ``"3"`` (both archive kinds) records where the
archive came from (``provenance``, captured at export) and, for a full
archive, every member's size and SHA-256 so import can refuse a modified
member before anything is published. Version ``"1"`` archives stay importable
with an explicit "provenance unavailable" notice.

EP/BV table:

| ID | Class | Input | Expected | Test |
|----|-------|-------|----------|------|
| EP-001 | valid | full export | v3 manifest, sorted ``files`` digests of the archived bytes | test_full_manifest_lists_every_member |
| EP-002 | valid | binary input, empty directory | digest of the exact bytes; directory round-trips | test_binary_and_empty_directory_round_trip |
| EP-003 | valid | export environment | rdetoolkit/python/platform known, no host/user/path | test_runtime_provenance_without_local_identity |
| EP-004 | valid | project in a git checkout | commit + dirty (tracked files) | test_git_checkout_is_recorded |
| EP-005 | valid | lockfiles | first supported name in fixed order, digest only | test_lockfile_digest_and_order |
| EP-006 | valid | manifest-only export | v3 with provenance, still no data | test_manifest_only_carries_provenance |
| EP-007 | valid | v1 manifest | import succeeds, says provenance unavailable | test_old_manifest_imports_with_provenance_unavailable |
| EP-008 | valid | inspect full / manifest-only / v1 / v2 | known vs unavailable, inputs status | test_inspect_* |
| NEG-001 | invalid | no git checkout / git absent / git fails | git unavailable, export still succeeds | test_git_unavailable_never_fails_export |
| NEG-002 | invalid | no lockfile / linked lockfile | lockfile unavailable | test_missing_or_linked_lockfile_is_unavailable |
| NEG-003 | invalid | one byte changed (valid CRC) | import exit 3 naming the member, target untouched | test_mismatched_checksum_is_refused_before_publish |
| NEG-004 | invalid | member not listed / listed but absent / size differs | exit 3 before extraction | test_listing_mismatch_is_refused |
| NEG-005 | invalid | malformed ``files`` entries | unsupported manifest, exit 3 | test_malformed_file_list_is_refused |
| NEG-006 | invalid | inspect of a modified member | exit 3, ``ReproChecksumMismatch`` | test_inspect_reports_mismatch |
| NEG-007 | invalid | inspect of unsafe / non-zip / bad format | exit 3, nothing extracted | test_inspect_refusals |
| NEG-008 | invalid | linked input escaping the project | export exit 3 | test_symlink_escape_is_refused_on_export |
| NEG-009 | invalid | untrusted provenance text | not echoed, reported unreadable | test_inspect_does_not_echo_unsafe_provenance |
| NEG-010 | invalid | non-string ``status`` (``[]``, ``{}``, number, null) | reported unreadable, no crash | test_inspect_non_string_status_is_unreadable |
| NEG-011 | invalid | non-string manifest-only ``schema_version`` | unsupported manifest, exit 3 | test_inspect_non_string_schema_version_is_refused |
| BV-001 | boundary | manifest exactly at / one over the cap | accepted / export refused, no file | test_manifest_size_limit |
| BV-002 | boundary | source files and .git next to data | never archived | test_source_is_never_bundled |
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit import __version__
from rdetoolkit.cli import _repro_provenance, repro_cmd
from rdetoolkit.cli.app import app
from tests.v2.cli.test_cli_repro_security_671 import (
    PAYLOAD,
    SECRET,
    _entries,
    _export,
    _import,
    _no_staging,
    _project,
    _rewrite,
)

GIT = shutil.which("git")
requires_git = pytest.mark.skipif(GIT is None, reason="git is not installed")


@pytest.fixture(autouse=True)
def _no_enclosing_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The temporary project must never be read as part of a checkout above it.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _manifest(archive: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive) as opened:
        return json.loads(opened.read("repro_manifest.json"))


def _export_full(tmp_path: Path, **project: bool) -> tuple[Path, Path]:
    data, report = _project(tmp_path, **project)
    archive = tmp_path / "full.zip"
    result = _export(report, archive)
    assert result.exit_code == 0, result.output
    return data, archive


def _inspect(archive: Path, *options: str):
    return CliRunner().invoke(app, ["repro", "inspect", str(archive), *options])


def _git(root: Path, *args: str) -> str:
    assert GIT is not None
    completed = subprocess.run(
        [GIT, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True, text=True,
    )
    return completed.stdout.strip()


# --------------------------------------------------------------------------- export


def test_full_manifest_lists_every_member(tmp_path: Path) -> None:
    # Given: a project with inputs in several directories, written out of order
    data, report = _project(tmp_path)
    for name in ("z.dat", "a.dat", "m/b.dat"):
        (data / "inputdata" / name).parent.mkdir(parents=True, exist_ok=True)
        (data / "inputdata" / name).write_bytes(name.encode())
    archive = tmp_path / "full.zip"
    # When: exporting the full archive
    result = _export(report, archive)
    # Then: a v3 full manifest lists every file member, path-sorted, with the archived bytes' digests
    assert result.exit_code == 0, result.output
    manifest = _manifest(archive)
    assert (manifest["schema_version"], manifest["format"], manifest["archive_kind"]) == ("3", "rdetoolkit.repro-manifest", "full")
    assert (manifest["replayable"], manifest["config_included"]) == (True, True)
    entries = _entries(archive)
    members = {name: value for name, value in entries.items() if not name.endswith("/") and name != "repro_manifest.json"}
    assert [item["path"] for item in manifest["files"]] == sorted(members)
    for item in manifest["files"]:
        content = members[item["path"]]
        assert item == {"path": item["path"], "byte_count": len(content), "sha256": "sha256:" + hashlib.sha256(content).hexdigest()}
    assert "rdeconfig.yaml" in members
    assert "data/logs/run_report_security.json" in members


def test_binary_and_empty_directory_round_trip(tmp_path: Path) -> None:
    # Given: a binary input with every byte value and an empty nested directory
    data, report = _project(tmp_path)
    binary = bytes(range(256)) * 64
    (data / "inputdata" / "raw.bin").write_bytes(binary)
    (data / "tasksupport" / "empty" / "deeper").mkdir(parents=True)
    archive = tmp_path / "full.zip"
    assert _export(report, archive).exit_code == 0
    # When: importing it
    target = tmp_path / "target"
    result = _import(archive, target)
    # Then: digest recorded for the exact bytes; both come back; stderr says what was verified
    assert result.exit_code == 0, result.output
    listed = {item["path"]: item for item in _manifest(archive)["files"]}
    assert listed["data/inputdata/raw.bin"]["sha256"] == "sha256:" + hashlib.sha256(binary).hexdigest()
    assert (target / "data" / "inputdata" / "raw.bin").read_bytes() == binary
    assert (target / "data" / "tasksupport" / "empty" / "deeper").is_dir()
    assert f"Verified {len(listed)} archived files" in result.stderr


def test_runtime_provenance_without_local_identity(tmp_path: Path) -> None:
    # Given/When: a full export
    _, archive = _export_full(tmp_path)
    provenance = _manifest(archive)["provenance"]
    # Then: the export environment is known and labelled as captured at export
    assert provenance["captured_at"] == "export"
    assert provenance["rdetoolkit"] == {"status": "known", "version": __version__}
    assert provenance["python"] == {"status": "known", "implementation": platform.python_implementation(), "version": platform.python_version()}
    assert provenance["platform"] == {
        "status": "known", "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
    }
    assert provenance["source_code"]["status"] == "not_included"
    # And: nothing that identifies the machine, the user or the local paths
    text = json.dumps(provenance)
    for leaked in (str(tmp_path), socket.gethostname(), SECRET):
        assert leaked not in text
    user = getpass.getuser()
    if len(user) >= 4:
        assert user not in text


@requires_git
def test_git_checkout_is_recorded(tmp_path: Path) -> None:
    # Given: the project is a git checkout with everything committed, plus a tracked notes file
    data, report = _project(tmp_path)
    root = data.parent
    (root / "notes.txt").write_text("v1", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    commit = _git(root, "rev-parse", "HEAD")
    # When: exporting clean, then after changing a tracked file
    clean = tmp_path / "clean.zip"
    assert _export(report, clean).exit_code == 0
    (root / "notes.txt").write_text("v2", encoding="utf-8")
    dirty = tmp_path / "dirty.zip"
    assert _export(report, dirty).exit_code == 0
    # Then: the commit is recorded, with the tracked-file dirty state
    assert _manifest(clean)["provenance"]["git"] == {"status": "known", "commit": commit, "dirty": False}
    assert _manifest(dirty)["provenance"]["git"] == {"status": "known", "commit": commit, "dirty": True}
    # And: inspect shows them as known provenance
    assert f"git: {commit} (clean)" in _inspect(clean).stdout
    assert f"git: {commit} (tracked files changed)" in _inspect(dirty).stdout


@pytest.mark.parametrize("cause", ["no_checkout", "git_absent", "git_error", "timeout", "not_executable"])
def test_git_unavailable_never_fails_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cause: str) -> None:
    # Given: no checkout, no git binary, a git that fails, one that hangs, or one that cannot start
    if cause == "git_absent":
        monkeypatch.setattr(_repro_provenance.shutil, "which", lambda name: None)
    elif cause != "no_checkout":
        monkeypatch.setattr(_repro_provenance.shutil, "which", lambda name: "/usr/bin/git")

        def fail(*args: object, **kwargs: object) -> object:
            if cause == "timeout":
                raise subprocess.TimeoutExpired("git", 5)
            if cause == "not_executable":
                raise OSError("exec format error")
            raise subprocess.CalledProcessError(128, "git")

        monkeypatch.setattr(_repro_provenance.subprocess, "run", fail)
    # When: exporting
    _, archive = _export_full(tmp_path)
    # Then: the export succeeds and git is explicitly unavailable, with a reason
    git = _manifest(archive)["provenance"]["git"]
    assert git["status"] == "unavailable"
    assert isinstance(git["reason"], str) and git["reason"]
    assert set(git) == {"status", "reason"}


def test_git_is_run_hardened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: an environment that would redirect git elsewhere
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "elsewhere"))
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def record(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="0" * 40 + "\n" if "rev-parse" in argv else "", stderr="")

    monkeypatch.setattr(_repro_provenance.shutil, "which", lambda name: "/usr/bin/git")
    monkeypatch.setattr(_repro_provenance.subprocess, "run", record)
    # When: capturing provenance
    git = _repro_provenance.capture_provenance(tmp_path)["git"]
    # Then: local, non-interactive, no fsmonitor hook, no inherited repository redirection, bounded time
    assert git == {"status": "known", "commit": "0" * 40, "dirty": False}
    for argv, kwargs in calls:
        assert argv[:3] == ["/usr/bin/git", "-c", "core.fsmonitor=false"]
        env = kwargs["env"]
        assert "GIT_DIR" not in env and "GIT_WORK_TREE" not in env
        assert (env["GIT_TERMINAL_PROMPT"], env["GIT_OPTIONAL_LOCKS"]) == ("0", "0")
        assert kwargs["timeout"] > 0 and kwargs["check"] is True
    assert any("--untracked-files=no" in argv for argv, _ in calls)


@pytest.mark.parametrize("stdout", ["not-a-commit\n", "", "g" * 40 + "\n"])
def test_unexpected_git_output_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    # Given: git answers with something that is not an object id
    monkeypatch.setattr(_repro_provenance.shutil, "which", lambda name: "/usr/bin/git")
    monkeypatch.setattr(
        _repro_provenance.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=""),
    )
    # When/Then: git is unavailable rather than recorded wrongly
    assert _repro_provenance.capture_provenance(tmp_path)["git"]["status"] == "unavailable"


def test_lockfile_digest_and_order(tmp_path: Path) -> None:
    # Given: two supported lockfiles at the project root
    data, report = _project(tmp_path)
    (data.parent / "poetry.lock").write_text("poetry", encoding="utf-8")
    (data.parent / "uv.lock").write_bytes(b"uv-lock-content")
    archive = tmp_path / "full.zip"
    # When: exporting
    assert _export(report, archive).exit_code == 0
    # Then: the first in the documented order is recorded by name and digest, its content is not archived
    lockfile = _manifest(archive)["provenance"]["lockfile"]
    assert lockfile == {"status": "known", "name": "uv.lock", "sha256": "sha256:" + hashlib.sha256(b"uv-lock-content").hexdigest()}
    assert not any(name.endswith(".lock") for name in _entries(archive))


def test_lockfile_order_is_fixed() -> None:
    # Then: the supported names and their precedence are part of the documented contract
    assert _repro_provenance.LOCKFILE_NAMES == ("uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock", "pylock.toml")


@pytest.mark.parametrize("kind", ["missing", "symlink", "directory"])
def test_missing_or_linked_lockfile_is_unavailable(tmp_path: Path, kind: str) -> None:
    # Given: no lockfile, a lockfile that is a link outside the project, or a directory named like one
    data, report = _project(tmp_path)
    if kind == "symlink":
        outside = tmp_path / "outside.lock"
        outside.write_text("outside", encoding="utf-8")
        (data.parent / "uv.lock").symlink_to(outside)
    elif kind == "directory":
        (data.parent / "uv.lock").mkdir()
    archive = tmp_path / "full.zip"
    # When: exporting
    assert _export(report, archive).exit_code == 0
    # Then: lockfile is unavailable, with a reason; nothing outside the project was read into the manifest
    lockfile = _manifest(archive)["provenance"]["lockfile"]
    assert lockfile["status"] == "unavailable" and lockfile["reason"]
    assert "sha256" not in lockfile


def test_unreadable_lockfile_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a lockfile that cannot be read
    (tmp_path / "uv.lock").write_text("x", encoding="utf-8")

    def refuse(path: Path) -> str:
        raise PermissionError("denied")

    monkeypatch.setattr(_repro_provenance, "_file_digest", refuse)
    # When/Then: unavailable, not an export failure
    assert _repro_provenance.capture_provenance(tmp_path)["lockfile"]["status"] == "unavailable"


def test_flat_project_reads_lockfile_at_data_root(tmp_path: Path) -> None:
    # Given: an alias-flat project (data root == project root) with a lockfile
    data, report = _project(tmp_path, flat=True)
    (data / "uv.lock").write_bytes(b"flat")
    archive = tmp_path / "full.zip"
    # When/Then: the lockfile is found at that root
    assert _export(report, archive).exit_code == 0
    assert _manifest(archive)["provenance"]["lockfile"]["name"] == "uv.lock"


def test_manifest_only_carries_provenance(tmp_path: Path) -> None:
    # Given: a project with a lockfile
    data, report = _project(tmp_path)
    (data.parent / "uv.lock").write_bytes(b"lock")
    archive = tmp_path / "metadata.zip"
    # When: exporting metadata only
    assert _export(report, archive, "--manifest-only").exit_code == 0
    # Then: v3 with provenance, still without names, contents or local paths
    content = _entries(archive)["repro_manifest.json"]
    manifest = json.loads(content)
    assert (manifest["schema_version"], manifest["archive_kind"]) == ("3", "manifest-only")
    assert manifest["provenance"]["rdetoolkit"]["version"] == __version__
    assert manifest["provenance"]["lockfile"]["name"] == "uv.lock"
    for leaked in (SECRET.encode(), PAYLOAD, str(tmp_path).encode()):
        assert leaked not in content


def test_source_is_never_bundled(tmp_path: Path) -> None:
    # Given: flow source, a secret file and a .git directory next to the data directory
    data, report = _project(tmp_path)
    (data.parent / "main.py").write_text("SECRET_KEY = 'x'\n", encoding="utf-8")
    (data.parent / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    (data.parent / ".git").mkdir()
    archive = tmp_path / "full.zip"
    # When: exporting
    assert _export(report, archive).exit_code == 0
    # Then: only the export layout is archived
    names = set(_entries(archive))
    assert all(name.startswith("data/") or name in {"rdeconfig.yaml", "repro_manifest.json"} for name in names)
    assert not any(name.endswith((".py", ".env")) or ".git" in name for name in names)


def test_symlink_escape_is_refused_on_export(tmp_path: Path) -> None:
    # Given: an input that links to a file outside the project
    data, report = _project(tmp_path)
    outside = tmp_path / "credentials.txt"
    outside.write_text("secret", encoding="utf-8")
    (data / "inputdata" / "link.txt").symlink_to(outside)
    archive = tmp_path / "full.zip"
    # When/Then: refused, no archive left behind
    result = _export(report, archive)
    assert result.exit_code == 3
    assert "symbolic link" in result.stderr
    assert not archive.exists()


@pytest.mark.parametrize("delta", [0, -1])
def test_manifest_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delta: int) -> None:
    # Given: the manifest size an export needs, then the cap set exactly there or one byte below
    _, archive = _export_full(tmp_path)
    size = len(_entries(archive)["repro_manifest.json"])
    archive.unlink()
    monkeypatch.setattr(repro_cmd, "_MAX_MANIFEST_BYTES", size + delta)
    _, report = tmp_path / "project" / "data", tmp_path / "project" / "data" / "logs" / "run_report_security.json"
    # When: exporting again (same inputs, same manifest size)
    result = _export(report, archive)
    # Then: the cap is inclusive, and an over-cap export leaves no file
    assert (result.exit_code == 0) is (delta == 0), result.output
    assert archive.exists() is (delta == 0)
    if delta:
        assert "manifest" in result.stderr


def test_default_manifest_cap_fits_the_member_limit() -> None:
    # Then: a listing of the maximum member count with typical names fits the cap
    assert repro_cmd._MAX_MANIFEST_BYTES == 64 * 1024**2
    assert repro_cmd._MAX_MEMBERS * 200 < repro_cmd._MAX_MANIFEST_BYTES


# --------------------------------------------------------------------------- import


def _replace(tmp_path: Path, archive: Path, changes: dict[str, bytes | None]) -> Path:
    entries = _entries(archive)
    for name, value in changes.items():
        if value is None:
            entries.pop(name)
        else:
            entries[name] = value
    return _rewrite(tmp_path / "altered.zip", entries)


@pytest.mark.parametrize("member", ["data/inputdata/{secret}.dat", "rdeconfig.yaml", "data/logs/run_report_security.json"])
@pytest.mark.parametrize("existing", [False, True])
def test_mismatched_checksum_is_refused_before_publish(tmp_path: Path, member: str, existing: bool) -> None:
    # Given: one member with one byte changed after export (same size), rewritten with a valid zip CRC
    _, archive = _export_full(tmp_path)
    name = member.format(secret=SECRET)
    original = _entries(archive)[name]
    middle = len(original) // 2
    altered = original[:middle] + bytes([original[middle] ^ 0x01]) + original[middle + 1 :]
    broken = _replace(tmp_path, archive, {name: altered})
    target = tmp_path / "target"
    if existing:
        target.mkdir()
    # When: importing it
    result = _import(broken, target)
    # Then: refused with a checksum error naming the member, nothing published, staging removed
    assert result.exit_code == 3, result.output
    assert "checksum" in result.stderr and name in result.stderr
    assert target.exists() is existing
    if existing:
        assert list(target.iterdir()) == []
    assert _no_staging(tmp_path)


@pytest.mark.parametrize("case", ["unlisted", "absent", "size"])
def test_listing_mismatch_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    # Given: a member the manifest does not list, a listed member missing, or a declared size that differs
    _, archive = _export_full(tmp_path)
    manifest = _manifest(archive)
    changes: dict[str, bytes | None] = {}
    if case == "unlisted":
        changes["data/inputdata/extra.dat"] = b"extra"
    elif case == "absent":
        changes[f"data/inputdata/{SECRET}.dat"] = None
    else:
        for item in manifest["files"]:
            if item["path"].startswith("data/inputdata/"):
                item["byte_count"] += 1
        changes["repro_manifest.json"] = json.dumps(manifest).encode()
    broken = _replace(tmp_path, archive, changes)
    opened: list[str] = []
    real_open = zipfile.ZipFile.open

    def track(self: zipfile.ZipFile, name: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(name if isinstance(name, str) else name.filename)
        return real_open(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", track)
    # When: importing it
    result = _import(broken, tmp_path / "target")
    # Then: refused from the listing alone, before any member besides the manifest is read
    assert result.exit_code == 3, result.output
    assert "manifest" in result.stderr
    assert opened == ["repro_manifest.json"]
    assert not (tmp_path / "target").exists()
    assert _no_staging(tmp_path)


@pytest.mark.parametrize(
    "files",
    [
        "not-a-list",
        [{"path": "rdeconfig.yaml", "byte_count": 1}],
        [{"path": "rdeconfig.yaml", "byte_count": -1, "sha256": "sha256:" + "0" * 64}],
        [{"path": "rdeconfig.yaml", "byte_count": True, "sha256": "sha256:" + "0" * 64}],
        [{"path": "rdeconfig.yaml", "byte_count": 1, "sha256": "md5:abc"}],
        [{"path": 7, "byte_count": 1, "sha256": "sha256:" + "0" * 64}],
        ["rdeconfig.yaml"],
        [{"path": "../escape", "byte_count": 1, "sha256": "sha256:" + "0" * 64}],
        [{"path": "data/other/x", "byte_count": 1, "sha256": "sha256:" + "0" * 64}],
        [{"path": "repro_manifest.json", "byte_count": 1, "sha256": "sha256:" + "0" * 64}],
        "duplicate",
    ],
)
def test_malformed_file_list_is_refused(tmp_path: Path, files: object) -> None:
    # Given: a v3 manifest whose file list is not well formed
    _, archive = _export_full(tmp_path)
    manifest = _manifest(archive)
    manifest["files"] = [*manifest["files"], manifest["files"][0]] if files == "duplicate" else files
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(manifest).encode()})
    # When/Then: refused as an unsupported manifest
    result = _import(broken, tmp_path / "target")
    assert result.exit_code == 3, result.output
    assert "Unsupported repro_manifest.json" in result.stderr
    assert not (tmp_path / "target").exists()


@pytest.mark.parametrize("field", [("format", "other"), ("archive_kind", "full-ish"), ("replayable", False)])
def test_v3_manifest_identity_is_required(tmp_path: Path, field: tuple[str, object]) -> None:
    # Given: a v3 manifest that does not say it is a full rdetoolkit repro manifest
    _, archive = _export_full(tmp_path)
    manifest = {**_manifest(archive), field[0]: field[1]}
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(manifest).encode()})
    # When/Then: refused
    result = _import(broken, tmp_path / "target")
    assert result.exit_code == 3, result.output
    assert not (tmp_path / "target").exists()


def _as_v1(tmp_path: Path, archive: Path) -> Path:
    manifest = _manifest(archive)
    legacy = {"schema_version": "1", "config_included": True, "config_digest": manifest["config_digest"]}
    return _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(legacy).encode()})


def test_old_manifest_imports_with_provenance_unavailable(tmp_path: Path) -> None:
    # Given: an archive written before #699 (manifest schema_version "1")
    _, archive = _export_full(tmp_path)
    legacy = _as_v1(tmp_path, archive)
    target = tmp_path / "target"
    # When: importing it
    result = _import(legacy, target)
    # Then: still importable, and it says what could not be checked
    assert result.exit_code == 0, result.output
    assert (target / "data" / "inputdata" / f"{SECRET}.dat").read_bytes() == PAYLOAD
    assert "Provenance unavailable" in result.stderr
    assert "per-file checksums" in result.stderr


@pytest.mark.parametrize("mutation", ["missing_config", "bad_config", "unreadable_report", "missing_inputs", "wrong_report_digest"])
def test_old_manifest_keeps_the_consistency_checks(tmp_path: Path, mutation: str) -> None:
    # Given: a v1 archive (no file list, so nothing is caught by the listing) with one part broken
    _, archive = _export_full(tmp_path)
    legacy = _entries(_as_v1(tmp_path, archive))
    report_name = next(name for name in legacy if name.startswith("data/logs/") and not name.endswith("/"))
    if mutation == "missing_config":
        legacy.pop("rdeconfig.yaml")
    elif mutation == "bad_config":
        legacy["rdeconfig.yaml"] = b"custom: [unclosed"
    elif mutation == "unreadable_report":
        legacy[report_name] = b"{"
    elif mutation == "missing_inputs":
        legacy = {name: value for name, value in legacy.items() if not name.startswith("data/invoice")}
    else:
        legacy[report_name] = json.dumps({**json.loads(legacy[report_name]), "config_digest": "sha256:" + "0" * 64}).encode()
    target = tmp_path / "target"
    # When/Then: the replay checks still refuse it and publish nothing
    result = _import(_rewrite(tmp_path / "legacy.zip", legacy), target)
    assert result.exit_code == 3, result.output
    assert not target.exists()
    assert _no_staging(tmp_path)


def test_v1_import_cannot_be_downgraded_from_v3_files(tmp_path: Path) -> None:
    # Given: a v1 manifest that still carries a (wrong) file list
    _, archive = _export_full(tmp_path)
    manifest = _manifest(archive)
    legacy = {"schema_version": "1", "config_included": True, "config_digest": manifest["config_digest"]}
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(legacy).encode(), f"data/inputdata/{SECRET}.dat": b"changed"})
    # When/Then: a v1 archive is checked as v1 (no per-file digests), and import says so
    result = _import(broken, tmp_path / "target")
    assert result.exit_code == 0, result.output
    assert "per-file checksums" in result.stderr


# --------------------------------------------------------------------------- inspect


def test_inspect_full_archive_text(tmp_path: Path) -> None:
    # Given: a full v3 archive from a project without git or lockfile
    _, archive = _export_full(tmp_path)
    before = sorted(tmp_path.rglob("*"))
    # When: inspecting it
    result = _inspect(archive)
    # Then: verified inputs, known provenance and unavailable attributes in separate sections
    assert result.exit_code == 0, result.output
    out = result.stdout
    count = len(_manifest(archive)["files"])
    assert "Archive: full, manifest schema_version 3, replayable" in out
    assert f"Verified inputs: {count} of {count} files match" in out
    assert out.index("Known provenance") < out.index("Unknown or unavailable")
    assert f"rdetoolkit: {__version__}" in out
    assert f"python: {platform.python_implementation()} {platform.python_version()}" in out
    assert "git: " in out.split("Unknown or unavailable")[1]
    assert "source_code: " in out.split("Unknown or unavailable")[1]
    assert "not proof that a rerun reproduces" in out
    # And: nothing was extracted or created
    assert sorted(tmp_path.rglob("*")) == before


def test_inspect_full_archive_json(tmp_path: Path) -> None:
    # Given: a full v3 archive
    _, archive = _export_full(tmp_path)
    # When: inspecting it as JSON
    result = _inspect(archive, "--format", "json")
    # Then: the diagnostics envelope with the archive, inputs and provenance split
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    count = len(_manifest(archive)["files"])
    assert (payload["format"], payload["schema_version"], payload["command"]) == ("rdetoolkit.diagnostics", "1", "repro inspect")
    assert payload["archive"] == {"schema_version": "3", "archive_kind": "full", "replayable": True, "config_digest": _manifest(archive)["config_digest"]}
    assert payload["inputs"] == {"status": "verified", "file_count": count, "verified_count": count, "mismatched": []}
    provenance = payload["provenance"]
    assert provenance["captured_at"] == "export"
    assert provenance["known"]["rdetoolkit"] == {"version": __version__}
    assert set(provenance["unavailable"]) == {"git", "lockfile", "source_code"}
    assert payload["status"] == "warning"
    names = {(item["name"], item["subject"], item["code"]) for item in payload["diagnostics"]}
    assert ("ReproProvenanceUnavailable", "git", None) in names
    assert ("ReproSourceNotIncluded", "source_code", None) in names


def test_inspect_reports_mismatch(tmp_path: Path) -> None:
    # Given: a full archive with one changed member
    _, archive = _export_full(tmp_path)
    name = f"data/inputdata/{SECRET}.dat"
    broken = _replace(tmp_path, archive, {name: b"X" + PAYLOAD[1:]})
    # When: inspecting it as text and as JSON
    text = _inspect(broken)
    as_json = _inspect(broken, "--format", "json")
    # Then: both exit 3 and name the member; JSON carries a symbolic error finding
    assert text.exit_code == 3 and as_json.exit_code == 3
    assert f"checksum mismatch: {name}" in text.stdout
    payload = json.loads(as_json.stdout)
    assert payload["status"] == "failed"
    assert payload["inputs"]["status"] == "mismatch"
    assert payload["inputs"]["mismatched"] == [name]
    assert any(item["name"] == "ReproChecksumMismatch" and item["subject"] == name and item["code"] is None for item in payload["diagnostics"])


def test_inspect_reports_listing_mismatch(tmp_path: Path) -> None:
    # Given: a member that the manifest does not list
    _, archive = _export_full(tmp_path)
    broken = _replace(tmp_path, archive, {"data/inputdata/extra.dat": b"x"})
    # When/Then: reported as a mismatch for that member
    payload = json.loads(_inspect(broken, "--format", "json").stdout)
    assert "data/inputdata/extra.dat" in payload["inputs"]["mismatched"]


def test_inspect_manifest_only(tmp_path: Path) -> None:
    # Given: a v3 manifest-only archive
    _, report = _project(tmp_path)
    archive = tmp_path / "metadata.zip"
    assert _export(report, archive, "--manifest-only").exit_code == 0
    # When: inspecting it
    payload = json.loads(_inspect(archive, "--format", "json").stdout)
    # Then: inputs are not included, provenance is known
    assert payload["archive"]["archive_kind"] == "manifest-only"
    assert payload["archive"]["replayable"] is False
    assert payload["inputs"]["status"] == "not_included"
    assert payload["provenance"]["known"]["python"]["version"] == platform.python_version()


@pytest.mark.parametrize("version", ["1", "2"])
def test_inspect_old_manifests(tmp_path: Path, version: str) -> None:
    # Given: a v1 full archive, or a v2 manifest-only archive
    _, archive = _export_full(tmp_path)
    if version == "1":
        old = _as_v1(tmp_path, archive)
    else:
        manifest = {**_manifest(archive), "schema_version": "2", "archive_kind": "manifest-only", "replayable": False}
        manifest.pop("provenance")
        old = _rewrite(tmp_path / "old.zip", {"repro_manifest.json": json.dumps(manifest).encode()})
    # When: inspecting it
    result = _inspect(old, "--format", "json")
    text = _inspect(old)
    # Then: readable; every attribute is unavailable because the manifest predates provenance
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["provenance"]["known"] == {}
    assert set(payload["provenance"]["unavailable"]) == set(_repro_provenance.ATTRIBUTES)
    assert all("predates" in reason for name, reason in payload["provenance"]["unavailable"].items() if name != "source_code")
    assert payload["inputs"]["status"] == ("unverifiable" if version == "1" else "not_included")
    assert "provenance unavailable" in text.stdout.lower()


def test_inspect_does_not_echo_unsafe_provenance(tmp_path: Path) -> None:
    # Given: a manifest whose provenance holds control characters, an oversized value and wrong types
    _, archive = _export_full(tmp_path)
    manifest = _manifest(archive)
    manifest["provenance"]["rdetoolkit"]["version"] = "2.0\x1b[31m"
    manifest["provenance"]["python"]["version"] = "3" * 500
    manifest["provenance"]["platform"] = "Linux"
    manifest["provenance"]["git"] = {"status": "known", "commit": "nothex", "dirty": False}
    manifest["provenance"]["lockfile"] = {"status": "known", "name": "evil.lock", "sha256": "sha256:" + "0" * 64}
    manifest["provenance"]["source_code"] = {"status": "included", "reason": "x"}
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(manifest).encode()})
    # When: inspecting it
    result = _inspect(broken)
    payload = json.loads(_inspect(broken, "--format", "json").stdout)
    # Then: none of them is echoed; each is reported as unreadable
    assert result.exit_code == 0, result.output
    assert "\x1b" not in result.stdout and "3" * 500 not in result.stdout and "evil.lock" not in result.stdout
    assert payload["provenance"]["known"] == {}
    for name in ("rdetoolkit", "python", "platform", "git", "lockfile", "source_code"):
        assert "unreadable" in payload["provenance"]["unavailable"][name]


def test_inspect_unavailable_without_readable_reason(tmp_path: Path) -> None:
    # Given: an unavailable attribute whose reason is not printable text
    _, archive = _export_full(tmp_path)
    manifest = _manifest(archive)
    manifest["provenance"]["git"] = {"status": "unavailable", "reason": "\x07bell"}
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(manifest).encode()})
    # When/Then: a fixed reason replaces it
    payload = json.loads(_inspect(broken, "--format", "json").stdout)
    assert payload["provenance"]["unavailable"]["git"] == "unavailable (no readable reason recorded)"


@pytest.mark.parametrize("captured_at", ["\x1b[2J", 3])
def test_inspect_unsafe_captured_at_is_dropped(tmp_path: Path, captured_at: object) -> None:
    _, archive = _export_full(tmp_path)
    manifest = _manifest(archive)
    manifest["provenance"]["captured_at"] = captured_at
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(manifest).encode()})
    payload = json.loads(_inspect(broken, "--format", "json").stdout)
    assert payload["provenance"]["captured_at"] is None


@pytest.mark.parametrize("case", ["traversal", "not_zip", "missing", "bad_format", "future", "no_manifest", "manifest_only_v1", "not_object"])
def test_inspect_refusals(tmp_path: Path, case: str) -> None:
    # Given: an unsafe, unreadable, absent or unsupported archive, or an unknown --format
    _, archive = _export_full(tmp_path)
    options: tuple[str, ...] = ()
    if case == "traversal":
        archive = _replace(tmp_path, archive, {"../escape": b"x"})
    elif case == "not_zip":
        archive.write_bytes(b"not a zip")
    elif case == "missing":
        archive = tmp_path / "absent.zip"
    elif case == "bad_format":
        options = ("--format", "yaml")
    elif case == "future":
        archive = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps({**_manifest(archive), "schema_version": "999"}).encode()})
    elif case == "no_manifest":
        archive = _replace(tmp_path, archive, {"repro_manifest.json": None})
    elif case == "not_object":
        archive = _replace(tmp_path, archive, {"repro_manifest.json": b"[]"})
    else:
        archive = _rewrite(tmp_path / "odd.zip", {"repro_manifest.json": json.dumps({"schema_version": "1", "archive_kind": "manifest-only"}).encode()})
    # When: inspecting it
    result = _inspect(archive, *options)
    # Then: exit 3, nothing extracted
    assert result.exit_code == 3, result.output
    assert not (tmp_path / "escape").exists()


def test_import_and_inspect_stay_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: no network at all
    _, archive = _export_full(tmp_path)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("repro must stay local")

    monkeypatch.setattr(socket, "socket", no_network)
    # When/Then: inspect and import both work
    assert _inspect(archive).exit_code == 0
    assert _import(archive, tmp_path / "target").exit_code == 0


def test_export_digest_is_of_archived_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: an input that changes on disk after it is listed but before the archive is written
    data, report = _project(tmp_path)
    path = data / "inputdata" / f"{SECRET}.dat"
    real = repro_cmd._preview_export

    def change_after_preview(*args: Any, **kwargs: Any) -> None:
        real(*args, **kwargs)
        path.write_bytes(b"changed-later")

    monkeypatch.setattr(repro_cmd, "_preview_export", change_after_preview)
    archive = tmp_path / "full.zip"
    # When: exporting and importing
    assert _export(report, archive).exit_code == 0
    # Then: the manifest digest describes what the archive holds, so the import verifies
    assert _import(archive, tmp_path / "target").exit_code == 0, "digest must be taken from the archived stream"
    assert (tmp_path / "target" / "data" / "inputdata" / f"{SECRET}.dat").read_bytes() == b"changed-later"


def test_large_file_entry_uses_zip64_when_needed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: zipfile's ZIP64 threshold lowered so a small input needs it
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 8)
    data, report = _project(tmp_path)
    (data / "inputdata" / "big.bin").write_bytes(os.urandom(64))
    archive = tmp_path / "full.zip"
    # When/Then: export and import still work
    assert _export(report, archive).exit_code == 0
    assert _import(archive, tmp_path / "target").exit_code == 0


@pytest.mark.parametrize("status", [[], {}, ["known"], 1, None])
def test_inspect_non_string_status_is_unreadable(tmp_path: Path, status: object) -> None:
    # Given: provenance attributes whose status is not a string (unhashable values included)
    _, archive = _export_full(tmp_path)
    manifest = _manifest(archive)
    manifest["provenance"]["git"] = {"status": status, "reason": "x"}
    manifest["provenance"]["rdetoolkit"] = {"status": status, "version": __version__}
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(manifest).encode()})
    # When: inspecting it as text and as JSON
    text = _inspect(broken)
    as_json = _inspect(broken, "--format", "json")
    # Then: no crash; both attributes are reported as unreadable, never as known
    assert text.exit_code == 0, text.output
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.stdout)
    assert payload["provenance"]["unavailable"]["git"] == "unreadable in the manifest"
    assert payload["provenance"]["unavailable"]["rdetoolkit"] == "unreadable in the manifest"


@pytest.mark.parametrize("version", [[], {}, ["3"]])
def test_inspect_non_string_schema_version_is_refused(tmp_path: Path, version: object) -> None:
    # Given: a manifest-only archive whose schema_version is not a string
    _, report = _project(tmp_path)
    archive = tmp_path / "metadata.zip"
    assert _export(report, archive, "--manifest-only").exit_code == 0
    manifest = _manifest(archive)
    manifest["schema_version"] = version
    broken = _replace(tmp_path, archive, {"repro_manifest.json": json.dumps(manifest).encode()})
    # When
    result = _inspect(broken)
    # Then: an unsupported-manifest usage error (exit 3), not a crash
    assert result.exit_code == 3, result.output
    assert "Unsupported repro_manifest.json" in result.output
