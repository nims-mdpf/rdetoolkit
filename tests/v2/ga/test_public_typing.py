"""GA gate (#698): the GA testing and diagnostics surface is typed for consumers.

A standalone consumer module is type-checked with ``mypy --strict`` against
the installed package (no repository config), the way a structured-program
author's CI would see it: the positive consumer must be clean, and each misuse
must be rejected with the precise error code.

EP table:
| TC | Input | Expected |
|----|-------|----------|
| GA-TYPE-001 | rde_case / RdeTestRunner / RdeTestResult (diagnostics_path, assertions) / rde_check / diagnostics sidecar constants | mypy --strict clean |

BV / negative table:
| TC | Misuse | Expected |
|----|--------|----------|
| GA-TYPE-NEG-001 | ``diagnostics_path`` used as a ``Path`` without a ``None`` check | ``[union-attr]`` |
| GA-TYPE-NEG-002 | ``expect_error_code="3001"`` | ``[arg-type]`` |
| GA-TYPE-NEG-003 | positional arguments to ``rde_case`` | ``[misc]`` |
| GA-TYPE-NEG-004 | ``RdeTestRunner.run`` without ``project`` | ``[call-arg]`` |
| GA-TYPE-NEG-005 | an unknown failure phase assigned to ``FailurePhase`` | ``[assignment]`` |
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_CONSUMER = '''from pathlib import Path

from rdetoolkit import flow
from rdetoolkit.report.failure import FAILURE_DIAGNOSTICS_FORMAT, FAILURE_DIAGNOSTICS_SCHEMA_VERSION, FAILURE_PHASES, FailurePhase
from rdetoolkit.testing import RdeIterationSummary, RdeTestResult, RdeTestRunner, rde_case, rde_check
from rdetoolkit.types import InputPaths


@flow
def pipeline(paths: InputPaths) -> None:
    assert paths.inputdata.is_dir()


@rde_check(id="has-invoice")
def has_invoice(result: RdeTestResult) -> None:
    result.assert_artifact("invoice/invoice.json")


@rde_case(
    flow=pipeline, project="tests/project", expect_status="failed", expect_error_code=3001,
    expect_phase="node_execution", expect_files=("job.failed",), checks=(has_invoice,),
)
def test_case(rde_run: RdeTestResult) -> None:
    sidecar: Path | None = rde_run.diagnostics_path
    if sidecar is not None:
        sidecar.read_text(encoding="utf-8")
    summaries: tuple[RdeIterationSummary, ...] = rde_run.iterations
    codes: list[int | None] = [summary.error_code for summary in summaries]
    rde_run.assert_status("failed")
    rde_run.assert_error_code(3001)
    del codes


def run_directly(base: Path) -> str:
    result = RdeTestRunner(base).run(flow=pipeline, project=base / "project", config={"execution": {"type_check": "strict"}})
    phase: FailurePhase = FAILURE_PHASES[0]
    return f"{result.status} {FAILURE_DIAGNOSTICS_FORMAT} {FAILURE_DIAGNOSTICS_SCHEMA_VERSION} {phase}"
'''


def _check(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(  # noqa: S603 -- fixed interpreter and arguments
        [
            sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental",
            "--cache-dir", str(tmp_path / ".mypy_cache"), str(consumer),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def test_ga_testing_and_diagnostics_surface_is_typed__ga_type_001(tmp_path: Path) -> None:
    """GA-TYPE-001: the documented GA consumer type-checks cleanly."""
    # When: checking a consumer of the GA surface against the installed stubs
    result = _check(tmp_path, _CONSUMER)
    # Then
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [
        pytest.param(
            "from rdetoolkit.testing import RdeTestResult\n"
            "def body(result: RdeTestResult) -> str:\n    return result.diagnostics_path.read_text()\n",
            "[union-attr]",
            id="ga-type-neg-001-optional-sidecar",
        ),
        pytest.param(
            "from rdetoolkit.testing import rde_case\n"
            "def f() -> None: ...\n"
            "rde_case(flow=f, project='p', expect_status='failed', expect_error_code='3001')\n",
            "[arg-type]",
            id="ga-type-neg-002-code-type",
        ),
        pytest.param(
            "from rdetoolkit.testing import rde_case\ndef f() -> None: ...\nrde_case(f, 'p')\n",
            "[misc]",
            id="ga-type-neg-003-positional",
        ),
        pytest.param(
            "from pathlib import Path\nfrom rdetoolkit.testing import RdeTestRunner\n"
            "def f() -> None: ...\nRdeTestRunner(Path('b')).run(flow=f)\n",
            "[call-arg]",
            id="ga-type-neg-004-missing-project",
        ),
        pytest.param(
            "from rdetoolkit.report.failure import FailurePhase\nphase: FailurePhase = 'node_exec'\n",
            "[assignment]",
            id="ga-type-neg-005-unknown-phase",
        ),
    ],
)
def test_misuse_is_rejected__ga_type_neg(tmp_path: Path, source: str, diagnostic: str) -> None:
    """GA-TYPE-NEG-001..005: the stubs keep their constraints for consumers."""
    # When
    result = _check(tmp_path, source)
    # Then: the precise violation is reported
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout, result.stdout
