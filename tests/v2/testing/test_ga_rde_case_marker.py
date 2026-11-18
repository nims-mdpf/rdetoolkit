"""GA-10 (#691): the opt-in ``rde_case`` marker and the ``rde_run`` fixture.

In-process tests use the marker exactly as a project would; the behaviours
that must make a pytest run fail or error (and ``--collect-only``) are
observed in a pytest subprocess on a generated test module.

EP table
========

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-CASE-EP-001 | decorated test | absolute project, expected file | rde_run is a successful RdeTestResult |
| TC-CASE-EP-002 | relative project | rootdir-relative path | resolved against pytest's rootdir |
| TC-CASE-EP-003 | parametrize | ordinary ``parametrize`` + case | every item runs the case |
| TC-CASE-EP-004 | multiple data cases | ``pytest.param(marks=rde_case(...))`` | each param runs its own case, readable IDs |
| TC-CASE-EP-005 | expected failure | ``expect_status='failed'`` + code | the failed run satisfies the case |
| TC-CASE-EP-006 | nested node/flow | flow calling a node | runs eagerly through the Runner |
| TC-CASE-EP-007 | raw marker | ``pytest.mark.rde_case(...)`` | same as the decorator |
| TC-CASE-EP-008 | decoration | ``rde_case(...)`` | returns a pytest mark; nothing is called or checked |
| TC-CASE-EP-009 | plain test | no decorator | ordinary pytest behaviour (no rde_run involvement) |
| TC-CASE-EP-010 | phase | sidecar recording the phase | expectation holds |
| TC-CASE-EP-011 | registration | ``--strict-markers`` / ``--markers`` | marker is registered |

BV / negative table
===================

| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-CASE-BV-001 | marker args | positional / unknown / missing / wrong types | ``RdeCaseError`` naming the parameter |
| TC-CASE-BV-002 | expect_files | absolute / traversal / bare string / non-iterable | ``RdeCaseError`` before any run |
| TC-CASE-BV-003 | contradictory | success + error code / phase | ``RdeCaseError`` |
| TC-CASE-BV-004 | expectations | status / code / phase / files violated | one readable message each |
| TC-CASE-BV-005 | pytest run | status mismatch | test FAILED (not passed) with the explanation |
| TC-CASE-BV-006 | pytest run | marked test without ``rde_run`` | setup ERROR, flow never executed |
| TC-CASE-BV-007 | pytest run | ``rde_run`` without marker | setup ERROR with guidance |
| TC-CASE-BV-008 | pytest run | invalid expect path | setup ERROR, no internal traceback, flow never executed |
| TC-CASE-BV-009 | ``--collect-only`` | marked tests | no flow call, no staging, project unchanged |
| TC-CASE-BV-010 | no pytest | ``import rdetoolkit.testing`` with pytest blocked | import and RdeTestRunner work; rde_case explains |
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path, PurePosixPath

import pytest

from rdetoolkit import flow, node
from rdetoolkit.testing import RdeTestResult, RdeTestRunner, rde_case
from rdetoolkit.testing.case import RdeCase, RdeCaseError, case_from_marker, check_case
from rdetoolkit.types import InputPaths, InvoiceData, OutputContext

FIXTURE = Path(__file__).parent / "fixtures" / "rde_case" / "sample"
_RELATIVE_FIXTURE = "tests/v2/testing/fixtures/rde_case/sample"

_CALLS: list[str] = []


@flow(id="tests.ga691.writes_result")
def _writes_result(paths: InputPaths, invoice: InvoiceData, out: OutputContext) -> None:
    _CALLS.append("writes_result")
    rows = paths.rawfiles[0].read_text(encoding="utf-8")
    out.write_bytes("struct", "result.csv", rows.encode())
    out.write_bytes("struct", "temperature.txt", str(invoice.raw["custom"]["temperature"]).encode())


@flow(id="tests.ga691.failing")
def _failing(paths: InputPaths) -> None:
    del paths
    msg = "case failure"
    raise ValueError(msg)


@node(id="tests.ga691.double")
def _double(value: float) -> float:
    return value * 2


@flow(id="tests.ga691.nested")
def _nested(invoice: InvoiceData, out: OutputContext) -> None:
    doubled = _double(float(invoice.raw["custom"]["temperature"]))
    out.write_bytes("struct", "doubled.txt", str(doubled).encode())


def _digest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
        for path in sorted(root.rglob("*"))
    }


_FIXTURE_DIGEST = _digest(FIXTURE)


# ---------------------------------------------------------------- in-process EP


@rde_case(flow=_writes_result, project=FIXTURE, expect_files=("structured/result.csv", "structured/temperature.txt"))
def test_decorated_case_runs_at_setup__tc_case_ep_001(rde_run: RdeTestResult, tmp_path: Path) -> None:
    """TC-CASE-EP-001: the case ran before the body; its result is the fixture value."""
    # Given / When: the case executed at fixture setup
    # Then: the result is a successful isolated run below this test's tmp_path
    assert isinstance(rde_run, RdeTestResult)
    assert rde_run.status == "success"
    assert rde_run.data_root.is_relative_to(tmp_path)
    assert rde_run.artifact_path("structured/temperature.txt").read_text(encoding="utf-8") == "300"
    assert _digest(FIXTURE) == _FIXTURE_DIGEST


@rde_case(flow=_writes_result, project=_RELATIVE_FIXTURE)
def test_relative_project_uses_rootdir__tc_case_ep_002(rde_run: RdeTestResult, request: pytest.FixtureRequest) -> None:
    """TC-CASE-EP-002: a relative project is resolved against pytest's rootdir."""
    # Given: the repository rootdir
    assert (request.config.rootpath / _RELATIVE_FIXTURE).is_dir()
    # Then: the staged copy is of that project
    assert rde_run.status == "success"
    assert rde_run.project_root.name == "sample"


@pytest.mark.parametrize("column", ["time", "value"])
@rde_case(flow=_writes_result, project=FIXTURE, expect_files=("structured/result.csv",))
def test_ordinary_parametrize_runs_case_per_item__tc_case_ep_003(rde_run: RdeTestResult, column: str) -> None:
    """TC-CASE-EP-003: each parametrized item runs the case on its own copy."""
    # Then: the parametrized value and the case result are both available
    header = rde_run.artifact_path("structured/result.csv").read_text(encoding="utf-8").splitlines()[0]
    assert column in header.split(",")


@pytest.mark.parametrize(
    "expected_name",
    [
        pytest.param("result.csv", marks=rde_case(flow=_writes_result, project=FIXTURE), id="valid-measurement"),
        pytest.param(None, marks=rde_case(flow=_failing, project=FIXTURE, expect_status="failed"), id="broken-reader"),
    ],
)
def test_multiple_data_cases__tc_case_ep_004(rde_run: RdeTestResult, expected_name: str | None, request: pytest.FixtureRequest) -> None:
    """TC-CASE-EP-004: per-parameter cases with readable IDs."""
    # Then: each parameter ran its own case and kept its readable ID
    assert request.node.name in {
        "test_multiple_data_cases__tc_case_ep_004[valid-measurement]",
        "test_multiple_data_cases__tc_case_ep_004[broken-reader]",
    }
    if expected_name is None:
        assert rde_run.status == "failed"
    else:
        assert rde_run.artifact_path(f"structured/{expected_name}").is_file()


@rde_case(flow=_failing, project=FIXTURE, expect_status="failed", expect_error_code=3001, expect_files=("job.failed",))
def test_expected_failure_case__tc_case_ep_005(rde_run: RdeTestResult) -> None:
    """TC-CASE-EP-005: a declared failure is a passing case with an inspectable result."""
    # Then: the failure is visible for further assertions
    assert rde_run.iterations[0].error_code == 3001
    assert rde_run.job_failed_path is not None


@rde_case(flow=_nested, project=FIXTURE, expect_files=("structured/doubled.txt",))
def test_nested_node_in_flow__tc_case_ep_006(rde_run: RdeTestResult) -> None:
    """TC-CASE-EP-006: a flow calling a node runs eagerly through the real Runner."""
    # Then: the node's value reached the artifact
    assert rde_run.artifact_path("structured/doubled.txt").read_text(encoding="utf-8") == "600.0"


@pytest.mark.rde_case(flow=_writes_result, project=FIXTURE, expect_files=["structured/result.csv"])
def test_raw_marker_is_equivalent__tc_case_ep_007(rde_run: RdeTestResult) -> None:
    """TC-CASE-EP-007: the marker applied directly behaves like the decorator."""
    # Then
    assert rde_run.status == "success"


def test_decoration_only_attaches_metadata__tc_case_ep_008(tmp_path: Path) -> None:
    """TC-CASE-EP-008: decorating neither calls the flow nor validates or touches the project."""
    # Given: a call log and a project that does not exist (yet)
    _CALLS.clear()
    missing = tmp_path / "not-created"

    # When: decorating a function
    mark = rde_case(flow=_writes_result, project=missing, expect_files=("/absolute",))

    def test_body() -> None: ...

    decorated = mark(test_body)

    # Then: only pytest mark metadata was attached
    assert decorated is test_body
    assert mark.name == "rde_case"
    assert mark.kwargs["project"] == missing
    assert [m.name for m in getattr(decorated, "pytestmark", [])] == ["rde_case"]
    assert _CALLS == []
    assert not missing.exists()


def test_plain_test_is_untouched__tc_case_ep_009(request: pytest.FixtureRequest) -> None:
    """TC-CASE-EP-009: a test without the decorator is ordinary pytest."""
    # Then: no case marker, no rde_run in the fixture closure
    assert request.node.get_closest_marker("rde_case") is None
    assert "rde_run" not in request.fixturenames


#: ``_result_with_sidecar`` document meaning "remove the sidecar the run wrote",
#: i.e. a historic run from before #686 or a sidecar whose write failed.
_NO_SIDECAR = object()


def _sidecar_document(diagnostics: object, **overrides: object) -> dict[str, object]:
    """Return a sidecar shaped like ``report/failure.py`` writes it."""
    document: dict[str, object] = {
        "schema_version": "1",
        "format": "rdetoolkit.failure-diagnostics",
        "run_id": "r",
        "run_status": "failed",
        "diagnostics": diagnostics,
        "truncated": False,
    }
    document.update(overrides)
    return document


def _result_with_sidecar(tmp_path: Path, document: object | str | None) -> RdeTestResult:
    """Run the failing case; ``None`` keeps the real sidecar, otherwise it is replaced or removed."""
    from rdetoolkit.testing.runner import _collect_result

    result = RdeTestRunner(tmp_path / "runs").run(flow=_failing, project=FIXTURE)
    sidecar = result.data_root / "logs" / f"diagnostics_{result.report.run_id}.json"
    # Since #686 every failed run writes the sidecar; the cases below start from it.
    assert result.diagnostics_path == sidecar
    if document is _NO_SIDECAR:
        sidecar.unlink()
    elif document is not None:
        sidecar.write_text(document if isinstance(document, str) else json.dumps(document), encoding="utf-8")
    return _collect_result(result.report, project_root=result.project_root, data_root=result.data_root)


def _failed_case(**overrides: object) -> RdeCase:
    values: dict[str, object] = {"flow": _failing, "project": FIXTURE, "expect_status": "failed"}
    values.update(overrides)
    return RdeCase(**values)  # type: ignore[arg-type]


def test_phase_expectation_reads_the_sidecar__tc_case_ep_010(tmp_path: Path) -> None:
    """TC-CASE-EP-010: a ``diagnostics[*].phase`` of the sidecar satisfies expect_phase."""
    # Given: a failed run whose sidecar records a node_execution diagnostic
    result = _result_with_sidecar(
        tmp_path, _sidecar_document([{"phase": "node_execution", "detail": {"phase": 3}}, "not-a-diagnostic"]),
    )
    # When / Then: the expectation holds
    assert check_case(_failed_case(expect_phase="node_execution"), result) == []


def test_phase_expectation_on_the_real_sidecar__tc_case_ep_010(tmp_path: Path) -> None:
    """TC-CASE-EP-010 (end to end): the sidecar a real failing run writes is what is read."""
    # Given: a real failed run whose sidecar is left exactly as the Runner wrote it
    result = _result_with_sidecar(tmp_path, None)
    assert result.diagnostics_path is not None
    document = json.loads(result.diagnostics_path.read_text(encoding="utf-8"))
    assert (document["format"], document["schema_version"]) == ("rdetoolkit.failure-diagnostics", "1")
    assert [item["phase"] for item in document["diagnostics"]] == ["node_execution"]

    # When / Then: the recorded phase holds, any other phase is reported with what was recorded
    assert check_case(_failed_case(expect_phase="node_execution"), result) == []
    assert check_case(_failed_case(expect_phase="post_validate"), result) == [
        "rde_case expected diagnostic phase 'post_validate'; the sidecar records ['node_execution']",
    ]


@rde_case(flow=_failing, project=FIXTURE, expect_status="failed", expect_error_code=3001, expect_phase="node_execution")
def test_phase_expectation_through_the_marker__tc_case_ep_010(rde_run: RdeTestResult) -> None:
    """TC-CASE-EP-010 (marker): the plugin checks expect_phase against the real sidecar."""
    # Then: the case passed its checks at setup, against the sidecar the run wrote
    assert rde_run.diagnostics_path is not None
    assert rde_run.diagnostics_path.name == f"diagnostics_{rde_run.report.run_id}.json"


@pytest.mark.parametrize(
    ("document", "fragment"),
    [
        pytest.param(
            [1, "phase", {"items": [{"phase": "node_execution"}, None]}],
            "is not a 'rdetoolkit.failure-diagnostics' document",
            id="top-level-list",
        ),
        pytest.param(
            {"schema_version": "1", "diagnostics": [{"phase": "node_execution"}]},
            "is not a 'rdetoolkit.failure-diagnostics' document",
            id="no-format",
        ),
        pytest.param(
            _sidecar_document([{"phase": "node_execution"}], format="rdetoolkit.diagnostics"),
            "is not a 'rdetoolkit.failure-diagnostics' document",
            id="other-format",
        ),
        pytest.param(
            _sidecar_document([{"phase": "node_execution"}], schema_version="2"),
            "schema_version '2'",
            id="unsupported-version",
        ),
        pytest.param(
            _sidecar_document({"phase": "node_execution"}),
            "has no 'diagnostics' list",
            id="diagnostics-not-a-list",
        ),
        pytest.param(
            _sidecar_document([{"exception": {"phase": "node_execution"}}], phase="node_execution"),
            "records none",
            id="phase-outside-diagnostics",
        ),
    ],
)
def test_phase_is_read_from_the_sidecar_schema_only__tc_case_ep_010(tmp_path: Path, document: object, fragment: str) -> None:
    """TC-CASE-EP-010 (layout): only ``diagnostics[*].phase`` of a known sidecar version counts."""
    # Given / When: a sidecar mentioning the expected phase outside the real schema
    failures = check_case(_failed_case(expect_phase="node_execution"), _result_with_sidecar(tmp_path, document))
    # Then: the expectation does not hold, and the message says why
    assert len(failures) == 1
    assert fragment in failures[0]


def test_error_code_found_on_a_tile_of_a_partial_run(tmp_path: Path) -> None:
    """A partial run without a run-level error still matches the failed tile's code."""
    # Given: a partial report whose only error is on tile 1
    from rdetoolkit.report.run_report import RunReport
    from rdetoolkit.testing.runner import _collect_result

    report = RunReport(
        run_id="r1", status="partial", flow_id="f", mode="multidatatile", started_at="", duration_ms=0.0,
        config_digest="", warnings=[], error=None,
        iterations=[
            {"index": 0, "datatile_id": "a", "status": "completed", "error": None},
            {"index": 1, "datatile_id": "b", "status": "failed", "error": {"code": 3001, "name": "N", "message": "m"}},
        ],
    )
    result = _collect_result(report, project_root=tmp_path, data_root=tmp_path)
    # When / Then: the expected code is found, a different one is reported
    assert check_case(_failed_case(expect_status="partial", expect_error_code=3001), result) == []
    assert check_case(_failed_case(expect_status="partial", expect_error_code=1002), result) == [
        "rde_case expected error code 1002; the run recorded [3001]",
    ]


def test_unknown_package_attribute_is_an_attribute_error() -> None:
    """The lazy exports do not turn a typo into an import of something else."""
    # When / Then
    from rdetoolkit import testing

    with pytest.raises(AttributeError, match="no attribute 'rde_cases'"):
        _ = testing.rde_cases


def test_setup_messages_name_the_test_and_the_fix() -> None:
    """The plugin's setup failures say what is wrong and how to fix it."""
    # Given / When
    from rdetoolkit.testing.case import missing_marker_message, missing_rde_run_message

    # Then
    assert missing_rde_run_message("t.py::test_a").startswith("t.py::test_a is marked rde_case")
    assert "add an 'rde_run' parameter" in missing_rde_run_message("t.py::test_a")
    assert "rdetoolkit.testing.rde_case(flow=..., project=...)" in missing_marker_message("t.py::test_b")
    assert "rde_runner fixture" in missing_marker_message("t.py::test_b")


def test_marker_is_registered__tc_case_ep_011(tmp_path: Path) -> None:
    """TC-CASE-EP-011: --strict-markers accepts rde_case and --markers documents it."""
    # Given: a module using the marker under --strict-markers
    completed = _pytest_subprocess(tmp_path, "--markers")
    # Then: the marker is listed with its parameters
    assert completed.returncode == 0, completed.stdout
    assert "@pytest.mark.rde_case(flow, project" in completed.stdout


# ----------------------------------------------------------- validation BV


@pytest.mark.parametrize(
    ("args", "kwargs", "fragment"),
    [
        pytest.param((_writes_result,), {"project": FIXTURE}, "keyword arguments only", id="positional"),
        pytest.param((), {"flow": _writes_result, "project": FIXTURE, "expect_file": ()}, "expect_file", id="unknown"),
        pytest.param((), {"project": FIXTURE}, "flow=", id="missing-flow"),
        pytest.param((), {"flow": _writes_result}, "project=", id="missing-project"),
        pytest.param((), {"flow": "pkg.mod:flow", "project": FIXTURE}, "flow=", id="flow-not-callable"),
        pytest.param((), {"flow": _writes_result, "project": 42}, "project=", id="project-type"),
        pytest.param((), {"flow": _writes_result, "project": "no/such/dir"}, "not an existing directory", id="project-missing"),
        pytest.param((), {"flow": _writes_result, "project": FIXTURE / "inputdata" / "sample.txt"}, "not an existing directory", id="project-file"),
        pytest.param((), {"flow": _writes_result, "project": FIXTURE, "expect_status": "ok"}, "expect_status", id="status"),
        pytest.param((), {"flow": _writes_result, "project": FIXTURE, "expect_status": "failed", "expect_error_code": True}, "expect_error_code", id="code-bool"),
        pytest.param((), {"flow": _writes_result, "project": FIXTURE, "expect_status": "failed", "expect_error_code": "3001"}, "expect_error_code", id="code-str"),
        pytest.param((), {"flow": _writes_result, "project": FIXTURE, "expect_status": "failed", "expect_phase": ""}, "expect_phase", id="phase-empty"),
        pytest.param((), {"flow": _writes_result, "project": FIXTURE, "config": "rdeconfig.yaml"}, "config=", id="config-path"),
    ],
)
def test_marker_parameters_are_validated__tc_case_bv_001(args: tuple[object, ...], kwargs: dict[str, object], fragment: str) -> None:
    """TC-CASE-BV-001: each misconfiguration names the offending parameter."""
    # When / Then
    with pytest.raises(RdeCaseError, match=fragment):
        case_from_marker(args, kwargs, rootpath=Path.cwd())


@pytest.mark.parametrize(
    ("expect_files", "fragment"),
    [
        pytest.param(("/etc/passwd",), "absolute", id="absolute"),
        pytest.param(("C:\\out.csv",), "absolute", id="windows-absolute"),
        pytest.param(("../outside.csv",), r"\.\.", id="traversal"),
        pytest.param(("structured/../../x",), r"\.\.", id="nested-traversal"),
        pytest.param(("",), "below the data root", id="empty"),
        pytest.param((7,), "str or os.PathLike", id="entry-type"),
        pytest.param("structured/result.csv", "sequence", id="bare-string"),
        pytest.param(Path("structured/result.csv"), "sequence", id="bare-path"),
        pytest.param(3, "sequence", id="not-iterable"),
    ],
)
def test_expected_paths_are_validated__tc_case_bv_002(expect_files: object, fragment: str) -> None:
    """TC-CASE-BV-002: expected artifacts must be relative to the isolated data root."""
    # When / Then
    with pytest.raises(RdeCaseError, match=fragment):
        case_from_marker((), {"flow": _writes_result, "project": FIXTURE, "expect_files": expect_files}, rootpath=Path.cwd())


@pytest.mark.parametrize("extra", [{"expect_error_code": 3001}, {"expect_phase": "node_execution"}])
def test_failure_expectations_need_failure_status__tc_case_bv_003(extra: dict[str, object]) -> None:
    """TC-CASE-BV-003: a success case cannot also expect an error code or phase."""
    # When / Then
    with pytest.raises(RdeCaseError, match="expect_status='failed'"):
        case_from_marker((), {"flow": _writes_result, "project": FIXTURE, **extra}, rootpath=Path.cwd())


def test_valid_marker_is_normalized() -> None:
    """A valid marker becomes an RdeCase with absolute project and POSIX artifact paths."""
    # When
    case = case_from_marker(
        (), {"flow": _writes_result, "project": _RELATIVE_FIXTURE, "expect_files": ["structured\\result.csv"]},
        rootpath=FIXTURE.parents[5],
    )
    # Then
    assert case.project == FIXTURE
    assert case.expect_files == (PurePosixPath("structured/result.csv"),)
    assert case.expect_status == "success"


def test_status_mismatch_message__tc_case_bv_004(tmp_path: Path) -> None:
    """TC-CASE-BV-004 (status): the message explains the actual run."""
    # Given: a failed run checked against a success case
    result = _result_with_sidecar(tmp_path, None)
    # When
    failures = check_case(RdeCase(flow=_failing, project=FIXTURE), result)
    # Then
    assert len(failures) == 1
    assert "'failed', expected 'success'" in failures[0]
    assert "case failure" in failures[0]


def test_error_code_mismatch_message__tc_case_bv_004(tmp_path: Path) -> None:
    """TC-CASE-BV-004 (code): the recorded codes are listed."""
    # Given / When
    failures = check_case(_failed_case(expect_error_code=4003), _result_with_sidecar(tmp_path, None))
    # Then
    assert failures == ["rde_case expected error code 4003; the run recorded [3001]"]


@pytest.mark.parametrize(
    ("document", "fragment"),
    [
        pytest.param(_NO_SIDECAR, "wrote no diagnostics sidecar", id="no-sidecar"),
        pytest.param(_sidecar_document([{"phase": "finalize"}]), "records ['finalize']", id="other-phase"),
        pytest.param(_sidecar_document([]), "records none", id="no-phase"),
        pytest.param("{not json", "could not read", id="unreadable"),
    ],
)
def test_phase_mismatch_message__tc_case_bv_004(tmp_path: Path, document: object, fragment: str) -> None:
    """TC-CASE-BV-004 (phase): a missing, different or unreadable sidecar is explained."""
    # Given / When
    failures = check_case(_failed_case(expect_phase="node_execution"), _result_with_sidecar(tmp_path, document))
    # Then
    assert len(failures) == 1
    assert fragment in failures[0]


def test_missing_files_message__tc_case_bv_004(tmp_path: Path) -> None:
    """TC-CASE-BV-004 (files): missing artifacts are listed with the data root."""
    # Given / When
    result = _result_with_sidecar(tmp_path, None)
    failures = check_case(_failed_case(expect_files=(PurePosixPath("structured/result.csv"),)), result)
    # Then
    assert failures == [f"rde_case expected artifact(s) missing below data root {result.data_root}: ['structured/result.csv']"]


# ------------------------------------------------------- pytest subprocess BV

_MODULE_TEMPLATE = '''
from pathlib import Path

import pytest

from rdetoolkit import flow
from rdetoolkit.testing import rde_case
from rdetoolkit.types import InputPaths

PROJECT = Path({project!r})
SENTINEL = Path({sentinel!r})


@flow(id="tests.ga691.subprocess")
def recorded(paths: InputPaths) -> None:
    SENTINEL.write_text("flow executed", encoding="utf-8")


@flow(id="tests.ga691.subprocess_failing")
def failing(paths: InputPaths) -> None:
    SENTINEL.write_text("flow executed", encoding="utf-8")
    raise ValueError("subprocess failure")

{body}
'''


def _write_module(tmp_path: Path, body: str) -> tuple[Path, Path]:
    sentinel = tmp_path / "sentinel.txt"
    module = tmp_path / "suite" / "test_generated.py"
    module.parent.mkdir()
    module.write_text(
        _MODULE_TEMPLATE.format(project=str(FIXTURE), sentinel=str(sentinel), body=textwrap.dedent(body)),
        encoding="utf-8",
    )
    return module, sentinel


def _pytest_subprocess(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--strict-markers",
            "--basetemp", str(tmp_path / "basetemp"), "-o", "addopts=", "-rA", *args,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def test_status_mismatch_fails_the_test__tc_case_bv_005(tmp_path: Path) -> None:
    """TC-CASE-BV-005: a violated expectation is a FAILED test, and the body never runs."""
    # Given: a success case whose flow fails
    module, _ = _write_module(tmp_path, """
        @rde_case(flow=failing, project=PROJECT)
        def test_case(rde_run):
            Path(str(SENTINEL) + ".body").write_text("body ran", encoding="utf-8")
    """)
    # When
    completed = _pytest_subprocess(tmp_path, str(module))
    # Then: the test failed with the explanation, not an error or a pass
    assert completed.returncode == 1, completed.stdout
    assert "1 failed" in completed.stdout
    assert "expected 'success'" in completed.stdout
    assert "3001" in completed.stdout
    assert "subprocess failure" in completed.stdout
    assert not Path(str(tmp_path / "sentinel.txt") + ".body").exists()


def test_marked_test_without_rde_run_errors__tc_case_bv_006(tmp_path: Path) -> None:
    """TC-CASE-BV-006: a case that would silently never run is a setup error."""
    # Given: a marked test that forgot the fixture
    module, sentinel = _write_module(tmp_path, """
        @rde_case(flow=recorded, project=PROJECT)
        def test_case():
            pass
    """)
    # When
    completed = _pytest_subprocess(tmp_path, str(module))
    # Then
    assert completed.returncode == 1, completed.stdout
    assert "1 error" in completed.stdout
    assert "does not request the rde_run fixture" in completed.stdout
    assert not sentinel.exists()


def test_rde_run_without_marker_errors__tc_case_bv_007(tmp_path: Path) -> None:
    """TC-CASE-BV-007: requesting rde_run without a case explains what is missing."""
    # Given
    module, sentinel = _write_module(tmp_path, """
        def test_case(rde_run):
            pass
    """)
    # When
    completed = _pytest_subprocess(tmp_path, str(module))
    # Then
    assert "1 error" in completed.stdout, completed.stdout
    assert "has no rde_case marker" in completed.stdout
    assert not sentinel.exists()


def test_invalid_expected_path_errors_at_setup__tc_case_bv_008(tmp_path: Path) -> None:
    """TC-CASE-BV-008: an escaping expected path is refused before the flow runs."""
    # Given
    module, sentinel = _write_module(tmp_path, """
        @rde_case(flow=recorded, project=PROJECT, expect_files=("../../etc/passwd",))
        def test_case(rde_run):
            pass
    """)
    # When
    completed = _pytest_subprocess(tmp_path, str(module))
    # Then: one clear setup error without rdetoolkit internals
    assert "1 error" in completed.stdout, completed.stdout
    assert "invalid rde_case on suite/test_generated.py::test_case" in completed.stdout
    assert "'..' is not allowed" in completed.stdout
    assert "rdetoolkit/testing/case.py" not in completed.stdout
    assert not sentinel.exists()
    assert not list((tmp_path / "basetemp").rglob("rde_runner/run-*"))


def test_collect_only_has_no_side_effects__tc_case_bv_009(tmp_path: Path) -> None:
    """TC-CASE-BV-009: collection neither runs flows nor stages or modifies data."""
    # Given: decorated, parametrized and invalid cases
    module, sentinel = _write_module(tmp_path, """
        @rde_case(flow=recorded, project=PROJECT)
        def test_single(rde_run):
            pass

        @pytest.mark.parametrize(
            "label",
            [
                pytest.param("a", marks=rde_case(flow=recorded, project=PROJECT), id="first-case"),
                pytest.param("b", marks=rde_case(flow=failing, project=PROJECT, expect_status="failed"), id="second-case"),
            ],
        )
        def test_cases(rde_run, label):
            pass

        @rde_case(flow=recorded, project=PROJECT / "missing", expect_files=("/abs",))
        def test_invalid(rde_run):
            pass
    """)
    before = _digest(FIXTURE)
    # When
    completed = _pytest_subprocess(tmp_path, "--collect-only", "-q", str(module))
    # Then: four readable IDs collected, nothing executed, staged or changed
    assert completed.returncode == 0, completed.stdout
    for test_id in ("test_single", "test_cases[first-case]", "test_cases[second-case]", "test_invalid"):
        assert f"suite/test_generated.py::{test_id}" in completed.stdout
    assert not sentinel.exists()
    assert not list(tmp_path.rglob("rde_runner"))
    assert _digest(FIXTURE) == before


_NO_PYTEST = r'''
import importlib.abc
import sys


class _BlockPytest(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in {"pytest", "_pytest"} or fullname.startswith(("pytest.", "_pytest.")):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


sys.meta_path.insert(0, _BlockPytest())
for name in [name for name in sys.modules if name == "pytest" or name.startswith(("pytest", "_pytest"))]:
    del sys.modules[name]

from pathlib import Path

import rdetoolkit.testing as testing
from rdetoolkit import flow
from rdetoolkit.types import InputPaths


@flow(id="tests.ga691.no_pytest")
def pipeline(paths: InputPaths) -> None:
    assert paths.inputdata.is_dir()


result = testing.RdeTestRunner(Path(sys.argv[2])).run(flow=pipeline, project=sys.argv[1])
assert result.status == "success", result.report.error
assert "pytest" not in sys.modules and "_pytest" not in sys.modules
try:
    testing.rde_case(flow=pipeline, project=sys.argv[1])
except ImportError as exc:
    print("RDE_CASE_IMPORT_ERROR:", exc)
print("IMPORT_OK")
'''


def test_import_without_pytest__tc_case_bv_010(tmp_path: Path) -> None:
    """TC-CASE-BV-010: rdetoolkit.testing imports and runs without pytest; rde_case explains."""
    # Given: an interpreter where importing pytest fails
    script = tmp_path / "no_pytest.py"
    script.write_text(_NO_PYTEST, encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PYTEST_", "COV_"))}
    # When
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(script), str(FIXTURE), str(tmp_path / "runs")],
        capture_output=True, text=True, check=False, timeout=300, env=env, cwd=tmp_path,
    )
    # Then
    assert completed.returncode == 0, completed.stderr
    assert "IMPORT_OK" in completed.stdout
    assert "RDE_CASE_IMPORT_ERROR: rdetoolkit.testing.rde_case requires pytest" in completed.stdout
