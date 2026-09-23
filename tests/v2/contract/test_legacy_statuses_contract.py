"""Phase H contract for ``RunReport.to_legacy_statuses()``.

EP table:

| RunReport mode | Frozen v1 oracle | Expected | Test ID |
|---|---|---|---|
| invoice | ``v1/invoice/ok.json`` | aggregator output converts to exact legacy JSON | TC-EP-G2-301 |
| excelinvoice | ``v1/excelinvoice/ok.json`` | exact legacy-return JSON | TC-EP-G2-302 |
| multidatatile | ``v1/multidatatile/ok.json`` | exact legacy-return JSON | TC-EP-G2-303 |
| smarttable | ``v1/smarttable/ok.json`` | exact legacy-return JSON | TC-EP-G2-304 |
| rdeformat | ``v1/rdeformat/ok.json`` | exact legacy-return JSON | TC-EP-G2-305 |
| each mode | ``usererr.json`` | total failed-run conversion | TC-EP-GR2-306..310 |
| each mode | ``valerr.json`` | total failed-run conversion | TC-EP-GR2-311..315 |
| ``Runner.run`` | two tiles, run UUID | each status uses its zero-padded tile index | TC-EP-HR2-AE-001 |

BV table:

| Boundary | Expected | Covered by |
|---|---|---|
| one status | full single-item ``statuses`` list | invoice cell |
| multiple statuses | order and every field preserved | other four cells |
| null v1 error return | v2 defines one structural failed status | ten error seats |
| two statuses | run UUID never leaks into either status | TC-BV-HR2-AE-001 |
"""

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest


_EXPECTED_ROOT = Path(__file__).parent / "fixtures" / "expected" / "v1"


def _iteration_titles(observed: dict[str, Any]) -> list[str]:
    """Derive iteration-ordered titles from independently frozen invoices."""
    invoices = observed["invoices"]

    def _iteration_index(path: str) -> int:
        parts = Path(path).parts
        return int(parts[2]) if parts[:2] == ("data", "divided") else 0

    ordered = sorted(invoices.items(), key=lambda item: _iteration_index(item[0]))
    return [str(invoice["basic"]["dataName"]) for _, invoice in ordered]


def _iteration_targets(mode: str, observed: dict[str, Any], count: int) -> list[str]:
    """Derive v1 basedirs from the independently frozen output inventory."""
    files = [Path(path) for path in observed["output_tree"]["files"]]
    if mode in {"invoice", "multidatatile"}:
        parent = next(path.parent for path in files if path.parts[:2] == ("data", "inputdata"))
        return [parent.as_posix()] * count
    if mode in {"excelinvoice", "smarttable"}:
        parent = next(path.parent for path in files if path.parts[:2] == ("data", "temp") and len(path.parts) == 3)
        return [parent.as_posix()] * count
    return [f"data/temp/{index:04d}/<TILE_SUBDIR>" for index in range(count)]


@pytest.mark.parametrize(
    "mode,test_id",
    [
        pytest.param("invoice", "TC-EP-G2-301", id="invoice"),
        pytest.param("excelinvoice", "TC-EP-G2-302", id="excelinvoice"),
        pytest.param("multidatatile", "TC-EP-G2-303", id="multidatatile"),
        pytest.param("smarttable", "TC-EP-G2-304", id="smarttable"),
        pytest.param("rdeformat", "TC-EP-G2-305", id="rdeformat"),
    ],
)
def test_to_legacy_statuses_matches_frozen_v1_ok_payload(
    mode: str,
    test_id: str,
    tmp_path: Path,
) -> None:
    """TC-EP-G2-301..305: Each mode matches its frozen v1 return JSON."""
    from rdetoolkit.runner.aggregator import RunAggregator
    from rdetoolkit.runner.execute import ExecutionResult

    # Given: the G1-frozen v1 return and a RunReport for that same scenario
    fixture: dict[str, Any] = json.loads(
        (_EXPECTED_ROOT / mode / "ok.json").read_text(encoding="utf-8"),
    )
    observed = fixture["observed"]
    expected = fixture["observed"]["legacy_return"]
    titles = _iteration_titles(observed)
    targets = _iteration_targets(mode, observed, len(titles))
    aggregator = RunAggregator(
        run_id="run-uuid-abc",
        flow_id="legacy:custom_dataset_function",
        mode=mode,
        config_digest="sha256:<NORMALIZED>",
        logs_dir=tmp_path / "logs",
    )
    for index, (title, target) in enumerate(zip(titles, targets, strict=True)):
        aggregator.record(
            ExecutionResult(
                iteration_index=index,
                status="completed",
                call_records=(),
                outputs=(),
                datatile_id=f"tile-{index}",
                title=title,
                target=target,
                stacktrace="<TRACEBACK>",
            ),
        )
    report = aggregator.build_report(
        status="success",
        started_at="<DATE>",
        duration_ms=0.0,
    )

    # When: requesting the explicit legacy compatibility representation
    actual_json = report.to_legacy_statuses()

    # Then: it is a JSON string matching every frozen field and value
    assert test_id.startswith("TC-EP-G2-3")
    assert isinstance(actual_json, str)
    assert json.loads(actual_json) == expected


@pytest.mark.parametrize(
    ("mode", "outcome", "test_id"),
    [
        pytest.param(mode, outcome, f"TC-EP-GR2-{306 + index}", id=f"{mode}-{outcome}")
        for index, (mode, outcome) in enumerate(
            (mode, outcome)
            for outcome in ("usererr", "valerr")
            for mode in ("invoice", "excelinvoice", "multidatatile", "smarttable", "rdeformat")
        )
    ],
)
def test_to_legacy_statuses_matches_frozen_v1_error_payload(
    mode: str,
    outcome: str,
    test_id: str,
    tmp_path: Path,
) -> None:
    """TC-EP-GR2-306..315: Error seats follow each frozen v1 return contract."""
    # Given: the frozen v1 error result for one mode/outcome seat
    fixture: dict[str, Any] = json.loads(
        (_EXPECTED_ROOT / mode / f"{outcome}.json").read_text(encoding="utf-8"),
    )
    observed = fixture["observed"]
    expected = observed["legacy_return"]
    from rdetoolkit.runner.aggregator import RunAggregator
    from rdetoolkit.runner.execute import ExecutionResult

    ok_fixture: dict[str, Any] = json.loads(
        (_EXPECTED_ROOT / mode / "ok.json").read_text(encoding="utf-8"),
    )
    ok_observed = ok_fixture["observed"]
    reference_status = ok_observed["legacy_return"]["statuses"][0]
    title = _iteration_titles(ok_observed)[0]
    target = _iteration_targets(mode, ok_observed, 1)[0]
    job_failed_text = observed["job_failed_text"]
    code_line, message_text = job_failed_text.split("\n", maxsplit=1)
    error = {
        "code": int(code_line.removeprefix("ErrorCode=")),
        "message": message_text.removeprefix("ErrorMessage=").rstrip("\n"),
    }
    aggregator = RunAggregator(
        run_id="run-uuid-abc",
        flow_id="legacy:custom_dataset_function",
        mode=mode,
        config_digest="sha256:<NORMALIZED>",
        logs_dir=tmp_path / "logs",
    )
    aggregator.record(
        ExecutionResult(
            iteration_index=0,
            status="failed",
            call_records=(),
            outputs=(),
            error=error,
            datatile_id="failed-tile",
            title=title,
            target=target,
            stacktrace="<TRACEBACK>",
        ),
    )
    report = aggregator.build_report(
        status="failed",
        started_at="<DATE>",
        duration_ms=0.0,
        error=error,
    )

    # When: converting the future unified failed report to the legacy shape
    actual_json = report.to_legacy_statuses()

    # Then: non-null v1 returns match exactly, while formerly unobservable
    # failed returns preserve the frozen field shape and job.failed values
    assert test_id.startswith("TC-EP-GR2-3")
    assert isinstance(actual_json, str)
    actual = json.loads(actual_json)
    if expected is not None:
        assert actual == expected
        return
    actual_statuses = actual["statuses"]
    assert len(actual_statuses) == len(report.iterations)
    assert set(actual_statuses[0]) == set(reference_status)
    assert actual_statuses[0]["error_code"] == error["code"]
    assert actual_statuses[0]["error_message"] == error["message"]
    assert actual_statuses[0]["run_id"] == "0000"
    assert actual_statuses[0]["run_id"] != report.run_id


def test_runner_run_legacy_statuses_use_tile_indexes_not_run_uuid__tc_ep_hr2_ae_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP/BV-HR2-AE-001: production Runner keeps tile and run identities distinct."""
    from rdetoolkit.report.run_report import RunReport
    from rdetoolkit.runner.lifecycle import Runner
    from rdetoolkit.runner.mode_resolver import ModeKind
    from rdetoolkit.runner.paths import resolve_tile_paths
    from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
    from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig

    data_root = tmp_path / "data"
    inputdata = data_root / "inputdata"
    inputdata.mkdir(parents=True)

    class TwoTilePlanner:
        """Provide two explicit tiles while retaining Runner's production execution path."""

        def create(
            self,
            request: Any,
            *,
            config: RdeConfig,
            mode: ModeKind,
            data_root: Path,
        ) -> ExecutionPlan:
            tiles: list[TilePlan] = []
            for index in range(2):
                raw = inputdata / f"tile-{index}.txt"
                raw.write_text(str(index), encoding="utf-8")
                resource_paths = resolve_tile_paths(data_root, index)
                for field in fields(resource_paths):
                    Path(getattr(resource_paths, field.name)).mkdir(parents=True, exist_ok=True)
                tiles.append(
                    TilePlan(
                        iteration=IterationInfo(index=index, total=2, mode=mode.value),
                        paths=InputPaths(
                            inputdata=inputdata,
                            invoice=data_root / "invoice",
                            tasksupport=data_root / "tasksupport",
                            raw=raw,
                            rawfiles=(raw,),
                        ),
                        out=OutputContext.from_resource_paths(resource_paths),
                        invoice=None,
                    ),
                )
            return ExecutionPlan(
                run_id="run-uuid-abc",
                target=request.target,
                mode=mode,
                config=config,
                root=request.root,
                error_policy="continue",
                tiles=tuple(tiles),
                data_root=data_root,
                invoice_source=data_root / "invoice" / "invoice.json",
            )

    # Given: a real Runner with a fixed run UUID and a production two-tile plan
    runner = Runner(
        root=tmp_path,
        planner=TwoTilePlanner(),  # type: ignore[arg-type]
        run_id_factory=lambda: "run-uuid-abc",
    )
    monkeypatch.setattr(runner, "load_config", lambda source: RdeConfig())
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)
    monkeypatch.setattr(runner, "pre_validate", lambda config: None)
    monkeypatch.setattr(runner, "post_validate", lambda config, report: None)
    monkeypatch.setattr(runner, "finalize", lambda report, config: None)

    def flow(iteration: IterationInfo) -> None:
        assert iteration.total == 2

    # When: Runner.run executes both tiles and the report is converted
    report: RunReport = runner.run(flow)
    statuses = json.loads(report.to_legacy_statuses())["statuses"]

    # Then: each legacy identity is its decimal tile index, never the run UUID
    assert report.run_id == "run-uuid-abc"
    assert [status["run_id"] for status in statuses] == ["0000", "0001"]
    assert all(status["run_id"] != report.run_id for status in statuses)
