"""Exclusive ownership of one data root for the duration of a run (#737).

Two runs on one data root interleave their writes of the shared tile invoices,
so a run can read a file the other is rewriting. The Runner therefore owns its
data root from before the first write until the report is persisted. A second
run on the same root is refused (3008) before it writes anything.

Ownership has two layers. A process-wide set keeps threads of one process
apart. An advisory OS lock on a file in the temporary directory keeps
processes apart. The file is keyed by the resolved data root, so no lock file
appears in the run's artifacts; the OS drops the lock when its process dies, so
a killed run leaves no stale lock; and the owner removes the file (and the
then-empty directory) when it releases, so a finished run leaves nothing in the
temporary directory either. Because a file can be removed between another
run's ``open`` and its lock, an acquirer keeps a lock only on the file that is
still at the path, and retries otherwise. When the directory cannot be used,
only the process-wide layer applies.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
from contextlib import suppress
from pathlib import Path

from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError

_RUN_ROOT_BUSY_CODE = 3008
#: Opens retried while previous owners remove the file or directory under us.
_ATTEMPTS = 8

_HELD: set[str] = set()
_HELD_GUARD = threading.Lock()


def default_lock_dir() -> Path:
    """Return the directory holding the cross-process lock files."""
    return Path(tempfile.gettempdir()) / "rdetoolkit-run-locks"


class DataRootLock:
    """Non-blocking exclusive ownership of one data root.

    Args:
        data_root: The run's resolved data root; symlinks are resolved again here.
        lock_dir: Directory of the cross-process lock files. ``None`` uses
            :func:`default_lock_dir`.
    """

    def __init__(self, data_root: Path, *, lock_dir: Path | None = None) -> None:
        self._key = os.path.normcase(str(data_root.resolve()))
        self._lock_dir = lock_dir if lock_dir is not None else default_lock_dir()
        self._fd: int | None = None
        self._held = False

    def acquire(self) -> bool:
        """Take the root if no other run owns it.

        Returns:
            ``True`` when this lock now owns the root, ``False`` when another run
            in this or another process does.
        """
        with _HELD_GUARD:
            if self._key in _HELD:
                return False
            _HELD.add(self._key)
        owned, fd = self._lock_file()
        if not owned:
            self._forget()
            return False
        self._fd = fd
        self._held = True
        return True

    def release(self) -> None:
        """Give the root up; releasing an unheld lock does nothing."""
        if not self._held:
            return
        if self._fd is not None:
            _release_file(self._fd, self._lock_path, self._lock_dir)
            self._fd = None
        self._held = False
        self._forget()

    def _forget(self) -> None:
        with _HELD_GUARD:
            _HELD.discard(self._key)

    @property
    def _lock_path(self) -> Path:
        return self._lock_dir / f"{hashlib.sha256(self._key.encode('utf-8')).hexdigest()[:32]}.lock"

    def _lock_file(self) -> tuple[bool, int | None]:
        """Lock the file currently at the lock path.

        Returns:
            ``(False, None)`` when another process owns it, ``(True, fd)`` when
            this lock does, and ``(True, None)`` when no lock file can be used.
        """
        for _ in range(_ATTEMPTS):
            try:
                self._lock_dir.mkdir(parents=True, exist_ok=True)
                fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            except FileNotFoundError:
                continue  # the previous owner removed the directory just now
            except OSError:
                return True, None
            if not _try_lock(fd):
                os.close(fd)
                return False, None
            if _is_current(fd, self._lock_path):
                return True, fd
            # The previous owner removed this file after we opened it.
            _unlock(fd)
            os.close(fd)
        return True, None


def run_root_busy_error(data_root: Path) -> RdeExecutionError:
    """Return the 3008 error of a run refused because its data root is owned.

    Args:
        data_root: The refused run's data root; only its name is reported.

    Returns:
        The catalogued error, with its remediation in the message.
    """
    definition = ERROR_CATALOG[_RUN_ROOT_BUSY_CODE]
    reason = f"another run is using the data root {data_root.name!r}"
    return RdeExecutionError(
        code=_RUN_ROOT_BUSY_CODE,
        name=definition.name,
        message=f"{definition.message_template.format(reason=reason)} Remediation: {definition.remediation}",
    )


if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        # msvcrt locks the bytes at the current position: always byte 0.
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

    def _is_current(fd: int, path: Path) -> bool:
        # An open file cannot be removed on Windows, so the locked file is the one at the path.
        return True

    def _release_file(fd: int, path: Path, directory: Path) -> None:
        _unlock(fd)
        os.close(fd)
        # Fails harmlessly while another process still has the file open.
        with suppress(OSError):
            path.unlink()
        with suppress(OSError):
            directory.rmdir()

else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)

    def _is_current(fd: int, path: Path) -> bool:
        try:
            current = os.stat(path)
        except OSError:
            return False
        opened = os.fstat(fd)
        return (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino)

    def _release_file(fd: int, path: Path, directory: Path) -> None:
        # Removed while still locked: an acquirer that opened it meanwhile sees
        # that it is no longer at the path and retries on a fresh file.
        with suppress(OSError):
            path.unlink()
        with suppress(OSError):
            directory.rmdir()
        _unlock(fd)
        os.close(fd)
