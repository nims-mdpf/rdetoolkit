"""Builtin node for running an external converter program from a flow."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from rdetoolkit.core.node import node
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.rdelogger import get_logger

_WINE = "wine"
_STDERR_TAIL_LINES = 5
_STDERR_TAIL_CHARS = 1000

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CompletedProgram:
    """Result of a finished ``run_program`` call.

    Attributes:
        args: Command line as executed, including a ``wine`` prefix and
            converted paths.
        returncode: Exit code of the program.
        stdout: Standard output, decoded as UTF-8 with replacement.
        stderr: Standard error, decoded as UTF-8 with replacement.
        duration: Wall-clock run time in seconds.
    """

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float


def _on_windows() -> bool:
    return os.name == "nt"


def to_wine_path(path: str | Path) -> str:
    """Write a host path the way a Windows program sees it under ``wine="auto"``.

    Outside Windows, an absolute path is placed on wine's default ``Z:`` drive
    (the host root) and separators become backslashes; a relative path only has
    its separators changed. On Windows the path is returned unchanged. Use this
    for paths embedded in option strings such as ``-OutputFolder:<path>``;
    ``run_program`` converts ``Path`` arguments itself.

    Args:
        path: Host path.

    Returns:
        The path as text for the Windows program.
    """
    if _on_windows():
        return str(path)
    posix = PurePosixPath(path)
    text = f"Z:{posix}" if posix.is_absolute() else str(posix)
    return text.replace("/", "\\")


def _command(args: Sequence[str | Path], *, wine: bool | Literal["auto"]) -> tuple[str, ...]:
    if isinstance(args, (str, bytes)):
        msg = "run_program args must be a sequence of arguments, not a single string"
        raise TypeError(msg)
    if not args:
        msg = "run_program args must name a program"
        raise ValueError(msg)
    under_wine = wine is True or (wine == "auto" and not _on_windows())
    if not under_wine:
        return tuple(str(arg) for arg in args)
    return (_WINE, *(to_wine_path(arg) if isinstance(arg, Path) else arg for arg in args))


def _stderr_tail(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return " | ".join(lines[-_STDERR_TAIL_LINES:])[-_STDERR_TAIL_CHARS:]


@node(tags=["builtin", "external"], version="2.0.0", idempotent=False)
def run_program(
    args: Sequence[str | Path], *, cwd: Path | None = None, timeout: float | None = None,
    env: Mapping[str, str] | None = None, wine: bool | Literal["auto"] = False,
    error_code: int | None = None, error_message: str | None = None,
) -> CompletedProgram:
    """Run an external program, such as a vendor converter, and wait for it.

    The program writes its outputs itself; pass output directories from
    ``OutputContext`` (``out.struct``, ``out.logs``) as arguments. Output
    streams are captured. Every failure is a ``StructuredError``, so it
    reaches ``RunReport.error`` and ``job.failed`` with ``error_code``
    instead of ErrorCode 3001. Its default message is one line naming the
    command, the exit code, the run time and the end of stderr; the command
    line and the outcome are also logged.

    Args:
        args: Program and its arguments. ``Path`` arguments are converted for
            wine; text arguments are passed unchanged.
        cwd: Working directory of the program.
        timeout: Seconds to wait before the program is killed.
        env: Variables added to, or overriding, the inherited environment.
        wine: ``True`` runs the program with ``wine`` and converts ``Path``
            arguments with ``to_wine_path``; ``"auto"`` does so only outside
            Windows.
        error_code: ``StructuredError`` code for failures. Defaults to 1.
        error_message: Message for failures, used verbatim.

    Returns:
        The executed command line, exit code, output streams and run time.

    Raises:
        StructuredError: If the program cannot be started, times out, or exits
            with a non-zero code. For a non-zero exit, ``eobj`` is the
            ``CompletedProgram``.
        TypeError: If ``args`` is a single string.
        ValueError: If ``args`` is empty.
    """
    command = _command(args, wine=wine)
    cmdline = shlex.join(command)
    code = 1 if error_code is None else error_code
    environment = None if env is None else {**os.environ, **env}
    logger.info(f"run_program: {cmdline}")
    start = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603 - the command is the caller's, never a shell string
            command, cwd=cwd, env=environment, timeout=timeout, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=False,
        )
    except subprocess.TimeoutExpired as exc:
        detail = f"External program timed out after {timeout}s; command: {cmdline}"
        logger.error(detail)
        raise StructuredError(error_message or detail, code) from exc
    except OSError as exc:
        detail = f"Cannot start external program {command[0]!r}: {exc.strerror or exc}; command: {cmdline}"
        logger.error(detail)
        raise StructuredError(error_message or detail, code) from exc
    result = CompletedProgram(command, completed.returncode, completed.stdout, completed.stderr, time.perf_counter() - start)
    if result.returncode == 0:
        logger.info(f"run_program: exit code 0 after {result.duration:.2f}s")
        return result
    detail = f"External program failed with exit code {result.returncode} after {result.duration:.2f}s; command: {cmdline}"
    tail = _stderr_tail(result.stderr)
    if tail:
        detail = f"{detail}; stderr: {tail}"
    logger.error(detail)
    raise StructuredError(error_message or detail, code, eobj=result)
