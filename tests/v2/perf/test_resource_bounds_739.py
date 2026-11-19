"""QA-04 (#739): bounded rendering resources and 100-tile failure, continue and interruption.

CI-fast smoke seats for the release gate. The reproducible measurements (time,
peak RSS, the 1000-series and 1000-tile sizes) live in ``scripts/bench_ga.py``;
these tests pin the properties that must hold on every machine:

* repeated renders retain nothing: after a collection, no ``Figure`` created by
  ``render_graph`` is still alive, pyplot tracks none, rcParams are unchanged
  and the traced Python heap does not grow with the number of repetitions;
* the artifact set is deterministic (manifest and file names) and its size is
  exactly figures x formats;
* a 100-row SmartTable run that renders a graph per tile keeps the
  ``continue`` / ``fail_fast`` contracts, and a SIGTERM inside tile 50 stops
  the run there and leaves no figure, rcParams change or data-root lock behind.

Inputs are synthetic (``tests/v2/perf/synthetic.py``); no real dataset is used.

EP table:

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-739-FIG-001 | written renders, repeated | 3 series, layout both, 10 runs | fignums and live figures back to the start after every run; rcParams unchanged |
| TC-739-FIG-002 | in-memory renders | ``output=None``, 10 runs | figures owned by the result; released once the result is dropped |
| TC-739-FIG-003 | failing export, repeated | 2nd export raises OSError, 10 runs | OSError each time; no figure left; rcParams unchanged |
| TC-739-MEM-001 | traced heap | 3 warm-up + 10 measured overlay renders | growth below 2 MiB (no per-render retention) |
| TC-739-ART-001 | determinism | same request into two directories | identical manifest JSON and file names; images == figures x formats |
| TC-739-TILE-001 | 100 rows, continue | every row with index % 10 == 3 fails | partial; exact status list; warning 3001 x10; no job.failed; 100 tiles |
| TC-739-TILE-002 | 100 rows, fail_fast | same | failed at index 3; four iterations; job.failed; no tile after 3 |
| TC-739-TILE-003 | 100 rows, SIGTERM in tile 50 | continue policy | 3004; job.failed; no tile after 50 started; events end failed; lock free; no figure left |

BV table:

| TC | Boundary | Expected |
|----|----------|----------|
| TC-739-BV-001 | 1 / 10 / 100 / 1000 Y-series, overlay | one image each; no figure left |
| TC-739-BV-002 | repetition count 1 vs 10 | live figures after collect identical (no growth with N) |
"""

from __future__ import annotations

import gc
import json
import os
import signal
import tracemalloc
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.graph.engine import render_graph
from rdetoolkit.graph.outputs import DirectorySink, OutputContextSink
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.spec import GraphSpec, OutputSpec
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.root_lock import DataRootLock
from rdetoolkit.types import IterationInfo, OutputContext
from tests.v2.perf import synthetic

_DPI = 30
_BOTH = GraphSpec(layout="both", unit_policy="allow")
_OVERLAY = GraphSpec(layout="overlay", unit_policy="allow")
_ROWS = 100
_FAILING_INDEX_DIGIT = 3
_INTERRUPTED_TILE = 50
_HEAP_GROWTH_LIMIT = 2 * 1024 * 1024


@pytest.fixture
def figure_baseline() -> Iterator[tuple[int, list[int], dict[str, Any]]]:
    """Return the live-figure count, pyplot figure numbers and rcParams before the test."""
    gc.collect()
    yield synthetic.live_figures(), plt.get_fignums(), dict(mpl.rcParams)


def _collected_live_figures() -> int:
    gc.collect()
    return synthetic.live_figures()


def _render_to(directory: Path, spec: GraphSpec = _BOTH, series: int = 3, formats: tuple[str, ...] = ("png",)) -> Any:
    sink = DirectorySink(directory / "other", main_image_dir=directory / "main")
    return render_graph(synthetic.wide_frame(series, 20), spec, output=OutputSpec(sink, formats=formats, dpi=_DPI))


def test_repeated_written_renders_release_every_figure__tc_739_fig_001(
    tmp_path: Path, figure_baseline: tuple[int, list[int], dict[str, Any]],
) -> None:
    """TC-739-FIG-001 / BV-002: nothing a written render creates outlives it."""
    live_before, fignums_before, rc_before = figure_baseline
    for repetition in range(10):
        # When: the same request is rendered again into a fresh directory
        result = _render_to(tmp_path / f"run{repetition}")
        assert len(result.artifacts) == 4
        del result
        # Then: no figure is reachable, none is pyplot-registered, rcParams are untouched
        assert _collected_live_figures() == live_before, f"figure retained after repetition {repetition}"
        assert plt.get_fignums() == fignums_before
    assert dict(mpl.rcParams) == rc_before


def test_in_memory_figures_belong_to_the_result__tc_739_fig_002(
    figure_baseline: tuple[int, list[int], dict[str, Any]],
) -> None:
    """TC-739-FIG-002: ``output=None`` hands figures to the caller and nothing else keeps them."""
    live_before, fignums_before, rc_before = figure_baseline
    for _ in range(10):
        result = render_graph(synthetic.wide_frame(3, 20), _BOTH)
        # Then: the caller owns one figure per planned figure, outside pyplot
        assert _collected_live_figures() == live_before + len(result.artifacts) == live_before + 4
        assert plt.get_fignums() == fignums_before
        del result
        assert _collected_live_figures() == live_before
    assert dict(mpl.rcParams) == rc_before


def test_failing_export_leaves_no_figure__tc_739_fig_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    figure_baseline: tuple[int, list[int], dict[str, Any]],
) -> None:
    """TC-739-FIG-003: an export failure in the middle of a render never strands a figure."""
    live_before, fignums_before, rc_before = figure_baseline
    original = MatplotlibRenderer.export
    calls: list[int] = []

    def failing_export(self: MatplotlibRenderer, handle: Any, fmt: str, *, dpi: int) -> bytes:
        calls.append(1)
        if len(calls) % 2 == 0:
            msg = "disk full"
            raise OSError(msg)
        return original(self, handle, fmt, dpi=dpi)

    monkeypatch.setattr(MatplotlibRenderer, "export", failing_export)
    for repetition in range(10):
        with pytest.raises(OSError, match="disk full"):
            _render_to(tmp_path / f"run{repetition}")
        assert _collected_live_figures() == live_before
        assert plt.get_fignums() == fignums_before
    assert dict(mpl.rcParams) == rc_before
    # And: nothing was written, since exports happen before any write
    assert synthetic.file_manifest(tmp_path) == []


def test_traced_heap_does_not_grow_with_repetitions__tc_739_mem_001(tmp_path: Path) -> None:
    """TC-739-MEM-001: the Python heap after 10 more renders stays within 2 MiB of the warm state."""
    for repetition in range(3):
        _render_to(tmp_path / f"warm{repetition}", _OVERLAY, series=2)
    gc.collect()
    tracemalloc.start()
    try:
        warm, _ = tracemalloc.get_traced_memory()
        for repetition in range(10):
            _render_to(tmp_path / f"run{repetition}", _OVERLAY, series=2)
        gc.collect()
        after, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert after - warm < _HEAP_GROWTH_LIMIT, f"traced heap grew by {after - warm} bytes over 10 renders"


def test_artifact_manifest_is_deterministic__tc_739_art_001(tmp_path: Path) -> None:
    """TC-739-ART-001: two renders of one request agree on the manifest and on every file name."""
    formats = ("png", "svg")
    first = _render_to(tmp_path / "a", series=5, formats=formats)
    second = _render_to(tmp_path / "b", series=5, formats=formats)
    assert first.manifest_json() == second.manifest_json()
    names_a = [name for name, _ in synthetic.file_manifest(tmp_path / "a")]
    names_b = [name for name, _ in synthetic.file_manifest(tmp_path / "b")]
    assert names_a == names_b
    # And: exactly one image per planned figure and format (overlay + 5 individual)
    assert len(first.plan.figures) == 6
    assert len(names_a) == len(first.artifacts) == len(first.plan.figures) * len(formats)


@pytest.mark.parametrize("series", [1, 10, 100, 1000])
def test_series_count_boundaries_render_one_overlay__tc_739_bv_001(
    tmp_path: Path, series: int, figure_baseline: tuple[int, list[int], dict[str, Any]],
) -> None:
    """TC-739-BV-001: 1 to 1000 Y-series draw on one overlay figure and leave nothing behind."""
    live_before, fignums_before, rc_before = figure_baseline
    result = _render_to(tmp_path, _OVERLAY, series=series)
    assert [(artifact.figure_id, artifact.format) for artifact in result.artifacts] == [("overlay", "png")]
    assert len(result.plan.figures[0].series_ids) == series
    del result
    assert _collected_live_figures() == live_before
    assert plt.get_fignums() == fignums_before
    assert dict(mpl.rcParams) == rc_before


# --- 100-tile SmartTable runs ---------------------------------------------------------

_TILE_FRAME = synthetic.wide_frame(1, 20)


@node(id="tests.v2.perf.plot_tile")
def _plot_tile(out: OutputContext, index: int) -> None:
    # Every tenth tile renders, so the run mixes rendering and non-rendering tiles.
    if index % 10 == 0:
        render_graph(_TILE_FRAME, _OVERLAY, output=OutputSpec(OutputContextSink(out), dpi=_DPI))


@node(id="tests.v2.perf.check_tile")
def _check_tile(index: int) -> None:
    if index % 10 == _FAILING_INDEX_DIGIT:
        msg = f"row {index} rejected"
        raise ValueError(msg)
    if index == _INTERRUPTED_TILE and os.environ.get("RDETOOLKIT_739_INTERRUPT") == "1":
        os.kill(os.getpid(), signal.SIGTERM)


@flow(id="tests.v2.perf.tile_flow")
def _tile_flow(iteration: IterationInfo, out: OutputContext) -> None:
    _plot_tile(out, iteration.index)
    _check_tile(iteration.index)


@pytest.fixture
def sigterm_guard() -> Iterator[None]:
    """Keep a stray SIGTERM from killing pytest; the Runner installs its own handler while running."""
    previous = signal.signal(signal.SIGTERM, lambda _signum, _frame: None)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _events(root: Path) -> list[dict[str, Any]]:
    (events_path,) = (root / "logs").glob("events_*.jsonl")
    return [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]


def _started_tiles(events: list[dict[str, Any]]) -> list[int]:
    return [event["payload"]["iteration_index"] for event in events if event.get("name") == "iteration.started"]


def _tile_dirs(root: Path) -> list[str]:
    return sorted(path.name for path in (root / "divided").iterdir()) if (root / "divided").exists() else []


def test_hundred_rows_continue_policy_is_partial__tc_739_tile_001(
    tmp_path: Path, figure_baseline: tuple[int, list[int], dict[str, Any]],
) -> None:
    """TC-739-TILE-001: every tile runs; the ten rejected rows make the run partial."""
    live_before, fignums_before, rc_before = figure_baseline
    root = synthetic.smarttable_root(tmp_path / "project", _ROWS)
    report = Runner(root=root).run(_tile_flow, execution={"on_iteration_error": "continue"})
    expected = ["failed" if index % 10 == _FAILING_INDEX_DIGIT else "completed" for index in range(_ROWS)]
    assert report.status == "partial"
    assert [iteration["status"] for iteration in report.iterations] == expected
    assert [iteration["index"] for iteration in report.iterations] == list(range(_ROWS))
    assert report.warnings == [{"code": 3001, "message": "10 iteration(s) failed", "failed_count": 10}]
    assert not (root / "job.failed").exists()
    # And: tile 0 writes to the data root, tiles 1..99 to divided/
    assert _tile_dirs(root) == [f"{index:04d}" for index in range(1, _ROWS)]
    # And: the ten rendering tiles each wrote one main image
    assert len(list((root / "main_image").glob("*.png"))) == 1
    assert [len(list((root / "divided" / f"{index:04d}" / "main_image").glob("*.png"))) for index in range(10, _ROWS, 10)] == [1] * 9
    assert _collected_live_figures() == live_before
    assert plt.get_fignums() == fignums_before
    assert dict(mpl.rcParams) == rc_before


def test_hundred_rows_fail_fast_stops_at_the_first_failure__tc_739_tile_002(tmp_path: Path) -> None:
    """TC-739-TILE-002: fail_fast stops at row 3; no later tile is planned onto disk."""
    root = synthetic.smarttable_root(tmp_path / "project", _ROWS)
    report = Runner(root=root).run(_tile_flow, execution={"on_iteration_error": "fail_fast"})
    assert report.status == "failed"
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "completed", "completed", "failed"]
    assert report.error is not None
    assert report.error["code"] == 3001
    assert (root / "job.failed").exists()
    assert _started_tiles(_events(root)) == [0, 1, 2, 3]
    assert _tile_dirs(root) == ["0001", "0002", "0003"]


def test_hundred_rows_interruption_cleans_up__tc_739_tile_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sigterm_guard: None,
    figure_baseline: tuple[int, list[int], dict[str, Any]],
) -> None:
    """TC-739-TILE-003: SIGTERM in tile 50 ends the run there and releases every resource."""
    del sigterm_guard
    live_before, fignums_before, rc_before = figure_baseline
    monkeypatch.setenv("RDETOOLKIT_739_INTERRUPT", "1")
    root = synthetic.smarttable_root(tmp_path / "project", _ROWS)
    report = Runner(root=root).run(_tile_flow, execution={"on_iteration_error": "continue"})
    # Then: the run is failed as interrupted, with the v1 failure marker
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 3004
    assert (root / "job.failed").exists()
    # And: tiles 0..50 started, nothing after the interrupted tile did
    events = _events(root)
    assert _started_tiles(events) == list(range(_INTERRUPTED_TILE + 1))
    assert _tile_dirs(root) == [f"{index:04d}" for index in range(1, _INTERRUPTED_TILE + 1)]
    assert events[-1]["name"] == "run.completed"
    assert events[-1]["payload"] == {"status": "failed"}
    # And: the data-root lock is free and no rendering state is left behind
    lock = DataRootLock(root)
    assert lock.acquire()
    lock.release()
    assert _collected_live_figures() == live_before
    assert plt.get_fignums() == fignums_before
    assert dict(mpl.rcParams) == rc_before
