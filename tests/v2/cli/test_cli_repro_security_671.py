"""Data handling and archive safety of ``repro export`` / ``repro import`` (#671).

EP table:
| Partition | Expected | Test |
| --- | --- | --- |
| --manifest-only, nested and alias-flat | no input bytes, names, invoice or config values; refused by import | test_manifest_only_holds_no_data |
| full export | confidentiality warning and per-directory inventory on stderr | test_full_export_previews_contents |
| link / special file / unreadable directory among inputs | export refused, no archive | test_export_refuses_unarchivable_inputs |
| existing or concurrently created output | never replaced | test_export_never_replaces_output, test_export_concurrent_destination |
| unsafe member names (all platforms / Windows only) | refused before extraction | test_unsafe_member_names, test_windows_only_names |
| links, special files, encryption, bzip2, directory payloads | refused before extraction | test_unsupported_member_kinds |
| duplicates (case, Unicode normalisation), file/directory clash | refused | test_duplicate_and_conflicting_members |
| count, total size, whole-archive ratio | refused | test_archive_limits |
| broken manifest / config / report / digests | no project published | test_inconsistent_archives |
| CRC error, extraction or publish failure | target unchanged, staging removed | test_failure_leaves_target_unchanged |
| target is a symlink or a file | refused, untouched | test_import_target_refusals |
| POSIX-legal names (``aux.csv``, ``12:30.csv``) and odd report names | export, import and digest round trip | test_portable_names_round_trip |
BV table:
| Boundary | Expected | Test |
| --- | --- | --- |
| members = limit / limit + 1 | accepted / refused | test_archive_limits |
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
import sys
import unicodedata
import warnings
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli import repro_cmd
from rdetoolkit.cli.app import app
from rdetoolkit.runner.config_loader import compute_config_digest, load_config

SECRET = "unpublished-sample-731824"
PAYLOAD = b"UNIQUE-reproduction-input-payload"


def _project(tmp_path: Path, *, flat: bool = False) -> tuple[Path, Path]:
    root = tmp_path / "project"
    data = root if flat else root / "data"
    for directory in ("inputdata", "invoice", "tasksupport", "logs"):
        (data / directory).mkdir(parents=True)
    (data / "inputdata" / f"{SECRET}.dat").write_bytes(PAYLOAD)
    (data / "invoice" / "invoice.json").write_text(json.dumps({"basic": {"dataName": SECRET}}), encoding="utf-8")
    (root / "rdeconfig.yaml").write_text(f"custom:\n  sample: {SECRET}\n", encoding="utf-8")
    digest = compute_config_digest(load_config(root, data_root=data))
    report = data / "logs" / "run_report_security.json"
    report.write_text(json.dumps({
        "schema_version": "2", "run_id": "security", "status": "failed", "flow_id": SECRET, "mode": "invoice",
        "started_at": SECRET, "duration_ms": 0, "config_digest": digest, "iterations": [],
        "warnings": [{"message": SECRET}], "error": {"code": 3001, "message": SECRET},
    }), encoding="utf-8")
    return data, report


def _export(report: Path, output: Path, *options: str):
    return CliRunner().invoke(app, ["repro", "export", str(report), "-o", str(output), *options])


def _import(archive: Path, target: Path):
    return CliRunner().invoke(app, ["repro", "import", str(archive), str(target)])


def _full_archive(tmp_path: Path) -> Path:
    _, report = _project(tmp_path)
    archive = tmp_path / "full.zip"
    result = _export(report, archive)
    assert result.exit_code == 0, result.output
    return archive


def _entries(archive: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(archive) as opened:
        return {info.filename: opened.read(info) for info in opened.infolist()}


def _rewrite(path: Path, entries: dict[str, bytes], **kwargs: int) -> Path:
    with zipfile.ZipFile(path, "w", **kwargs) as opened:
        for name, value in entries.items():
            opened.writestr(name, value)
    return path


def _no_staging(tmp_path: Path) -> bool:
    return not list(tmp_path.glob(".rdetoolkit-import-*"))


@pytest.mark.parametrize("flat", [False, True])
def test_manifest_only_holds_no_data(tmp_path: Path, flat: bool) -> None:
    # Given: both layouts, with a secret in a file name, the input bytes, the invoice, the config and the report text
    _, report = _project(tmp_path, flat=flat)
    archive = tmp_path / "metadata.zip"
    # When: exporting metadata only
    result = _export(report, archive, "--manifest-only")
    # Then: one manifest without any of those values, explicitly not replayable
    assert result.exit_code == 0, result.output
    entries = _entries(archive)
    assert list(entries) == ["repro_manifest.json"]
    content = entries["repro_manifest.json"]
    for leaked in (SECRET.encode(), PAYLOAD, str(tmp_path).encode()):
        assert leaked not in content
    manifest = json.loads(content)
    assert (manifest["schema_version"], manifest["archive_kind"], manifest["replayable"], manifest["config_included"]) == ("2", "manifest-only", False, False)
    assert manifest["files"][0]["sha256"] == "sha256:" + hashlib.sha256(PAYLOAD).hexdigest()
    assert manifest["directories"]["inputdata"] == {"file_count": 1, "byte_count": len(PAYLOAD)}
    assert manifest["diagnostics"]["command"] == "report diagnose"
    # And: import refuses it, saying why
    refused = _import(archive, tmp_path / "target")
    assert refused.exit_code == 3
    assert "--manifest-only" in refused.stderr
    assert "Unable to import" not in refused.stderr  # one reason, not two
    assert not (tmp_path / "target").exists()


def test_manifest_only_refuses_unreadable_report_without_echo(tmp_path: Path) -> None:
    # Given: a report that is not JSON and quotes a secret
    _, report = _project(tmp_path)
    report.write_text(f"{SECRET}: not json", encoding="utf-8")
    output = tmp_path / "metadata.zip"
    # When: exporting metadata only
    result = _export(report, output, "--manifest-only")
    # Then: a fixed message, no archive
    assert result.exit_code == 3, result.output
    assert SECRET not in result.output
    assert not output.exists()


@pytest.mark.parametrize("digest", [None, 7, "not-a-digest"])
def test_manifest_only_omits_malformed_config_digest(tmp_path: Path, digest: object) -> None:
    # Given: a report whose config_digest is not a sha256 digest
    _, report = _project(tmp_path)
    report.write_text(json.dumps({**json.loads(report.read_text(encoding="utf-8")), "config_digest": digest}), encoding="utf-8")
    archive = tmp_path / "metadata.zip"
    # When/Then: metadata is still written, with the digest left out
    assert _export(report, archive, "--manifest-only").exit_code == 0
    assert json.loads(_entries(archive)["repro_manifest.json"])["config_digest"] is None


def test_full_export_previews_contents(tmp_path: Path) -> None:
    # Given: a full reproduction tree
    _, report = _project(tmp_path)
    # When: exporting it with no network available
    result = _export(report, tmp_path / "full.zip")
    # Then: stderr warns and lists what the archive holds, per directory
    assert result.exit_code == 0, result.output
    assert "confidential" not in result.stdout
    assert "unpublished research data" in result.stderr
    assert f"data/inputdata/: 1 files, {len(PAYLOAD)} bytes" in result.stderr
    assert "rdeconfig.yaml" in result.stderr
    assert result.stdout.strip() == str(tmp_path / "full.zip")


@pytest.mark.parametrize("kind", ["file_link", "dir_link", "root_link", "fifo", "unreadable"])
def test_export_refuses_unarchivable_inputs(tmp_path: Path, kind: str) -> None:
    # Given: an input that would be followed outside the project, read as a device, or silently skipped
    data, report = _project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private").write_bytes(PAYLOAD)
    hidden = data / "inputdata" / "private"
    if kind == "file_link":
        (data / "inputdata" / "link").symlink_to(outside / "private")
    elif kind == "dir_link":
        (data / "inputdata" / "link").symlink_to(outside, target_is_directory=True)
    elif kind == "root_link":
        (data / "tasksupport").rmdir()
        (data / "tasksupport").symlink_to(outside, target_is_directory=True)
    elif kind == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("no FIFOs on this platform")
        os.mkfifo(data / "inputdata" / "pipe")
    else:
        hidden.mkdir()
        (hidden / "required.bin").write_bytes(PAYLOAD)
        hidden.chmod(0)
        if os.access(hidden, os.R_OK):
            hidden.chmod(0o700)
            pytest.skip("this user can read directories without permission bits")
    output = tmp_path / "bundle.zip"
    try:
        for options in ((), ("--manifest-only",)):
            # When: exporting either kind of archive
            result = _export(report, output, *options)
            # Then: refused with no archive left
            assert result.exit_code == 3, result.output
            assert not output.exists()
    finally:
        if hidden.exists():
            hidden.chmod(0o700)


def test_export_never_replaces_output(tmp_path: Path) -> None:
    # Given: an existing file at the output path
    _, report = _project(tmp_path)
    output = tmp_path / "existing.zip"
    output.write_bytes(b"keep")
    # When/Then: export refuses and the file is untouched
    for options in ((), ("--manifest-only",)):
        assert _export(report, output, *options).exit_code == 3
        assert output.read_bytes() == b"keep"


def test_export_concurrent_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: another writer creates the output after the existence check
    _, report = _project(tmp_path)
    output = tmp_path / "full.zip"
    real_preview = repro_cmd._preview_export

    def concurrent_writer(*args: object, **kwargs: object) -> None:
        real_preview(*args, **kwargs)
        output.write_bytes(b"other writer")

    monkeypatch.setattr(repro_cmd, "_preview_export", concurrent_writer)
    # When/Then: exclusive creation keeps the other writer's file
    assert _export(report, output).exit_code == 3
    assert output.read_bytes() == b"other writer"


def test_export_write_failure_removes_partial_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a disk error after the output was created
    _, report = _project(tmp_path)
    output = tmp_path / "full.zip"

    def broken_write(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(repro_cmd, "_write_full_archive", broken_write)
    # When/Then: exit 3 and no partial archive
    assert _export(report, output).exit_code == 3
    assert not output.exists()


@pytest.mark.parametrize(
    "name",
    ["../escape", "/absolute", "data/inputdata/../../escape", "data\\inputdata\\escape", "data/inputdata/a\x01",
     "data/inputdata/a\x7f", "data/./inputdata/a", "data//inputdata/a", "C:/escape", "unexpected.py",
     "data/other/a", "data/logs/notes.txt", "data/inputdata"],
)
def test_unsafe_member_names(tmp_path: Path, name: str) -> None:
    # Given: an otherwise valid archive with one unsafe or unexpected member
    entries = {**_entries(_full_archive(tmp_path)), name: b"bad"}
    archive = _rewrite(tmp_path / "evil.zip", entries)
    target = tmp_path / "target"
    # When: importing it
    result = _import(archive, target)
    # Then: refused for the member, before anything is extracted
    assert result.exit_code == 3, result.output
    assert "member" in result.stderr
    assert not target.exists()
    assert not (tmp_path / "escape").exists()
    assert _no_staging(tmp_path)


@pytest.mark.parametrize("name", ["data/inputdata/a:stream", "data/inputdata/CON", "data/inputdata/aux.csv", "data/inputdata/file.", "data/inputdata/file "])
def test_windows_only_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    # Given: a name Windows reads as a drive, stream or device, checked as on Windows
    archive = _rewrite(tmp_path / "evil.zip", {**_entries(_full_archive(tmp_path)), name: b"bad"})
    monkeypatch.setattr(repro_cmd, "_WINDOWS", True)
    # When/Then: refused as an unsafe name
    result = _import(archive, tmp_path / "target")
    assert result.exit_code == 3
    assert "Unsafe archive member name" in result.stderr


@pytest.mark.parametrize(
    ("mode", "flag_bits", "compression"),
    [(stat.S_IFLNK | 0o777, 0, zipfile.ZIP_STORED), (stat.S_IFIFO | 0o600, 0, zipfile.ZIP_STORED), (stat.S_IFCHR | 0o600, 0, zipfile.ZIP_STORED),
     (stat.S_IFREG | 0o600, 0x1, zipfile.ZIP_STORED), (stat.S_IFREG | 0o600, 0, zipfile.ZIP_BZIP2)],
)
def test_unsupported_member_kinds(tmp_path: Path, mode: int, flag_bits: int, compression: int) -> None:
    # Given: a member that is a link, a special file, encrypted, or bzip2-compressed
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        for name, value in _entries(_full_archive(tmp_path)).items():
            opened.writestr(name, value)
        member = zipfile.ZipInfo("data/inputdata/odd")
        member.external_attr = mode << 16
        member.compress_type = compression
        opened.writestr(member, b"/etc/passwd")
    if flag_bits:
        # The encryption bit lives in both the local header and the central directory.
        contents = archive.read_bytes()
        offset = contents.rindex(b"PK\x01\x02")
        contents = contents[: offset + 8] + bytes([contents[offset + 8] | flag_bits]) + contents[offset + 9 :]
        archive.write_bytes(contents)
    # When/Then: refused before extraction
    target = tmp_path / "target"
    result = _import(archive, target)
    assert result.exit_code == 3, result.output
    assert not target.exists()
    assert _no_staging(tmp_path)


def test_directory_entry_with_payload_is_refused(tmp_path: Path) -> None:
    entries = _entries(_full_archive(tmp_path))
    entries["data/inputdata/"] = b"unexpected"
    result = _import(_rewrite(tmp_path / "evil.zip", entries), tmp_path / "target")
    assert result.exit_code == 3
    assert not (tmp_path / "target").exists()


@pytest.mark.parametrize(
    "names",
    [["data/inputdata/a", "data/inputdata/a"], ["data/inputdata/A", "data/inputdata/a"],
     [unicodedata.normalize("NFC", "data/inputdata/é"), unicodedata.normalize("NFD", "data/inputdata/é")],
     ["data/inputdata/a", "data/inputdata/a/b"], ["data/inputdata/a/b", "data/inputdata/A"]],
)
def test_duplicate_and_conflicting_members(tmp_path: Path, names: list[str]) -> None:
    # Given: two members that name the same file, or a file used as a directory
    archive = tmp_path / "evil.zip"
    with warnings.catch_warnings(), zipfile.ZipFile(archive, "w") as opened:
        warnings.simplefilter("ignore")  # zipfile warns about the duplicate it is asked to write
        for name, value in _entries(_full_archive(tmp_path)).items():
            opened.writestr(name, value)
        for name in names:
            opened.writestr(name, b"x")
    # When/Then: refused before extraction (not by the file system tripping over it)
    result = _import(archive, tmp_path / "target")
    assert result.exit_code == 3, result.output
    assert "duplicated" in result.stderr or "inside a file entry" in result.stderr
    assert not (tmp_path / "target").exists()


@pytest.mark.parametrize(
    ("limit", "extra", "accepted"),
    [("_MAX_MEMBERS", 0, True), ("_MAX_MEMBERS", -1, False), ("_MAX_TOTAL_BYTES", -1, False), ("_MAX_COMPRESSION_RATIO", None, False)],
)
def test_archive_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str, extra: int | None, accepted: bool) -> None:
    # Given: a valid archive, and a limit set exactly at or just below what it needs
    archive = _full_archive(tmp_path)
    with zipfile.ZipFile(archive) as opened:
        members = opened.infolist()
    needed = {"_MAX_MEMBERS": len(members), "_MAX_TOTAL_BYTES": sum(m.file_size for m in members)}.get(limit, 0)
    monkeypatch.setattr(repro_cmd, limit, needed + extra if extra is not None else 0)
    # When: importing it
    target = tmp_path / "target"
    result = _import(archive, target)
    # Then: the limit is inclusive and a refusal extracts nothing
    assert (result.exit_code == 0) is accepted, result.output
    assert target.exists() is accepted
    assert _no_staging(tmp_path)


@pytest.mark.parametrize(
    "mutation",
    ["missing_manifest", "invalid_manifest", "deep_manifest", "large_manifest", "future_manifest", "config_omitted",
     "wrong_digest", "wrong_report_digest", "unreadable_report", "missing_config", "bad_config", "missing_report",
     "two_reports", "missing_inputs"],
)
def test_inconsistent_archives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    # Given: a full archive with one part broken or disagreeing with the others
    entries = _entries(_full_archive(tmp_path))
    manifest = json.loads(entries["repro_manifest.json"])
    report_name = next(name for name in entries if name.startswith("data/logs/"))
    report = json.loads(entries[report_name])
    changes = {
        "missing_manifest": {"repro_manifest.json": None},
        "invalid_manifest": {"repro_manifest.json": b"[]"},
        "deep_manifest": {"repro_manifest.json": b"[" * 100_000},
        "future_manifest": {"repro_manifest.json": json.dumps({**manifest, "schema_version": "999"}).encode()},
        "config_omitted": {"repro_manifest.json": json.dumps({**manifest, "config_included": False}).encode()},
        "wrong_digest": {"repro_manifest.json": json.dumps({**manifest, "config_digest": "sha256:" + "0" * 64}).encode()},
        "wrong_report_digest": {report_name: json.dumps({**report, "config_digest": "sha256:" + "0" * 64}).encode()},
        "unreadable_report": {report_name: b"{"},
        "missing_config": {"rdeconfig.yaml": None},
        "bad_config": {"rdeconfig.yaml": b"custom: [unclosed"},
        "missing_report": {report_name: None},
        "two_reports": {"data/logs/run_report_other.json": entries[report_name]},
        "missing_inputs": {name: None for name in entries if name.startswith("data/invoice")},
    }.get(mutation, {})
    if mutation == "large_manifest":
        monkeypatch.setattr(repro_cmd, "_MAX_MANIFEST_BYTES", 1)
    for name, value in changes.items():
        if value is None:
            entries.pop(name)
        else:
            entries[name] = value
    # When: importing it
    target = tmp_path / "target"
    result = _import(_rewrite(tmp_path / "broken.zip", entries), target)
    # Then: no project appears and the staging directory is gone
    assert result.exit_code == 3, result.output
    assert not target.exists()
    assert _no_staging(tmp_path)


@pytest.mark.parametrize("failure", ["crc", "corrupt_deflate", "extract", "publish"])
@pytest.mark.parametrize("existing", [False, True])
def test_failure_leaves_target_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, existing: bool) -> None:
    # Given: an archive that fails during extraction or at the final rename
    archive = _full_archive(tmp_path)
    if failure == "crc":
        _rewrite(archive, _entries(archive), compression=zipfile.ZIP_STORED)
        archive.write_bytes(archive.read_bytes().replace(PAYLOAD, b"X" * len(PAYLOAD)))
    elif failure == "corrupt_deflate":
        entries = {**_entries(archive), "data/inputdata/big.bin": os.urandom(16) * 4096}
        _rewrite(archive, entries, compression=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(archive) as opened:
            info = opened.getinfo("data/inputdata/big.bin")
        contents = bytearray(archive.read_bytes())
        start = info.header_offset + 30 + len(info.filename)
        contents[start + 10 : start + 40] = b"\xff" * 30
        archive.write_bytes(bytes(contents))
    elif failure == "extract":
        real_open = zipfile.ZipFile.open
        calls = 0

        def fail_second(self: zipfile.ZipFile, *args: object, **kwargs: object):
            nonlocal calls
            calls += 1
            if calls == 2:  # the first is the manifest read
                raise OSError("simulated disk failure")
            return real_open(self, *args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, "open", fail_second)
    target = tmp_path / "target"
    if existing:
        target.mkdir()
    if failure == "publish":
        real_rename = Path.rename

        def refuse(self: Path, destination: Path) -> Path:
            if Path(destination) == target:
                raise OSError("simulated rename failure")
            return real_rename(self, destination)

        monkeypatch.setattr(Path, "rename", refuse)
    # When: importing it
    result = _import(archive, target)
    # Then: the target is as before and the staging directory is gone
    assert result.exit_code == 3, result.output
    assert target.exists() is existing
    if existing:
        assert list(target.iterdir()) == []
    assert _no_staging(tmp_path)


@pytest.mark.parametrize("kind", ["symlink", "file", "nonempty"])
def test_import_target_refusals(tmp_path: Path, kind: str) -> None:
    # Given: a target that is a link to an empty directory, a file, or a used directory
    archive = _full_archive(tmp_path)
    target = tmp_path / "target"
    original = tmp_path / "original"
    original.mkdir()
    if kind == "symlink":
        target.symlink_to(original, target_is_directory=True)
    elif kind == "file":
        target.write_bytes(PAYLOAD)
    else:
        target.mkdir()
        (target / "keep.txt").write_bytes(PAYLOAD)
    # When/Then: refused, and nothing is written through or over it
    assert _import(archive, target).exit_code == 3
    assert list(original.iterdir()) == []
    if kind == "file":
        assert target.read_bytes() == PAYLOAD
    if kind == "nonempty":
        assert [p.name for p in target.iterdir()] == ["keep.txt"]


@pytest.mark.skipif(sys.platform == "win32", reason="these names are not legal on Windows")
@pytest.mark.parametrize("flat", [False, True])
def test_portable_names_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flat: bool) -> None:
    # Given: inputs named in ways POSIX allows, a report with a non-Runner name, and no network
    data, report = _project(tmp_path, flat=flat)
    for name in ("aux.csv", "12:30.csv", "trailing."):
        (data / "inputdata" / name).write_bytes(PAYLOAD)
    (data / "inputdata" / "nested" / "empty").mkdir(parents=True)
    renamed = report.with_name("local.json")
    report.rename(renamed)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("repro must stay local")

    monkeypatch.setattr(socket, "socket", no_network)
    # When: exporting and importing the full archive
    archive = tmp_path / "full.zip"
    exported = _export(renamed, archive)
    target = tmp_path / "target"
    imported = _import(archive, target)
    # Then: every input comes back byte for byte, and the config replays to the report's digest
    assert exported.exit_code == 0, exported.output
    assert imported.exit_code == 0, imported.output
    for name in ("aux.csv", "12:30.csv", "trailing.", f"{SECRET}.dat"):
        assert (target / "data" / "inputdata" / name).read_bytes() == PAYLOAD
    assert (target / "data" / "inputdata" / "nested" / "empty").is_dir()
    digest = json.loads(renamed.read_text(encoding="utf-8"))["config_digest"]
    assert compute_config_digest(load_config(target, data_root=target / "data")) == digest
    assert (target / "data" / "logs" / "run_report_export.json").is_file()


def test_nul_in_member_name_is_refused(tmp_path: Path) -> None:
    # Given: a valid archive whose input name has a NUL, which zipfile would silently cut off
    archive = _full_archive(tmp_path)
    name = f"data/inputdata/{SECRET}.dat".encode()
    altered = name[:-5] + b"\x00.dat"
    contents = archive.read_bytes()
    assert contents.count(name) == 2  # local header and central directory
    archive.write_bytes(contents.replace(name, altered))
    target = tmp_path / "target"
    # When/Then: the altered spelling is refused before extraction
    result = _import(archive, target)
    assert result.exit_code == 3, result.output
    assert "Unsafe archive member name" in result.stderr
    assert not target.exists()
    assert _no_staging(tmp_path)
