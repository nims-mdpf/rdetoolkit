"""Distribution EP/BV table.

EP: build/version manifest -> test_build; offline copy/discovery layout ->
test_offline_install; clean uninstall -> test_uninstall; existing target ->
test_conflict; wrong version -> test_version_mismatch; corrupt payload ->
test_corrupt; traversal -> test_traversal; local edit -> test_edited_uninstall;
symlink target -> test_symlink; source version mismatch -> test_source_mismatch.
BV: five Skills exactly -> test_build; duplicate install -> test_conflict;
zero Skills -> test_empty_source. Failures leave the project unchanged.
"""

# ruff: noqa: INP001
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "skills_pack.py"
NAMES = ("flow-authoring", "metadata", "debugging", "testing", "v1-migration")


def invoke(*args: object) -> subprocess.CompletedProcess[str]:
    """Invoke."""
    return subprocess.run([sys.executable, str(SCRIPT), *(str(x) for x in args)], capture_output=True, text=True, check=False)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """Source."""
    root = tmp_path / "source"
    (root / "src/rdetoolkit").mkdir(parents=True)
    (root / "src/rdetoolkit/__init__.py").write_text('__version__ = "2.0.1"\n')
    (root / "pyproject.toml").write_text('[project]\nversion = "2.0.1"\n')
    for name in NAMES:
        skill = root / ".agents/skills" / f"rdetoolkit-{name}"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: rdetoolkit-{name}\ndescription: Test {name}\n---\n")
    return root


@pytest.fixture
def pack(source: Path, tmp_path: Path) -> Path:
    """Pack."""
    result = invoke("build", "--repo", source, "--output", tmp_path / "dist")
    assert result.returncode == 0, result.stderr
    return tmp_path / "dist/rdetoolkit-skills-2.0.1.zip"


def install(pack: Path, project: Path, agent: str = "codex", version: str = "2.0.1") -> subprocess.CompletedProcess[str]:
    """Install."""
    return invoke("install", "--pack", pack, "--project", project, "--agent", agent, "--version", version)


def test_build(source: Path, tmp_path: Path) -> None:
    # Given a versioned source with five Skills; When building offline.
    """Test build."""
    result = invoke("build", "--repo", source, "--output", tmp_path / "dist")
    # Then all payload bytes are accounted for by a versioned manifest.
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(tmp_path / "dist/rdetoolkit-skills-2.0.1.zip") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == "2.0.1"
        assert manifest["schema_version"] == 1
        assert len([p for p in manifest["files"] if p.endswith("/SKILL.md")]) == 5
        assert set(archive.namelist()) == {*manifest["files"], "manifest.json"}
        for path, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read(path)).hexdigest() == digest


@pytest.mark.parametrize(("agent", "directory"), [("codex", ".agents"), ("claude", ".claude")])
def test_offline_install(pack: Path, tmp_path: Path, agent: str, directory: str) -> None:
    # Given a downloaded pack; When using its bundled installer without source access.
    """Test offline install."""
    installer = tmp_path / "install_skills.py"
    with zipfile.ZipFile(pack) as archive:
        installer.write_bytes(archive.read("install_skills.py"))
    project = tmp_path / "project"
    result = subprocess.run([sys.executable, str(installer), "install", "--pack", str(pack), "--project", str(project), "--agent", agent, "--version", "2.0.1"], capture_output=True, text=True, check=False)
    # Then each agent's documented discovery layout contains the five real files.
    assert result.returncode == 0, result.stderr
    assert sorted(p.parent.name for p in (project / directory / "skills").glob("*/SKILL.md")) == sorted(f"rdetoolkit-{n}" for n in NAMES)


def test_uninstall(pack: Path, tmp_path: Path) -> None:
    # Given an unchanged install; When uninstalling.
    """Test uninstall."""
    project = tmp_path / "project"
    assert install(pack, project).returncode == 0
    result = invoke("uninstall", "--project", project, "--agent", "codex")
    # Then only owned Skills disappear.
    assert result.returncode == 0, result.stderr
    assert not list((project / ".agents/skills").glob("rdetoolkit-*"))


def test_conflict(pack: Path, tmp_path: Path) -> None:
    # Given an existing user Skill; When installing.
    """Test conflict."""
    project = tmp_path / "project"
    target = project / ".agents/skills/rdetoolkit-metadata"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("user content")
    result = install(pack, project)
    # Then the installer refuses without partial writes.
    assert result.returncode == 1
    assert "exists" in result.stderr
    assert (target / "SKILL.md").read_text() == "user content"
    assert len(list(target.parent.iterdir())) == 1


def test_version_mismatch(pack: Path, tmp_path: Path) -> None:
    # Given mismatched runtime and pack versions; When installing.
    """Test version mismatch."""
    result = install(pack, tmp_path / "project", version="2.0.2")
    # Then no project is created.
    assert result.returncode == 1
    assert "version" in result.stderr
    assert not (tmp_path / "project").exists()


def rewrite_pack(pack: Path, name: str, content: bytes) -> Path:
    """Rewrite pack."""
    changed = pack.with_name("changed.zip")
    with zipfile.ZipFile(pack) as original, zipfile.ZipFile(changed, "w") as target:
        for path in original.namelist():
            target.writestr(path, content if path == name else original.read(path))
    return changed


def test_corrupt(pack: Path, tmp_path: Path) -> None:
    # Given a changed payload; When verifying before install.
    """Test corrupt."""
    changed = rewrite_pack(pack, "skills/rdetoolkit-metadata/SKILL.md", b"tampered")
    result = install(changed, tmp_path / "project")
    # Then its digest mismatch prevents writes.
    assert result.returncode == 1
    assert "digest" in result.stderr
    assert not (tmp_path / "project").exists()


def test_traversal(pack: Path, tmp_path: Path) -> None:
    # Given a malicious manifest; When installing.
    """Test traversal."""
    with zipfile.ZipFile(pack) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    manifest["files"]["skills/../../escape"] = "0" * 64
    changed = rewrite_pack(pack, "manifest.json", json.dumps(manifest).encode())
    result = install(changed, tmp_path / "project")
    # Then path traversal is rejected before creating directories.
    assert result.returncode == 1
    assert not (tmp_path / "project").exists()
    assert not (tmp_path / "escape").exists()


def test_edited_uninstall(pack: Path, tmp_path: Path) -> None:
    # Given a locally edited installed Skill; When uninstalling.
    """Test edited uninstall."""
    project = tmp_path / "project"
    assert install(pack, project).returncode == 0
    path = project / ".agents/skills/rdetoolkit-metadata/SKILL.md"
    path.write_text("my changes")
    result = invoke("uninstall", "--project", project, "--agent", "codex")
    # Then the user must first preserve or restore changes.
    assert result.returncode == 1
    assert "modified" in result.stderr
    assert path.read_text() == "my changes"


def test_symlink(pack: Path, tmp_path: Path) -> None:
    # Given an agent directory redirected outside the project; When installing.
    """Test symlink."""
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (project / ".agents").symlink_to(external, target_is_directory=True)
    result = install(pack, project)
    # Then external directories stay untouched.
    assert result.returncode == 1
    assert not list(external.iterdir())


def test_source_mismatch(source: Path, tmp_path: Path) -> None:
    # Given inconsistent package versions; When building.
    """Test source mismatch."""
    (source / "src/rdetoolkit/__init__.py").write_text('__version__ = "9.0.0"\n')
    result = invoke("build", "--repo", source, "--output", tmp_path / "dist")
    # Then no mismatched pack can be published.
    assert result.returncode == 1
    assert "version" in result.stderr


def test_empty_source(source: Path, tmp_path: Path) -> None:
    # Given a missing canonical Skill; When building.
    """Test empty source."""
    (source / ".agents/skills/rdetoolkit-metadata/SKILL.md").unlink()
    result = invoke("build", "--repo", source, "--output", tmp_path / "dist")
    # Then incomplete release packs are rejected.
    assert result.returncode == 1
    assert "SKILL.md" in result.stderr


@pytest.mark.parametrize("value", [[], None, {"schema_version": 1, "version": "2.0.1", "files": []}])
def test_malformed_manifest(pack: Path, tmp_path: Path, value: object) -> None:
    """Malformed JSON structures fail cleanly before any project write."""
    # Given a malformed manifest; When installing.
    changed = rewrite_pack(pack, "manifest.json", json.dumps(value).encode())
    result = install(changed, tmp_path / "project")
    # Then the installer returns an actionable error without a traceback.
    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "project").exists()


def test_unrelated_contributor_skill_excluded(source: Path, tmp_path: Path) -> None:
    """Release builds ignore unrelated contributor Skills and include migration code."""
    # Given a broken unrelated symlink and an executable migration reference.
    root = source / ".agents/skills"
    (root / "examples.json").write_text("{}")
    (root / "rdetoolkit-testing/cache.bin").write_bytes(b"ignore")
    (root / "unrelated-contributor").symlink_to(tmp_path / "missing", target_is_directory=True)
    reference = root / "rdetoolkit-v1-migration/references"
    reference.mkdir()
    (reference / "legacy.py").write_text("# Real migration callback fixture\n")
    # When building the allowlisted pack.
    result = invoke("build", "--repo", source, "--output", tmp_path / "dist")
    # Then migration fixtures ship without unrelated contributor files.
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(tmp_path / "dist/rdetoolkit-skills-2.0.1.zip") as archive:
        assert "skills/rdetoolkit-v1-migration/references/legacy.py" in archive.namelist()
        assert not any("unrelated-contributor" in name for name in archive.namelist())


@pytest.mark.parametrize("mutation", ["version", "directory-link", "file-link"])
def test_invalid_source(source: Path, tmp_path: Path, mutation: str) -> None:
    """Build rejects malformed versions and links within canonical Skills."""
    # Given an invalid source tree.
    root = source / ".agents/skills"
    if mutation == "version":
        (source / "pyproject.toml").write_text('[project]\nversion = "invalid"\n')
        (source / "src/rdetoolkit/__init__.py").write_text('__version__ = "invalid"\n')
    elif mutation == "directory-link":
        target = root / "rdetoolkit-metadata"
        target.rename(root / "moved")
        target.symlink_to(root / "moved", target_is_directory=True)
    else:
        (root / "rdetoolkit-metadata/extra.md").symlink_to(tmp_path / "missing")
    # When building; Then reject the invalid input.
    result = invoke("build", "--repo", source, "--output", tmp_path / "dist")
    assert result.returncode == 1
    assert "ERROR:" in result.stderr


@pytest.mark.parametrize("mutation", ["unsafe-path", "unexpected-path", "hash-type", "missing-skill", "duplicate"])
def test_invalid_archive(pack: Path, tmp_path: Path, mutation: str) -> None:
    """Archive validation rejects unsafe members and incomplete manifests."""
    # Given a malicious or incomplete archive whose member list matches its manifest.
    with zipfile.ZipFile(pack) as original:
        data = {name: original.read(name) for name in original.namelist()}
    manifest = json.loads(data.pop("manifest.json"))
    if mutation in {"unsafe-path", "unexpected-path"}:
        name = "skills/../escape" if mutation == "unsafe-path" else "escape"
        data[name] = b"payload"
        manifest["files"][name] = hashlib.sha256(data[name]).hexdigest()
    elif mutation == "hash-type":
        manifest["files"]["install_skills.py"] = None
    elif mutation == "missing-skill":
        name = "skills/rdetoolkit-metadata/SKILL.md"
        del data[name]
        del manifest["files"][name]
    changed = pack.with_name("invalid.zip")
    with zipfile.ZipFile(changed, "w") as target:
        for name, content in data.items():
            target.writestr(name, content)
        target.writestr("manifest.json", json.dumps(manifest))
        if mutation == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                target.writestr("install_skills.py", data["install_skills.py"])
    # When installing; Then fail without writing any project file.
    result = install(changed, tmp_path / "project")
    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert not (tmp_path / "project").exists()


@pytest.mark.parametrize("mutation", ["add", "remove", "inner-link", "skill-link", "bad-receipt", "receipt-type"])
def test_modified_installation(pack: Path, tmp_path: Path, mutation: str) -> None:
    """Uninstall preserves installations whose content or receipt has changed."""
    # Given an installed pack with one local modification.
    project = tmp_path / "project"
    assert install(pack, project).returncode == 0
    root = project / ".agents/skills"
    skill = root / "rdetoolkit-metadata"
    if mutation == "add":
        (skill / "local.md").write_text("local")
    elif mutation == "remove":
        (skill / "SKILL.md").unlink()
    elif mutation == "inner-link":
        (skill / "local.md").symlink_to(tmp_path / "missing")
    elif mutation == "skill-link":
        skill.rename(root / "preserved")
        skill.symlink_to(root / "preserved", target_is_directory=True)
    else:
        (root / ".rdetoolkit-skills.json").write_text("[]" if mutation == "receipt-type" else '{"schema_version": 99}')
    # When uninstalling; Then all five Skill names remain.
    result = invoke("uninstall", "--project", project, "--agent", "codex")
    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert all((root / f"rdetoolkit-{name}").exists() for name in NAMES)
