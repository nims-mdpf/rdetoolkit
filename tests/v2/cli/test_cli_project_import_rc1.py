"""Project-module import from the working directory (Session RC1-INT-CLI, review item F02).

The installed ``rdetoolkit`` console script starts with the venv ``bin/`` as
``sys.path[0]``, so ``run --flow demo_flow:pipeline`` and ``--module demo_flow``
failed with ``No module named 'demo_flow'`` while ``python -m rdetoolkit``
succeeded. Every CLI path that imports a user-named module now gets
``python -m`` semantics: the working directory is put at the front of
``sys.path`` when it is not already there, through one shared helper.

These tests launch the real installed console script (located beside
``sys.executable``) with ``PYTHONPATH`` removed, so neither pytest's own path
handling nor an inherited variable can mask the defect.

EP table:
    TC-RC1-F02-EP-001 | console script, ``run --flow`` cwd module, --validate-only | exit 0
    TC-RC1-F02-EP-002 | console script, ``flows list --module`` cwd module            | exit 0, flow id listed
    TC-RC1-F02-EP-003 | console script, ``nodes lint --module`` cwd module            | exit 0
    TC-RC1-F02-EP-004 | console script, v1 ``run module::attr`` cwd module            | callback imported, run succeeds (exit 0)
    TC-RC1-F02-EP-005 | console script, missing ``--module``                          | exit 3 with the import message
    TC-RC1-F02-EP-006 | console script, missing ``--flow`` module                     | exit 3 with the import message
    TC-RC1-F02-EP-007 | helper, cwd absent from sys.path                              | inserted at index 0
    TC-RC1-F02-EP-008 | helper, PYTHONPATH set to another directory                   | that directory is not added

BV table:
    TC-RC1-F02-BV-001 | helper, cwd already present (not first)  | sys.path unchanged (no duplicate, no move)
    TC-RC1-F02-BV-002 | helper, called twice                     | cwd appears exactly once
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rdetoolkit.cli._v2_common import ensure_cwd_on_sys_path

_CONSOLE_SCRIPT = Path(sys.executable).parent / "rdetoolkit"

_DEMO_FLOW = (
    "from rdetoolkit import flow, node\n"
    "from rdetoolkit.types import InputPaths\n"
    "@node(id='rc1_f02.demo.node')\n"
    "def demo_node(paths: InputPaths) -> None:\n"
    "    return None\n"
    "@flow(id='rc1_f02.demo.pipeline')\n"
    "def pipeline(paths: InputPaths) -> None:\n"
    "    demo_node(paths)\n"
)

_DEMO_CALLBACK = (
    "def callback(srcpaths, resource_paths):\n"
    "    return None\n"
)


def _seed(data_root: Path) -> None:
    """Create a valid one-tile invoice-mode input tree."""
    for dirname in ("inputdata", "invoice", "tasksupport", "temp"):
        (data_root / dirname).mkdir(parents=True, exist_ok=True)
    (data_root / "inputdata" / "sample.txt").write_text("input", encoding="utf-8")
    invoice = {
        "datasetId": "rc1-f02-dataset",
        "basic": {"dateSubmitted": "2026-07-12", "dataOwnerId": "0" * 56, "dataName": "rc1"},
    }
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    (data_root / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text('{"constant": {}, "variable": []}', encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a project directory with a valid input tree and two importable modules."""
    root = tmp_path / "console_project"
    _seed(root / "data")
    (root / "demo_flow.py").write_text(_DEMO_FLOW, encoding="utf-8")
    (root / "demo_callback.py").write_text(_DEMO_CALLBACK, encoding="utf-8")
    return root


def _console(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    if not _CONSOLE_SCRIPT.is_file():
        pytest.skip(f"installed console script not found beside the interpreter: {_CONSOLE_SCRIPT}")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(_CONSOLE_SCRIPT), *arguments],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_console_run_flow_imports_cwd_module__tc_rc1_f02_ep_001(project: Path) -> None:
    """TC-RC1-F02-EP-001: the console script resolves a flow defined in the project directory."""
    # Given: a project directory holding demo_flow.py and a valid input tree
    # When: the installed console script validates that flow without PYTHONPATH
    result = _console(project, "run", "--flow", "demo_flow:pipeline", "--validate-only")
    # Then: the module is found exactly as under ``python -m rdetoolkit``
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validation succeeded" in result.stdout


def test_console_module_option_imports_cwd_module__tc_rc1_f02_ep_002(project: Path) -> None:
    """TC-RC1-F02-EP-002: ``--module`` on an inspection command resolves a project module."""
    # Given: the same project directory
    # When: flows list imports the project module through --module
    result = _console(project, "flows", "list", "--module", "demo_flow")
    # Then: the import succeeds before enumeration
    assert result.returncode == 0, result.stdout + result.stderr
    assert "rc1_f02.demo.pipeline" in result.stdout


def test_console_lint_module_imports_cwd_module__tc_rc1_f02_ep_003(project: Path) -> None:
    """TC-RC1-F02-EP-003: ``nodes lint --module`` uses the same project import rule."""
    # Given: the same project directory
    # When: lint imports the project module before linting
    result = _console(project, "nodes", "lint", "--module", "demo_flow")
    # Then: the module is imported and lint completes cleanly
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 violations" in result.stdout


def test_console_legacy_run_target_imports_cwd_module__tc_rc1_f02_ep_004(project: Path) -> None:
    """TC-RC1-F02-EP-004: the v1 ``module::attr`` target form resolves a project module too."""
    # Given: a project directory holding a v1 callback module
    # When: the console script runs the dotted v1 target form
    result = _console(project, "run", "demo_callback::callback")
    # Then: the callback is imported and the v1 run succeeds (it was a BadParameter usage error)
    combined = result.stdout + result.stderr
    assert "Failed to import module: demo_callback" not in combined, combined
    assert result.returncode == 0, combined
    assert '"status": "success"' in result.stdout


def test_console_missing_module_is_usage_error__tc_rc1_f02_ep_005(project: Path) -> None:
    """TC-RC1-F02-EP-005: a module that exists nowhere still exits 3 with the import message."""
    # Given: a module name with no file in the project directory
    # When: an inspection command is asked to import it
    result = _console(project, "flows", "list", "--module", "rc1_f02_missing_module")
    # Then: the usage-error contract and the import message are preserved
    assert result.returncode == 3, result.stdout + result.stderr
    assert "Unable to import module rc1_f02_missing_module" in result.stderr
    assert "No module named 'rc1_f02_missing_module'" in result.stderr


def test_console_missing_flow_module_is_usage_error__tc_rc1_f02_ep_006(project: Path) -> None:
    """TC-RC1-F02-EP-006: ``run --flow`` against a missing module still exits 3."""
    # Given: a flow reference whose module does not exist
    # When: the console script tries to resolve it
    result = _console(project, "run", "--flow", "rc1_f02_missing_module:pipeline", "--validate-only")
    # Then: the usage error names the missing module
    assert result.returncode == 3, result.stdout + result.stderr
    assert "No module named 'rc1_f02_missing_module'" in result.stderr


def test_helper_prepends_cwd_when_absent__tc_rc1_f02_ep_007(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F02-EP-007: the helper puts the working directory at the front."""
    # Given: a working directory that is not on sys.path
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry and Path(entry) != tmp_path])
    # When: the helper runs
    ensure_cwd_on_sys_path()
    # Then: the working directory is sys.path[0]
    assert sys.path[0] == os.getcwd()


def test_helper_ignores_pythonpath__tc_rc1_f02_ep_008(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F02-EP-008: only the working directory is added; PYTHONPATH is never read."""
    # Given: PYTHONPATH naming a directory other than the working directory
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("PYTHONPATH", str(elsewhere))
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry])
    before = list(sys.path)
    # When: the helper runs
    ensure_cwd_on_sys_path()
    # Then: exactly the working directory was added, nothing from PYTHONPATH
    assert sys.path == [str(workdir), *before]
    assert str(elsewhere) not in sys.path


def test_helper_keeps_present_cwd_in_place__tc_rc1_f02_bv_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F02-BV-001: a working directory already on sys.path is neither duplicated nor moved."""
    # Given: the working directory already present, but not first
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", ["/rc1-f02-first", str(tmp_path), "/rc1-f02-last"])
    # When: the helper runs
    ensure_cwd_on_sys_path()
    # Then: sys.path is unchanged
    assert sys.path == ["/rc1-f02-first", str(tmp_path), "/rc1-f02-last"]


def test_helper_is_idempotent__tc_rc1_f02_bv_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F02-BV-002: repeated calls add the working directory once."""
    # Given: a working directory absent from sys.path
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", ["/rc1-f02-only"])
    # When: the helper runs twice
    ensure_cwd_on_sys_path()
    ensure_cwd_on_sys_path()
    # Then: the working directory appears exactly once, at the front
    assert sys.path == [str(tmp_path), "/rc1-f02-only"]
