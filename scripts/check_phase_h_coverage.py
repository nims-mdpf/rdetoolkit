# ruff: noqa: INP001
"""Enforce Phase H per-module branch coverage after a full Python 3.12 run."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


_INCLUDE_ARGS = (
    ("--include", "*/rdetoolkit/domain/artifacts.py"),
    ("--include", "*/rdetoolkit/report/run_report.py"),
    ("--include", "*/rdetoolkit/runner/executor.py"),
    ("--include", "*/rdetoolkit/runner/invoker.py"),
    ("--include", "*/rdetoolkit/runner/planner.py"),
    ("--include", "*/rdetoolkit/runner/finalize.py"),
)


def main(posargs: Sequence[str] | None = None) -> int:
    """Run each scoped coverage gate unless tox received focused test arguments.

    Args:
        posargs: Arguments forwarded to the preceding pytest command by tox.

    Returns:
        Zero when focused execution skips the gate or every module reaches 95%;
        otherwise the first failing coverage command's exit code.
    """
    focused_args = tuple(sys.argv[1:] if posargs is None else posargs)
    if focused_args:
        print("Phase H coverage gates skipped for focused tox posargs.")  # noqa: T201
        return 0

    for include_flag, include_pattern in _INCLUDE_ARGS:
        completed = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "coverage",
                "report",
                "--fail-under=95",
                include_flag,
                include_pattern,
            ],
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
