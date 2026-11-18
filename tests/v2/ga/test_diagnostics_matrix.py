"""GA gate (#698): cross-mode, cross-entry diagnostics and error-contract cells.

Every cell runs one entry (``flow`` / v1 ``callback``) on one mode's committed
contract input and asserts the published contract *and* the GA diagnostics
for that outcome: ``RunReport`` status / error / iteration count, ``job.failed``,
the diagnostics sidecar's phase, code and source line, and ``report explain``.
Expectations come from the frozen v1 observations, from source text and from
the catalog (see ``_harness``), never from a v2 run.

``test_every_matrix_cell_is_covered_or_excluded`` keeps ``matrix.yaml`` honest:
each entry x mode x outcome cell names collected test ids or a specific
exclusion rationale.

EP table (each row x 2 entries x 5 modes unless stated):
| TC | Outcome | Induced by | Expected |
|----|---------|------------|----------|
| GA-*-STRUCTURED-ERROR | known StructuredError | user code raises the frozen v1 error (999) | 999 / emsg verbatim in report, job.failed, sidecar; frozen ``usererr`` job.failed / tree / raw; stops at tile 0; node_execution at the raise line |
| GA-*-PLAIN-EXCEPTION | user node/callback failure | ``ValueError`` | failed; flow 3001 with node id, callback 999 (frozen ``invoice/plainerr``); phase node_execution at the raise line |
| GA-*-STRICT-TYPE-MISMATCH | strict argument rejection | ``str`` passed to an ``int`` node under ``type_check: strict`` | failed 3002; phase node_argument_validation with node / parameter / type names; no executed call recorded |
| GA-*-PUBLICATION-FAILURE | raw publication fails | ``RawArtifactService.copy`` raises ``PermissionError`` | failed 3005; phase artifact_publish; user code never ran |
| GA-*-POST-VALIDATION-FAILURE | post-validation fails | user code writes invalid metadata | failed 4002; every frozen tile kept as completed; phase post_validate on ``meta/metadata.json`` |
| GA-*-INVALID-SOURCE-INVOICE | invalid source invoice | ``basic: null`` | I6-0 ``valerr`` row at its #647 timing: flow 4001 pre_validate / callback 4001 post_validate, tiles kept / table modes tile_prepare |
| GA-*-INFLIGHT-EVENTS | in-flight events | one node call per tile | one started/finished invocation pair per tile, unique ids, before the call's ``node.completed`` |

BV / negative table:
| TC | Boundary | Expected |
|----|----------|----------|
| GA-MATRIX-001 | matrix completeness | every cell exactly once; covered xor excluded; no generic rationale |
| GA-MATRIX-001-NEG | missing / duplicate / both / neither / generic / unknown-mode cell | ``AssertionError`` naming the defect |
| GA-MATRIX-002 | referenced ids | every referenced test id is collected by pytest |
| GA-MATRIX-003 | GA cells | every GA cell id in tests/v2/ga is referenced by the matrix |
| GA-MATRIX-004 | human doc | every outcome is described in docs/ga_debuggability_contract.md |
"""

from __future__ import annotations

import itertools
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from rdetoolkit.errors import ERROR_CATALOG
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.flow_error_table import (
    IterationRule,
    MessageRule,
    expected_cb_v2_iteration_count,
    flow_error_cell,
)
from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.observe import observe_v2_run, parity_view
from tests.v2.ga import _harness as ga
from tests.v2.ga._harness import cells

_MATRIX_PATH = Path(__file__).with_name("matrix.yaml")
_DOC_PATH = _generate.REPOSITORY_ROOT / "docs" / "ga_debuggability_contract.md"


def _assert_located(diagnostic: Any, function: Any, needle: str = "raise ") -> None:
    """The diagnostic's source location is the user's raise statement."""
    location = diagnostic["location"]
    assert location is not None, diagnostic
    assert location["file"].endswith(ga.source_file(function)), location
    assert location["line"] == ga.raise_line(function, needle), location
    assert location["function"] == function.__name__


def _explanation(run: ga.GaRun) -> dict[str, Any]:
    document = run.explain()
    assert (document["run_id"], document["run_status"], document["mode"]) == (
        run.report.run_id, run.report.status, run.report.mode,
    )
    assert document["diagnostics_available"] is True
    return dict(ga.only(document["explanations"]))


# ------------------------------------------------------------ known StructuredError


@pytest.mark.parametrize(("entry", "mode"), cells("structured_error"))
def test_structured_error_passes_through_every_artifact(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-STRUCTURED-ERROR: ecode/emsg reach report, job.failed and sidecar unchanged."""
    # Given: user code raising the frozen v1 user error, under v1's fail_fast
    expected = frozen_observed(f"v1/{mode}/usererr")
    function, needle = ga.RAISE_SITES["structured_error"][entry]

    # When
    run = ga.run_case(entry, mode, tmp_path / mode, monkeypatch, function=ga.USER_CODE["structured_error"][entry])

    # Then: the run failed with the user's code and message, verbatim
    assert run.report.status == "failed"
    assert (run.report.error or {}).get("code") == ga.STRUCTURED_CODE
    assert (run.report.error or {}).get("message") == ga.STRUCTURED_MESSAGE
    assert run.job_failed() == expected["job_failed_text"]
    assert run.job_failed() == f"ErrorCode={ga.STRUCTURED_CODE}\nErrorMessage={ga.STRUCTURED_MESSAGE}\n"

    # And: fail_fast stopped exactly where v1 stopped, leaving v1's tree and raw copies
    assert len(run.report.iterations) == expected["callback_count"] == 1
    assert [iteration["status"] for iteration in run.report.iterations] == ["failed"]
    observed, frozen_view = observe_v2_run(run.root), parity_view(expected)
    assert observed["output_tree"] == frozen_view["output_tree"]
    assert observed["raw_sha256"] == frozen_view["raw_sha256"]

    # And: the sidecar attributes the failure to the raise statement
    diagnostic = ga.only(run.diagnostics())
    assert (diagnostic["phase"], diagnostic["code"], diagnostic["category"]) == (
        "node_execution", ga.STRUCTURED_CODE, "structured_error",
    )
    assert diagnostic["message"] == ga.STRUCTURED_MESSAGE
    assert diagnostic["iteration_index"] == 0
    assert diagnostic["exception"]["type"].endswith("StructuredError")
    _assert_located(diagnostic, function, needle)
    if entry == "flow":
        assert diagnostic["node_id"] == "tests.v2.ga.structured_failure"

    # And: report explain tells the same story
    item = _explanation(run)
    assert (item["source"], item["phase"], item["code"], item["iteration_index"]) == (
        "diagnostics", "node_execution", ga.STRUCTURED_CODE, 0,
    )
    assert item["location"]["line"] == ga.raise_line(function, needle)


# ------------------------------------------------------------ plain user exception


@pytest.mark.parametrize(("entry", "mode"), cells("plain_exception"))
def test_plain_user_exception_is_diagnosed(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-PLAIN-EXCEPTION: an ordinary exception in user code is located and coded."""
    # Given: user code raising ValueError("boom")
    function, needle = ga.RAISE_SITES["plain_exception"][entry]
    # Both entries publish the catalog's node failure. For the callback this is
    # the documented divergence from v1's 999 (contracts.md §J1-5, measured by
    # TC-J1-CBP-EV-011 against the frozen invoice/plainerr observation).
    expected_code = 3001

    # When
    run = ga.run_case(entry, mode, tmp_path / mode, monkeypatch, function=ga.USER_CODE["plain_exception"][entry])

    # Then: failed with the expected code in report and job.failed
    assert run.report.status == "failed"
    assert (run.report.error or {}).get("code") == expected_code
    job_failed = run.job_failed()
    assert job_failed is not None
    assert job_failed.splitlines()[0] == f"ErrorCode={expected_code}"
    assert _generate.PLAIN_FAILURE_MESSAGE in job_failed
    assert (run.report.error or {}).get("name") == ERROR_CATALOG[3001].name
    if entry == "callback":
        # The divergence is a real one: v1 published a different first line.
        assert job_failed.splitlines()[0] != frozen_observed("v1/invoice/plainerr")["job_failed_text"].splitlines()[0]
    assert len(run.report.iterations) == 1

    # And: the sidecar names the exception and its raise line
    diagnostic = ga.only(run.diagnostics())
    assert (diagnostic["phase"], diagnostic["code"]) == ("node_execution", expected_code)
    assert diagnostic["exception"]["type"] == "ValueError"
    assert diagnostic["exception"]["message"] == _generate.PLAIN_FAILURE_MESSAGE
    _assert_located(diagnostic, function, needle)
    if entry == "flow":
        assert diagnostic["node_id"] == "tests.v2.ga.plain_failure"
        assert diagnostic["call_id"] == run.report.iterations[0]["error"]["call_id"]
    assert _explanation(run)["phase"] == "node_execution"


# ------------------------------------------------------------ strict argument rejection


@pytest.mark.parametrize(("entry", "mode"), cells("strict_type_mismatch"))
def test_strict_argument_rejection_names_node_and_parameter(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-STRICT-TYPE-MISMATCH: the rejected argument is attributed, no call is invented."""
    # Given: a str handed to an int node under type_check: strict
    config = ga.v2_config(mode, type_check="strict")

    # When
    run = ga.run_case(
        entry, mode, tmp_path / mode, monkeypatch, function=ga.USER_CODE["strict_type_mismatch"][entry], config=config,
    )

    # Then: failed with the catalog's argument type error
    assert run.report.status == "failed"
    assert (run.report.error or {}).get("code") == 3002
    assert (run.report.error or {}).get("name") == ERROR_CATALOG[3002].name
    job_failed = run.job_failed()
    assert job_failed is not None
    assert job_failed.splitlines()[0] == "ErrorCode=3002"
    assert len(run.report.iterations) == 1

    # And: the rejected node never ran, so no executed call is recorded for it
    calls = [call["node_id"] for call in run.report.iterations[0].get("node_calls") or []]
    assert "tests.v2.ga.typed" not in calls

    # And: the sidecar names node, parameter and type names only
    diagnostic = ga.only(run.diagnostics())
    assert diagnostic["phase"] == "node_argument_validation"
    assert (diagnostic["node_id"], diagnostic["parameter"]) == ("tests.v2.ga.typed", "value")
    assert (diagnostic["expected_type"], diagnostic["actual_type"]) == ("int", "str")
    assert diagnostic["call_id"] is None
    assert diagnostic["iteration_index"] == 0
    item = _explanation(run)
    assert (item["phase"], item["node_id"]) == ("node_argument_validation", "tests.v2.ga.typed")


# ------------------------------------------------------------ publication failure


def _denied_copy(*_args: Any, **_kwargs: Any) -> None:
    msg = "raw/: permission denied"
    raise PermissionError(msg)


@pytest.mark.parametrize(("entry", "mode"), cells("publication_failure"))
def test_publication_failure_is_artifact_publish(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-PUBLICATION-FAILURE: a raw copy failure is 3005 in artifact_publish, before user code."""
    # Given: the raw publication stage cannot write (RDEFormat installs its own
    # component-dispatching copy strategy instead of the generic service)
    target = (
        "rdetoolkit.modes.rdeformat.RdeFormatRawCopyStrategy.copy"
        if mode == "rdeformat"
        else "rdetoolkit.domain.artifacts.RawArtifactService.copy"
    )
    monkeypatch.setattr(target, _denied_copy)

    # When
    run = ga.run_case(entry, mode, tmp_path / mode, monkeypatch, function=ga.USER_CODE["structured_error"][entry])

    # Then: failed with the catalog's publication code, the user code never reached
    assert run.report.status == "failed"
    assert (run.report.error or {}).get("code") == 3005
    job_failed = run.job_failed()
    assert job_failed is not None
    assert job_failed.splitlines()[0] == "ErrorCode=3005"
    assert run.callback_count() == 0
    assert len(run.report.iterations) == 1
    assert run.report.iterations[0].get("node_calls") in (None, [])

    # And: the sidecar points at the publication stage and the raiser
    diagnostic = ga.only(run.diagnostics())
    assert (diagnostic["phase"], diagnostic["code"], diagnostic["iteration_index"]) == ("artifact_publish", 3005, 0)
    assert diagnostic["exception"]["type"] == "PermissionError"
    _assert_located(diagnostic, _denied_copy)
    assert _explanation(run)["phase"] == "artifact_publish"


# ------------------------------------------------------------ post-validation failure


@pytest.mark.parametrize(("entry", "mode"), cells("post_validation_failure"))
def test_post_validation_failure_keeps_every_tile(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-POST-VALIDATION-FAILURE: iterations survive (#685) and post_validate is diagnosed."""
    # Given: user code that publishes an invalid metadata.json on every tile
    tiles = ga.tile_count(mode)

    # When
    run = ga.run_case(entry, mode, tmp_path / mode, monkeypatch, function=ga.USER_CODE["post_validation_failure"][entry])

    # Then: failed with the metadata validation code
    assert run.report.status == "failed"
    assert (run.report.error or {}).get("code") == 4002
    job_failed = run.job_failed()
    assert job_failed is not None
    assert job_failed.splitlines()[0] == "ErrorCode=4002"

    # And: every tile v1 runs for this input is kept, as it completed
    assert [iteration["index"] for iteration in run.report.iterations] == list(range(tiles))
    assert [iteration["status"] for iteration in run.report.iterations] == ["completed"] * tiles
    if entry == "flow":
        assert [
            [call["node_id"] for call in iteration["node_calls"]] for iteration in run.report.iterations
        ] == [["tests.v2.ga.write_invalid_metadata"]] * tiles
    else:
        assert run.callback_count() == tiles

    # And: the sidecar names the phase and the rejected artifact
    diagnostic = ga.only(run.diagnostics())
    assert (diagnostic["phase"], diagnostic["code"]) == ("post_validate", 4002)
    assert diagnostic["artifact_path"] == "meta/metadata.json"
    assert diagnostic["iteration_index"] == 0
    assert diagnostic["location"] is not None
    assert _explanation(run)["phase"] == "post_validate"


# ------------------------------------------------------------ invalid source invoice


@pytest.mark.parametrize(("entry", "mode"), cells("invalid_source_invoice"))
def test_invalid_source_invoice_follows_validation_timing(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-INVALID-SOURCE-INVOICE: the I6-0 ``valerr`` row, diagnosed where it fails (#647)."""
    # Given: the contracted translation of a schema-invalid source invoice
    cell = flow_error_cell(mode, "valerr")
    tiles = ga.tile_count(mode)

    # When: the source invoice violates its schema
    run = ga.run_case(
        entry, mode, tmp_path / mode, monkeypatch, function=ga.USER_CODE["ok"][entry], invalidate_invoice=True,
    )

    # Then: failed with the contracted code in the report and job.failed
    assert run.report.status == "failed"
    assert (run.report.error or {}).get("code") == cell.v2_code
    job_failed = run.job_failed()
    assert job_failed is not None
    assert job_failed.splitlines()[0] == f"ErrorCode={cell.v2_code}"
    diagnostic = ga.only(run.diagnostics())
    assert diagnostic["code"] == cell.v2_code

    if cell.v2_message is MessageRule.V2_PREPARATION:
        # And: a table mode cannot build its first tile, so no user code runs; under
        # the v1 configuration (fail_fast) both entries stop there, which is the
        # table's CB-V2 column
        assert cell.cb_v2_iterations is IterationRule.FIRST_TILE
        expected = expected_cb_v2_iteration_count(cell, tiles)
        assert [iteration["status"] for iteration in run.report.iterations] == ["failed"] * expected
        assert run.callback_count() == 0
        assert (diagnostic["phase"], diagnostic["artifact_path"], diagnostic["iteration_index"]) == ("tile_prepare", None, 0)
    elif entry == "flow":
        # And: a flow's source invoice is final, so it is rejected before any tile
        assert cell.v2_iterations is IterationRule.NONE
        assert run.report.iterations == []
        assert run.callback_count() == 0
        assert (diagnostic["phase"], diagnostic["artifact_path"], diagnostic["iteration_index"]) == (
            "pre_validate", "invoice/invoice.json", None,
        )
    else:
        # And: a callback may still complete the invoice, so it runs every tile and
        # the final invoice is rejected after them, with the tiles kept (#685)
        assert cell.cb_v2_iterations is IterationRule.EXECUTED
        assert [iteration["status"] for iteration in run.report.iterations] == ["completed"] * tiles
        assert run.callback_count() == cell.cb_v2_callback_count == tiles
        assert (diagnostic["phase"], diagnostic["artifact_path"], diagnostic["iteration_index"]) == (
            "post_validate", "invoice/invoice.json", 0,
        )
    assert _explanation(run)["phase"] == diagnostic["phase"]


# ------------------------------------------------------------ in-flight events


@pytest.mark.parametrize(("entry", "mode"), cells("inflight_events"))
def test_inflight_events_bracket_every_node_call(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-INFLIGHT-EVENTS: each node call is announced before it completes, once per tile."""
    # When: user code calls one node per tile
    run = ga.run_case(entry, mode, tmp_path / mode, monkeypatch, function=ga.USER_CODE["inflight"][entry])

    # Then: the run succeeded over every tile v1 runs
    tiles = ga.tile_count(mode)
    assert run.report.status == "success"
    assert len(run.report.iterations) == tiles

    # And: one started/finished pair per tile, correlated and unique
    events = run.events()
    names = [event["name"] for event in events]
    started = [event for event in events if event["name"] == "node.invocation_started"]
    finished = [event for event in events if event["name"] == "node.invocation_finished"]
    assert [event["node_id"] for event in started] == ["tests.v2.ga.probe"] * tiles
    ids = [event["payload"]["invocation_id"] for event in started]
    assert len(set(ids)) == tiles
    assert [event["payload"]["invocation_id"] for event in finished] == ids
    assert [event["payload"]["outcome"] for event in finished] == ["completed"] * tiles
    assert [event["payload"]["iteration_index"] for event in started] == list(range(tiles))
    # The announcement precedes the call's classic completion event.
    completed = [index for index, name in enumerate(names) if name == "node.completed"]
    announced = [index for index, name in enumerate(names) if name == "node.invocation_started"]
    assert len(completed) == tiles
    assert all(start < done for start, done in zip(announced, completed, strict=True))
    assert run.sidecar() is None


# ------------------------------------------------------------ matrix completeness


def _matrix() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(_MATRIX_PATH.read_text(encoding="utf-8"))
    return document


def _expand(pattern: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if pattern == "*":
        return values
    assert pattern in values, f"unknown matrix key {pattern!r}; expected one of {values}"
    return (pattern,)


def _matrix_cells(document: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Expand the matrix's ``entry/mode`` keys (``*`` allowed) into concrete cells."""
    entries, modes = tuple(document["entries"]), tuple(document["modes"])
    expanded: dict[tuple[str, str, str], dict[str, Any]] = {}
    for outcome, spec in document["outcomes"].items():
        for key, cell in spec["cells"].items():
            entry_pattern, mode_pattern = key.split("/")
            for entry, mode in itertools.product(_expand(entry_pattern, entries), _expand(mode_pattern, modes)):
                assert (entry, mode, outcome) not in expanded, f"cell {entry}/{mode}/{outcome} is declared twice"
                expanded[(entry, mode, outcome)] = cell
    return expanded


def _test_ids(cell: dict[str, Any], entry: str, mode: str) -> list[str]:
    values = {
        "entry": entry,
        "ENTRY": ga.ENTRY_IDS[entry],
        "mode": mode,
        "MODE": ga.MODE_IDS[mode],
    }
    return [test.format(**values) for test in cell.get("tests", [])]


#: Rationales that would let a gap pass unexplained.
_GENERIC_RATIONALES = re.compile(r"^\s*(n/?a|none|skip(ped)?|todo|tbd|not applicable)\s*\.?\s*$", re.IGNORECASE)


def _validate_matrix(document: dict[str, Any]) -> None:
    """Fail unless every cell is declared once, covered xor excluded, specifically."""
    assert tuple(document["entries"]) == ga.ENTRIES
    assert tuple(document["modes"]) == ga.MODES
    expanded = _matrix_cells(document)
    required = set(itertools.product(ga.ENTRIES, ga.MODES, document["outcomes"]))
    assert set(expanded) == required, f"missing cells: {sorted(required - set(expanded))}"
    for (entry, mode, outcome), cell in sorted(expanded.items()):
        label = f"{entry}/{mode}/{outcome}"
        assert set(cell) <= {"tests", "excluded", "note"}, f"{label}: unknown keys {set(cell)}"
        assert bool(cell.get("tests")) != bool(cell.get("excluded")), f"{label}: needs tests xor excluded"
        rationale = cell.get("excluded")
        if rationale:
            assert len(rationale) >= 40 and not _GENERIC_RATIONALES.match(rationale), f"{label}: rationale too generic"


def test_every_matrix_cell_is_covered_or_excluded__ga_matrix_001() -> None:
    """GA-MATRIX-001: every entry x mode x outcome cell is declared exactly once."""
    # Given / When / Then: the committed matrix validates
    _validate_matrix(_matrix())


def _drop_cell(document: dict[str, Any]) -> None:
    del document["outcomes"]["inflight_events"]["cells"]["*/*"]
    document["outcomes"]["inflight_events"]["cells"]["flow/*"] = {"tests": ["x::y"]}


def _duplicate_cell(document: dict[str, Any]) -> None:
    document["outcomes"]["inflight_events"]["cells"]["flow/invoice"] = {"tests": ["x::y"]}


def _both(document: dict[str, Any]) -> None:
    document["outcomes"]["inflight_events"]["cells"]["*/*"] = {"tests": ["x::y"], "excluded": "x" * 50}


def _neither(document: dict[str, Any]) -> None:
    document["outcomes"]["inflight_events"]["cells"]["*/*"] = {"note": "covered somewhere"}


def _generic(document: dict[str, Any]) -> None:
    document["outcomes"]["inflight_events"]["cells"]["*/*"] = {"excluded": "n/a"}


def _unknown_mode(document: dict[str, Any]) -> None:
    document["outcomes"]["inflight_events"]["cells"]["flow/rdeformat2"] = {"tests": ["x::y"]}


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        pytest.param(_drop_cell, "missing cells", id="missing-cell"),
        pytest.param(_duplicate_cell, "declared twice", id="duplicate-cell"),
        pytest.param(_both, "tests xor excluded", id="covered-and-excluded"),
        pytest.param(_neither, "tests xor excluded", id="neither"),
        pytest.param(_generic, "too generic", id="generic-rationale"),
        pytest.param(_unknown_mode, "unknown matrix key", id="unknown-mode"),
    ],
)
def test_matrix_gaps_are_rejected__ga_matrix_001_neg(mutate: Any, fragment: str) -> None:
    """GA-MATRIX-001 (negative): a silent gap in the matrix makes the gate RED."""
    # Given: the committed matrix with one defect
    document = _matrix()
    mutate(document)
    # When / Then
    with pytest.raises(AssertionError, match=fragment):
        _validate_matrix(document)


def _collected_ids(paths: set[str]) -> set[str]:
    completed = subprocess.run(  # noqa: S603 -- fixed interpreter and arguments
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-o", "addopts=", *sorted(paths)],
        cwd=_generate.REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-4000:]
    return {line.strip() for line in completed.stdout.splitlines() if "::" in line}


def test_every_referenced_test_id_is_collected__ga_matrix_002_003() -> None:
    """GA-MATRIX-002/003: referenced ids exist; every GA cell is referenced."""
    # Given: every test id the matrix references
    expanded = _matrix_cells(_matrix())
    referenced = {test for (entry, mode, _outcome), cell in expanded.items() for test in _test_ids(cell, entry, mode)}
    files = {test.split("::")[0] for test in referenced} | {
        path.relative_to(_generate.REPOSITORY_ROOT).as_posix() for path in sorted(Path(__file__).parent.glob("test_*.py"))
    }

    # When: pytest collects the referenced files
    collected = _collected_ids(files)

    # Then: no reference points at a test that does not exist
    assert sorted(referenced - collected) == []

    # And: every GA cell in tests/v2/ga is part of the matrix
    ga_cells = {test for test in collected if "[GA-" in test and test.startswith("tests/v2/ga/")}
    assert ga_cells, "no GA cell was collected"
    assert sorted(ga_cells - referenced) == []


def test_every_outcome_is_documented__ga_matrix_004() -> None:
    """GA-MATRIX-004: the human contract describes every machine-readable outcome."""
    # Given: the human document and the matrix
    text = _DOC_PATH.read_text(encoding="utf-8")
    document = _matrix()
    # Then: each outcome key appears as code in the document
    missing = [outcome for outcome in document["outcomes"] if f"`{outcome}`" not in text]
    assert missing == []
    assert "candidate SHA" in text
