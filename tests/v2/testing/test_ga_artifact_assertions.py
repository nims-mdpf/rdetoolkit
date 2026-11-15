"""GA-11 (#692): readable RDE artifact assertions on ``RdeTestResult``.

Every assertion runs against a real isolated run (``RdeTestRunner`` on a
staged copy of the shared sample project).

EP table
========

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-ASSERT-EP-001 | status / error code | matching status, recorded code | passes |
| TC-ASSERT-EP-002 | existence | present file / absent file | passes |
| TC-ASSERT-EP-003 | JSON subset / exact | matching content | passes |
| TC-ASSERT-EP-004 | CSV header / rows | matching header and cells | passes |
| TC-ASSERT-EP-005 | tree | exact file set (with explicit ignore) | passes |
| TC-ASSERT-EP-006 | metadata / invoice | valid documents with defined keys | passes |
| TC-ASSERT-EP-007 | read helpers | json / csv / text / streamed csv | parsed content |
| TC-ASSERT-EP-008 | standalone | ``assertions.assert_json_subset(result, ...)`` | same as the method |

BV / negative table
===================

| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-ASSERT-BV-001 | status | different status / unknown status | AssertionError explaining the run / ValueError |
| TC-ASSERT-BV-002 | error code | other code / success run / bool | lists recorded codes / TypeError |
| TC-ASSERT-BV-003 | existence | missing file / unexpected file | message names path and siblings |
| TC-ASSERT-BV-004 | JSON pointer | changed / missing / null-vs-absent / bool-vs-int / int-vs-float / extra key / list length / type | one pointer line each |
| TC-ASSERT-BV-005 | CSV | missing / extra column, changed cell, row count, non-str cell | names column and row |
| TC-ASSERT-BV-006 | tree | missing / extra files | both listed |
| TC-ASSERT-BV-007 | traversal | absolute / ``..`` artifact names | ValueError before reading |
| TC-ASSERT-BV-008 | size | artifact above ``max_bytes`` | AssertionError naming the limit |
| TC-ASSERT-BV-009 | metadata | invalid structure / undefined key / missing definition | AssertionError |
| TC-ASSERT-BV-010 | invoice | schema violation | AssertionError |
| TC-ASSERT-BV-011 | context | any failure | message ends with data root and run report |
| TC-ASSERT-BV-012 | bad JSON / text | malformed JSON, undecodable text, directory as file | AssertionError |
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from rdetoolkit import flow
from rdetoolkit.testing import RdeTestResult, RdeTestRunner, assertions
from rdetoolkit.types import InputPaths, OutputContext

FIXTURE = Path(__file__).parent / "fixtures" / "rde_case" / "sample"

_RESULT_CSV = b"time,value,label\n0,1.0,a\n1,2.5,b\n"
_RESULT_JSON = {
    "custom": {"temperature": 300, "pressure": 1.0, "enabled": True, "note": None},
    "peaks": [{"q": 1.2, "intensity": 10}, {"q": 2.4, "intensity": 5}],
}
_METADATA = {"constant": {"temperature": {"value": 300}}, "variable": [{"intensity": {"value": 10}}]}
_METADATA_DEF = {
    "temperature": {"name": {"ja": "温度", "en": "temperature"}, "schema": {"type": "number"}},
    "intensity": {"name": {"ja": "強度", "en": "intensity"}, "schema": {"type": "number"}},
}


@flow(id="tests.ga692.artifacts")
def _artifacts(paths: InputPaths, out: OutputContext) -> None:
    del paths
    out.write_bytes("struct", "result.csv", _RESULT_CSV)
    out.write_bytes("struct", "result.json", json.dumps(_RESULT_JSON).encode())
    out.write_bytes("meta", "metadata.json", json.dumps(_METADATA).encode())


@flow(id="tests.ga692.failing")
def _failing(paths: InputPaths) -> None:
    del paths
    msg = "broken reader"
    raise ValueError(msg)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The shared sample project plus a metadata definition."""
    root = tmp_path_factory.mktemp("ga692") / "sample"
    shutil.copytree(FIXTURE, root)
    (root / "tasksupport" / "metadata-def.json").write_text(json.dumps(_METADATA_DEF), encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def run(project: Path, tmp_path_factory: pytest.TempPathFactory) -> RdeTestResult:
    """One successful run shared by the read-only tests."""
    result = RdeTestRunner(tmp_path_factory.mktemp("ga692-runs")).run(flow=_artifacts, project=project)
    assert result.status == "success", result.failure_summary(expected_status="success")
    return result


@pytest.fixture
def scratch(project: Path, tmp_path: Path) -> RdeTestResult:
    """A run of its own, for tests that add files to the retained data root."""
    return RdeTestRunner(tmp_path).run(flow=_artifacts, project=project)


@pytest.fixture(scope="module")
def failed(project: Path, tmp_path_factory: pytest.TempPathFactory) -> RdeTestResult:
    """One failed run (E3001) shared by the read-only tests."""
    return RdeTestRunner(tmp_path_factory.mktemp("ga692-failed")).run(flow=_failing, project=project)


def _message(excinfo: pytest.ExceptionInfo[AssertionError]) -> str:
    return str(excinfo.value)


# ------------------------------------------------------------------------ EP


def test_status_and_error_code_pass__tc_assert_ep_001(run: RdeTestResult, failed: RdeTestResult) -> None:
    """TC-ASSERT-EP-001: matching status and a recorded code pass."""
    # When / Then: no exception
    run.assert_status("success")
    failed.assert_status("failed")
    failed.assert_error_code(3001)


def test_existence_passes__tc_assert_ep_002(run: RdeTestResult) -> None:
    """TC-ASSERT-EP-002: present and absent artifacts as declared."""
    # When / Then
    run.assert_artifact("structured/result.csv")
    run.assert_artifact("structured/result.csv", exists=True)
    run.assert_artifact("job.failed", exists=False)


def test_json_subset_and_exact_pass__tc_assert_ep_003(run: RdeTestResult) -> None:
    """TC-ASSERT-EP-003: subset and exact JSON comparison of matching content."""
    # When / Then
    run.assert_json_subset("structured/result.json", {"custom": {"temperature": 300, "note": None}})
    run.assert_json_subset("invoice/invoice.json", {"custom": {"temperature": 300}})
    run.assert_json_equal("structured/result.json", _RESULT_JSON)


def test_csv_header_and_rows_pass__tc_assert_ep_004(run: RdeTestResult) -> None:
    """TC-ASSERT-EP-004: CSV columns (subset and exact) and every cell."""
    # When / Then
    run.assert_csv_columns("structured/result.csv", {"time", "value"})
    run.assert_csv_columns("structured/result.csv", ["time", "value", "label"], exact=True)
    run.assert_csv_rows(
        "structured/result.csv",
        [{"time": "0", "value": "1.0", "label": "a"}, {"time": "1", "value": "2.5", "label": "b"}],
    )


def test_tree_passes__tc_assert_ep_005(run: RdeTestResult) -> None:
    """TC-ASSERT-EP-005: the exact file set below a directory, ignoring only listed patterns."""
    # When / Then
    run.assert_tree({"result.csv", "result.json"}, root="structured")
    run.assert_tree(["metadata.json"], root="meta")
    run.assert_tree(["structured/result.csv", "structured/result.json", "meta/metadata.json"], ignore=("logs/*", "inputdata/*", "invoice/*", "tasksupport/*", "nonshared_raw/*"))


def test_metadata_and_invoice_valid__tc_assert_ep_006(run: RdeTestResult) -> None:
    """TC-ASSERT-EP-006: metadata uses defined keys; the invoice matches its schema."""
    # When / Then
    run.assert_metadata_valid()
    run.assert_metadata_valid("meta/metadata.json", definition=None)
    run.assert_invoice_valid()


def test_read_helpers__tc_assert_ep_007(run: RdeTestResult) -> None:
    """TC-ASSERT-EP-007: read helpers parse the artifact; cells stay strings."""
    # When
    rows = run.read_csv("structured/result.csv")
    # Then
    assert rows[1] == {"time": "1", "value": "2.5", "label": "b"}
    assert list(run.iter_csv("structured/result.csv")) == rows
    assert run.read_json("structured/result.json") == _RESULT_JSON
    assert run.read_text("structured/result.csv").startswith("time,")
    assert run.read_bytes("structured/result.csv") == _RESULT_CSV


def test_standalone_functions_match_methods__tc_assert_ep_008(run: RdeTestResult) -> None:
    """TC-ASSERT-EP-008: the module functions are the same assertions."""
    # When / Then
    assertions.assert_json_subset(run, "structured/result.json", {"custom": {"enabled": True}})
    with pytest.raises(AssertionError, match="/custom/enabled"):
        assertions.assert_json_subset(run, "structured/result.json", {"custom": {"enabled": False}})


# ------------------------------------------------------------------------ BV


def test_status_mismatch_explains_the_run__tc_assert_bv_001(failed: RdeTestResult) -> None:
    """TC-ASSERT-BV-001: the status message carries the run error and paths."""
    # When
    with pytest.raises(AssertionError) as excinfo:
        failed.assert_status("success")
    # Then
    message = _message(excinfo)
    assert "'failed', expected 'success'" in message
    assert "broken reader" in message
    assert "run report:" in message


def test_unknown_status_is_a_usage_error__tc_assert_bv_001(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-001: a typo in the expected status is not a silent mismatch."""
    # When / Then
    with pytest.raises(ValueError, match="expected status must be one of"):
        run.assert_status("ok")


def test_error_code_mismatch__tc_assert_bv_002(run: RdeTestResult, failed: RdeTestResult) -> None:
    """TC-ASSERT-BV-002: another code lists what was recorded; a success run records none."""
    # When / Then
    with pytest.raises(AssertionError, match=r"expected error code 4003; the run recorded \[3001\]"):
        failed.assert_error_code(4003)
    with pytest.raises(AssertionError, match="the run recorded none"):
        run.assert_error_code(3001)
    with pytest.raises(TypeError, match="int catalog code"):
        failed.assert_error_code(True)


def test_missing_and_unexpected_artifacts__tc_assert_bv_003(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-003: existence failures name the path and what is there instead."""
    # When
    with pytest.raises(AssertionError) as missing:
        run.assert_artifact("structured/results.csv")
    with pytest.raises(AssertionError) as present:
        run.assert_artifact("structured/result.csv", exists=False)
    with pytest.raises(AssertionError, match="'nope/x.csv' to exist, but it is missing\n"):
        run.assert_artifact("nope/x.csv")
    # Then
    assert "expected artifact 'structured/results.csv' to exist, but it is missing" in _message(missing)
    assert "structured/ contains ['result.csv', 'result.json']" in _message(missing)
    assert "expected artifact 'structured/result.csv' to be absent, but it exists" in _message(present)


@pytest.mark.parametrize(
    ("expected", "line"),
    [
        pytest.param({"custom": {"temperature": 301}}, "/custom/temperature: expected 301, got 300", id="changed"),
        pytest.param({"custom": {"humidity": 3}}, "/custom/humidity: missing (expected 3)", id="missing"),
        pytest.param({"custom": {"absent": None}}, "/custom/absent: missing (expected null)", id="null-vs-absent"),
        pytest.param({"custom": {"note": "x"}}, '/custom/note: expected "x", got null', id="value-vs-null"),
        pytest.param({"custom": {"enabled": 1}}, "/custom/enabled: expected 1, got true", id="int-vs-bool"),
        pytest.param({"custom": {"temperature": 300.0}}, "/custom/temperature: expected 300.0, got 300", id="float-vs-int"),
        pytest.param({"custom": {"pressure": 1}}, "/custom/pressure: expected 1, got 1.0", id="int-vs-float"),
        pytest.param({"peaks": [{"q": 1.2}]}, "/peaks: expected 1 item(s), got 2", id="list-length"),
        pytest.param({"peaks": [{"q": 1.2}, {"q": 2.5}]}, "/peaks/1/q: expected 2.5, got 2.4", id="list-element"),
        pytest.param({"custom": [1]}, "/custom: expected an array, got {", id="object-vs-array"),
        pytest.param({"custom": {"temperature": {"value": 300}}}, "/custom/temperature: expected an object, got 300", id="scalar-vs-object"),
        pytest.param({"a/b~c": 1}, "/a~1b~0c: missing", id="pointer-escaping"),
    ],
)
def test_json_subset_names_the_pointer__tc_assert_bv_004(run: RdeTestResult, expected: dict[str, object], line: str) -> None:
    """TC-ASSERT-BV-004: each JSON difference is reported by pointer with strict JSON types."""
    # When
    with pytest.raises(AssertionError) as excinfo:
        run.assert_json_subset("structured/result.json", expected)
    # Then
    assert "JSON artifact 'structured/result.json' does not contain the expected subset:" in _message(excinfo)
    assert line in _message(excinfo)


def test_json_equal_reports_unexpected_keys__tc_assert_bv_004(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-004 (exact): extra keys are differences, not ignored."""
    # Given: the content without one key
    expected = json.loads(json.dumps(_RESULT_JSON))
    del expected["custom"]["note"]
    # When
    with pytest.raises(AssertionError) as excinfo:
        run.assert_json_equal("structured/result.json", expected)
    # Then
    assert "/custom/note: unexpected (got null)" in _message(excinfo)
    assert "differs from the expected content" in _message(excinfo)


def test_json_nan_is_equal_to_nan() -> None:
    """NaN recorded on both sides is the same value, not a difference."""
    # When / Then
    assert assertions.json_differences({"x": float("nan")}, {"x": float("nan")}, subset=False) == []
    assert assertions.json_differences({"x": float("nan")}, {"x": 1.0}, subset=False) == ["/x: expected NaN, got 1.0"]
    assert assertions.json_differences(1, 2, subset=True) == ["/: expected 1, got 2"]


def test_message_helpers_edge_values(run: RdeTestResult) -> None:
    """Non-JSON and long values stay printable; a run without a report file omits that line."""
    # When / Then
    assert assertions._short({1}) == "{1}"
    assert assertions._short("x" * 200).endswith('...')
    assert len(assertions._short("x" * 200)) == 80
    assert assertions.context_lines(dataclasses.replace(run, report_path=None)) == [f"data root: {run.data_root}"]


def test_many_differences_are_capped() -> None:
    """A long difference list stays readable."""
    # When
    lines = assertions.json_differences(list(range(30)), [-1] * 30, subset=False)
    # Then
    assert len(lines) == 30
    assert assertions._capped(lines)[-1] == "  ... and 10 more"


@pytest.mark.parametrize(
    ("columns", "exact", "fragments"),
    [
        pytest.param({"time", "intensity"}, False, ("missing column(s):", "  intensity"), id="missing"),
        pytest.param(["time", "value"], True, ("unexpected column(s):", "  label"), id="extra-exact"),
    ],
)
def test_csv_columns_mismatch__tc_assert_bv_005(run: RdeTestResult, columns: object, exact: bool, fragments: tuple[str, ...]) -> None:
    """TC-ASSERT-BV-005 (header): missing and unexpected columns are listed with the header."""
    # When
    with pytest.raises(AssertionError) as excinfo:
        run.assert_csv_columns("structured/result.csv", columns, exact=exact)  # type: ignore[arg-type]
    # Then
    assert "header ['time', 'value', 'label']" in _message(excinfo)
    for fragment in fragments:
        assert fragment in _message(excinfo)


def test_csv_changed_cell_and_row_count__tc_assert_bv_005(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-005 (data): a changed cell names row and column; row counts are compared."""
    # When
    with pytest.raises(AssertionError) as changed:
        run.assert_csv_rows(
            "structured/result.csv",
            [{"time": "0", "value": "1", "label": "a"}, {"time": "1", "value": "2.5", "label": "b"}],
        )
    with pytest.raises(AssertionError) as count:
        run.assert_csv_rows("structured/result.csv", [{"time": "0", "value": "1.0", "label": "a"}])
    # Then
    assert "row 1, column 'value': expected '1', got '1.0'" in _message(changed)
    assert "expected 1 data row(s), got 2" in _message(count)


@pytest.mark.parametrize(
    ("call", "error", "fragment"),
    [
        pytest.param(lambda r: r.assert_csv_columns("structured/result.csv", "time"), TypeError, "iterable of strings", id="bare-string-columns"),
        pytest.param(lambda r: r.assert_csv_columns("structured/result.csv", [1]), TypeError, "entries must be strings", id="non-str-column"),
        pytest.param(lambda r: r.assert_csv_rows("structured/result.csv", [{"time": 0}]), TypeError, "pass a str", id="non-str-cell"),
        pytest.param(lambda r: r.assert_csv_rows("structured/result.csv", [("0", "1.0")]), TypeError, "must be a mapping", id="row-not-mapping"),
        pytest.param(lambda r: r.assert_tree("result.csv", root="structured"), TypeError, "iterable of relative paths", id="bare-string-tree"),
    ],
)
def test_assertion_arguments_are_validated__tc_assert_bv_005(run: RdeTestResult, call: object, error: type[Exception], fragment: str) -> None:
    """TC-ASSERT-BV-005 (arguments): a mistyped expectation is a usage error, not a silent pass."""
    # When / Then
    with pytest.raises(error, match=fragment):
        call(run)  # type: ignore[operator]


def test_tree_lists_missing_and_extra__tc_assert_bv_006(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-006: the tree diff lists both directions."""
    # When
    with pytest.raises(AssertionError) as excinfo:
        run.assert_tree({"result.csv", "peaks.csv"}, root="structured")
    # Then
    message = _message(excinfo)
    assert "file tree below 'structured' differs" in message
    assert "missing:\n  peaks.csv" in message
    assert "unexpected:\n  result.json" in message


def test_tree_of_missing_directory_lists_everything_missing__tc_assert_bv_006(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-006: a directory that does not exist has no files."""
    # When / Then
    with pytest.raises(AssertionError, match="missing:\n  a.csv"):
        run.assert_tree({"a.csv"}, root="divided")


@pytest.mark.parametrize("name", ["/etc/passwd", "../outside.json", "structured/../../x.json", "C:\\x.json"])
def test_traversal_is_refused__tc_assert_bv_007(run: RdeTestResult, name: str) -> None:
    """TC-ASSERT-BV-007: every helper resolves through the validated artifact path."""
    # When / Then
    for call in (run.read_json, run.assert_artifact, lambda n: run.assert_json_subset(n, {}), lambda n: run.assert_tree([], root=n)):
        with pytest.raises(ValueError, match="data root"):
            call(name)


def test_read_limit__tc_assert_bv_008(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-008: a payload above the limit is refused unless the limit is raised."""
    # When / Then
    with pytest.raises(AssertionError, match=r"is 33 bytes, above the read limit of 10 bytes"):
        run.read_bytes("structured/result.csv", max_bytes=10)
    with pytest.raises(AssertionError, match="read limit"):
        run.read_csv("structured/result.csv", max_bytes=10)
    assert run.read_bytes("structured/result.csv", max_bytes=None) == _RESULT_CSV
    assert assertions.DEFAULT_MAX_BYTES == 16 * 1024 * 1024


def _write(run: RdeTestResult, name: str, content: object) -> None:
    path = run.artifact_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")


def test_metadata_failures__tc_assert_bv_009(scratch: RdeTestResult) -> None:
    """TC-ASSERT-BV-009: invalid structure, undefined keys and a missing definition fail."""
    # Given: extra metadata documents in the retained run
    run = scratch
    _write(run, "meta/invalid.json", {"constant": {"temperature": {"unit": "K"}}})
    _write(run, "meta/undefined.json", {"constant": {"humidity": {"value": 3}}, "variable": [{"temperature": {"value": 1}}]})
    # When / Then
    with pytest.raises(AssertionError, match="metadata artifact 'meta/invalid.json' is invalid"):
        run.assert_metadata_valid("meta/invalid.json")
    with pytest.raises(AssertionError, match=r"uses key\(s\) not defined in 'tasksupport/metadata-def.json': \['humidity'\]"):
        run.assert_metadata_valid("meta/undefined.json")
    with pytest.raises(AssertionError, match="'tasksupport/none.json' is missing"):
        run.assert_metadata_valid(definition="tasksupport/none.json")
    with pytest.raises(AssertionError, match="'meta/absent.json' is missing"):
        run.assert_metadata_valid("meta/absent.json")


def test_metadata_keys_of_non_object_document() -> None:
    """A metadata document that is not an object defines no keys."""
    # When / Then
    assert assertions._metadata_keys([1]) == set()
    assert assertions._metadata_keys({"constant": None, "variable": ["x", {"a": {}}]}) == {"a"}


def test_invoice_schema_violation__tc_assert_bv_010(scratch: RdeTestResult) -> None:
    """TC-ASSERT-BV-010: an invoice that breaks the schema is an assertion failure."""
    # Given: an invoice without the required basic block
    run = scratch
    _write(run, "invoice/broken.json", {"datasetId": "x", "custom": {"temperature": 300}})
    # When / Then
    with pytest.raises(AssertionError, match="invoice artifact 'invoice/broken.json' does not validate against 'tasksupport/invoice.schema.json'"):
        run.assert_invoice_valid("invoice/broken.json")


def test_messages_point_at_the_retained_run__tc_assert_bv_011(run: RdeTestResult) -> None:
    """TC-ASSERT-BV-011: every artifact failure ends with the data root and run report."""
    # When
    with pytest.raises(AssertionError) as excinfo:
        run.assert_csv_columns("structured/result.csv", {"intensity"})
    # Then
    tail = _message(excinfo).splitlines()[-2:]
    assert tail == [f"data root: {run.data_root}", f"run report: {run.report_path}"]


def test_unreadable_artifacts__tc_assert_bv_012(scratch: RdeTestResult) -> None:
    """TC-ASSERT-BV-012: malformed JSON, undecodable text and directories fail readably."""
    # Given
    run = scratch
    _write(run, "structured/bad.json", "{not json")
    run.artifact_path("structured/bad.txt").write_bytes(b"\xff\xfe")
    # When / Then
    with pytest.raises(AssertionError, match="'structured/bad.json' is not valid JSON"):
        run.read_json("structured/bad.json")
    with pytest.raises(AssertionError, match="'structured/bad.txt' is not valid utf-8 text"):
        run.read_text("structured/bad.txt")
    with pytest.raises(AssertionError, match="'structured' is a directory, not a file"):
        run.read_json("structured")
    with pytest.raises(AssertionError, match="'structured/none.csv' is missing"):
        list(run.iter_csv("structured/none.csv"))
