"""QA-04 (#739): the GA benchmark's record, its release-gate comparison and the committed baseline.

``scripts/bench_ga.py`` is the separately runnable, reproducible benchmark; the
GA benchmark workflow runs it against a clean wheel and fails on a regression.
These tests pin the gate logic with hand-built results (so no timing is
involved), run a small subset of the real cases end to end, and keep the
committed baseline in step with the case list.

EP table:

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-739-GATE-001 | result equals its own baseline | baseline_from(result) | every row ok |
| TC-739-GATE-002 | exact metric differs | images 4 -> 5 | regression on images only |
| TC-739-GATE-003 | case set differs | baseline case absent / new case | missing / unbaselined |
| TC-739-GATE-004 | figure ownership | figures_open 1 / live_figures_after_collect 2 / both 0 | two violations / none |
| TC-739-GATE-005 | real run, quick subset | four cases, --baseline of itself | exit 0; environment, data sizes, commands, results recorded |
| TC-739-GATE-006 | real run, tampered baseline | images changed | exit 1, row names the metric |
| TC-739-GATE-007 | unknown case name | --cases nope | exit 2 |
| TC-739-GATE-008 | committed baseline | scripts/bench_ga_baseline.json | covers exactly the full profile; no figure left; provenance recorded |
| TC-739-GATE-009 | earlier repetitions fail, the last succeeds | run: failed / partial then success | repetitions 0 and 1 are work violations; exit 1 |
| TC-739-GATE-010 | truncated parse | StandardReader returns a 1 x 1 frame | every repetition a work violation; parsed rows and columns regress against the baseline |
| TC-739-GATE-011 | earlier plan / render incomplete | plan: 1 tile; render: 1 series instead of 3 | the incomplete repetition is a work violation; exit 1 |

BV table:

| TC | Boundary | Expected |
|----|----------|----------|
| TC-739-GATE-BV-001 | normalized_seconds at 2.0x / just above | ok / regression |
| TC-739-GATE-BV-002 | peak RSS delta at 1.5x + 64 MiB / just above | ok / regression |
| TC-739-GATE-BV-003 | negative RSS-growth baseline, current at the slack / above | ok / regression |
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "bench_ga.py"
BASELINE = ROOT / "scripts" / "bench_ga_baseline.json"


def _load_bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_ga", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bench = _load_bench()


def _result() -> dict[str, Any]:
    return {
        "profile": "full",
        "environment": {"hardware": {"cpu_count": 1}},
        "calibration_seconds": 0.05,
        "cases": {
            "render_both_3": {
                "normalized_seconds": 10.0, "peak_rss_delta_mib": 100.0, "images": 4,
                "manifest_sha256": "abc", "figures_open": 0, "live_figures_after_collect": 0, "live_figures_max": 2,
            },
            "run_smarttable_5": {"normalized_seconds": 4.0, "peak_rss_delta_mib": 10.0, "status": "success", "iterations": 5},
        },
    }


def _verdicts(rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    return {(row["case"], row["metric"]): row["verdict"] for row in rows}


def test_result_matches_its_own_baseline__tc_739_gate_001() -> None:
    """TC-739-GATE-001: a result compared with the baseline it establishes passes every row."""
    result = _result()
    rows = bench.compare(result, bench.baseline_from(result))
    assert rows
    assert {row["verdict"] for row in rows} == {"ok"}
    # And: the exact metrics and every thresholded metric of each case are checked
    assert {metric for (case, metric) in _verdicts(rows) if case == "render_both_3"} == {
        "images", "manifest_sha256", "figures_open", "live_figures_after_collect",
        "normalized_seconds", "peak_rss_delta_mib", "live_figures_max",
    }


def test_exact_metric_change_is_a_regression__tc_739_gate_002() -> None:
    """TC-739-GATE-002: one more image than the baseline fails that metric and nothing else."""
    result = _result()
    baseline = bench.baseline_from(result)
    result["cases"]["render_both_3"]["images"] = 5
    verdicts = _verdicts(bench.compare(result, baseline))
    assert verdicts[("render_both_3", "images")] == "regression"
    assert [key for key, verdict in verdicts.items() if verdict != "ok"] == [("render_both_3", "images")]


def test_case_set_changes_are_reported__tc_739_gate_003() -> None:
    """TC-739-GATE-003: a dropped case is missing (fails); a new case is unbaselined (reported)."""
    result = _result()
    baseline = bench.baseline_from(result)
    del result["cases"]["run_smarttable_5"]
    result["cases"]["render_overlay_7"] = {"normalized_seconds": 1.0}
    verdicts = _verdicts(bench.compare(result, baseline))
    assert verdicts[("run_smarttable_5", "*")] == "missing"
    assert verdicts[("render_overlay_7", "*")] == "unbaselined"


@pytest.mark.parametrize(
    ("factor", "verdict"),
    [(2.0, "ok"), (2.0001, "regression")],
    ids=["at-limit", "above-limit"],
)
def test_normalized_time_threshold__tc_739_gate_bv_001(factor: float, verdict: str) -> None:
    """TC-739-GATE-BV-001: normalized time may double; anything slower fails."""
    result = _result()
    baseline = bench.baseline_from(result)
    result["cases"]["run_smarttable_5"]["normalized_seconds"] = 4.0 * factor
    assert _verdicts(bench.compare(result, baseline))[("run_smarttable_5", "normalized_seconds")] == verdict


@pytest.mark.parametrize(("current", "verdict"), [(214.0, "ok"), (214.01, "regression")], ids=["at-limit", "above-limit"])
def test_peak_rss_threshold__tc_739_gate_bv_002(current: float, verdict: str) -> None:
    """TC-739-GATE-BV-002: peak RSS delta may reach 1.5 x baseline + 64 MiB."""
    result = _result()
    baseline = bench.baseline_from(result)
    result["cases"]["render_both_3"]["peak_rss_delta_mib"] = current
    assert _verdicts(bench.compare(result, baseline))[("render_both_3", "peak_rss_delta_mib")] == verdict


@pytest.mark.parametrize(("current", "verdict"), [(32.0, "ok"), (32.01, "regression")], ids=["at-slack", "above-slack"])
def test_negative_baseline_keeps_the_slack__tc_739_gate_bv_003(current: float, verdict: str) -> None:
    """TC-739-GATE-BV-003: a baseline that returned memory (-14 MiB) still allows the 32 MiB slack."""
    result = _result()
    result["cases"]["render_both_3"]["rss_growth_mib"] = -14.0
    baseline = bench.baseline_from(result)
    result["cases"]["render_both_3"]["rss_growth_mib"] = current
    assert _verdicts(bench.compare(result, baseline))[("render_both_3", "rss_growth_mib")] == verdict


def test_figure_ownership_violations__tc_739_gate_004() -> None:
    """TC-739-GATE-004: any open or surviving figure is a violation, without a baseline."""
    cases = {
        "a": {"figures_open": 1, "live_figures_after_collect": 2},
        "b": {"figures_open": 0, "live_figures_after_collect": 0},
        "c": {"normalized_seconds": 1.0},
    }
    assert bench.figure_violations(cases) == [
        "a: figures_open = 1 (must be 0)",
        "a: live_figures_after_collect = 2 (must be 0)",
    ]


def _gate(case_metrics: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    result = {"cases": {"case": case_metrics}}
    return bench._apply_gate(result, None), result  # noqa: SLF001


def _failing_first(original: Any, broken: Any, failures: int) -> Any:
    calls = [0]

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        calls[0] += 1
        return broken(*args, **kwargs) if calls[0] <= failures else original(*args, **kwargs)

    return wrapper


@pytest.mark.slow
def test_every_run_repetition_is_validated__tc_739_gate_009(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-739-GATE-009: a failed and a partial repetition fail the gate even when the last run succeeds."""
    from rdetoolkit.runner.lifecycle import Runner  # noqa: PLC0415

    reports = iter([SimpleNamespace(status="failed", iterations=[]), SimpleNamespace(status="partial", iterations=[None] * 2)])
    monkeypatch.setattr(Runner, "run", _failing_first(Runner.run, lambda *_args, **_kwargs: next(reports), 2))
    metrics = bench.run_case_inline("run", {"mode": "smarttable", "tiles": 5}, 3)
    # The last repetition alone looks like a clean run
    assert (metrics["status"], metrics["iterations"]) == ("success", 5)
    assert metrics["work_violations"] == [
        "repetition 0: status = 'failed', expected 'success'",
        "repetition 0: iterations = 0, expected 5",
        "repetition 1: status = 'partial', expected 'success'",
        "repetition 1: iterations = 2, expected 5",
    ]
    exit_code, result = _gate(metrics)
    assert exit_code == 1
    assert result["work_violations"][0] == "case: repetition 0: status = 'failed', expected 'success'"


@pytest.mark.slow
def test_truncated_parse_fails_the_gate__tc_739_gate_010(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-739-GATE-010: a reader returning a 1 x 1 frame is caught per repetition and against the baseline."""
    from rdetoolkit.graph.readers.builtin import StandardReader  # noqa: PLC0415

    original = StandardReader.read
    monkeypatch.setattr(StandardReader, "read", lambda self, path: SimpleNamespace(frame=original(self, path).frame.iloc[:1, :1]))
    metrics = bench.run_case_inline("csv_parse", {"series": 1000, "rows": 200}, 2)
    assert metrics["status"] == "standard"
    assert metrics["work_violations"] == [
        "repetition 0: shape = (1, 1), expected (200, 1001)",
        "repetition 1: shape = (1, 1), expected (200, 1001)",
    ]
    assert _gate(metrics)[0] == 1
    # And: the parsed dimensions are exact metrics of the committed baseline
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    rows = bench.compare({"cases": {"csv_parse_columns": metrics}}, {"cases": {"csv_parse_columns": baseline["cases"]["csv_parse_columns"]}})
    assert {(row["metric"], row["current"]) for row in rows if row["verdict"] == "regression"} == {("parsed_rows", 1), ("parsed_columns", 1)}


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["plan", "render"])
def test_incomplete_plan_or_render_repetition_fails__tc_739_gate_011(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """TC-739-GATE-011: an incomplete first plan or render is a work violation although the last is complete."""
    if kind == "plan":
        from rdetoolkit.runner import preview  # noqa: PLC0415

        original = preview.preview_registration

        def one_tile(root: Path, **kwargs: Any) -> Any:
            full = original(root, **kwargs)
            return SimpleNamespace(tiles=full.tiles[:1], decision=full.decision)

        monkeypatch.setattr(preview, "preview_registration", _failing_first(original, one_tile, 1))
        metrics = bench.run_case_inline("plan", {"mode": "smarttable", "tiles": 5}, 2)
        assert metrics["tiles"] == 5
        assert metrics["work_violations"] == ["repetition 0: tiles = 1, expected 5"]
    else:
        from rdetoolkit.graph import engine  # noqa: PLC0415

        original = engine.render_graph
        one_series = _failing_first(original, lambda frame, spec, **kwargs: original(frame.iloc[:, :2], spec, **kwargs), 1)
        monkeypatch.setattr(engine, "render_graph", one_series)
        metrics = bench.run_case_inline("render", {"series": 3, "layout": "both"}, 2)
        assert metrics["images"] == 4
        assert metrics["work_violations"][0] == "repetition 0: images = 2, expected 4"
    assert _gate(metrics)[0] == 1


_QUICK_SUBSET = "render_both_3,csv_parse_rows,plan_smarttable_5,run_smarttable_5"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--profile", "quick", "--repeat", "1", *args],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )


@pytest.fixture(scope="module")
def quick_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run the quick subset once, writing the result and the baseline it establishes."""
    work = tmp_path_factory.mktemp("bench")
    output, baseline = work / "result.json", work / "baseline.json"
    completed = _run_script("--cases", _QUICK_SUBSET, "--output", str(output), "--write-baseline", str(baseline))
    return completed, output, baseline


@pytest.mark.slow
def test_quick_run_records_everything_the_gate_needs__tc_739_gate_005(
    quick_run: tuple[subprocess.CompletedProcess[str], Path, Path],
) -> None:
    """TC-739-GATE-005: hardware, Python, dependencies, data sizes, commands and results are recorded."""
    completed, output, baseline = quick_run
    assert completed.returncode == 0, completed.stderr[-2000:]
    result = json.loads(output.read_text(encoding="utf-8"))
    environment = result["environment"]
    assert environment["hardware"]["cpu_count"] >= 1
    assert environment["python"]["version"].count(".") == 2
    assert environment["dependencies"]["matplotlib"]
    assert environment["dependencies"]["rdetoolkit"]
    assert environment["command"][1].endswith("bench_ga.py")
    assert result["calibration_seconds"] > 0
    assert result["figure_violations"] == []
    assert result["work_violations"] == []
    assert sorted(result["cases"]) == sorted(_QUICK_SUBSET.split(","))
    for case in result["cases"].values():
        assert case["data"]
        assert case["command"][0].endswith("bench_ga.py")
        assert case["seconds"]["median"] > 0
        assert case["normalized_seconds"] > 0
    render = result["cases"]["render_both_3"]
    assert (render["images"], render["figures_open"], render["live_figures_after_collect"]) == (4, 0, 0)
    assert (result["cases"]["run_smarttable_5"]["status"], result["cases"]["run_smarttable_5"]["iterations"]) == ("success", 5)
    assert result["cases"]["plan_smarttable_5"]["tiles"] == 5
    csv_rows = result["cases"]["csv_parse_rows"]
    assert (csv_rows["parsed_rows"], csv_rows["parsed_columns"]) == (1000, 11)
    # And: the run passes the gate against the baseline it established
    again = _run_script("--cases", _QUICK_SUBSET, "--baseline", str(baseline))
    assert again.returncode == 0, again.stderr[-2000:]


@pytest.mark.slow
def test_tampered_baseline_fails_the_gate__tc_739_gate_006(
    quick_run: tuple[subprocess.CompletedProcess[str], Path, Path], tmp_path: Path,
) -> None:
    """TC-739-GATE-006: an image-count change against the baseline exits 1 and names the metric."""
    _, _, baseline = quick_run
    tampered = json.loads(baseline.read_text(encoding="utf-8"))
    tampered["cases"]["render_both_3"]["images"] = 5
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    completed = _run_script("--cases", "render_both_3", "--baseline", str(path))
    assert completed.returncode == 1
    rows = json.loads(completed.stdout)["comparison"]
    assert [(row["metric"], row["baseline"], row["current"]) for row in rows if row["verdict"] == "regression"] == [("images", 5, 4)]


def test_unknown_case_is_rejected__tc_739_gate_007() -> None:
    """TC-739-GATE-007: a case name outside the profile is a usage error."""
    completed = _run_script("--cases", "nope")
    assert completed.returncode == 2
    assert "nope" in completed.stderr


def test_committed_baseline_covers_the_full_profile__tc_739_gate_008() -> None:
    """TC-739-GATE-008: the committed baseline gates exactly the full profile's cases."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    names = [case.name for case in bench._profile_cases("full")]  # noqa: SLF001
    assert baseline["profile"] == "full"
    assert sorted(baseline["cases"]) == sorted(names)
    assert baseline["thresholds"] == bench.DEFAULT_THRESHOLDS
    # And: where and how it was established is recorded
    established = baseline["established_on"]
    assert established["hardware"]["cpu_count"]
    assert established["python"]["version"]
    assert established["dependencies"]["matplotlib"]
    assert established["git_revision"]
    # And: the baseline itself satisfies the absolute figure invariants
    assert bench.figure_violations(baseline["cases"]) == []
    for name in names:
        case = baseline["cases"][name]
        assert case["normalized_seconds"] > 0
        if name.startswith("render_"):
            assert (case["figures_open"], case["live_figures_after_collect"]) == (0, 0)
        if name.startswith("run_"):
            assert case["status"] == "success"
            assert case["iterations"] == int(name.rsplit("_", 1)[1])
        if name.startswith("plan_"):
            assert case["tiles"] == int(name.rsplit("_", 1)[1])
    for case in bench._profile_cases("full"):  # noqa: SLF001
        if case.kind == "csv_parse":
            expected = baseline["cases"][case.name]
            assert (expected["parsed_rows"], expected["parsed_columns"]) == (case.params["rows"], case.params["series"] + 1)
