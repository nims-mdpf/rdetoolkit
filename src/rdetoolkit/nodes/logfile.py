"""Builtin node for a log file that a tile streams into an output directory."""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import Literal

from rdetoolkit.core.node import node
from rdetoolkit.types import OutputContext, OutputKind

DEFAULT_LOG_FORMAT = "%(asctime)s - [%(name)s](%(levelname)s) - %(message)s"
"""Line format of v1 ``rdelogger.get_logger(file_path=...)``."""

_LOG_FILE_MODES = frozenset({"a", "w"})


class ArtifactLogger:
    """Attach a file handler to one logger for the duration of a ``with`` block.

    Returned by the ``artifact_logger`` node. Entering the block adds a
    ``logging.FileHandler`` for the artifact path to the logger and returns
    the logger; leaving it removes and closes that handler and restores the
    logger's level, also when the block raises. Records logged inside the
    block, including an ERROR record logged while handling the exception,
    are in the file; records logged after it are not, so a logger shared by
    several tiles never writes into another tile's file.

    The handler is ordinary ``logging`` state of this process: threads in the
    process write to the file, other processes do not.
    """

    __slots__ = ("_encoding", "_fmt", "_handler", "_level", "_logger", "_mode", "_path", "_saved_level")

    def __init__(self, logger: logging.Logger, path: Path, *, fmt: str, level: int, mode: str, encoding: str) -> None:
        self._logger = logger
        self._path = path
        self._fmt = fmt
        self._level = level
        self._mode = mode
        self._encoding = encoding
        self._handler: logging.FileHandler | None = None
        self._saved_level = logging.NOTSET

    @property
    def logger(self) -> logging.Logger:
        """Logger the file handler is attached to."""
        return self._logger

    @property
    def path(self) -> Path:
        """Path of the log file artifact."""
        return self._path

    def __repr__(self) -> str:
        return f"ArtifactLogger(name={self._logger.name!r}, path={str(self._path)!r})"

    def __enter__(self) -> logging.Logger:
        if self._handler is not None:
            msg = f"{self!r} is already active"
            raise RuntimeError(msg)
        # delay=True: like v1 get_logger, the file is created by the first
        # record, so a tile that logs nothing leaves no empty file.
        handler = logging.FileHandler(self._path, mode=self._mode, encoding=self._encoding, delay=True)
        handler.setLevel(self._level)
        handler.setFormatter(logging.Formatter(self._fmt))
        self._saved_level = self._logger.level
        if self._logger.level == logging.NOTSET or self._logger.level > self._level:
            self._logger.setLevel(self._level)
        self._logger.addHandler(handler)
        self._handler = handler
        return self._logger

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        handler, self._handler = self._handler, None
        if handler is None:
            return
        try:
            self._logger.removeHandler(handler)
            self._logger.setLevel(self._saved_level)
        finally:
            handler.close()


@node(tags=["builtin", "logging"], version="2.0.0", idempotent=False)
def artifact_logger(
    out: OutputContext,
    filename: str,
    *,
    name: str | None = None,
    kind: OutputKind = "struct",
    fmt: str = DEFAULT_LOG_FORMAT,
    level: int = logging.DEBUG,
    mode: Literal["a", "w"] = "a",
    encoding: str = "utf-8",
) -> ArtifactLogger:
    """Declare a log file artifact that a logger streams into during a tile.

    The v2 counterpart of v1 ``rdelogger.get_logger(name, file_path=...)``.
    Use the result as a context manager; it yields the logger with a file
    handler attached until the block ends::

        with artifact_logger(out, "structured_log.txt", name="eis") as logger:
            logger.info("processing")

    The call is recorded in the call log like any node call; the file itself
    is written by the records logged inside the block.

    Args:
        out: Output resource context of the tile.
        filename: Simple output filename.
        name: Logger name. Defaults to the filename without its suffix.
        kind: Output directory kind, defaulting to structured data.
        fmt: ``logging.Formatter`` format of each line. The default matches
            v1 ``rdelogger.get_logger``.
        level: Lowest level written to the file. The logger's own level is
            lowered to it for the block when needed and restored afterwards.
        mode: ``"a"`` appends to an existing file (v1 behavior); ``"w"``
            truncates it at the first record.
        encoding: Character encoding of the file.

    Returns:
        Context manager that attaches the file handler while it is active.

    Raises:
        ValueError: If the filename, kind or mode is invalid.
    """
    if mode not in _LOG_FILE_MODES:
        msg = f"Unknown log file mode: {mode!r} (expected 'a' or 'w')"
        raise ValueError(msg)
    path = out.path_for(kind, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name if name is not None else Path(filename).stem)
    return ArtifactLogger(logger, path, fmt=fmt, level=level, mode=mode, encoding=encoding)
