"""Isolated real-Runner execution for tests: ``RdeTestRunner`` and ``RdeTestResult``.

The module never imports pytest, so ``RdeTestRunner`` also works in plain
scripts; the ``rde_runner`` pytest fixture is a thin wrapper defined in
``rdetoolkit.testing.plugin``.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, cast

from rdetoolkit.testing import assertions as _assertions
from rdetoolkit.testing import snapshot as _snapshot
from rdetoolkit.testing.assertions import DEFAULT_MAX_BYTES

if TYPE_CHECKING:
    from rdetoolkit.report.run_report import RunReport
    from rdetoolkit.templates.base import ProcessingTemplate
    from rdetoolkit.types import RdeConfig

#: Artifacts resolved through ``RdeTestResult.artifact_path`` while an
#: ``rde_check`` runs (``None`` otherwise), so a failing check can name the
#: artifacts and tiles it inspected (#693).
ARTIFACT_ACCESS: ContextVar[list[PurePosixPath] | None] = ContextVar("rdetoolkit_testing_artifact_access", default=None)


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
        relative = relative_artifact(name)
        accessed = ARTIFACT_ACCESS.get()
        if accessed is not None:
            accessed.append(relative)
        return self.data_root.joinpath(*relative.parts)

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
            (f"RDE run status was {self.status!r}, expected {expected_status!r} "
            f"(flow {self.report.flow_id!r}, mode {self.report.mode!r}, run {self.report.run_id})"),
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

    # Artifact reading and assertions (#692). The logic lives in
    # ``rdetoolkit.testing.assertions`` / ``.snapshot`` so it is also usable
    # as plain functions; these methods only bind the result.

    def read_bytes(self, name: str | os.PathLike[str], *, max_bytes: int | None = DEFAULT_MAX_BYTES) -> bytes:
        """Return an artifact's bytes; see :func:`rdetoolkit.testing.assertions.read_bytes`."""
        return _assertions.read_bytes(self, name, max_bytes=max_bytes)

    def read_text(self, name: str | os.PathLike[str], *, encoding: str = "utf-8", max_bytes: int | None = DEFAULT_MAX_BYTES) -> str:
        """Return an artifact's text; see :func:`rdetoolkit.testing.assertions.read_text`."""
        return _assertions.read_text(self, name, encoding=encoding, max_bytes=max_bytes)

    def read_json(self, name: str | os.PathLike[str], *, max_bytes: int | None = DEFAULT_MAX_BYTES) -> Any:
        """Return an artifact's parsed JSON; see :func:`rdetoolkit.testing.assertions.read_json`."""
        return _assertions.read_json(self, name, max_bytes=max_bytes)

    def read_csv(
        self, name: str | os.PathLike[str], *, encoding: str = "utf-8", max_bytes: int | None = DEFAULT_MAX_BYTES,
    ) -> list[dict[str, str]]:
        """Return a CSV artifact's rows; see :func:`rdetoolkit.testing.assertions.read_csv`."""
        return _assertions.read_csv(self, name, encoding=encoding, max_bytes=max_bytes)

    def iter_csv(self, name: str | os.PathLike[str], *, encoding: str = "utf-8") -> Iterator[dict[str, str]]:
        """Stream a CSV artifact's rows; see :func:`rdetoolkit.testing.assertions.iter_csv`."""
        return _assertions.iter_csv(self, name, encoding=encoding)

    def assert_status(self, expected: str) -> None:
        """Assert the run status; see :func:`rdetoolkit.testing.assertions.assert_status`."""
        _assertions.assert_status(self, expected)

    def assert_error_code(self, code: int) -> None:
        """Assert a recorded catalog code; see :func:`rdetoolkit.testing.assertions.assert_error_code`."""
        _assertions.assert_error_code(self, code)

    def assert_artifact(self, name: str | os.PathLike[str], *, exists: bool = True) -> None:
        """Assert presence or absence; see :func:`rdetoolkit.testing.assertions.assert_artifact`."""
        _assertions.assert_artifact(self, name, exists=exists)

    def assert_tree(
        self,
        expected: Iterable[str | os.PathLike[str]],
        *,
        root: str | os.PathLike[str] | None = None,
        ignore: Iterable[str] = (),
    ) -> None:
        """Assert the exact file set; see :func:`rdetoolkit.testing.assertions.assert_tree`."""
        _assertions.assert_tree(self, expected, root=root, ignore=ignore)

    def assert_json_subset(self, name: str | os.PathLike[str], expected: Mapping[str, Any]) -> None:
        """Assert JSON containment; see :func:`rdetoolkit.testing.assertions.assert_json_subset`."""
        _assertions.assert_json_subset(self, name, expected)

    def assert_json_equal(self, name: str | os.PathLike[str], expected: Any) -> None:
        """Assert exact JSON content; see :func:`rdetoolkit.testing.assertions.assert_json_equal`."""
        _assertions.assert_json_equal(self, name, expected)

    def assert_csv_columns(self, name: str | os.PathLike[str], columns: Iterable[str], *, exact: bool = False) -> None:
        """Assert a CSV header; see :func:`rdetoolkit.testing.assertions.assert_csv_columns`."""
        _assertions.assert_csv_columns(self, name, columns, exact=exact)

    def assert_csv_rows(self, name: str | os.PathLike[str], expected: Sequence[Mapping[str, str]]) -> None:
        """Assert every CSV cell; see :func:`rdetoolkit.testing.assertions.assert_csv_rows`."""
        _assertions.assert_csv_rows(self, name, expected)

    def assert_metadata_valid(
        self,
        name: str | os.PathLike[str] = "meta/metadata.json",
        *,
        definition: str | os.PathLike[str] | None = "tasksupport/metadata-def.json",
    ) -> None:
        """Assert metadata validity; see :func:`rdetoolkit.testing.assertions.assert_metadata_valid`."""
        _assertions.assert_metadata_valid(self, name, definition=definition)

    def assert_invoice_valid(
        self,
        name: str | os.PathLike[str] = "invoice/invoice.json",
        *,
        schema: str | os.PathLike[str] = "tasksupport/invoice.schema.json",
    ) -> None:
        """Assert invoice validity; see :func:`rdetoolkit.testing.assertions.assert_invoice_valid`."""
        _assertions.assert_invoice_valid(self, name, schema=schema)

    def assert_snapshot(
        self,
        artifact: str | os.PathLike[str],
        golden: str | os.PathLike[str],
        *,
        ignore_fields: Iterable[str] = (),
        ignore_columns: Iterable[str] = (),
        ignore_files: Iterable[str] = (),
        max_bytes: int = DEFAULT_MAX_BYTES,
        allow_raw: bool = False,
    ) -> None:
        """Compare with an approved golden copy; see :func:`rdetoolkit.testing.snapshot.assert_snapshot`.

        Changes are approved only by ``pytest --rde-update-snapshots`` (refused
        under CI); no argument here can approve one.
        """
        _snapshot.assert_snapshot(
            self,
            artifact,
            golden,
            ignore_fields=ignore_fields,
            ignore_columns=ignore_columns,
            ignore_files=ignore_files,
            max_bytes=max_bytes,
            allow_raw=allow_raw,
        )

    def assert_checks(self, *checks: Callable[[RdeTestResult], object]) -> None:
        """Run reusable output checks explicitly; see :func:`rdetoolkit.testing.checks.run_checks`.

        Raises:
            AssertionError: Naming every failing check with its rule ID, the
                artifacts it read and the assertion.
        """
        from rdetoolkit.testing.checks import run_checks  # noqa: PLC0415 - checks imports this module

        failures = run_checks(self, checks)
        if failures:
            raise AssertionError("\n".join(failures))


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
        # Kept so a failing test can list where its runs were retained (#694).
        self._results: list[RdeTestResult] = []

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
        result = _collect_result(report, project_root=staged, data_root=data_root)
        self._results.append(result)
        return result

    @property
    def results(self) -> tuple[RdeTestResult, ...]:
        """Return the results of every completed ``run``, in order."""
        return tuple(self._results)

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


def retained_runs_report(results: Sequence[RdeTestResult]) -> str:
    """Return where each run of a failing test was retained, one block per run.

    Args:
        results: The runs, in execution order.

    Returns:
        Lines such as ``run 1: status 'failed' (flow 'x', run <id>)`` followed
        by the data root and the run report, diagnostics and ``job.failed``
        paths that exist; empty when there were no runs.
    """
    lines: list[str] = []
    for number, result in enumerate(results, start=1):
        lines.append(f"run {number}: status {result.status!r} (flow {result.report.flow_id!r}, run {result.report.run_id})")
        lines.append(f"  data root: {result.data_root}")
        lines.extend(
            f"  {label}: {path}"
            for label, path in (
                ("run report", result.report_path),
                ("diagnostics", result.diagnostics_path),
                ("job.failed", result.job_failed_path),
            )
            if path is not None
        )
    return "\n".join(lines)


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
