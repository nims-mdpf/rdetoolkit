#!/usr/bin/env python3
"""Build and install offline, version-matched Skills independently of Python packages.

The installer only copies files; it never fetches instructions or invokes an agent.
SHA-256 detects corruption, not publisher identity: obtain packs from trusted releases.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import NoReturn

NAMES = tuple(f"rdetoolkit-{name}" for name in ("flow-authoring", "metadata", "debugging", "testing", "v1-migration"))
AGENTS = {"codex": ".agents", "claude": ".claude"}
RECEIPT = ".rdetoolkit-skills.json"
MIN_PAYLOAD_PARTS = 2
MIN_SKILL_PARTS = 3


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_version(repo: Path) -> str:
    project = re.search(r'^version\s*=\s*"([^"]+)"', (repo / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    runtime = re.search(r'^__version__\s*=\s*"([^"]+)"', (repo / "src/rdetoolkit/__init__.py").read_text(encoding="utf-8"), re.MULTILINE)
    if project is None or runtime is None or project[1] != runtime[1]:
        fail("package version declarations must agree")
    version = project[1]
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?", version) is None:
        fail("noncanonical package version")
    return version


def build(repo: Path, output: Path) -> Path:
    version = package_version(repo)
    source = repo / ".agents/skills"
    for name in NAMES:
        if (source / name).is_symlink():
            fail(f"symlink in canonical Skills: {name}")
        if not (source / name / "SKILL.md").is_file():
            fail(f"missing {name}/SKILL.md")
    payload = {"install_skills.py": Path(__file__).read_bytes()}
    paths = [path for name in NAMES for path in (source / name).rglob("*")]
    examples = source / "examples.json"
    if examples.exists():
        paths.append(examples)
    for path in sorted(paths):
        if path.is_symlink():
            fail(f"symlink in canonical Skills: {path}")
        if path.is_file() and path.suffix in {".md", ".json", ".py"}:
            payload[f"skills/{path.relative_to(source).as_posix()}"] = path.read_bytes()
    manifest = {"schema_version": 1, "version": version, "files": {path: digest(data) for path, data in payload.items()}}
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"rdetoolkit-skills-{version}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member, data in sorted(payload.items()):
            archive.writestr(member, data)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    target.with_suffix(".zip.sha256").write_text(f"{digest(target.read_bytes())}  {target.name}\n", encoding="utf-8")
    return target


def payload_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts or str(path) != value:
        fail(f"unsafe archive path: {value}")
    if value != "install_skills.py" and not (len(path.parts) >= MIN_PAYLOAD_PARTS and path.parts[0] == "skills"):
        fail(f"unexpected archive path: {value}")
    return path


def read_pack(pack: Path, version: str) -> tuple[dict[str, object], dict[str, bytes]]:
    with zipfile.ZipFile(pack) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict):
            fail("invalid archive manifest")
        if manifest.get("schema_version") != 1 or manifest.get("version") != version:
            fail("Skills pack version must exactly match the installed runtime version")
        files = manifest.get("files")
        if not isinstance(files, dict) or len(set(archive.namelist())) != len(archive.namelist()):
            fail("invalid archive manifest or duplicate members")
        if set(archive.namelist()) != {*files, "manifest.json"}:
            fail("archive members do not match manifest")
        data = {}
        for name, expected in files.items():
            if not isinstance(name, str) or not isinstance(expected, str):
                fail("invalid archive manifest entry")
            payload_path(name)
            content = archive.read(name)
            if digest(content) != expected:
                fail(f"digest mismatch: {name}")
            data[name] = content
    for name in NAMES:
        if f"skills/{name}/SKILL.md" not in data:
            fail(f"missing {name}/SKILL.md")
    return manifest, data


def destination(project: Path, agent: str) -> Path:
    root = project.absolute()
    target = root / AGENTS[agent] / "skills"
    for parent in (target, *target.parents):
        if parent.is_symlink():
            fail(f"symlink destination is unsupported; use a real directory: {parent}")
    return target


def skill_files(data: dict[str, bytes]) -> dict[str, bytes]:
    result = {}
    for path, content in data.items():
        parts = payload_path(path).parts
        if len(parts) >= MIN_SKILL_PARTS and parts[0] == "skills" and parts[1] in NAMES:
            result["/".join(parts[1:])] = content
    return result


def install(pack: Path, project: Path, agent: str, version: str) -> None:
    manifest, payload = read_pack(pack, version)
    files = skill_files(payload)
    target = destination(project, agent)
    for name in (*NAMES, RECEIPT):
        if (target / name).exists() or (target / name).is_symlink():
            fail(f"destination exists: {target / name}; uninstall the previous pack or preserve your Skill first")
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".rdetoolkit-stage-", dir=target) as temporary:
        stage = Path(temporary)
        for path, content in files.items():
            item = stage / path
            item.parent.mkdir(parents=True, exist_ok=True)
            item.write_bytes(content)
        for name in NAMES:
            (stage / name).rename(target / name)
    receipt = {"schema_version": 1, "version": manifest["version"], "files": {path: digest(content) for path, content in files.items()}}
    (target / RECEIPT).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def installed_files(target: Path) -> set[str]:
    actual = set()
    for name in NAMES:
        for path in (target / name).rglob("*"):
            if path.is_symlink():
                fail(f"modified installed Skill: {path}")
            if path.is_file():
                actual.add(path.relative_to(target).as_posix())
    return actual


def validate_receipt(target: Path) -> None:
    receipt = json.loads((target / RECEIPT).read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        fail("invalid installation receipt")
    if receipt.get("schema_version") != 1 or not isinstance(receipt.get("files"), dict):
        fail("invalid installation receipt")
    expected = receipt["files"]
    actual = installed_files(target)
    if set(expected) != actual:
        fail("modified installed Skills: added or removed files; preserve changes before uninstalling")
    for path, expected_digest in expected.items():
        if digest((target / path).read_bytes()) != expected_digest:
            fail(f"modified installed Skill: {path}; preserve changes before uninstalling")


def uninstall(project: Path, agent: str) -> None:
    target = destination(project, agent)
    if (target / RECEIPT).is_symlink() or any((target / name).is_symlink() for name in NAMES):
        fail("modified installed Skills: symlink")
    validate_receipt(target)
    for name in NAMES:
        shutil.rmtree(target / name)
    (target / RECEIPT).unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    builder.add_argument("--output", type=Path, required=True)
    for action in ("install", "uninstall"):
        command = commands.add_parser(action)
        command.add_argument("--project", type=Path, required=True)
        command.add_argument("--agent", choices=AGENTS, required=True)
        if action == "install":
            command.add_argument("--pack", type=Path, required=True)
            command.add_argument("--version", help="Exact installed rdetoolkit version; otherwise read from package metadata")
    args = parser.parse_args()
    try:
        if args.command == "build":
            print(build(args.repo, args.output))
        elif args.command == "install":
            version = args.version or importlib.metadata.version("rdetoolkit")
            install(args.pack, args.project, args.agent, version)
        else:
            uninstall(args.project, args.agent)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, importlib.metadata.PackageNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
