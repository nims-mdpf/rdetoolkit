"""Phase K2(d): the v1 orchestration is unreachable from the installed package.

merge_v1/Design.md §I9 exit condition: "with the wheel installed, the old
orchestration cannot be reached". K2(a)–(c) deleted ``rdetoolkit.modeproc``,
``rdetoolkit.processing`` and ``domain/mode.py`` and shrank the public
surface; this module pins that state so a stray re-export, a dangling import
or a resurrected module fails the suite. Every probe that imports runs in a
fresh interpreter, so nothing already imported by the test session can mask
a missing module.

EP table:
| TC | Probe | Expected |
|----|-------|----------|
| TC-K2-UNREACH-001 | ``find_spec`` of the deleted modules | absent (``None`` or ``ModuleNotFoundError``) |
| TC-K2-UNREACH-002 | ``rdetoolkit.workflows`` attributes | legacy names absent, public functions present |
| TC-K2-UNREACH-003 | ``rdetoolkit.<internal>`` attribute access | ``AttributeError``; absent from ``__all__`` and ``dir()``; no fallback import |
| TC-K2-UNREACH-004 | public ``run()`` on both targets in a fresh interpreter | deleted modules never enter ``sys.modules`` |
| TC-K2-UNREACH-005 | ``pkgutil.walk_packages`` over the installed package | every module imports; no deleted module listed |
| TC-K2-UNREACH-007 | ``.pyi`` stubs shipped with the package | each has a ``.py`` twin, a package directory or the extension module |
| TC-K2-UNREACH-010 | shipped agent guide | no reference to ``rdetoolkit.processing`` |

CLI exit codes (item 8) stay pinned by ``tests/v2/cli/test_cli_run.py``; the
Tier-1 surface (item 9) by ``tests/v2/compat/test_tier1_surface.py``; the
wheel contents (item 6) by ``tests/v2/test_wheel_layout.py``.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.v2.contract.fixtures import _generate

DELETED_MODULES = (
    "rdetoolkit.modeproc",
    "rdetoolkit.processing",
    "rdetoolkit.processing.pipeline",
    "rdetoolkit.processing.context",
    "rdetoolkit.processing.factories",
    "rdetoolkit.processing.processors",
    "rdetoolkit.processing.processors.invoice",
    "rdetoolkit.domain.mode",
)
LEGACY_WORKFLOW_NAMES = (
    "_run_legacy",
    "_process_mode",
    "_create_error_status",
    "invoice_mode_process",
    "excel_invoice_mode_process",
    "multifile_mode_process",
    "rdeformat_mode_process",
    "smarttable_invoice_mode_process",
)
PUBLIC_WORKFLOW_NAMES = ("run", "check_files", "check_files_result", "generate_folder_paths_iterator")
INTERNALISED_NAMES = ("modeproc", "processing", "impl", "interfaces")


def _run_python(code: str, *, cwd: Path | None = None) -> dict[str, object]:
    """Run ``code`` in a fresh interpreter and return the JSON it prints last."""
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _spec_is_absent(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:
        return True


@pytest.mark.parametrize("name", DELETED_MODULES)
def test_deleted_modules_have_no_spec__tc_k2_unreach_001(name: str) -> None:
    """TC-K2-UNREACH-001: the deleted modules cannot be located by the import system."""
    assert _spec_is_absent(name), f"{name} is still importable"


def test_workflows_exposes_only_the_public_functions__tc_k2_unreach_002() -> None:
    """TC-K2-UNREACH-002: the loop and its shims are gone; the public functions remain."""
    from rdetoolkit import workflows

    assert [name for name in LEGACY_WORKFLOW_NAMES if hasattr(workflows, name)] == []
    assert [name for name in PUBLIC_WORKFLOW_NAMES if not hasattr(workflows, name)] == []


def test_internal_modules_are_not_package_attributes__tc_k2_unreach_003() -> None:
    """TC-K2-UNREACH-003: no lazy export, no ``__all__`` entry, no fallback import."""
    result = _run_python(
        """
import json, sys
import rdetoolkit
errors = {}
for name in ("modeproc", "processing", "impl", "interfaces", "definitely_not_an_attribute"):
    try:
        getattr(rdetoolkit, name)
        errors[name] = "accessible"
    except AttributeError:
        errors[name] = "AttributeError"
print(json.dumps({
    "errors": errors,
    "in_all": [n for n in ("modeproc", "processing", "impl", "interfaces") if n in rdetoolkit.__all__],
    "in_dir": [n for n in ("modeproc", "processing", "impl", "interfaces") if n in dir(rdetoolkit)],
    "fallback_imported": [m for m in ("rdetoolkit.impl", "rdetoolkit.interfaces") if m in sys.modules],
}))
""",
    )
    assert result["errors"] == dict.fromkeys(
        ("modeproc", "processing", "impl", "interfaces", "definitely_not_an_attribute"),
        "AttributeError",
    )
    assert result["in_all"] == []
    assert result["in_dir"] == []
    # The old ``__getattr__`` fallback imported impl/interfaces on any unknown name.
    assert result["fallback_imported"] == []


def test_public_entry_points_never_import_the_deleted_modules__tc_k2_unreach_004(tmp_path: Path) -> None:
    """TC-K2-UNREACH-004: both ``run()`` targets complete without touching the deleted modules."""
    callback_root = tmp_path / "callback"
    flow_root = tmp_path / "flow"
    _generate.materialize_sut_case("invoice", callback_root)
    _generate.materialize_sut_case("invoice", flow_root)
    result = _run_python(
        f"""
import json, os, sys
from rdetoolkit.workflows import run
from rdetoolkit.models.config import Config, SystemSettings
from rdetoolkit.core.flow import flow
from rdetoolkit.types import InputPaths

def callback(srcpaths, resource_paths):
    pass

os.chdir({str(callback_root)!r})
legacy = run(custom_dataset_function=callback, config=Config(system=SystemSettings()))

@flow
def noop_flow(paths: InputPaths) -> None:
    pass

os.chdir({str(flow_root)!r})
report = run(flow=noop_flow)
print(json.dumps({{
    "legacy_statuses": [s["status"] for s in json.loads(legacy)["statuses"]],
    "flow_status": report.status,
    "flow_error": report.error,
    "leaked": sorted(m for m in sys.modules if m.startswith(("rdetoolkit.processing", "rdetoolkit.modeproc", "rdetoolkit.domain.mode"))),
}}))
""",
    )
    assert result["legacy_statuses"] == ["success"]
    assert result["flow_status"] == "success", result["flow_error"]
    assert result["leaked"] == []


def test_every_installed_module_imports__tc_k2_unreach_005() -> None:
    """TC-K2-UNREACH-005: no dangling import survives, and no deleted module is listed."""
    result = _run_python(
        """
import importlib, json, pkgutil
import rdetoolkit
names, failures = [], {}
for info in pkgutil.walk_packages(rdetoolkit.__path__, "rdetoolkit."):
    names.append(info.name)
    try:
        importlib.import_module(info.name)
    except Exception as exc:  # noqa: BLE001
        failures[info.name] = repr(exc)[:200]
print(json.dumps({"count": len(names), "failures": failures,
                  "deleted_listed": [n for n in names if n.startswith(("rdetoolkit.processing", "rdetoolkit.modeproc", "rdetoolkit.domain.mode"))]}))
""",
    )
    assert result["failures"] == {}
    assert result["deleted_listed"] == []
    assert result["count"] > 100


def test_every_stub_has_a_module_twin__tc_k2_unreach_007() -> None:
    """TC-K2-UNREACH-007: no orphaned ``.pyi`` advertises a deleted module (two-way stub check)."""
    import rdetoolkit

    package_root = Path(rdetoolkit.__file__).parent
    orphans = []
    for stub in sorted(package_root.rglob("*.pyi")):
        twin = stub.with_suffix(".py")
        package_dir = stub.with_suffix("")
        extension = list(stub.parent.glob(stub.stem + ".*.so")) + list(stub.parent.glob(stub.stem + ".*.pyd"))
        if not (twin.exists() or package_dir.is_dir() or extension):
            orphans.append(stub.relative_to(package_root).as_posix())
    assert orphans == []


def test_shipped_agent_guide_does_not_mention_the_processing_package__tc_k2_unreach_010() -> None:
    """TC-K2-UNREACH-010: the guide shipped in the wheel no longer teaches the deleted API."""
    from rdetoolkit import get_agent_guide

    guide = get_agent_guide()
    assert "rdetoolkit.processing" not in guide
    assert "rdetoolkit.modeproc" not in guide
