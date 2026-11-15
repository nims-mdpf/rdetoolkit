"""Isolated real-Runner execution for tests: ``RdeTestRunner`` and ``RdeTestResult``.

The module never imports pytest, so ``RdeTestRunner`` also works in plain
scripts; the ``rde_runner`` pytest fixture is a thin wrapper defined in
``rdetoolkit.testing.plugin``.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from rdetoolkit.report.run_report import RunReport
    from rdetoolkit.templates.base import ProcessingTemplate
    from rdetoolkit.types import RdeConfig


@dataclass(frozen=True)
class RdeIterationSummary:
    """One iteration (data tile) of a test run, as recorded in the RunReport.

    Attributes:
        index: Tile index (``0`` writes below the data root, ``>= 1`` below
            ``divided/<index:04d>``).
        datatile_id: The tile identifier the Runner recorded.
        status: ``"completed"`` or ``"failed"``.
        error_code: Catalog code of the tile's error, if it failed.
        error_name: Catalog name of the tile's error, if it failed.
        error_message: Message of the tile's error, if it failed.
    """

    index: int
    datatile_id: str
    status: str
    error_code: int | None = None
    error_name: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class RdeTestResult:
    """Inspectable outcome of one isolated test run.

    A failed run is returned, not raised: call ``assert_success`` (or inspect
    ``report``) to turn it into a test failure.

    Attributes:
        report: The RunReport the real Runner produced.
        project_root: The staged copy of the project the run executed in.
        data_root: The staged data root, resolved by the production rule.
        report_path: ``logs/run_report_<run_id>.json``, if it was written.
        events_path: ``logs/events_<run_id>.jsonl``, if it was written.
        diagnostics_path: ``logs/diagnostics_<run_id>.json``, if it was written.
        job_failed_path: ``job.failed``, if the run wrote the failure marker.
    """

    report: RunReport
    project_root: Path
    data_root: Path
    report_path: Path | None
    events_path: Path | None
    diagnostics_path: Path | None
    job_failed_path: Path | None

    @property
    def status(self) -> str:
        """Return the run status: ``"success"``, ``"partial"`` or ``"failed"``."""
        return self.report.status

    @property
    def iterations(self) -> tuple[RdeIterationSummary, ...]:
        """Return one summary per recorded iteration, in report order."""
        return tuple(_iteration_summary(iteration) for iteration in self.report.iterations)

    def artifact_path(self, name: str | os.PathLike[str]) -> Path:
        """Resolve an artifact name relative to the isolated data root.

        Args:
            name: Relative artifact path such as ``"structured/result.csv"``.

        Returns:
            The artifact's path below ``data_root`` (it may not exist).

        Raises:
            TypeError: If ``name`` is not a string or path.
            ValueError: If ``name`` is empty, absolute, or leaves the data root.
        """
        return self.data_root.joinpath(*relative_artifact(name).parts)

    def assert_success(self) -> None:
        """Fail with a readable explanation unless the run succeeded.

        Raises:
            AssertionError: If ``status`` is not ``"success"``. The message
                names the status, the run and tile errors (code, name,
                message, recorded stack trace) and where the artifacts are.
        """
        if self.status != "success":
            raise AssertionError(self.failure_summary(expected_status="success"))

    def failure_summary(self, *, expected_status: str) -> str:
        """Return a multi-line explanation of this run for an assertion message.

        Args:
            expected_status: The status the test expected.

        Returns:
            The status line, run error, failed iterations and artifact paths.
        """
        lines = [
            f"RDE run status was {self.status!r}, expected {expected_status!r} "
            f"(flow {self.report.flow_id!r}, mode {self.report.mode!r}, run {self.report.run_id})",
        ]
        if self.report.error is not None:
            lines.append(f"run error: {_describe_error(self.report.error)}")
        for iteration in self.report.iterations:
            error = iteration.get("error")
            if not isinstance(error, Mapping):
                continue
            lines.append(
                f"iteration {iteration.get('index')} (datatile {iteration.get('datatile_id')!r}) failed: "
                f"{_describe_error(error)}",
            )
            stacktrace = iteration.get("stacktrace")
            if isinstance(stacktrace, str) and stacktrace:
                lines.extend(f"    {line}" for line in stacktrace.rstrip().splitlines())
        lines.append(f"data root: {self.data_root}")
        lines.extend(
            f"{label}: {path}"
            for label, path in (
                ("job.failed", self.job_failed_path),
                ("run report", self.report_path),
                ("diagnostics", self.diagnostics_path),
            )
            if path is not None
        )
        return "\n".join(lines)


class RdeTestRunner:
    """Run a flow on a staged copy of an RDE project through the real Runner.

    Every ``run`` copies the project into a new directory below ``base_dir``
    (pytest's per-test ``tmp_path`` for the ``rde_runner`` fixture), so the
    source fixture is never written and sequential runs never share a root.
    The staged copies are kept for inspection after the run.
    """

    def __init__(self, base_dir: Path) -> None:
        """Create a runner that stages projects below ``base_dir``.

        Args:
            base_dir: Directory that receives one ``run-NNN`` directory per
                run. It is created on the first run.
        """
        self.base_dir = Path(base_dir)

    def run(
        self,
        *,
        flow: Callable[..., Any] | type[ProcessingTemplate],
        project: str | os.PathLike[str],
        config: RdeConfig | Mapping[str, Any] | None = None,
    ) -> RdeTestResult:
        """Stage ``project`` and run ``flow`` on the copy, as ``workflows.run(flow=...)`` does.

        The data root is resolved from the staged copy with the production
        rule (``<project>/data`` or an alias-flat project), the working
        directory is the staged project during the run, and the caller's
        working directory is restored afterwards, even when the run raises.

        Args:
            flow: Flow callable or concrete ``ProcessingTemplate`` subclass.
            project: Project directory (``<project>/data``) or an alias-flat
                data root. A relative path is resolved against the cwd.
            config: Optional ``RdeConfig`` or override mapping, passed to the
                Runner exactly like ``workflows.run(flow=..., config=...)``.

        Returns:
            The inspectable result; a failed run is returned, not raised.

        Raises:
            TypeError: If ``flow`` is ``None`` (the v1 callback entry is not
                a flow), or the Runner rejects ``flow``.
            FileNotFoundError: If ``project`` does not exist.
            NotADirectoryError: If ``project`` is not a directory.
        """
        if flow is None:
            msg = "RdeTestRunner.run requires a flow callable or ProcessingTemplate subclass, got None"
            raise TypeError(msg)
        source = _existing_project(Path(project))
        staged = self._stage(source)
        from rdetoolkit import workflows  # noqa: PLC0415
        from rdetoolkit.runner.paths import resolve_data_root  # noqa: PLC0415

        # Resolved before the run like workflows.run does: an alias-flat root
        # must not be re-resolved after the Runner has created directories.
        data_root = resolve_data_root(staged)
        with _chdir(staged):
            # Same narrowing as cli/run_cmd.py: the flow entry returns a RunReport.
            report = cast("RunReport", workflows.run(flow=flow, config=config))
        return _collect_result(report, project_root=staged, data_root=data_root)

    def _stage(self, source: Path) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        index = 0
        while True:
            run_dir = self.base_dir / f"run-{index:03d}"
            try:
                # exist_ok=False makes the claim atomic, so two runners on the
                # same base directory can never pick the same directory.
                run_dir.mkdir()
            except FileExistsError:
                index += 1
                continue
            break
        staged = run_dir / source.name
        # Symlinks are copied by content: a flow that writes through a staged
        # input must never reach the file the source project points at.
        shutil.copytree(source, staged, symlinks=False)
        return staged


def relative_artifact(name: str | os.PathLike[str]) -> PurePosixPath:
    """Validate an artifact name relative to an RDE data root.

    Both separators are treated as path separators, so a name is rejected the
    same way on every platform.

    Args:
        name: Candidate relative artifact path.

    Returns:
        The normalized relative path.

    Raises:
        TypeError: If ``name`` is not a string or ``os.PathLike`` of ``str``.
        ValueError: If ``name`` is empty, names the root itself, is absolute
            (POSIX, drive or UNC form) or contains a ``..`` component.
    """
    if not isinstance(name, (str, os.PathLike)):
        msg = f"artifact path must be a str or os.PathLike, got {type(name).__name__}"
        raise TypeError(msg)
    text = os.fspath(name)
    if not isinstance(text, str):
        msg = f"artifact path must be text, got {type(text).__name__}"
        raise TypeError(msg)
    posix = PurePosixPath(text.replace("\\", "/"))
    windows = PureWindowsPath(text)
    if not text.strip() or not posix.parts:
        msg = f"artifact path {text!r} must name a file or directory below the data root"
        raise ValueError(msg)
    if posix.is_absolute() or windows.drive or windows.root:
        msg = f"artifact path {text!r} must be relative to the data root, not absolute"
        raise ValueError(msg)
    if ".." in posix.parts:
        msg = f"artifact path {text!r} must not leave the data root ('..' is not allowed)"
        raise ValueError(msg)
    return posix


def _existing_project(project: Path) -> Path:
    if not project.exists():
        msg = f"RDE test project does not exist: {project}"
        raise FileNotFoundError(msg)
    if not project.is_dir():
        msg = f"RDE test project is not a directory: {project}"
        raise NotADirectoryError(msg)
    return project.resolve()


def _collect_result(report: RunReport, *, project_root: Path, data_root: Path) -> RdeTestResult:
    logs = data_root / "logs"
    return RdeTestResult(
        report=report,
        project_root=project_root,
        data_root=data_root,
        report_path=_if_file(logs / f"run_report_{report.run_id}.json"),
        events_path=_if_file(logs / f"events_{report.run_id}.jsonl"),
        diagnostics_path=_if_file(logs / f"diagnostics_{report.run_id}.json"),
        job_failed_path=_if_file(data_root / "job.failed"),
    )


def _if_file(path: Path) -> Path | None:
    return path if path.is_file() else None


def _iteration_summary(iteration: Mapping[str, Any]) -> RdeIterationSummary:
    error = iteration.get("error")
    error_map: Mapping[str, Any] = error if isinstance(error, Mapping) else {}
    code = error_map.get("code")
    name = error_map.get("name")
    message = error_map.get("message")
    return RdeIterationSummary(
        index=int(iteration.get("index", 0)),
        datatile_id=str(iteration.get("datatile_id", "")),
        status=str(iteration.get("status", "")),
        error_code=code if isinstance(code, int) else None,
        error_name=name if isinstance(name, str) else None,
        error_message=message if isinstance(message, str) else None,
    )


def _describe_error(error: Mapping[str, Any]) -> str:
    return f"[{error.get('code')} {error.get('name')}] {error.get('message')}"


@contextmanager
def _chdir(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
