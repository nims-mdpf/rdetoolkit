"""Cross-suite guards for v2 tests.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| repository guard | unchanged session delta | suite completes | TC-H0-GUARD-EP-001 |
| repository guard | changed tracked or new untracked path | teardown fails with remediation | TC-H0-GUARD-EP-002 |
| sys.path guard | in-process CLI prepends its working directory | entry removed after the test | TC-RC1-F02-GUARD-EP-001 |
| flow registry guard | a test registers a local flow | registration dropped after the test | TC-640-GUARD-EP-001 |
| flow registry guard | a test imports a module defining a flow | registration kept (matches the import cache) | TC-640-GUARD-EP-002 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| repository guard | one ignored leftover | warn without failing | TC-H0-GUARD-BV-001 |
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any

import pytest

from rdetoolkit.core import flow as flow_module
from rdetoolkit.core import registry

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


@pytest.fixture(autouse=True)
def restore_sys_path() -> Iterator[None]:
    """Undo ``sys.path`` growth caused by in-process CLI invocations.

    CLI commands that import a user-named module put the working directory at
    the front of ``sys.path`` (``python -m`` semantics, review F02). Under
    ``CliRunner`` that is the test process itself, so each ``tmp_path`` a test
    ``chdir``s into would otherwise stay importable for every later test.
    """
    saved = list(sys.path)
    yield
    sys.path[:] = saved


# flow id -> (name, namespace) of the module whose import registered it (#640).
_FLOW_IMPORT_OWNERS: dict[str, tuple[str, dict[str, Any]]] = {}


def _importing_module(frame: FrameType | None) -> tuple[str, dict[str, Any]] | None:
    """Return the module whose import is executing at ``frame``, if any.

    The first ``<module>`` frame up the stack decides: it counts only when the
    import system runs it (importlib, or an import hook's ``exec_module`` such
    as pytest's assertion rewriter). ``exec`` snippets, ``runpy`` and
    ``__main__`` run module code outside an import, so they own nothing.
    """
    while frame is not None:
        if frame.f_code.co_name == "<module>":
            caller = frame.f_back
            run_by_import = caller is not None and (caller.f_code.co_filename.startswith("<frozen importlib") or caller.f_code.co_name == "exec_module")
            name = frame.f_globals.get("__name__")
            return (name, frame.f_globals) if run_by_import and isinstance(name, str) else None
        frame = frame.f_back
    return None


_register_flow = flow_module.register_flow


def _register_flow_recording_import_owner(spec: registry.FlowSpec, fn: Any) -> None:
    """Register through the real registry, remembering which import did it."""
    _register_flow(spec, fn)
    owner = _importing_module(sys._getframe(1))
    if owner is not None:
        _FLOW_IMPORT_OWNERS[spec.id] = owner


flow_module.register_flow = _register_flow_recording_import_owner


def _owned_by_cached_import(flow_id: str) -> bool:
    """Return whether the module whose import registered ``flow_id`` is still cached.

    Such a registration must stay: dropping it would leave the module in
    ``sys.modules`` without its flow, and a later import would not re-run the
    decorator to restore it — however the module exposes the flow (its own
    name, an alias, a factory result, or not at all).
    """
    owner = _FLOW_IMPORT_OWNERS.get(flow_id)
    if owner is None:
        return False
    name, namespace = owner
    module = sys.modules.get(name)
    return module is not None and vars(module) is namespace


@pytest.fixture(autouse=True)
def isolate_flow_registry() -> Iterator[None]:
    """Drop the throwaway flows a test registers once it finishes (issue #640).

    A flow id now belongs to exactly one callable per process (E2007), and a
    flow defined inside a test, helper or executed docs example gets the same
    id on every parametrized run. A flow registered while a module was being
    imported stays as long as that module is in ``sys.modules``, so the
    registry keeps matching the import cache; both maps are restored together
    so they never disagree.
    """
    saved = set(registry._flow_specs)
    yield
    _drop_flows_registered_since(saved)


def _drop_flows_registered_since(saved: set[str]) -> None:
    """Drop the flows registered after ``saved`` that no cached import owns."""
    for flow_id in [flow_id for flow_id in registry._flow_specs if flow_id not in saved]:
        if not _owned_by_cached_import(flow_id):
            del registry._flow_specs[flow_id]
            del registry._flow_functions[flow_id]
            _FLOW_IMPORT_OWNERS.pop(flow_id, None)
