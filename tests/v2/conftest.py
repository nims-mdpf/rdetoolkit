"""Cross-suite guards for v2 tests.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| repository guard | unchanged session delta | suite completes | TC-H0-GUARD-EP-001 |
| repository guard | changed tracked or new untracked path | teardown fails with remediation | TC-H0-GUARD-EP-002 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| repository guard | one ignored leftover | warn without failing | TC-H0-GUARD-BV-001 |
"""

from __future__ import annotations

import hashlib
import subprocess
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

_REMEDIATION = "Isolate repository-relative writes with tmp_path and monkeypatch.chdir(tmp_path)."


@dataclass(frozen=True)
class _RepositoryState:
    tracked_hashes: dict[str, str | None]
    untracked: frozenset[str]


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_paths(root: Path, *args: str) -> frozenset[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return frozenset(path.decode("utf-8", errors="surrogateescape") for path in result.stdout.split(b"\0") if path)


def _tracked_hashes(root: Path) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for relative in _git_paths(root):
        path = root / relative
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return hashes


def _repository_state(root: Path) -> _RepositoryState:
    return _RepositoryState(
        tracked_hashes=_tracked_hashes(root),
        untracked=_git_paths(root, "--others", "--exclude-standard"),
    )


def _porcelain_status(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line for line in result.stdout.splitlines() if line)


def _ignored_data_paths(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignored=matching",
            "--",
            "data",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line[3:] for line in result.stdout.splitlines() if line.startswith("!! "))


def _changed_tracked(before: _RepositoryState, after: _RepositoryState) -> list[str]:
    paths = before.tracked_hashes.keys() | after.tracked_hashes.keys()
    return sorted(path for path in paths if before.tracked_hashes.get(path) != after.tracked_hashes.get(path))


@pytest.fixture(scope="session", autouse=True)
def guard_repository_tree_delta() -> Iterator[None]:
    """Require v2 tests to leave no tracked or non-ignored repository delta."""
    root = _repository_root()
    # Given: a teardown baseline that adapts to the session's initial state
    before = _repository_state(root)
    initial_status = _porcelain_status(root)
    if initial_status:
        warnings.warn(
            f"Repository was already dirty before the v2 test session; using that state as the delta baseline: {', '.join(initial_status)}",
            UserWarning,
            stacklevel=1,
        )

    # When: the complete v2 test session runs
    yield

    # Then: ignored leftovers warn, while tracked or non-ignored deltas fail
    ignored = _ignored_data_paths(root)
    if ignored:
        warnings.warn(
            f"Ignored repository data leftovers after the v2 test session: {', '.join(ignored)}",
            UserWarning,
            stacklevel=1,
        )
    after = _repository_state(root)
    changed_tracked = _changed_tracked(before, after)
    new_untracked = sorted(after.untracked - before.untracked)
    assert not changed_tracked and not new_untracked, f"Repository pollution detected after the v2 test session: tracked changes={changed_tracked}, new untracked={new_untracked}. {_REMEDIATION}"
