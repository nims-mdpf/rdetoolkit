"""GA572-TYPE: installed stubs expose report exits and constrain the opt-in flag."""

from pathlib import Path

import pytest

from tests.v2.test_ga_public_typing import _check


def test_exit_api_is_publicly_typed__ga572_type(tmp_path: Path) -> None:
    """GA572-TYPE: consumers retain the v1/v2 return split with the new API."""
    # Given: a strict consumer of the installed package
    source = '''from rdetoolkit.workflows import run
from rdetoolkit.report.run_report import RunReport
def pipeline() -> None:
    pass
report: RunReport = run(flow=pipeline, exit_on_failure=True)
exit_code: int = report.exit_code
legacy: str = run(exit_on_failure=False)
'''
    # When: checking the consumer independently of repository settings
    result = _check(tmp_path, source)
    # Then: both entry return types and the property are available
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("source, diagnostic", [
    ('from rdetoolkit.workflows import run\ndef pipeline() -> None: pass\nrun(flow=pipeline, exit_on_failure="yes")\n', "[call-overload]"),
    ('from rdetoolkit.workflows import run\nrun(exit_on_failure=True)\n', "[call-overload]"),
    ('from rdetoolkit.report.run_report import RunReport\ndef invalid(report: RunReport) -> None:\n    report.exit_code = 0\n', "[misc]"),
])
def test_invalid_exit_usage_is_rejected__ga572_type(tmp_path: Path, source: str, diagnostic: str) -> None:
    """GA572-TYPE: invalid flags and property mutation fail static checks."""
    # Given: an invalid consumer declaration
    # When: checking it with strict mypy
    result = _check(tmp_path, source)
    # Then: invalid usage cannot silently pass through the stubs
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout
