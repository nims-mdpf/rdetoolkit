r"""One run per data root at a time (#737, error 3008 ``RunRootBusy``).

Two runs on one data root used to interleave their writes of the shared tile
invoices: a run could read ``invoice/invoice.json`` or ``temp/invoice_org.json``
while the other was rewriting it and fail with 4010 / 4003 / 1. The Runner now
owns the data root for the whole run; a second run on the same root fails before
it writes anything, on both entries, in the same or another process.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| DataRootLock | free root | acquired; released; acquirable again | TC-737-LOCK-EP-001 |
| DataRootLock | root held in this process | not acquired | TC-737-LOCK-EP-002 |
| DataRootLock | different roots | both acquired | TC-737-LOCK-EP-003 |
| DataRootLock | same root through a symlink | not acquired | TC-737-LOCK-EP-004 |
| DataRootLock | root held by another process | not acquired; acquired after that process is killed | TC-737-LOCK-EP-005 |
| Runner.run | root busy (flow and callback entries) | failed, 3008 RunRootBusy, nothing written; holder unaffected | TC-737-LOCK-EP-006 |
| Runner.run | after a failed run / an exception escaping run | root free again | TC-737-LOCK-EP-007 |
| workflows.run (v1 entry) | root busy | SystemExit(1), no job.failed | TC-737-LOCK-EP-008 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| DataRootLock | lock directory cannot be created | in-process exclusion still holds; run proceeds | TC-737-LOCK-BV-001 |
| DataRootLock | release twice / release without acquire | no error | TC-737-LOCK-BV-002 |
| DataRootLock | last owner releases | lock file and empty lock directory removed | TC-737-LOCK-BV-004 |
| DataRootLock | lock file removed between open and lock | the stale file is not trusted; the fresh one is locked | TC-737-LOCK-BV-005 |
| DataRootLock | every retry lands on a removed file | not acquired; nothing reserved | TC-737-LOCK-BV-006 |
| DataRootLock | forked worker after the parent released | acquired in the worker | TC-737-LOCK-BV-007 |
| DataRootLock | forked worker while the parent holds the root | not acquired; releasing the inherited copy leaves the parent's lock | TC-737-LOCK-BV-008 |
| DataRootLock | POSIX root name that is not valid UTF-8 | acquired, released, acquired again | TC-737-LOCK-BV-009 |
| DataRootLock | acquisition setup raises | the error propagates; the root is not left reserved | TC-737-LOCK-BV-010 |
| Runner.run | two sequential runs on one root | both succeed | TC-737-LOCK-BV-003 |
"""

from __future__ import annotations

import multiprocessing
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import workflows
from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.root_lock import DataRootLock
from rdetoolkit.types import IterationInfo
from tests.v2.contract.fixtures import _generate

_BUSY = 3008

_HOLDER_SCRIPT = """
import sys
from pathlib import Path
from rdetoolkit.runner.root_lock import DataRootLock
lock = DataRootLock(Path(sys.argv[1]), lock_dir=Path(sys.argv[2]))
print("held" if lock.acquire() else "busy", flush=True)
sys.stdin.read()
"""

_entered = threading.Event()
_release = threading.Event()


@node(id="tests.v2.runner.lock737.wait")
def wait_for_release(index: int) -> int:
    """Signal that the run owns its root, then wait until the test lets it finish."""
    _entered.set()
    assert _release.wait(timeout=120), "the test never released the holding run"
    return index


@flow(id="tests.v2.runner.lock737.holding_flow")
def holding_flow(iteration: IterationInfo) -> None:
    """Own the root until the test releases the run."""
    wait_for_release(iteration.index)


@flow(id="tests.v2.runner.lock737.noop_flow")
def noop_flow(iteration: IterationInfo) -> None:
    """Succeed on every tile."""
    assert iteration.index >= 0


@flow(id="tests.v2.runner.lock737.failing_flow")
def failing_flow(iteration: IterationInfo) -> None:
    """Fail every tile, so the run ends failed."""
    msg = f"tile {iteration.index} fails"
    raise ValueError(msg)


@flow(id="tests.v2.runner.lock737.interrupting_flow")
def interrupting_flow(iteration: IterationInfo) -> None:
    """Raise an exception that escapes ``Runner.run``."""
    raise KeyboardInterrupt


def noop_callback(srcpaths: object, resource_paths: object) -> None:
    """A v1 callback that does nothing."""
    assert srcpaths is not None


def _runner(root: Path, run_id: str) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        run_id_factory=lambda: run_id,
    )


def _run(root: Path, target: FlowTarget | LegacyCallbackTarget, run_id: str) -> RunReport:
    return _runner(root, run_id).run(RunRequest(root=root, target=target, config_source={"system": {"save_thumbnail_image": False}}))


def _tree(root: Path) -> dict[str, bytes]:
    data = root / "data"
    return {path.relative_to(data).as_posix(): path.read_bytes() for path in sorted(data.rglob("*")) if path.is_file()}


@pytest.fixture
def invoice_root(tmp_path: Path) -> Path:
    """Materialize the committed Invoice-mode contract input."""
    root = tmp_path / "root"
    _generate.materialize_sut_case("invoice", root)
    return root


@pytest.fixture
def holding_run(invoice_root: Path) -> Any:
    """Start a flow run that owns ``invoice_root`` until the test releases it."""
    _entered.clear()
    _release.clear()
    outcome: dict[str, RunReport] = {}
    thread = threading.Thread(target=lambda: outcome.setdefault("report", _run(invoice_root, FlowTarget(function=holding_flow), "holder")))
    thread.start()
    assert _entered.wait(timeout=120), "the holding run never reached its flow"

    def finish() -> RunReport:
        _release.set()
        thread.join(timeout=120)
        return outcome["report"]

    yield finish
    _release.set()
    thread.join(timeout=120)


# ------------------------------------------------------------------ the lock


def test_free_root_is_acquired_released_and_reacquired__tc_737_lock_ep_001(tmp_path: Path) -> None:
    """TC-737-LOCK-EP-001: a free root can be owned, released and owned again."""
    # Given: a data root nobody holds
    root = tmp_path / "data"
    root.mkdir()
    lock = DataRootLock(root, lock_dir=tmp_path / "locks")

    # When / Then: it is acquired, released and acquired again
    assert lock.acquire() is True
    lock.release()
    assert lock.acquire() is True
    lock.release()


def test_root_held_in_this_process_is_busy__tc_737_lock_ep_002(tmp_path: Path) -> None:
    """TC-737-LOCK-EP-002: a second owner in the same process is refused."""
    # Given: a held data root
    root = tmp_path / "data"
    root.mkdir()
    first = DataRootLock(root, lock_dir=tmp_path / "locks")
    assert first.acquire()

    # When: another lock object asks for the same root
    second = DataRootLock(root, lock_dir=tmp_path / "locks")

    # Then: it is refused until the first owner releases
    try:
        assert second.acquire() is False
    finally:
        first.release()
    assert second.acquire() is True
    second.release()


def test_different_roots_do_not_contend__tc_737_lock_ep_003(tmp_path: Path) -> None:
    """TC-737-LOCK-EP-003: distinct data roots are owned independently."""
    # Given: two data roots
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    first, second = DataRootLock(one, lock_dir=tmp_path / "locks"), DataRootLock(two, lock_dir=tmp_path / "locks")

    # Then: both are acquired at once
    assert first.acquire() is True
    assert second.acquire() is True
    first.release()
    second.release()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_same_root_through_a_symlink_is_busy__tc_737_lock_ep_004(tmp_path: Path) -> None:
    """TC-737-LOCK-EP-004: the root is identified by its resolved path."""
    # Given: a held data root and a symlink to it
    root = tmp_path / "data"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    first = DataRootLock(root, lock_dir=tmp_path / "locks")
    assert first.acquire()

    # Then: the alias names the same, busy root
    try:
        assert DataRootLock(alias, lock_dir=tmp_path / "locks").acquire() is False
    finally:
        first.release()


def test_root_held_by_another_process_is_busy_until_it_dies__tc_737_lock_ep_005(tmp_path: Path) -> None:
    """TC-737-LOCK-EP-005: the lock crosses processes and dies with its holder."""
    # Given: another process holding the root
    root = tmp_path / "data"
    root.mkdir()
    locks = tmp_path / "locks"
    holder = subprocess.Popen(  # noqa: S603 -- fixed interpreter and script
        [sys.executable, "-c", _HOLDER_SCRIPT, str(root), str(locks)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"

        # When: this process asks for the same root
        lock = DataRootLock(root, lock_dir=locks)

        # Then: it is refused while the holder lives
        assert lock.acquire() is False
    finally:
        # And: a killed holder leaves no stale lock behind
        holder.kill()
        holder.wait(timeout=60)
    assert lock.acquire() is True
    lock.release()


def test_unavailable_lock_directory_keeps_in_process_exclusion__tc_737_lock_bv_001(tmp_path: Path) -> None:
    """TC-737-LOCK-BV-001: no lock directory means no cross-process lock, not a failed run."""
    # Given: a lock directory that cannot be created (a regular file is in the way)
    root = tmp_path / "data"
    root.mkdir()
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    first = DataRootLock(root, lock_dir=blocker / "locks")

    # When / Then: the root is still owned, and still exclusive within this process
    assert first.acquire() is True
    try:
        assert DataRootLock(root, lock_dir=blocker / "locks").acquire() is False
    finally:
        first.release()


def test_release_is_idempotent__tc_737_lock_bv_002(tmp_path: Path) -> None:
    """TC-737-LOCK-BV-002: releasing an unheld lock is harmless."""
    # Given: a lock that was never acquired
    root = tmp_path / "data"
    root.mkdir()
    lock = DataRootLock(root, lock_dir=tmp_path / "locks")

    # When / Then: releasing before and after a cycle raises nothing
    lock.release()
    assert lock.acquire()
    lock.release()
    lock.release()
    assert DataRootLock(root, lock_dir=tmp_path / "locks").acquire() is True


def test_release_leaves_nothing_in_the_lock_directory__tc_737_lock_bv_004(tmp_path: Path) -> None:
    """TC-737-LOCK-BV-004: a finished run leaves no lock file and no lock directory."""
    # Given: a root that was owned and released
    root = tmp_path / "data"
    root.mkdir()
    locks = tmp_path / "locks"
    lock = DataRootLock(root, lock_dir=locks)
    assert lock.acquire()
    assert [path.suffix for path in locks.iterdir()] == [".lock"]

    # When: it is released
    lock.release()

    # Then: the lock directory is gone
    assert not locks.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="an open file cannot be removed on Windows")
def test_a_removed_lock_file_is_not_trusted__tc_737_lock_bv_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-737-LOCK-BV-005: locking a file its previous owner just removed retries on a fresh file."""
    # Given: an acquirer whose first lock lands on a file that is removed right after it was opened
    from rdetoolkit.runner import root_lock  # noqa: PLC0415 -- the seam under test

    root = tmp_path / "data"
    root.mkdir()
    locks = tmp_path / "locks"
    real_try_lock = root_lock._try_lock  # noqa: SLF001
    calls: list[int] = []

    def remove_then_lock(fd: int) -> bool:
        calls.append(fd)
        if len(calls) == 1:
            for path in locks.iterdir():
                path.unlink()
        return real_try_lock(fd)

    monkeypatch.setattr(root_lock, "_try_lock", remove_then_lock)
    lock = DataRootLock(root, lock_dir=locks)

    # When: it acquires
    assert lock.acquire() is True

    # Then: it locked twice, and holds the file that is at the path now
    try:
        assert len(calls) == 2
        monkeypatch.setattr(root_lock, "_try_lock", real_try_lock)
        holder = subprocess.run(  # noqa: S603 -- fixed interpreter and script
            [sys.executable, "-c", _HOLDER_SCRIPT, str(root), str(locks)],
            input="",
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        assert holder.stdout.strip() == "busy"
    finally:
        lock.release()


def test_exhausted_retries_refuse_the_root__tc_737_lock_bv_006(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-737-LOCK-BV-006: no lock on the current file means no ownership, however often it was retried."""
    # Given: an acquirer whose every lock lands on a file that is no longer at the path
    from rdetoolkit.runner import root_lock  # noqa: PLC0415 -- the seam under test

    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setattr(root_lock, "_is_current", lambda fd, path: False)
    lock = DataRootLock(root, lock_dir=tmp_path / "locks")

    # When / Then: it is refused, and the root is not left reserved in this process
    assert lock.acquire() is False
    monkeypatch.undo()
    fresh = DataRootLock(root, lock_dir=tmp_path / "locks")
    assert fresh.acquire() is True
    fresh.release()


def _fork_worker(root: str, locks: str, inherited: DataRootLock | None, start: Any, result: Any) -> None:
    """Wait for the parent, optionally release the inherited copy, then try a fresh acquisition."""
    start.wait(timeout=60)
    if inherited is not None:
        inherited.release()
    lock = DataRootLock(Path(root), lock_dir=Path(locks))
    owned = lock.acquire()
    result.send(owned)
    if owned:
        lock.release()


def _fork_context() -> Any:
    if sys.platform == "win32" or "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("fork is not available on this platform")
    return multiprocessing.get_context("fork")


def test_a_forked_worker_acquires_after_the_parent_released__tc_737_lock_bv_007(tmp_path: Path) -> None:
    """TC-737-LOCK-BV-007: a worker forked while the parent held the root is not stuck on 3008."""
    # Given: a worker forked while the parent owns the root
    context = _fork_context()
    root = tmp_path / "data"
    root.mkdir()
    locks = tmp_path / "locks"
    lock = DataRootLock(root, lock_dir=locks)
    assert lock.acquire()
    start = context.Event()
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_fork_worker, args=(str(root), str(locks), None, start, sender))
    worker.start()

    # When: the parent releases, then the worker acquires
    lock.release()
    start.set()

    # Then: the worker owns the root
    try:
        assert receiver.poll(60)
        assert receiver.recv() is True
    finally:
        worker.join(60)
    assert worker.exitcode == 0


def test_a_forked_worker_cannot_take_or_free_the_parents_root__tc_737_lock_bv_008(tmp_path: Path) -> None:
    """TC-737-LOCK-BV-008: the inherited copy of the parent's lock is not the worker's to release."""
    # Given: a worker forked while the parent owns the root
    context = _fork_context()
    root = tmp_path / "data"
    root.mkdir()
    locks = tmp_path / "locks"
    lock = DataRootLock(root, lock_dir=locks)
    assert lock.acquire()
    try:
        start = context.Event()
        receiver, sender = context.Pipe(duplex=False)
        worker = context.Process(target=_fork_worker, args=(str(root), str(locks), lock, start, sender))
        worker.start()

        # When: the worker releases its inherited copy and then tries to acquire
        start.set()
        assert receiver.poll(60)
        worker_owned = receiver.recv()
        worker.join(60)

        # Then: the worker was refused, and the parent still owns the root against other processes
        assert worker_owned is False
        assert worker.exitcode == 0
        assert [path.suffix for path in locks.iterdir()] == [".lock"]
        holder = subprocess.run(  # noqa: S603 -- fixed interpreter and script
            [sys.executable, "-c", _HOLDER_SCRIPT, str(root), str(locks)],
            input="",
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        assert holder.stdout.strip() == "busy"
    finally:
        lock.release()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows file names are not byte strings")
def test_a_non_utf8_root_name_is_lockable__tc_737_lock_bv_009(tmp_path: Path) -> None:
    """TC-737-LOCK-BV-009: a valid POSIX name that is not UTF-8 is hashed by its file-system bytes."""
    # Given: a data root whose name holds the byte 0xff
    root = Path(os.fsdecode(os.fsencode(tmp_path) + b"/data-\xff"))
    try:
        root.mkdir()
    except OSError:
        pytest.skip("this file system rejects non-UTF-8 names")
    lock = DataRootLock(root, lock_dir=tmp_path / "locks")

    # When / Then: it is acquired, released and acquired again
    assert lock.acquire() is True
    lock.release()
    again = DataRootLock(root, lock_dir=tmp_path / "locks")
    assert again.acquire() is True
    again.release()


def test_a_failed_acquisition_does_not_leave_the_root_reserved__tc_737_lock_bv_010(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-737-LOCK-BV-010: an error while locking the file rolls the in-process reservation back."""
    # Given: an acquisition whose file locking raises
    from rdetoolkit.runner import root_lock  # noqa: PLC0415 -- the seam under test

    root = tmp_path / "data"
    root.mkdir()

    def broken(fd: int) -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(root_lock, "_try_lock", broken)

    # When: it raises
    with pytest.raises(RuntimeError, match="boom"):
        DataRootLock(root, lock_dir=tmp_path / "locks").acquire()

    # Then: the root can be acquired once locking works again
    monkeypatch.undo()
    lock = DataRootLock(root, lock_dir=tmp_path / "locks")
    assert lock.acquire() is True
    lock.release()


# ------------------------------------------------------------------ the Runner


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(FlowTarget(function=noop_flow), id="TC-737-LOCK-EP-006-FLOW"),
        pytest.param(LegacyCallbackTarget(function=noop_callback), id="TC-737-LOCK-EP-006-CB"),
    ],
)
def test_a_run_on_a_busy_root_fails_without_writing(
    target: FlowTarget | LegacyCallbackTarget, invoice_root: Path, holding_run: Any,
) -> None:
    """TC-737-LOCK-EP-006: the second run is refused before it touches the root."""
    # Given: a run that owns the root, and the root as it is right now
    before = _tree(invoice_root)

    # When: a second run starts on the same root
    report = _run(invoice_root, target, "intruder")

    # Then: it fails with RunRootBusy and names its remedy
    assert (report.run_id, report.status, report.iterations) == ("intruder", "failed", [])
    assert report.error is not None
    assert (report.error["code"], report.error["name"]) == (_BUSY, "RunRootBusy")
    assert ERROR_CATALOG[_BUSY].remediation in report.error["message"]

    # And: it wrote nothing -- no report, no events, no job.failed
    assert _tree(invoice_root) == before

    # And: the holder finishes as if it had been alone
    holder = holding_run()
    assert (holder.status, holder.error) == ("success", None)
    assert not (invoice_root / "data" / "job.failed").exists()
    assert not (invoice_root / "data" / "logs" / "run_report_intruder.json").exists()
    assert (invoice_root / "data" / "logs" / "run_report_holder.json").is_file()


@pytest.mark.parametrize(
    ("function", "raises"),
    [
        pytest.param(failing_flow, None, id="TC-737-LOCK-EP-007-FAILED"),
        pytest.param(interrupting_flow, KeyboardInterrupt, id="TC-737-LOCK-EP-007-ESCAPING"),
    ],
)
def test_the_root_is_free_after_a_failed_or_escaping_run(function: Any, raises: type[BaseException] | None, invoice_root: Path) -> None:
    """TC-737-LOCK-EP-007: a run releases its root however it ends."""
    # Given: a run that fails, or whose exception escapes Runner.run
    if raises is None:
        assert _run(invoice_root, FlowTarget(function=function), "first").status == "failed"
    else:
        with pytest.raises(raises):
            _run(invoice_root, FlowTarget(function=function), "first")

    # When: the next run starts on the same root
    report = _run(invoice_root, FlowTarget(function=noop_flow), "second")

    # Then: it owns the root and succeeds
    assert (report.status, report.error) == ("success", None)


def test_sequential_runs_on_one_root_both_succeed__tc_737_lock_bv_003(invoice_root: Path) -> None:
    """TC-737-LOCK-BV-003: the lock serializes, it does not forbid reruns."""
    # When: two runs follow each other on one root
    first = _run(invoice_root, FlowTarget(function=noop_flow), "first")
    second = _run(invoice_root, FlowTarget(function=noop_flow), "second")

    # Then: both succeed
    assert (first.status, second.status) == ("success", "success")


def test_v1_entry_on_a_busy_root_exits_1_without_job_failed__tc_737_lock_ep_008(
    invoice_root: Path, holding_run: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-737-LOCK-EP-008: ``run(custom_dataset_function=...)`` keeps its failure exit, not the holder's artifacts."""
    # Given: a run that owns the root, and the v1 entry's working directory
    monkeypatch.chdir(invoice_root)
    before = _tree(invoice_root)

    # When: the v1 entry starts on the same root
    with pytest.raises(SystemExit) as exited:
        workflows.run(custom_dataset_function=noop_callback)

    # Then: v1's failure exit and the 3008 message on stderr
    assert exited.value.code == 1
    assert "RunRootBusy" in capsys.readouterr().err

    # And: the only new file is the v1 entry's own system log, opened before any run
    after = _tree(invoice_root)
    added = sorted(set(after) - set(before))
    assert all(name.startswith("logs/rdesys_") and name.endswith(".log") for name in added), added
    assert {name: after[name] for name in before} == before
    assert (holding_run().status, (invoice_root / "data" / "job.failed").exists()) == ("success", False)


def test_the_error_is_catalogued() -> None:
    """TC-737-LOCK-EP-006 (catalog): 3008 is an execution-band entry with a remedy."""
    # Given: the error catalog
    definition = ERROR_CATALOG[_BUSY]

    # Then: 3008 is RunRootBusy, with a reason slot and a remedy
    assert definition.name == "RunRootBusy"
    assert "{reason}" in definition.message_template
    assert definition.remediation
