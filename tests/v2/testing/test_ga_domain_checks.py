"""GA-12 (#693): reusable, opt-in domain checks for RDE pytest cases.

EP table
========

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-CHECK-EP-001 | decorated | ``rde_check(id=...)`` function in ``checks=`` | runs after the run, passes |
| TC-CHECK-EP-002 | plain | undecorated function / lambda in ``checks=`` | accepted |
| TC-CHECK-EP-003 | several | two passing checks | both run, in order |
| TC-CHECK-EP-004 | zero | ``checks=()`` or omitted | the case is unchanged |
| TC-CHECK-EP-005 | explicit | calling the check / ``run.assert_checks`` in a plain test | plain call semantics |
| TC-CHECK-EP-006 | decorator | ``rde_check`` | returns the same function, only adds the id |
| TC-CHECK-EP-007 | failure case | ``expect_status='failed'`` + check on job.failed | checks run on the expected failure |

BV / negative table
===================

| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-CHECK-BV-001 | failing check | assertion on a read artifact | "output contract failed", id, dataset, artifact, tile, detail, location |
| TC-CHECK-BV-002 | several failing | two failing, one passing | every failure reported (no early stop) |
| TC-CHECK-BV-003 | processing failure | run failed, case expects success | "checks not run", status explanation, check not called |
| TC-CHECK-BV-004 | production state | failing check | RunReport.status, run report file and job.failed unchanged |
| TC-CHECK-BV-005 | registration | decorating checks | no node / flow registered; production runs never call checks |
| TC-CHECK-BV-006 | silent pass | a check returning False / a value | failure explaining checks must raise |
| TC-CHECK-BV-007 | error | check raising ValueError | failure with the exception type |
| TC-CHECK-BV-008 | multi-tile | check reading tile 1's artifact | tile 1 and its datatile named |
| TC-CHECK-BV-009 | arguments | bad id / non-callable / bare callable / string / non-callable entry | ValueError / TypeError / RdeCaseError |
| TC-CHECK-BV-010 | pytest run | failing check in a subprocess | FAILED (not error), message in output |
| TC-CHECK-BV-011 | no artifact read | check not using the helpers | message says no artifact was read |
| TC-CHECK-BV-012 | bounded reads | large artifact | default read limit applies inside checks |
"""

from __future__ import annotations

import functools
import hashlib
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from rdetoolkit import flow
from rdetoolkit.core import registry
from rdetoolkit.testing import RdeTestResult, RdeTestRunner, rde_case, rde_check
from rdetoolkit.testing.case import RdeCase, RdeCaseError, case_from_marker, check_case
from rdetoolkit.testing.checks import CHECK_ID_ATTRIBUTE, check_id, run_checks
from rdetoolkit.types import InputPaths, OutputContext

FIXTURE = Path(__file__).parent / "fixtures" / "rde_case" / "sample"

_CALLED: list[str] = []


@flow(id="tests.ga693.peaks")
def _peaks(paths: InputPaths, out: OutputContext) -> None:
    # A tile whose raw file name contains "bad" records a negative intensity.
    bad = "bad" in paths.rawfiles[0].name
    out.write_bytes("struct", "peaks.csv", f"q,intensity\n1.0,10\n2.0,{-5 if bad else 5}\n".encode())


@flow(id="tests.ga693.failing")
def _failing(paths: InputPaths) -> None:
    del paths
    msg = "instrument file unreadable"
    raise ValueError(msg)


@rde_check(id="positive-intensity")
def positive_intensity(run: RdeTestResult) -> None:
    """XRD-style rule: no negative intensity in the peak table."""
    _CALLED.append("positive-intensity")
    rows = run.read_csv("structured/peaks.csv")
    assert all(float(row["intensity"]) >= 0 for row in rows), "negative intensity in structured/peaks.csv"


@rde_check(id="invoice-temperature")
def invoice_temperature(run: RdeTestResult) -> None:
    """Invoice custom-field rule: the temperature is physical."""
    _CALLED.append("invoice-temperature")
    temperature = run.read_json("invoice/invoice.json")["custom"]["temperature"]
    assert temperature >= 0


def peak_columns(run: RdeTestResult) -> None:
    """A plain, undecorated check."""
    _CALLED.append("peak_columns")
    run.assert_csv_columns("structured/peaks.csv", {"q", "intensity"})


def _project(tmp_path: Path, *, bad: bool = False, tiles: int = 1) -> Path:
    project = tmp_path / ("bad" if bad else "good")
    shutil.copytree(FIXTURE, project)
    if bad:
        (project / "inputdata" / "sample.txt").rename(project / "inputdata" / "bad.txt")
    for index in range(1, tiles):
        (project / "inputdata" / f"z{index}-{'bad' if index == tiles - 1 else 'ok'}.txt").write_text("x", encoding="utf-8")
    return project


def _case(project: Path, **overrides: object) -> RdeCase:
    return case_from_marker((), {"flow": _peaks, "project": project, **overrides}, rootpath=project)


@pytest.fixture(autouse=True)
def _clear_calls() -> None:
    _CALLED.clear()


# ------------------------------------------------------------------------ EP


@rde_case(flow=_peaks, project=FIXTURE, checks=(positive_intensity, invoice_temperature, peak_columns))
def test_checks_run_after_the_case__tc_check_ep_001(rde_run: RdeTestResult) -> None:
    """TC-CHECK-EP-001 / 002 / 003: decorated and plain checks ran, in order, before the body."""
    # Then
    assert _CALLED == ["positive-intensity", "invoice-temperature", "peak_columns"]
    assert rde_run.status == "success"


@rde_case(flow=_peaks, project=FIXTURE, checks=[lambda run: run.assert_artifact("structured/peaks.csv")])
def test_lambda_check__tc_check_ep_002(rde_run: RdeTestResult) -> None:
    """TC-CHECK-EP-002: a one-off lambda needs no decorator."""
    # Then
    assert rde_run.status == "success"


@rde_case(flow=_peaks, project=FIXTURE)
def test_no_checks__tc_check_ep_004(rde_run: RdeTestResult) -> None:
    """TC-CHECK-EP-004: without checks= nothing extra runs."""
    # Then
    assert _CALLED == []
    assert rde_run.status == "success"


def test_explicit_calls_in_a_plain_test__tc_check_ep_005(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-CHECK-EP-005: checks are ordinary functions usable without rde_case."""
    # Given
    run = rde_runner.run(flow=_peaks, project=_project(tmp_path))
    # When / Then: direct call and the explicit helper
    assert positive_intensity(run) is None
    run.assert_checks(positive_intensity, peak_columns)
    assert _CALLED == ["positive-intensity", "positive-intensity", "peak_columns"]
    run.assert_checks()


def test_decorator_is_transparent__tc_check_ep_006() -> None:
    """TC-CHECK-EP-006: rde_check returns the function itself with an id attached."""
    # Given
    def raw(run: RdeTestResult) -> None:
        del run

    # When
    decorated = rde_check(id="my.rule:1")(raw)
    # Then
    assert decorated is raw
    assert getattr(raw, CHECK_ID_ATTRIBUTE) == "my.rule:1"
    assert check_id(raw) == "my.rule:1"
    assert check_id(peak_columns) == "peak_columns"
    assert check_id(functools.partial(peak_columns)).startswith("functools.partial(")


@rde_case(flow=_failing, project=FIXTURE, expect_status="failed", expect_error_code=3001, checks=(lambda run: run.assert_artifact("job.failed"),))
def test_checks_on_an_expected_failure__tc_check_ep_007(rde_run: RdeTestResult) -> None:
    """TC-CHECK-EP-007: a declared failure case still runs its output checks."""
    # Then
    assert rde_run.job_failed_path is not None


# ------------------------------------------------------------------------ BV


def test_failing_check_message__tc_check_bv_001(tmp_path: Path) -> None:
    """TC-CHECK-BV-001: the message separates the output contract from processing and attributes it."""
    # Given: a bad dataset that processes successfully
    project = _project(tmp_path, bad=True)
    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=project)
    # When
    failures = check_case(_case(project, checks=(positive_intensity,)), run)
    # Then
    assert len(failures) == 1
    message = failures[0]
    assert message.startswith("output contract failed: rde_check 'positive-intensity' (tests.v2.testing.test_ga_domain_checks.positive_intensity)")
    assert "  dataset: bad" in message
    assert "    structured/peaks.csv (tile 0, datatile 'bad')" in message
    assert "AssertionError: negative intensity in structured/peaks.csv" in message
    assert f"at {Path(__file__)}:" in message
    assert f"run report: {run.report_path}" in message
    assert "processing" not in message.splitlines()[0]


def test_every_failing_check_is_reported__tc_check_bv_002(tmp_path: Path) -> None:
    """TC-CHECK-BV-002: one test reports all broken rules, passing ones stay silent."""
    # Given
    @rde_check(id="always-fails")
    def always_fails(run: RdeTestResult) -> None:
        del run
        raise AssertionError

    project = _project(tmp_path, bad=True)
    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=project)
    # When
    failures = run_checks(run, (positive_intensity, invoice_temperature, always_fails))
    # Then
    assert [line.splitlines()[0].split("'")[1] for line in failures] == ["positive-intensity", "always-fails"]
    assert "AssertionError: " in failures[1]
    assert _CALLED == ["positive-intensity", "invoice-temperature"]
    with pytest.raises(AssertionError, match="always-fails"):
        run.assert_checks(always_fails)


def test_processing_failure_skips_checks__tc_check_bv_003(tmp_path: Path) -> None:
    """TC-CHECK-BV-003: a processing failure is reported as such; checks are not run."""
    # Given
    project = _project(tmp_path)
    run = RdeTestRunner(tmp_path / "runs").run(flow=_failing, project=project)
    case = case_from_marker((), {"flow": _failing, "project": project, "checks": (positive_intensity,)}, rootpath=project)
    # When
    failures = check_case(case, run)
    # Then
    assert "RDE run status was 'failed', expected 'success'" in failures[0]
    assert failures[-1] == "rde_case output checks not run (1): processing ended with status 'failed', expected 'success'"
    assert _CALLED == []


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_failed_check_leaves_production_state__tc_check_bv_004(tmp_path: Path) -> None:
    """TC-CHECK-BV-004: a failing check changes neither RunReport.status nor job.failed."""
    # Given
    project = _project(tmp_path, bad=True)
    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=project)
    assert run.report_path is not None
    before = (run.report.status, _digest(run.report_path), (run.data_root / "job.failed").exists())
    # When
    failures = run_checks(run, (positive_intensity,))
    # Then
    assert failures
    assert (run.report.status, _digest(run.report_path), (run.data_root / "job.failed").exists()) == before
    assert before == ("success", before[1], False)


def test_checks_are_not_registered_or_run_by_production__tc_check_bv_005(tmp_path: Path) -> None:
    """TC-CHECK-BV-005: rde_check registers nothing and the Runner never calls checks."""
    # Given: the registry before decorating a new check
    nodes, flows = registry.list_nodes(), registry.list_flows()

    @rde_check(id="leak-probe")
    def probe(run: RdeTestResult) -> None:
        del run
        _CALLED.append("leak-probe")

    # When: decorating and running the flow through the production entry
    after_nodes, after_flows = registry.list_nodes(), registry.list_flows()
    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=_project(tmp_path))
    # Then
    assert (after_nodes, after_flows) == (nodes, flows)
    assert not hasattr(probe, "__rde_node_spec__")
    assert run.status == "success"
    assert _CALLED == []


@pytest.mark.parametrize("returned", [False, True, 0, "ok"])
def test_returning_a_value_is_a_failure__tc_check_bv_006(tmp_path: Path, returned: object) -> None:
    """TC-CHECK-BV-006: a check that returns instead of asserting cannot pass silently."""
    # Given
    project = _project(tmp_path, bad=True)
    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=project)
    # When
    failures = run_checks(run, (lambda result: (result.read_csv("structured/peaks.csv"), returned)[1],))
    # Then
    assert len(failures) == 1
    assert f"the check returned {returned!r}; a check fails by raising" in failures[0]
    assert "structured/peaks.csv (tile 0" in failures[0]


def test_error_in_a_check_is_its_failure__tc_check_bv_007(tmp_path: Path) -> None:
    """TC-CHECK-BV-007: any exception names its type; the run itself is untouched."""
    # Given
    def broken(run: RdeTestResult) -> None:
        msg = "no such column\nsecond line"
        raise ValueError(msg)

    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=_project(tmp_path))
    # When
    failures = run_checks(run, (broken,))
    # Then
    assert "rde_check 'test_error_in_a_check_is_its_failure__tc_check_bv_007.<locals>.broken'" in failures[0]
    assert "  ValueError: no such column\n      second line" in failures[0]
    assert "artifacts read: none through the result helpers" in failures[0]


def test_multi_tile_attribution__tc_check_bv_008(tmp_path: Path) -> None:
    """TC-CHECK-BV-008: a failing tile's artifact is attributed to that tile."""
    # Given: two tiles, the second one bad
    project = _project(tmp_path, tiles=2)
    config = {"system": {"extended_mode": "MultiDataTile"}}
    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=project, config=config)
    assert run.status == "success", run.failure_summary(expected_status="success")
    datatile = {summary.index: summary.datatile_id for summary in run.iterations}

    @rde_check(id="per-tile-intensity")
    def per_tile(result: RdeTestResult) -> None:
        for summary in result.iterations:
            prefix = "" if summary.index == 0 else f"divided/{summary.index:04d}/"
            rows = result.read_csv(f"{prefix}structured/peaks.csv")
            assert all(float(row["intensity"]) >= 0 for row in rows), f"tile {summary.index}"

    # When
    failures = run_checks(run, (per_tile,))
    # Then
    assert len(failures) == 1
    assert f"structured/peaks.csv (tile 0, datatile {datatile[0]!r})" in failures[0]
    assert f"divided/0001/structured/peaks.csv (tile 1, datatile {datatile[1]!r})" in failures[0]
    assert "AssertionError: tile 1" in failures[0]


@pytest.mark.parametrize("bad_id", ["", "-leading", "has space", "x" * 129, 3])
def test_invalid_ids__tc_check_bv_009(bad_id: object) -> None:
    """TC-CHECK-BV-009: rule IDs are short, stable tokens."""
    # When / Then
    with pytest.raises(ValueError, match="rde_check id= must match"):
        rde_check(id=bad_id)  # type: ignore[arg-type]


def test_decorating_non_callables__tc_check_bv_009() -> None:
    """TC-CHECK-BV-009: only callables that can carry the id are decorated."""
    # When / Then
    with pytest.raises(TypeError, match="decorates a callable"):
        rde_check(id="x")(3)  # type: ignore[type-var]
    with pytest.raises(TypeError, match="wrap it in a def function"):
        rde_check(id="x")(len)


@pytest.mark.parametrize(
    ("checks", "fragment"),
    [
        pytest.param(positive_intensity, "must be a sequence of check callables", id="bare-callable"),
        pytest.param("positive_intensity", "must be a sequence", id="string"),
        pytest.param(3, "must be a sequence", id="not-iterable"),
        pytest.param((positive_intensity, "x"), "entry 'x' is not callable", id="entry"),
    ],
)
def test_invalid_checks_parameter__tc_check_bv_009(checks: object, fragment: str) -> None:
    """TC-CHECK-BV-009: checks= is validated at fixture setup like every other parameter."""
    # When / Then
    with pytest.raises(RdeCaseError, match=fragment):
        _case(FIXTURE, checks=checks)


def test_exception_without_traceback_has_no_location() -> None:
    """An exception that was never raised has no user frame to point at."""
    # When / Then
    from rdetoolkit.testing.checks import _describe

    assert _describe(ValueError("x")) == ["ValueError: x"]
    assert _describe(AssertionError()) == ["AssertionError: "]


def test_valid_checks_are_kept_in_order() -> None:
    """A valid checks= sequence becomes a tuple in the given order."""
    # When / Then
    assert _case(FIXTURE, checks=[peak_columns, positive_intensity]).checks == (peak_columns, positive_intensity)
    assert _case(FIXTURE).checks == ()


def test_reads_are_bounded_inside_checks__tc_check_bv_012(tmp_path: Path) -> None:
    """TC-CHECK-BV-012: checks use the same bounded readers as tests."""
    # Given
    run = RdeTestRunner(tmp_path / "runs").run(flow=_peaks, project=_project(tmp_path))
    # When
    failures = run_checks(run, (lambda result: result.read_text("structured/peaks.csv", max_bytes=4) and None,))
    # Then
    assert "above the read limit of 4 bytes" in failures[0]


def test_failing_check_fails_the_pytest_test__tc_check_bv_010(tmp_path: Path) -> None:
    """TC-CHECK-BV-010: an rde_case whose check fails is FAILED with the attributed message."""
    # Given
    project = _project(tmp_path, bad=True)
    module = tmp_path / "suite" / "test_checks.py"
    module.parent.mkdir()
    module.write_text(
        textwrap.dedent(f"""
            from pathlib import Path

            from rdetoolkit import flow
            from rdetoolkit.testing import rde_case, rde_check
            from rdetoolkit.types import InputPaths, OutputContext


            @flow(id="tests.ga693.subprocess")
            def pipeline(paths: InputPaths, out: OutputContext) -> None:
                out.write_bytes("struct", "peaks.csv", b"q,intensity\\n1.0,-1\\n")


            @rde_check(id="positive-intensity")
            def positive_intensity(run):
                rows = run.read_csv("structured/peaks.csv")
                assert all(float(row["intensity"]) >= 0 for row in rows)


            @rde_case(flow=pipeline, project=Path({str(project)!r}), checks=(positive_intensity,))
            def test_xrd(rde_run):
                Path(__file__).with_suffix(".body").write_text("ran", encoding="utf-8")
        """),
        encoding="utf-8",
    )
    # When
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-o", "addopts=", "--basetemp", str(tmp_path / "bt"), str(module)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    # Then: FAILED, with the rule, the artifact and pytest's rewritten assertion
    assert completed.returncode == 1, completed.stdout
    assert "1 failed" in completed.stdout
    assert "output contract failed: rde_check 'positive-intensity'" in completed.stdout
    assert "structured/peaks.csv (tile 0, datatile 'bad')" in completed.stdout
    assert "AssertionError: assert False" in completed.stdout
    assert not module.with_suffix(".body").exists()
