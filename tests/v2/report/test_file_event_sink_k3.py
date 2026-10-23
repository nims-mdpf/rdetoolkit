"""FileEventSink size cap and durability contract (Session K3, rulings #2/#3).

Design authority: Design §8.1 (events), PhaseK_prompts ruling #6(a) and Q6:
the events JSONL has a 64 MiB soft cap. Once a node-level event would cross it
the sink writes **one** ``warning`` event with code W1002, prints one stderr
line, drops every later ``node.*`` event and keeps writing ``run.*``,
``iteration.*`` and ``warning`` events. The stream is append-only, so it is
flushed per line and fsynced on close instead of being replaced atomically.

EP table:

| TC-ID         | Partition                              | Expected                                              |
|---------------|----------------------------------------|-------------------------------------------------------|
| TC-K3-CAP-001 | default construction                   | cap is 64 MiB                                         |
| TC-K3-CAP-002 | node events below the cap              | every event written, no W1002                         |
| TC-K3-CAP-003 | node events crossing the cap           | one W1002 warning, later node events dropped          |
| TC-K3-CAP-004 | run/iteration/warning after truncation | still written                                         |
| TC-K3-CAP-005 | truncation                             | exactly one stderr line naming W1002                  |
| TC-K3-CAP-006 | W1002 catalog entry                    | WARNING_CATALOG[1002] carries the ruling's text       |
| TC-K3-CAP-007 | non-positive / bool max_bytes          | ValueError at construction                            |
| TC-K3-CAP-008 | reopen for a second run                | truncation state reset                                |
| TC-K3-DUR-001 | every emitted line                     | flushed: readable before close                        |
| TC-K3-DUR-002 | close                                  | os.fsync called on the events file descriptor         |
| TC-K3-DUR-003 | close twice / close before open        | no error, no fsync of a missing file                  |
| TC-K3-DUR-004 | emit before open                       | RuntimeError (unchanged contract)                     |
| TC-K3-DUR-005 | payload value that is not JSON         | written as its str(), the run is not failed by the log |

BV table:

| TC-ID         | Boundary                               | Expected                                              |
|---------------|----------------------------------------|-------------------------------------------------------|
| TC-K3-CAP-BV1 | node line ends exactly at the cap      | written, not truncated                                |
| TC-K3-CAP-BV2 | node line ends one byte past the cap   | dropped, W1002 written                                |
| TC-K3-CAP-BV3 | non-node line crosses the cap          | written, does not trigger W1002 by itself             |
| TC-K3-CAP-BV4 | max_bytes = 1                          | every node event dropped, header and run events kept  |
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from rdetoolkit.errors import WARNING_CATALOG
from rdetoolkit.report.events import DEFAULT_EVENTS_MAX_BYTES, Event, FileEventSink

_RUN_ID = "k3-cap"


def _lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _node_started(index: int) -> Event:
    # A fixed timestamp keeps every line's byte length predictable for cap arithmetic.
    event = Event.node_started(run_id=_RUN_ID, node_id="k3_node", call_id=f"k3_node#{index}")
    return replace(event, timestamp=1_000_000_000.5)


def _encoded_size(event: Event) -> int:
    return len((json.dumps(event.to_dict(), ensure_ascii=False) + "\n").encode("utf-8"))


def _opened(tmp_path: Path) -> tuple[FileEventSink, int]:
    """Open a sink and return it with its actual header size.

    The header carries a float timestamp whose repr length varies, so cap
    arithmetic must start from the header this very sink wrote.
    """
    sink = FileEventSink(tmp_path)
    sink.open(_RUN_ID)
    return sink, len((tmp_path / f"events_{_RUN_ID}.jsonl").read_bytes())


class TestDefaultCap:
    def test_default_cap_is_64_mib__tc_k3_cap_001(self, tmp_path: Path) -> None:
        """TC-K3-CAP-001: the Q6 soft cap is 64 MiB."""
        # Given/When: the module constant and a default-constructed sink
        sink = FileEventSink(tmp_path)
        # Then: both name 64 MiB
        assert DEFAULT_EVENTS_MAX_BYTES == 64 * 1024 * 1024
        assert sink.max_bytes == DEFAULT_EVENTS_MAX_BYTES

    def test_w1002_catalog_entry__tc_k3_cap_006(self) -> None:
        """TC-K3-CAP-006: W1002 is catalogued with the ruling's message."""
        # Given/When: the warning catalog
        entry = WARNING_CATALOG[1002]
        # Then: a stable name and the ruling's text
        assert entry.name == "EventsLogTruncated"
        assert entry.message_template == (
            "events log truncated at the size cap; node-level events are no longer recorded for this run"
        )


class TestInvalidCap:
    @pytest.mark.parametrize("value", [0, -1, True])
    def test_non_positive_cap_rejected__tc_k3_cap_007(self, tmp_path: Path, value: int) -> None:
        """TC-K3-CAP-007: a cap that can never hold the header is a usage error."""
        # Given/When/Then: construction fails before any file exists
        with pytest.raises(ValueError, match="max_bytes"):
            FileEventSink(tmp_path, max_bytes=value)
        assert list(tmp_path.iterdir()) == []


class TestCapBehaviour:
    def test_below_cap_writes_everything__tc_k3_cap_002(self, tmp_path: Path) -> None:
        """TC-K3-CAP-002: under the cap nothing is dropped and no W1002 appears."""
        # Given: a generous cap
        sink = FileEventSink(tmp_path, max_bytes=1_000_000)
        sink.open(_RUN_ID)
        # When: emitting node events
        for index in range(5):
            sink.emit(_node_started(index))
        sink.close()
        # Then: header + 5 events, no warning
        lines = _lines(tmp_path / f"events_{_RUN_ID}.jsonl")
        assert len(lines) == 6
        assert not [line for line in lines if line.get("name") == "warning"]
        assert sink.truncated is False

    def test_crossing_cap_warns_once_and_drops_node_events__tc_k3_cap_003(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """TC-K3-CAP-003/005: one W1002 + one stderr line, node events dropped after."""
        # Given: a cap that holds the header and exactly two node events
        path = tmp_path / f"events_{_RUN_ID}.jsonl"
        sink, header = _opened(tmp_path)
        sink.max_bytes = header + _encoded_size(_node_started(0)) + _encoded_size(_node_started(1))
        # When: emitting five node events
        for index in range(5):
            sink.emit(_node_started(index))
        sink.close()
        # Then: two node events survive, then exactly one W1002 warning
        lines = _lines(path)
        names = [line.get("name") for line in lines[1:]]
        assert names == ["node.started", "node.started", "warning"]
        warning = lines[-1]
        assert warning["run_id"] == _RUN_ID
        assert warning["payload"] == {"code": 1002, "message": WARNING_CATALOG[1002].message_template}
        assert sink.truncated is True
        assert sink.path == path
        err_lines = [line for line in capsys.readouterr().err.splitlines() if line]
        assert len(err_lines) == 1
        assert "W1002" in err_lines[0]
        assert str(path) in err_lines[0]

    def test_run_iteration_and_warning_continue_after_truncation__tc_k3_cap_004(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """TC-K3-CAP-004 / BV4: coarse events keep flowing after the cap."""
        # Given: a cap of one byte, already exceeded by the header
        sink = FileEventSink(tmp_path, max_bytes=1)
        sink.open(_RUN_ID)
        # When: a run's worth of mixed events is emitted
        sink.emit(Event.run_started(run_id=_RUN_ID))
        sink.emit(Event.iteration_started(run_id=_RUN_ID, index=0))
        sink.emit(_node_started(0))
        sink.emit(Event.node_completed(run_id=_RUN_ID, node_id="k3_node", call_id="k3_node#0"))
        sink.emit(Event.node_failed(run_id=_RUN_ID, node_id="k3_node", call_id="k3_node#1", error_msg="x"))
        sink.emit(Event.warning(run_id=_RUN_ID, code=1001, message="mode override"))
        sink.emit(Event.iteration_completed(run_id=_RUN_ID, index=0))
        sink.emit(Event.run_completed(run_id=_RUN_ID, status="success"))
        sink.close()
        # Then: every node event is gone, one W1002 replaced them, the rest stay in order
        lines = _lines(tmp_path / f"events_{_RUN_ID}.jsonl")
        assert lines[0]["type"] == "run.meta"
        names = [line.get("name") for line in lines[1:]]
        assert names == [
            "run.started",
            "iteration.started",
            "warning",
            "warning",
            "iteration.completed",
            "run.completed",
        ]
        codes = [line["payload"]["code"] for line in lines[1:] if line.get("name") == "warning"]  # type: ignore[index]
        assert codes == [1002, 1001]
        assert len([line for line in capsys.readouterr().err.splitlines() if "W1002" in line]) == 1

    def test_line_ending_exactly_at_cap_is_written__tc_k3_cap_bv1(self, tmp_path: Path) -> None:
        """TC-K3-CAP-BV1: the cap is inclusive."""
        # Given: a cap equal to header + one node line
        sink, header = _opened(tmp_path)
        cap = header + _encoded_size(_node_started(0))
        sink.max_bytes = cap
        # When: emitting that one node line
        sink.emit(_node_started(0))
        sink.close()
        # Then: it is written and the file is exactly at the cap
        path = tmp_path / f"events_{_RUN_ID}.jsonl"
        assert sink.truncated is False
        assert len(path.read_bytes()) == cap

    def test_line_one_byte_past_cap_is_dropped__tc_k3_cap_bv2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """TC-K3-CAP-BV2: one byte over the cap truncates."""
        # Given: a cap one byte short of header + one node line
        sink, header = _opened(tmp_path)
        sink.max_bytes = header + _encoded_size(_node_started(0)) - 1
        # When: emitting the node line
        sink.emit(_node_started(0))
        sink.close()
        # Then: the node event is replaced by the W1002 warning
        names = [line.get("name") for line in _lines(tmp_path / f"events_{_RUN_ID}.jsonl")[1:]]
        assert names == ["warning"]
        assert sink.truncated is True
        assert "W1002" in capsys.readouterr().err

    def test_non_node_line_crossing_cap_does_not_truncate__tc_k3_cap_bv3(self, tmp_path: Path) -> None:
        """TC-K3-CAP-BV3: only a node-level event triggers W1002."""
        # Given: a cap below the header size (non-node lines are never capped)
        sink = FileEventSink(tmp_path, max_bytes=1)
        sink.open(_RUN_ID)
        # When: only coarse events are emitted
        sink.emit(Event.run_started(run_id=_RUN_ID))
        sink.emit(Event.run_completed(run_id=_RUN_ID, status="success"))
        sink.close()
        # Then: no warning was produced
        names = [line.get("name") for line in _lines(tmp_path / f"events_{_RUN_ID}.jsonl")[1:]]
        assert names == ["run.started", "run.completed"]
        assert sink.truncated is False

    def test_reopen_resets_truncation__tc_k3_cap_008(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """TC-K3-CAP-008: the cap and the one-warning budget are per run."""
        # Given: a sink truncated during a first run
        sink = FileEventSink(tmp_path, max_bytes=1)
        sink.open("run-a")
        sink.emit(Event.node_started(run_id="run-a", node_id="n", call_id="n#1"))
        sink.close()
        assert sink.truncated is True
        # When: the same sink is reopened for a second run with a cap that now fits
        sink.max_bytes = 1_000_000
        sink.open("run-b")
        sink.emit(Event.node_started(run_id="run-b", node_id="n", call_id="n#1"))
        sink.close()
        # Then: the second run's file has its node event and no warning
        names = [line.get("name") for line in _lines(tmp_path / "events_run-b.jsonl")[1:]]
        assert names == ["node.started"]
        assert sink.truncated is False
        assert capsys.readouterr().err.count("W1002") == 1


class TestDurability:
    def test_each_line_is_flushed_before_close__tc_k3_dur_001(self, tmp_path: Path) -> None:
        """TC-K3-DUR-001: a reader sees every complete line while the run is live."""
        # Given: an open sink
        sink = FileEventSink(tmp_path)
        sink.open(_RUN_ID)
        # When: one event is emitted and the sink is still open
        sink.emit(Event.run_started(run_id=_RUN_ID))
        # Then: both lines are already on disk and parse as JSON
        lines = _lines(tmp_path / f"events_{_RUN_ID}.jsonl")
        assert [line.get("type") or line.get("name") for line in lines] == ["run.meta", "run.started"]
        sink.close()

    def test_close_fsyncs_the_file__tc_k3_dur_002(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-DUR-002: close forces the stream to stable storage."""
        # Given: an open sink and an fsync spy
        synced: list[int] = []
        real_fsync = os.fsync

        def _spy(fd: int) -> None:
            synced.append(fd)
            real_fsync(fd)

        monkeypatch.setattr("rdetoolkit.report.events.os.fsync", _spy)
        sink = FileEventSink(tmp_path)
        sink.open(_RUN_ID)
        # When: closing
        sink.close()
        # Then: exactly one fsync happened
        assert len(synced) == 1

    def test_close_without_open_and_double_close__tc_k3_dur_003(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-DUR-003: closing nothing never fsyncs and never raises."""
        # Given: an fsync spy and a sink that was never opened
        synced: list[int] = []
        monkeypatch.setattr("rdetoolkit.report.events.os.fsync", synced.append)
        sink = FileEventSink(tmp_path)
        # When: closing it, then opening/closing/closing again
        sink.close()
        sink.open(_RUN_ID)
        sink.close()
        sink.close()
        # Then: only the one real close synced
        assert len(synced) == 1

    def test_emit_before_open_still_raises__tc_k3_dur_004(self, tmp_path: Path) -> None:
        """TC-K3-DUR-004: the pre-K3 usage contract is unchanged."""
        # Given: an unopened sink
        sink = FileEventSink(tmp_path)
        # When/Then: emitting fails loudly
        with pytest.raises(RuntimeError, match="open"):
            sink.emit(Event.run_started(run_id=_RUN_ID))

    def test_non_json_payload_is_stringified__tc_k3_dur_005(self, tmp_path: Path) -> None:
        """TC-K3-DUR-005: the log never fails a run over an unserializable value."""
        # Given: an open sink and a payload carrying a non-JSON object
        sink = FileEventSink(tmp_path)
        sink.open(_RUN_ID)
        marker = object()
        # When: emitting it
        sink.emit(Event(run_id=_RUN_ID, name="run.completed", payload={"status": marker}))
        sink.close()
        # Then: the line is valid JSON holding the value's str()
        lines = _lines(tmp_path / f"events_{_RUN_ID}.jsonl")
        assert lines[-1]["payload"] == {"status": str(marker)}
