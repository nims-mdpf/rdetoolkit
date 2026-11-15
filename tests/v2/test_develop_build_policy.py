"""Executable contract for event-aware development wheel builds (#748).

EP table:

| Partition | Expected | Test ID |
| --- | --- | --- |
| develop/v2 push | three native 3.12 builds, no cross builds | EP-001 |
| develop/v2 PR to main or other supported branches | 15 native + 3 cross builds | EP-002 |
| excluded branch | build jobs and summary do not run | EP-003 |
| failed/cancelled/skipped required job | summary fails | EP-004 |
| complete artifact set | summary succeeds | EP-005 |
| missing/unexpected/empty artifact | summary fails | EP-006 |
| upload policy | missing wheels fail; only disposable push has short retention | EP-007 |
| workflow wiring | established triggers, dependency results and upload names preserved | EP-008 |

BV table:

| Boundary | Expected | Test ID |
| --- | --- | --- |
| one missing artifact at each matrix seat | summary fails | BV-001 |
| zero-byte wheel or zero artifacts | summary fails | BV-002 |
| develop/v2 prefix versus exact branch | full builds for develop/v20 | BV-003 |

These tests execute the workflow's status/artifact shell steps and evaluate its
limited GitHub expression vocabulary against independent event/artifact oracles.
No package runtime, eager execution, domain errors, or coverage gate changes occur.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
OS_NAMES = {"ubuntu-latest": "Linux", "windows-latest": "Windows", "macos-latest": "macOS"}
PYTHONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]
CROSS_TARGETS = ["x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu", "armv7-unknown-linux-gnueabihf"]


def _workflow() -> dict[str, Any]:
    return yaml.safe_load((ROOT / ".github/workflows/build-test-develop.yml").read_text(encoding="utf-8"))


def _event(event: str, branch: str) -> dict[str, str]:
    return {"event_name": event, "ref": f"refs/heads/{branch}", "ref_name": branch, "head_ref": branch if event == "pull_request" else ""}


def _evaluate(value: Any, context: dict[str, str]) -> Any:
    if not isinstance(value, str) or not value.startswith("${{"):
        return value
    expression = value[3:-2].strip()
    expression = re.sub(r"github\.(\w+)", lambda match: repr(context[match[1]]), expression)
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"!(?!=)", " not ", expression)
    return eval(  # noqa: S307 - fixed repository expressions, with no Python builtins
        expression,
        {"__builtins__": {}},
        {"fromJSON": json.loads, "startsWith": str.startswith, "contains": lambda value, part: part in value, "always": lambda: True},
    )


def _artifacts(smoke: bool) -> set[str]:
    native = {f"wheels-{platform}-py{version}" for platform in OS_NAMES.values() for version in (["3.12"] if smoke else PYTHONS)}
    return native if smoke else native | {f"wheels-linux-{target}" for target in CROSS_TARGETS}


def _write_artifacts(root: Path, names: set[str]) -> None:
    for name in names:
        directory = root / "all-wheels" / name
        directory.mkdir(parents=True)
        (directory / "rdetoolkit.whl").write_bytes(b"wheel")


def _run_summary(root: Path, smoke: bool, native: str = "success", cross: str | None = None) -> subprocess.CompletedProcess[str]:
    summary = _workflow()["jobs"]["summary"]
    environment = os.environ | {"SMOKE_BUILD": str(smoke).lower(), "NATIVE_RESULT": native, "CROSS_RESULT": cross or ("skipped" if smoke else "success")}
    for step in summary["steps"]:
        if "run" in step:
            result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=root, env=environment, capture_output=True, text=True, check=False)
            if result.returncode:
                return result
    return result


@pytest.mark.parametrize(
    ("event", "branch", "smoke"),
    [("push", "develop/v2", True), ("pull_request", "develop/v2", False), ("push", "develop/v1.4.0", False), ("pull_request", "develop/v1.4.0", False), ("push", "develop/v20", False)],
)
def test_event_matrix__ep_001_002_bv_003(event: str, branch: str, smoke: bool) -> None:
    """EP-001/002/BV-003: the exact event selects smoke or release breadth."""
    # Given: an independently classified eligible workflow event
    jobs = _workflow()["jobs"]
    context = _event(event, branch)
    native = jobs["test-build-multi-platform"]
    cross = jobs["test-build-cross-platform"]
    # When: GitHub evaluates the job guards and the native Python matrix
    versions = _evaluate(native["strategy"]["matrix"]["python-version"], context)
    # Then: only the exact develop/v2 push is reduced
    assert _evaluate(native["if"], context)
    assert versions == (["3.12"] if smoke else PYTHONS)
    assert native["strategy"]["matrix"]["os"] == list(OS_NAMES)
    assert {entry["os"]: entry["platform_name"] for entry in native["strategy"]["matrix"]["include"]} == OS_NAMES
    assert bool(_evaluate(cross["if"], context)) is not smoke
    assert cross["strategy"]["matrix"]["target"] == CROSS_TARGETS
    build = next(step for step in cross["steps"] if step.get("uses", "").startswith("PyO3/maturin-action@"))
    assert build["with"]["args"] == "--release --out dist -i 3.10 3.11 3.12 3.13 3.14"
    assert _evaluate(jobs["summary"]["if"], context)
    assert set(jobs["summary"]["needs"]) == {"test-build-multi-platform", "test-build-cross-platform"}
    assert _evaluate(jobs["summary"]["env"]["SMOKE_BUILD"], context) is smoke


@pytest.mark.parametrize("branch", ["develop/v2_private", "docs/builds", "doc-builds", "feature/example", "main"])
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_excluded_branches__ep_003(event: str, branch: str) -> None:
    """EP-003: established branch exclusions continue to skip every job."""
    # Given: branches excluded by the established workflow policy
    jobs = _workflow()["jobs"]
    # When/Then: neither builds nor summary run for these branches
    assert all(not _evaluate(job["if"], _event(event, branch)) for job in jobs.values())


@pytest.mark.parametrize("smoke", [False, True])
@pytest.mark.parametrize(("job", "result"), [("native", "failure"), ("native", "cancelled"), ("native", "skipped"), ("cross", "failure"), ("cross", "cancelled"), ("cross", "unexpected")])
def test_failed_jobs_reject_even_complete_artifacts__ep_004(tmp_path: Path, smoke: bool, job: str, result: str) -> None:
    """EP-004: wheel presence cannot hide an unsuccessful dependency."""
    # Given: complete artifacts but an unsuccessful required job
    _write_artifacts(tmp_path, _artifacts(smoke))
    arguments = {job: result}
    # When: executing the actual summary commands
    outcome = _run_summary(tmp_path, smoke, **arguments)
    # Then: artifacts cannot hide failed/cancelled/skipped dependencies
    assert outcome.returncode != 0, outcome.stdout


@pytest.mark.parametrize("smoke", [False, True])
def test_complete_artifacts__ep_005(tmp_path: Path, smoke: bool) -> None:
    """EP-005: all required jobs and artifacts let the summary succeed."""
    # Given: the complete event-specific artifact set and successful jobs
    _write_artifacts(tmp_path, _artifacts(smoke))
    # When: executing the actual summary commands
    outcome = _run_summary(tmp_path, smoke)
    # Then: the complete build passes
    assert outcome.returncode == 0, outcome.stdout + outcome.stderr


@pytest.mark.parametrize(("smoke", "missing"), [(smoke, name) for smoke in [False, True] for name in sorted(_artifacts(smoke))])
def test_each_missing_artifact__ep_006_bv_001(tmp_path: Path, smoke: bool, missing: str) -> None:
    """EP-006/BV-001: every individual matrix artifact is mandatory."""
    # Given: exactly one artifact is missing at a native or cross matrix seat
    _write_artifacts(tmp_path, _artifacts(smoke) - {missing})
    # When: executing the actual summary commands
    outcome = _run_summary(tmp_path, smoke)
    # Then: one successful wheel cannot mask the missing seat
    assert outcome.returncode != 0, outcome.stdout


@pytest.mark.parametrize("smoke", [False, True])
@pytest.mark.parametrize("defect", ["unexpected", "empty", "zero-byte", "none", "wrong-cross-result"])
def test_artifact_and_dependency_boundaries__ep_006_bv_002(tmp_path: Path, smoke: bool, defect: str) -> None:
    """EP-006/BV-002: artifact completeness includes content and job results."""
    # Given: a complete artifact set modified at one acceptance boundary
    names = _artifacts(smoke)
    _write_artifacts(tmp_path, set() if defect == "none" else names)
    if defect == "unexpected":
        _write_artifacts(tmp_path, {"wheels-unexpected"})
    if defect in {"empty", "zero-byte"}:
        wheel = tmp_path / "all-wheels" / sorted(names)[0] / "rdetoolkit.whl"
        wheel.unlink() if defect == "empty" else wheel.write_bytes(b"")
    # When: executing the actual summary commands
    cross = ("success" if smoke else "skipped") if defect == "wrong-cross-result" else None
    outcome = _run_summary(tmp_path, smoke, cross=cross)
    # Then: missing content, unexpected artifacts and invalid cross skips fail closed
    assert outcome.returncode != 0, outcome.stdout


@pytest.mark.parametrize(("event", "branch", "retention"), [("push", "develop/v2", 3), ("pull_request", "develop/v2", 0), ("push", "develop/v20", 0), ("push", "develop/v1.4.0", 0)])
def test_upload_policy__ep_007(event: str, branch: str, retention: int) -> None:
    """EP-007: upload failures remain visible and retention follows the event."""
    # Given: native/cross wheel uploads and an eligible event
    jobs = _workflow()["jobs"]
    uploads = [step for name in ["test-build-multi-platform", "test-build-cross-platform"] for step in jobs[name]["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    # When/Then: missing files fail the job and only disposable native wheels expire early
    assert len(uploads) == 2
    assert all(step["with"].get("if-no-files-found") == "error" for step in uploads)
    assert _evaluate(uploads[0]["with"].get("retention-days", 0), _event(event, branch)) == retention
    assert "retention-days" not in uploads[1]["with"]


def test_workflow_wiring__ep_008() -> None:
    """EP-008: summary inputs and artifact producers match the tested contract."""
    # Given: the complete development build workflow
    workflow = _workflow()
    jobs = workflow["jobs"]
    triggers = workflow.get("on", workflow.get(True))  # PyYAML's YAML 1.1 loader treats "on" as true.
    # When: inspecting the event and dependency bindings used by GitHub
    summary = jobs["summary"]
    uploads = [step for name in ["test-build-multi-platform", "test-build-cross-platform"] for step in jobs[name]["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    # Then: production execution supplies exactly the inputs used by these tests
    assert triggers == {"pull_request": {"branches": ["main"]}, "push": {"branches": ["develop/v*", "!develop/v*_*"]}}
    assert "always()" in summary["if"]
    assert summary["env"]["NATIVE_RESULT"] == "${{ needs.test-build-multi-platform.result }}"
    assert summary["env"]["CROSS_RESULT"] == "${{ needs.test-build-cross-platform.result }}"
    assert uploads[0]["with"]["name"] == "wheels-${{ matrix.platform_name }}-py${{ matrix.python-version }}"
    assert uploads[1]["with"]["name"] == "wheels-linux-${{ matrix.target }}"
    assert all(not job.get("continue-on-error") for job in jobs.values())
    assert all(not step.get("continue-on-error") for job in jobs.values() for step in job["steps"])
