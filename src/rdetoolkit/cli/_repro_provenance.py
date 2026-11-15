"""Reproducibility provenance recorded in ``repro_manifest.json`` (#699).

The values describe the environment that ran ``repro export``, not
necessarily the one that ran the flow: a RunReport does not record its
interpreter or toolkit version. Each attribute is a mapping with ``status``
``known``, ``unavailable`` (with a ``reason``) or ``not_included``.

Only coarse, reproduction-relevant facts are captured: no host name, user
name, absolute path, remote URL or branch name. Git is queried as a local
subprocess, never over the network, and any failure makes the attribute
``unavailable`` instead of failing the export.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
from functools import partial
from pathlib import Path
from typing import Any

from rdetoolkit import __version__

#: Attribute names, in the order they are written and shown.
ATTRIBUTES = ("rdetoolkit", "python", "platform", "git", "lockfile", "source_code")
#: Supported dependency lockfiles at the project root, by precedence.
LOCKFILE_NAMES = ("uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock", "pylock.toml")
CAPTURED_AT = "export"
SOURCE_NOT_INCLUDED = "repro archives never contain the flow's source code; supply it separately at the recorded commit"

_GIT_TIMEOUT_SECONDS = 10
#: Variables that would point git at another repository than the project's.
_GIT_REDIRECTS = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY"})
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_TEXT = 100
#: Fields each known attribute must carry (``source_code`` is never known).
_FIELDS: dict[str, tuple[str, ...]] = {
    "rdetoolkit": ("version",),
    "python": ("implementation", "version"),
    "platform": ("system", "release", "machine"),
}


def _file_digest(path: Path) -> str:
    """Return ``sha256:<hex>`` of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(partial(source.read, 1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _unavailable(reason: str) -> dict[str, Any]:
    return {"status": "unavailable", "reason": reason}


def _git(git: str, root: Path, *args: str) -> str:
    """Run one read-only git command in ``root`` and return its stdout.

    ``core.fsmonitor`` is disabled because a repository's config could
    otherwise name a program for git to run; prompts and optional locks are
    off so the call never waits or writes.
    """
    env = {key: value for key, value in os.environ.items() if key not in _GIT_REDIRECTS}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    completed = subprocess.run(  # noqa: S603 -- fixed argv, resolved git binary, no shell
        [git, "-c", "core.fsmonitor=false", "-C", str(root), *args],
        capture_output=True, text=True, timeout=_GIT_TIMEOUT_SECONDS, check=True, env=env,
    )
    return completed.stdout


def _git_provenance(root: Path) -> dict[str, Any]:
    git = shutil.which("git")
    if git is None:
        return _unavailable("git is not installed")
    try:
        commit = _git(git, root, "rev-parse", "--verify", "HEAD").strip()
        changes = _git(git, root, "status", "--porcelain", "--untracked-files=no")
    except subprocess.TimeoutExpired:
        return _unavailable("git did not answer in time")
    except subprocess.CalledProcessError:
        return _unavailable("the project is not in a git checkout with a commit")
    except OSError:
        return _unavailable("git could not be run")
    if not _COMMIT.match(commit):
        return _unavailable("git did not report a commit id")
    return {"status": "known", "commit": commit, "dirty": bool(changes.strip())}


def _lockfile_provenance(root: Path) -> dict[str, Any]:
    for name in LOCKFILE_NAMES:
        path = root / name
        # A link could point outside the project; only a regular file is described.
        if path.is_symlink() or not path.is_file():
            continue
        try:
            return {"status": "known", "name": name, "sha256": _file_digest(path)}
        except OSError:
            return _unavailable(f"{name} could not be read")
    return _unavailable("no supported lockfile (" + ", ".join(LOCKFILE_NAMES) + ") at the project root")


def capture_provenance(project_root: Path) -> dict[str, Any]:
    """Describe the export environment for ``repro_manifest.json``.

    Args:
        project_root: Directory searched for a lockfile and used for git.

    Returns:
        ``captured_at`` plus one status mapping per name in :data:`ATTRIBUTES`.
    """
    return {
        "captured_at": CAPTURED_AT,
        "rdetoolkit": {"status": "known", "version": __version__},
        "python": {"status": "known", "implementation": platform.python_implementation(), "version": platform.python_version()},
        "platform": {"status": "known", "system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "git": _git_provenance(project_root),
        "lockfile": _lockfile_provenance(project_root),
        "source_code": {"status": "not_included", "reason": SOURCE_NOT_INCLUDED},
    }


def safe_text(value: object) -> str | None:
    """Return ``value`` if it is short printable text, else None (never echoed)."""
    return value if isinstance(value, str) and 0 < len(value) <= _MAX_TEXT and value.isprintable() else None


def _known_fields(name: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    """Return the validated fields of a ``known`` attribute, or None if any is unusable."""
    if name == "git":
        commit, dirty = entry.get("commit"), entry.get("dirty")
        git_ok = isinstance(commit, str) and _COMMIT.match(commit) is not None and isinstance(dirty, bool)
        return {"commit": commit, "dirty": dirty} if git_ok else None
    if name == "lockfile":
        lock, digest = entry.get("name"), entry.get("sha256")
        lock_ok = lock in LOCKFILE_NAMES and isinstance(digest, str) and _DIGEST.match(digest) is not None
        return {"name": lock, "sha256": digest} if lock_ok else None
    fields = {field: safe_text(entry.get(field)) for field in _FIELDS.get(name, ())}
    return fields if fields and all(value is not None for value in fields.values()) else None


def _read_attribute(name: str, entry: object) -> tuple[dict[str, Any] | None, str]:
    """Classify one recorded attribute as known fields, or an unavailable reason."""
    if not isinstance(entry, dict):
        return None, "unreadable in the manifest"
    if entry.get("status") == "known":
        fields = _known_fields(name, entry)
        return (fields, "") if fields is not None else (None, "unreadable in the manifest")
    if entry.get("status") in {"unavailable", "not_included"}:
        reason = safe_text(entry.get("reason"))
        return None, reason if reason is not None else "unavailable (no readable reason recorded)"
    return None, "unreadable in the manifest"


def read_provenance(manifest: dict[str, Any]) -> tuple[str | None, dict[str, dict[str, Any]], dict[str, str]]:
    """Split a manifest's provenance into known attributes and unavailable ones.

    The manifest is untrusted: a value is reported only after it passes the
    field checks, otherwise the attribute becomes unavailable as unreadable.

    Args:
        manifest: A parsed ``repro_manifest.json`` of any supported version.

    Returns:
        ``(captured_at, known, unavailable)``: when the values were captured
        (None if not recorded), known attribute fields by name, and a reason
        by name for every other attribute in :data:`ATTRIBUTES`.
    """
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        version = safe_text(manifest.get("schema_version")) or "unknown"
        reason = f"manifest schema_version {version!r} predates provenance"
        return None, {}, {name: SOURCE_NOT_INCLUDED if name == "source_code" else reason for name in ATTRIBUTES}
    captured_at = provenance.get("captured_at")
    known: dict[str, dict[str, Any]] = {}
    unavailable: dict[str, str] = {}
    for name in ATTRIBUTES:
        fields, reason = _read_attribute(name, provenance.get(name))
        if fields is None:
            unavailable[name] = reason
        else:
            known[name] = fields
    return (captured_at if captured_at == CAPTURED_AT else None), known, unavailable
