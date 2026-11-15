"""The five-mode migration parity gate accepts only complete passing evidence (#672).

EP/BV table (written before implementation)
| ID | Partition / boundary | Expected |
| MODE-GATE-PASS | one passing selected case | exit 0 |
| MODE-GATE-SKIP | one skipped selected case | exit 1; incomplete evidence |
| MODE-GATE-XFAIL | one expected-failing selected case | exit 1; incomplete evidence |
| MODE-GATE-XPASS | one unexpectedly passing xfail case | exit 1; incomplete evidence |
| MODE-GATE-FAIL | one failing selected case | exit 1 |
| MODE-GATE-MISSING | selected node ID does not exist | exit 4; not found |
| MODE-GATE-BROAD | selector collects a passing and a skipped case | exit 1; incomplete evidence |
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / ".agents/skills/rdetoolkit-v1-migration/scripts/check_mode_parity.py"
_PASS_AND_SKIP = "import pytest\ndef test_a():\n    pass\ndef test_b():\n    pytest.skip('missing oracle')\n"


@pytest.mark.parametrize(
    ("source", "selector", "expected", "evidence"),
    [
        pytest.param("def test_case():\n    pass\n", "probe.py::test_case", 0, "1 passed", id="MODE-GATE-PASS"),
        pytest.param("import pytest\ndef test_case():\n    pytest.skip('missing oracle')\n", "probe.py::test_case", 1, "incomplete", id="MODE-GATE-SKIP"),
        pytest.param("import pytest\n@pytest.mark.xfail\ndef test_case():\n    assert False\n", "probe.py::test_case", 1, "incomplete", id="MODE-GATE-XFAIL"),
        pytest.param("import pytest\n@pytest.mark.xfail\ndef test_case():\n    pass\n", "probe.py::test_case", 1, "incomplete", id="MODE-GATE-XPASS"),
        pytest.param("def test_case():\n    assert False\n", "probe.py::test_case", 1, "1 failed", id="MODE-GATE-FAIL"),
        pytest.param("def test_case():\n    pass\n", "probe.py::missing", 4, "not found", id="MODE-GATE-MISSING"),
        pytest.param(_PASS_AND_SKIP, "probe.py", 1, "incomplete", id="MODE-GATE-BROAD"),
    ],
)
def test_mode_gate_requires_every_selected_case_to_pass(
    tmp_path: Path, source: str, selector: str, expected: int, evidence: str,
) -> None:
    # Given: an isolated pytest case representing one evidence outcome.
    (tmp_path / "probe.py").write_text(source, encoding="utf-8")
    driver = (
        "import importlib.util, pathlib, sys\n"
        "spec = importlib.util.spec_from_file_location('mode_gate', sys.argv[1])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "raise SystemExit(module.run_cases(pathlib.Path(sys.argv[2]), (sys.argv[3],)))\n"
    )
    # When: executing the real harness gate against that selected case.
    result = subprocess.run(
        [sys.executable, "-c", driver, str(SCRIPT), str(tmp_path), selector],
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True, text=True, check=False,
    )
    # Then: only completed passing evidence permits a successful gate.
    assert result.returncode == expected, result.stdout + result.stderr
    assert evidence in result.stdout + result.stderr
