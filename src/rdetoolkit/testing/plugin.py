"""Pytest plugin fixtures for v2 workflow tests."""

from __future__ import annotations  # pragma: no cover

import sys  # pragma: no cover
from collections.abc import Generator  # pragma: no cover
from pathlib import Path  # pragma: no cover
from typing import TYPE_CHECKING, Any  # pragma: no cover

import pytest  # pragma: no cover

if TYPE_CHECKING:  # pragma: no cover
    from rdetoolkit.testing.case import RdeCase
    from rdetoolkit.testing.runner import RdeTestResult, RdeTestRunner
    from rdetoolkit.types import InputPaths, InvoiceData, OutputContext, RdeConfig

# This module is imported through the ``pytest11`` entry point before coverage
# starts, hence the pragmas; the logic the hooks call lives in ``testing.case``
# and ``testing.runner``, which are imported lazily and measured normally.

#: The case and result of an ``rde_run`` fixture, checked before the test body.
_PENDING_CASE: pytest.StashKey[tuple[RdeCase, RdeTestResult]] = pytest.StashKey()  # pragma: no cover


def pytest_addoption(parser: pytest.Parser) -> None:  # pragma: no cover
    """Add ``--rde-update-snapshots``, the only way a test run may rewrite golden files."""
    parser.getgroup("rdetoolkit").addoption(
        "--rde-update-snapshots",
        action="store_true",
        default=False,
        dest="rde_update_snapshots",
        help="approve changed rdetoolkit golden snapshots (assert_snapshot) by rewriting them; "
        "refused when the CI environment variable is set",
    )


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover
    """Register the ``rde_case`` marker so ``--strict-markers`` accepts it."""
    config.addinivalue_line(
        "markers",
        "rde_case(flow, project, expect_status='success', expect_files=(), expect_error_code=None, "
        "expect_phase=None, config=None, checks=()): declarative RDE integration case executed by the rde_run "
        "fixture (see rdetoolkit.testing.rde_case)",
    )
    if config.getoption("rde_update_snapshots", default=False):
        from rdetoolkit.testing import snapshot  # noqa: PLC0415

        # Refused before any test runs, so CI can never approve a change.
        if snapshot.ci_is_active():
            raise pytest.UsageError(snapshot.ci_refusal_message())
        snapshot.set_update_mode(True)


def pytest_unconfigure(config: pytest.Config) -> None:  # pragma: no cover
    """Forget the snapshot update mode so it cannot leak into another session."""
    del config
    module = sys.modules.get("rdetoolkit.testing.snapshot")
    if module is not None:
        module.reset()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:  # pragma: no cover
    """List every golden file an approved snapshot update wrote or removed."""
    module = sys.modules.get("rdetoolkit.testing.snapshot")
    lines = module.update_summary_lines() if module is not None else []
    if lines:
        terminalreporter.section("rdetoolkit: snapshot updates")
        for line in lines:
            terminalreporter.line(line)


@pytest.hookimpl(tryfirst=True)  # pragma: no cover
def pytest_runtest_setup(item: pytest.Item) -> None:  # pragma: no cover
    """Refuse a case-marked test that would never run its case."""
    if item.get_closest_marker("rde_case") is None or "rde_run" in getattr(item, "fixturenames", ()):
        return
    from rdetoolkit.testing.case import missing_rde_run_message  # noqa: PLC0415

    pytest.fail(missing_rde_run_message(item.nodeid), pytrace=False)


@pytest.hookimpl(tryfirst=True)  # pragma: no cover
def pytest_runtest_call(item: pytest.Item) -> None:  # pragma: no cover
    """Check the declared ``rde_case`` expectations as part of the test call."""
    pending = item.stash.get(_PENDING_CASE, None)
    if pending is None:
        return
    from rdetoolkit.testing.case import check_case  # noqa: PLC0415

    failures = check_case(*pending)
    if failures:
        pytest.fail("\n".join(failures), pytrace=False)


@pytest.hookimpl(hookwrapper=True)  # pragma: no cover
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, None]:  # pragma: no cover
    """Attach the retained RDE runs to the report of a failing test, after pytest's own context."""
    del call
    outcome = yield
    report = outcome.get_result()
    runner = getattr(item, "funcargs", {}).get("rde_runner")
    if not report.failed or runner is None or not runner.results:
        return
    from rdetoolkit.testing.runner import retained_runs_report  # noqa: PLC0415

    report.sections.append(("rdetoolkit: retained runs", retained_runs_report(runner.results)))


@pytest.fixture  # pragma: no cover
def rde_runner(tmp_path: Path) -> RdeTestRunner:  # pragma: no cover
    """Return a runner that stages each project copy below this test's ``tmp_path``."""
    from rdetoolkit.testing.runner import RdeTestRunner  # noqa: PLC0415

    return RdeTestRunner(tmp_path / "rde_runner")


@pytest.fixture  # pragma: no cover
def rde_run(request: pytest.FixtureRequest, rde_runner: RdeTestRunner) -> RdeTestResult:  # pragma: no cover
    """Run the test's ``rde_case`` at fixture setup and return its result."""
    from rdetoolkit.testing.case import RdeCaseError, case_from_marker, missing_marker_message  # noqa: PLC0415

    marker = request.node.get_closest_marker("rde_case")
    if marker is None:
        pytest.fail(missing_marker_message(request.node.nodeid), pytrace=False)
    try:
        case = case_from_marker(marker.args, marker.kwargs, rootpath=request.config.rootpath)
    except RdeCaseError as exc:
        pytest.fail(f"invalid rde_case on {request.node.nodeid}: {exc}", pytrace=False)
    result = rde_runner.run(flow=case.flow, project=case.project, config=case.config)
    request.node.stash[_PENDING_CASE] = (case, result)
    return result


@pytest.fixture  # pragma: no cover
def rde_paths(tmp_path: Path) -> InputPaths:  # pragma: no cover
    """Return an isolated minimal ``InputPaths`` tree."""
    from rdetoolkit.testing.builders import make_input_paths  # noqa: PLC0415

    return make_input_paths(tmp_path)


@pytest.fixture  # pragma: no cover
def rde_out(tmp_path: Path) -> OutputContext:  # pragma: no cover
    """Return an isolated ``OutputContext`` with all directories created."""
    from rdetoolkit.testing.builders import make_output_context  # noqa: PLC0415

    return make_output_context(tmp_path / "out")


@pytest.fixture  # pragma: no cover
def rde_config() -> RdeConfig:  # pragma: no cover
    """Return the default strict v2 configuration."""
    from rdetoolkit.types import RdeConfig  # noqa: PLC0415

    return RdeConfig()


@pytest.fixture  # pragma: no cover
def rde_invoice() -> InvoiceData:  # pragma: no cover
    """Return minimal non-empty invoice data."""
    from rdetoolkit.testing.builders import make_invoice  # noqa: PLC0415

    return make_invoice()
