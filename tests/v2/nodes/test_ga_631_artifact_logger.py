"""GA631 EP/BV: ``artifact_logger`` streams a logger into a tile artifact file.

EP table
========

==============================  ==================================  ==================================  ============
Partition                       Input                               Expected                            Test ID
==============================  ==================================  ==================================  ============
records inside the block        info / debug lines                  lines in out.struct, v1 format      GA631-EP-1
block raises                    logger.exception, then re-raise     ERROR line written, handler gone    GA631-EP-2
logger shared by two tiles      same name, two OutputContexts       each file holds only its own tile   GA631-EP-3
existing file, mode             "a" / "w"                           appended / truncated                GA631-EP-4
output kind                     kind="logs"                         file under out.logs                 GA631-EP-5
threads in the process          4 workers x 50 records              every record written once           GA631-EP-6
call log                        call inside an active recorder      completed record, ArtifactLogger    GA631-EP-7
Runner run, MultiDataTile       logger shared by every tile         per-tile file, no duplicated lines  GA631-EP-8
two Runners run concurrently    same logger, overlapping blocks     each file holds only its own run    GA631-EP-9
forked worker process           Pool forked in tile 1, reused       no worker line in either file       GA631-EP-10
==============================  ==================================  ==================================  ============

BV table
========

==============================  ==================================  ==================================  ============
Boundary                        Input                               Expected                            Test ID
==============================  ==================================  ==================================  ============
level filter                    level=INFO, logger NOTSET           debug dropped, level restored       GA631-BV-1
nothing logged                  empty block                         no file created (v1 delay=True)     GA631-BV-2
invalid filename / kind / mode  "../x", "temp", "x"                 ValueError, nothing created         GA631-BV-3
re-entering an active block     nested ``with`` of the same object  RuntimeError, outer stays active    GA631-BV-4
logger name omitted             name=None                           filename without suffix             GA631-BV-5
overlapping blocks end unsorted A enters, B enters, A exits first     level held for B, then restored     GA631-BV-6
==============================  ==================================  ==================================  ============
"""

from __future__ import annotations

import logging
import multiprocessing
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.nodes import ArtifactLogger, artifact_logger
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import OutputContext
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree

_V1_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - \[(?P<name>[^\]]+)\]\((?P<level>[A-Z]+)\) - (?P<message>.*)$")


@pytest.fixture
def logger_name(request: pytest.FixtureRequest) -> str:
    """Give each test its own logger and leave no handler behind."""
    name = f"ga631.{request.node.name}"
    yield name  # type: ignore[misc]
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _messages(path: Path) -> list[str]:
    return [match.group("message") for match in map(_V1_LINE.match, _lines(path)) if match]


def test_records_inside_block_are_written_in_v1_format__ga631_ep_1(tmp_path: Path, logger_name: str) -> None:
    """GA631-EP-1: lines logged in the block land in out.struct with the v1 line format."""
    # Given: a tile output context and a logger without handlers
    out = make_output_context(tmp_path)
    logger = logging.getLogger(logger_name)
    handlers_before = list(logger.handlers)
    # When: logging inside and after the block
    with artifact_logger(out, "structured_log.txt", name=logger_name) as active:
        active.info("start")
        active.debug("detail")
    logger.info("after the block")
    # Then: both block records are written once, in v1's format, and the handler is gone
    path = out.struct / "structured_log.txt"
    lines = _lines(path)
    assert [_V1_LINE.match(line) is not None for line in lines] == [True, True]
    assert lines[0].endswith(f" - [{logger_name}](INFO) - start")
    assert lines[1].endswith(f" - [{logger_name}](DEBUG) - detail")
    assert active is logger
    assert logger.handlers == handlers_before


def test_error_line_is_written_when_block_raises__ga631_ep_2(tmp_path: Path, logger_name: str) -> None:
    """GA631-EP-2: an ERROR logged while handling the failure is in the file; the handler is removed."""
    # Given: a block whose processing fails
    out = make_output_context(tmp_path)
    logger = logging.getLogger(logger_name)
    # When: the template logs the exception and re-raises it
    message = "bad spectrum"
    with pytest.raises(ValueError, match=message), artifact_logger(out, "structured_log.txt", name=logger_name) as active:
        try:
            raise ValueError(message)
        except ValueError:
            active.exception("fitting failed")
            raise
    # Then: the ERROR line (with traceback) is in the artifact and no handler remains
    text = (out.struct / "structured_log.txt").read_text(encoding="utf-8")
    assert f"[{logger_name}](ERROR) - fitting failed" in text
    assert "ValueError: bad spectrum" in text
    assert logger.handlers == []


def test_shared_logger_writes_each_tile_into_its_own_file__ga631_ep_3(tmp_path: Path, logger_name: str) -> None:
    """GA631-EP-3: the global logger never duplicates one tile's lines into the next tile's file."""
    # Given: two tiles with their own output contexts and one module-level logger
    outs = [make_output_context(tmp_path / f"tile{index}") for index in range(2)]
    module_logger = logging.getLogger(logger_name)
    # When: each tile logs to the same logger inside its own block
    for index, out in enumerate(outs):
        with artifact_logger(out, "structured_log.txt", name=logger_name):
            module_logger.info("tile %d", index)
    # Then: each file holds exactly its own tile's line
    assert [_messages(out.struct / "structured_log.txt") for out in outs] == [["tile 0"], ["tile 1"]]


@pytest.mark.parametrize(("mode", "expected"), [("a", ["old", "new"]), ("w", ["new"])])
def test_existing_file_is_appended_or_truncated__ga631_ep_4(tmp_path: Path, logger_name: str, mode: Any, expected: list[str]) -> None:
    """GA631-EP-4: mode="a" (default, as v1) appends; mode="w" truncates."""
    # Given: a log file left by an earlier step of the tile
    out = make_output_context(tmp_path)
    path = out.struct / "fitting.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old\n", encoding="utf-8")
    # When: streaming a record with the given mode and a bare message format
    with artifact_logger(out, "fitting.log", name=logger_name, fmt="%(message)s", mode=mode) as logger:
        logger.info("new")
    # Then: the earlier content is kept or replaced
    assert _lines(path) == expected


def test_kind_selects_the_output_directory__ga631_ep_5(tmp_path: Path, logger_name: str) -> None:
    """GA631-EP-5: kind selects the directory, as for the save_* nodes."""
    # Given: a tile output context
    out = make_output_context(tmp_path)
    # When: declaring the log under logs/
    with artifact_logger(out, "tile.log", name=logger_name, kind="logs") as logger:
        logger.warning("kept")
    # Then: the file is under out.logs, not out.struct
    assert _messages(out.logs / "tile.log") == ["kept"]
    assert not (out.struct / "tile.log").exists()


def test_records_from_worker_threads_are_written__ga631_ep_6(tmp_path: Path, logger_name: str) -> None:
    """GA631-EP-6: parallel fit workers (threads) log every record once into the file."""
    # Given: four worker threads logging to the tile's logger
    out = make_output_context(tmp_path)

    def fit(worker: int) -> None:
        worker_logger = logging.getLogger(logger_name)
        for step in range(50):
            worker_logger.info("worker %d step %d", worker, step)

    # When: the workers run inside the block
    with artifact_logger(out, "fitting.log", name=logger_name, fmt="%(message)s"), ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fit, range(4)))
    # Then: every record is a complete line, written once
    lines = _lines(out.struct / "fitting.log")
    assert sorted(lines) == sorted(f"worker {worker} step {step}" for worker in range(4) for step in range(50))


def test_call_is_recorded_in_call_log__ga631_ep_7(tmp_path: Path, logger_name: str) -> None:
    """GA631-EP-7: declaring the artifact is a node call, so it appears in the call log."""
    # Given: an active call-log recorder with repr capture
    out = make_output_context(tmp_path)
    # When: declaring and using the artifact logger
    with CallLogRecorder(repr_head="on", repr_head_len=200) as recorder, artifact_logger(out, "structured_log.txt", name=logger_name) as logger:
        logger.info("recorded")
    # Then: one completed record names the node, its filename input and the artifact
    (record,) = recorder.records
    assert record.node_id.endswith("artifact_logger")
    assert record.status == "completed"
    assert record.inputs["filename"].repr_head == "'structured_log.txt'"
    assert [summary.type_name for summary in record.outputs] == ["rdetoolkit.nodes.logfile.ArtifactLogger"]
    assert "structured_log.txt" in (record.outputs[0].repr_head or "")


def test_flow_tiles_each_get_their_own_log__ga631_ep_8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logger_name: str) -> None:
    """GA631-EP-8: through the Runner, a shared logger writes one log per tile with no carry-over."""
    # Given: a MultiDataTile project with three inputs and a flow logging to one logger
    data_root = tmp_path / "data"
    _build_tree(data_root)
    for index in (1, 2):
        (data_root / "inputdata" / f"file_{index}.txt").write_text(f"data-{index}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    module_logger = logging.getLogger(logger_name)

    @flow
    def pipeline(out: OutputContext) -> None:
        with artifact_logger(out, "structured_log.txt", name=logger_name):
            module_logger.info("processing %s", out.struct.parent.name)

    # When: executing the flow through the public v2 entry
    report = workflows.run(flow=pipeline, config={"system": {"extended_mode": "MultiDataTile", "save_thumbnail_image": False}})
    # Then: every tile's structured/ holds exactly one line, and the logger is clean again
    assert report.status == "success", report.error
    logs = sorted(data_root.glob("**/structured/structured_log.txt"))
    assert len(logs) == 3
    assert all(len(_messages(path)) == 1 for path in logs)
    assert len({_messages(path)[0] for path in logs}) == 3
    assert module_logger.handlers == []
    # and the RunReport lists the declaration among each tile's node calls
    for iteration in report.iterations:
        assert [call["node_id"].rsplit(".", 1)[-1] for call in iteration["node_calls"]] == ["artifact_logger"]


def test_concurrent_runners_keep_their_logs_apart__ga631_ep_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logger_name: str) -> None:
    """GA631-EP-9: two Runners in one process, same logger, overlapping blocks: no mixing, level restored."""
    # Given: two projects and a flow whose blocks overlap; run "a" leaves its block first
    monkeypatch.chdir(tmp_path)
    module_logger = logging.getLogger(logger_name)
    module_logger.setLevel(logging.WARNING)
    both_inside = threading.Barrier(2, timeout=30)
    a_left = threading.Event()

    @flow
    def pipeline(out: OutputContext) -> None:
        run = out.struct.parents[1].name
        with artifact_logger(out, "structured_log.txt", name=logger_name):
            module_logger.info("%s entered", run)
            both_inside.wait()
            if run == "b":
                assert a_left.wait(timeout=30)
            module_logger.info("%s leaving", run)
        if run == "a":
            a_left.set()

    reports: dict[str, Any] = {}

    def run(name: str) -> None:
        root = tmp_path / name
        _build_tree(root / "data")
        runner = Runner(root=root, inputdata_path=root / "data" / "inputdata", unpacked_dir_path=root / "data" / "temp")
        reports[name] = runner.run(pipeline)

    # When: running both concurrently
    threads = [threading.Thread(target=run, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    # Then: both succeed, each file holds only its own run's lines, and the level is back
    for name in ("a", "b"):
        assert reports[name].status == "success", reports[name].error
        (log,) = (tmp_path / name).glob("**/structured/structured_log.txt")
        assert _messages(log) == [f"{name} entered", f"{name} leaving"]
    assert module_logger.level == logging.WARNING
    assert module_logger.handlers == []


def _log_from_worker(logger_name: str, message: str) -> None:
    logging.getLogger(logger_name).info(message)


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="needs the fork start method")
def test_forked_worker_never_writes_to_a_tile_file__ga631_ep_10(tmp_path: Path, logger_name: str) -> None:
    """GA631-EP-10: a worker forked in tile 1 and reused in tile 2 writes into neither file."""
    # Given: two tile output contexts
    first, second = make_output_context(tmp_path / "t1"), make_output_context(tmp_path / "t2")
    # When: a fork pool created inside the first block logs in both tiles
    with artifact_logger(first, "structured_log.txt", name=logger_name) as logger:
        logger.info("tile 1 parent")
        pool = multiprocessing.get_context("fork").Pool(1)
        pool.apply(_log_from_worker, (logger_name, "tile 1 worker"))
    try:
        with artifact_logger(second, "structured_log.txt", name=logger_name) as logger:
            logger.info("tile 2 parent")
            pool.apply(_log_from_worker, (logger_name, "tile 2 worker"))
    finally:
        pool.close()
        pool.join()
    # Then: each file holds only its own parent's line
    assert _messages(first.struct / "structured_log.txt") == ["tile 1 parent"]
    assert _messages(second.struct / "structured_log.txt") == ["tile 2 parent"]


def test_level_filters_records_and_is_restored__ga631_bv_1(tmp_path: Path, logger_name: str) -> None:
    """GA631-BV-1: level=INFO drops DEBUG; the logger's own level is restored afterwards."""
    # Given: a logger whose level is unset (effective WARNING through the root)
    out = make_output_context(tmp_path)
    logger = logging.getLogger(logger_name)
    assert logger.level == logging.NOTSET
    # When: streaming with level=INFO
    with artifact_logger(out, "structured_log.txt", name=logger_name, level=logging.INFO, fmt="%(levelname)s %(message)s") as active:
        active.debug("dropped")
        active.info("kept")
    # Then: INFO is written (although WARNING is the logger's effective level), DEBUG is not
    assert _lines(out.struct / "structured_log.txt") == ["INFO kept"]
    assert logger.level == logging.NOTSET


def test_empty_block_creates_no_file__ga631_bv_2(tmp_path: Path, logger_name: str) -> None:
    """GA631-BV-2: like v1 get_logger (delay=True), a tile that logs nothing leaves no file."""
    # Given: a tile output context
    out = make_output_context(tmp_path)
    # When: entering and leaving the block without logging
    with artifact_logger(out, "structured_log.txt", name=logger_name):
        pass
    # Then: no empty artifact exists
    assert not (out.struct / "structured_log.txt").exists()


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"filename": "../escape.log"}, "filename"),
        ({"filename": "x.log", "kind": "temp"}, "Unknown output kind"),
        ({"filename": "x.log", "mode": "x"}, "Unknown log file mode"),
    ],
    ids=["filename", "kind", "mode"],
)
def test_invalid_arguments_are_rejected__ga631_bv_3(tmp_path: Path, logger_name: str, kwargs: dict[str, Any], match: str) -> None:
    """GA631-BV-3: filename and kind are validated by OutputContext; mode by the node."""
    # Given: a tile output context
    out = make_output_context(tmp_path)
    # When / Then: the declaration fails before any handler is attached
    with pytest.raises(ValueError, match=match):
        artifact_logger(out, name=logger_name, **kwargs)
    assert logging.getLogger(logger_name).handlers == []
    assert not (tmp_path / "escape.log").exists()


def test_reentering_active_logger_raises__ga631_bv_4(tmp_path: Path, logger_name: str) -> None:
    """GA631-BV-4: one ArtifactLogger is active once at a time; the outer block is unaffected."""
    # Given: an active artifact logger
    out = make_output_context(tmp_path)
    artifact = artifact_logger(out, "structured_log.txt", name=logger_name, fmt="%(message)s")
    assert isinstance(artifact, ArtifactLogger)
    with artifact as logger:
        # When: entering the same object again
        with pytest.raises(RuntimeError, match="already active"):
            artifact.__enter__()
        logger.info("outer")
    # Then: the outer block wrote its record once and removed its only handler
    assert _lines(artifact.path) == ["outer"]
    assert logger.handlers == []


def test_logger_name_defaults_to_filename_stem__ga631_bv_5(tmp_path: Path) -> None:
    """GA631-BV-5: without ``name`` the logger is named after the file, without its suffix."""
    # Given: a tile output context
    out = make_output_context(tmp_path)
    # When: declaring the artifact without a logger name
    artifact = artifact_logger(out, "ga631_default_name.txt")
    # Then: the logger name is the file stem and the path is under out.struct
    assert artifact.logger.name == "ga631_default_name"
    assert artifact.path == out.struct / "ga631_default_name.txt"


def test_overlapping_blocks_restore_level_in_any_order__ga631_bv_6(tmp_path: Path, logger_name: str) -> None:
    """GA631-BV-6: A enters, B enters, A exits first: B keeps its level, the original returns after B."""
    # Given: a WARNING logger and two blocks on it
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.WARNING)
    first = artifact_logger(make_output_context(tmp_path / "a"), "log.txt", name=logger_name, level=logging.INFO)
    second = artifact_logger(make_output_context(tmp_path / "b"), "log.txt", name=logger_name, level=logging.DEBUG)
    # When: the blocks end in the order they were entered
    first.__enter__()
    second.__enter__()
    assert logger.level == logging.DEBUG
    first.__exit__(None, None, None)
    # Then: the remaining block still has its level, and the original returns after it
    assert logger.level == logging.DEBUG
    second.__exit__(None, None, None)
    assert logger.level == logging.WARNING
    assert logger.handlers == []
