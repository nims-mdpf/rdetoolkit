# ruff: noqa: INP001
"""Run the explicitly selected frozen-v1 / v2 Runner compatibility evidence.

This repository-only development harness needs pytest and the full checkout.
It never regenerates frozen expectations or calls an external AI provider.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


_MATRIX = "tests/v2/contract/test_unified_matrix.py"
_MODES = ("INV", "XLS", "MDT", "RDF", "SMT")
CASES = (
    *(
        f"{_MATRIX}::test_flow_entry_success_matches_frozen_v1_primary_contract[TC-UM-{mode}-FLOW-OK]"
        for mode in _MODES
    ),
    *(
        f"{_MATRIX}::test_canary_flow_entry_matches_frozen_real_input_observation[TC-UM-{mode}-CANARY-FLOW-OK]"
        for mode in _MODES
    ),
    *(
        f"{_MATRIX}::test_flow_error_cells_match_the_i6_0_translation_table[TC-UM-{mode}-FLOW-{outcome}]"
        for mode in _MODES
        for outcome in ("USERERR", "VALERR")
    ),
    *(
        f"{_MATRIX}::test_multitile_fail_fast_matches_the_v1_oracle[TC-UM-{mode}-FLOW-FAIL-FAST]"
        for mode in ("XLS", "MDT", "SMT")
    ),
    f"{_MATRIX}::test_multitile_continue_partial_matches_the_v1_oracle[TC-UM-MDT-FLOW-CONTINUE-PARTIAL]",
)


class _Evidence:
    def __init__(self) -> None:
        self.collected = 0
        self.passed: set[str] = set()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call" and report.passed and not hasattr(report, "wasxfail"):
            self.passed.add(report.nodeid)


def run_cases(repository: Path, selectors: tuple[str, ...] = CASES) -> int:
    """Run exact selected pytest cases, rejecting incomplete parity evidence.

    Args:
        repository: Checkout root containing the selected tests.
        selectors: Repository-relative exact pytest node IDs.

    Returns:
        Pytest's failure exit code, or 1 when skipped/xfail cases left the
        evidence incomplete. Zero requires every selected case to pass.
    """
    evidence = _Evidence()
    result = pytest.main(
        ["-q", "-o", "addopts=", *(str(repository / selector) for selector in selectors)],
        plugins=[evidence],
    )
    if result:
        return int(result)
    # Each selector is one exact node ID: N selectors must collect N items and
    # all N must pass, so a broadened selector cannot hide a skipped case.
    if not selectors or not (evidence.collected == len(evidence.passed) == len(selectors)):
        sys.stderr.write(
            f"Migration parity incomplete: {len(evidence.passed)} passed, {evidence.collected} collected, "
            f"{len(selectors)} selected; skips and xfails are not evidence.\n",
        )
        return 1
    return 0


if __name__ == "__main__":
    checkout = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(checkout))
    raise SystemExit(run_cases(checkout))
