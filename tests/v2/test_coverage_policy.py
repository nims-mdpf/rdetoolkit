"""Coverage-policy contract for new v2 code.

EP table:

| Configuration | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``tool.coverage.run`` | repository coverage settings | branch measurement enabled | TC-EP-HR-F6-001 |
| ``py312-module`` | six Phase H modules | each has an independent 95% gate | TC-EP-HR2-C-001 |
| ``py312-module`` | focused posargs run | scoped gate is skipped | TC-EP-HR2-C-002 |

BV table:

| Configuration | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``branch`` | boolean true | no truthy string surrogate | TC-BV-HR-F6-001 |
| global threshold | existing 80% gate | retained alongside scoped gates | TC-BV-HR2-C-001 |
"""

from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib



def test_branch_coverage_is_enabled__tc_ep_hr_f6_001() -> None:
    """TC-EP/BV-HR-F6-001: coverage measures branches with a real boolean."""
    # Given: the repository's canonical Python tool configuration
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    # When: reading the coverage runtime policy
    branch = config["tool"]["coverage"]["run"].get("branch")

    # Then: branch measurement is explicitly enabled as a boolean
    assert branch is True


def test_tox_enforces_six_phase_h_module_gates__tc_ep_bv_hr2_c_001() -> None:
    """TC-EP/BV-HR2-C-001: scoped 95% gates supplement the global 80% gate."""
    # Given: the tox configuration and the six independently measured modules
    root = Path(__file__).resolve().parents[2]
    tox_config = (root / "tox.ini").read_text(encoding="utf-8")
    section = tox_config.split("[testenv:py312-module]", maxsplit=1)[1].split(
        "[testenv:",
        maxsplit=1,
    )[0]
    gate_script = (root / "scripts" / "check_phase_h_coverage.py").read_text(encoding="utf-8")
    modules = (
        "domain/artifacts.py",
        "report/run_report.py",
        "runner/executor.py",
        "runner/invoker.py",
        "runner/planner.py",
        "runner/finalize.py",
    )

    # When: inspecting the dedicated coverage contract
    gates = [line.strip() for line in gate_script.splitlines() if '"--include"' in line]

    # Then: every module has its own 95% branch gate and global 80% remains
    assert len(gates) == len(modules)
    assert gate_script.count('"--fail-under=95"') == 1
    assert all(any(module in gate for gate in gates) for module in modules)
    assert "--cov-fail-under=80" in section
    assert "scripts/check_phase_h_coverage.py {posargs:}" in section


def test_ci_runs_existing_py312_module_contract__tc_ep_hr2_c_002() -> None:
    """TC-EP-HR2-C-002: CI's existing 3.12 module seat owns the scoped gate."""
    # Given: the primary workflow and tox configuration
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")
    tox_config = (root / "tox.ini").read_text(encoding="utf-8")

    # When/Then: matrix expansion reaches py312-module with no duplicate env
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]' in workflow
    assert "tox-env: [module, ruff, mypy]" in workflow
    assert 'tox -e py$(echo "${{ matrix.python-version }}" | tr -d .)-${{ matrix.tox-env }}' in workflow
    assert "[testenv:py312-covcontract]" not in tox_config
