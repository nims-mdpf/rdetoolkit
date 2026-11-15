"""Declarative RDE integration test cases: the ``rde_case`` marker.

``rde_case(...)`` only attaches pytest marker metadata to a test. Nothing is
validated, copied or executed when the test module is imported or collected;
the ``rde_run`` fixture (``rdetoolkit.testing.plugin``) reads the marker at
fixture setup, runs the case through ``RdeTestRunner``, and the plugin checks
the declared expectations before the test body runs.

pytest is imported only when ``rde_case`` is called, so importing this module
(and ``rdetoolkit.testing``) works without pytest installed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from rdetoolkit.testing.runner import RdeTestResult, relative_artifact

if TYPE_CHECKING:
    from pytest import MarkDecorator

    from rdetoolkit.templates.base import ProcessingTemplate
    from rdetoolkit.types import RdeConfig

#: Marker name registered by the rdetoolkit pytest plugin.
MARKER_NAME = "rde_case"

_STATUSES = ("success", "partial", "failed")
_PARAMETERS = ("flow", "project", "expect_status", "expect_files", "expect_error_code", "expect_phase", "config")
_REQUIRED = ("flow", "project")


class RdeCaseError(ValueError):
    """An ``rde_case`` marker whose parameters cannot describe a runnable case."""


@dataclass(frozen=True)
class RdeCase:
    """Validated parameters of one ``rde_case`` marker.

    Attributes:
        flow: Flow callable or concrete ``ProcessingTemplate`` subclass.
        project: Absolute path of the source project to stage.
        expect_status: Expected run status.
        expect_files: Artifacts expected below the isolated data root.
        expect_error_code: Catalog code expected on the run or a tile.
        expect_phase: Phase expected in the diagnostics sidecar.
        config: Configuration passed to the Runner.
    """

    flow: Callable[..., Any]
    project: Path
    expect_status: str = "success"
    expect_files: tuple[PurePosixPath, ...] = ()
    expect_error_code: int | None = None
    expect_phase: str | None = None
    config: RdeConfig | Mapping[str, Any] | None = None


def rde_case(
    *,
    flow: Callable[..., Any] | type[ProcessingTemplate],
    project: str | os.PathLike[str],
    expect_status: str = "success",
    expect_files: Sequence[str | os.PathLike[str]] = (),
    expect_error_code: int | None = None,
    expect_phase: str | None = None,
    config: RdeConfig | Mapping[str, Any] | None = None,
) -> MarkDecorator:
    """Declare an RDE integration case for a test that requests ``rde_run``.

    The returned object is an ordinary pytest mark: decorate a test with it,
    or pass it to ``pytest.param(..., marks=...)`` to give each parameter its
    own case. Parameters are validated when the ``rde_run`` fixture is set
    up, never at import or collection time.

    Args:
        flow: Flow callable or concrete ``ProcessingTemplate`` subclass.
        project: Project directory (``<project>/data``) or alias-flat data
            root. A relative path is resolved against pytest's rootdir.
        expect_status: ``"success"`` (default), ``"partial"`` or ``"failed"``.
        expect_files: Artifact paths relative to the isolated data root that
            must exist after the run (absolute or ``..`` paths are refused).
        expect_error_code: Catalog code the run or one of its tiles must
            record. Only valid with a non-success ``expect_status``.
        expect_phase: Phase that the diagnostics sidecar
            (``logs/diagnostics_<run_id>.json``) must record. Only valid with a
            non-success ``expect_status``.
        config: ``RdeConfig`` or override mapping for the run.

    Returns:
        The ``pytest.mark.rde_case`` mark carrying these parameters.

    Raises:
        ImportError: If pytest is not installed.
    """
    try:
        import pytest  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - exercised in a subprocess without pytest
        msg = "rdetoolkit.testing.rde_case requires pytest; install pytest to declare RDE test cases"
        raise ImportError(msg) from exc
    return pytest.mark.rde_case(
        flow=flow,
        project=project,
        expect_status=expect_status,
        expect_files=expect_files,
        expect_error_code=expect_error_code,
        expect_phase=expect_phase,
        config=config,
    )


def case_from_marker(args: Sequence[object], kwargs: Mapping[str, object], *, rootpath: Path) -> RdeCase:
    """Validate an ``rde_case`` marker's parameters.

    Args:
        args: Positional marker arguments (none are accepted).
        kwargs: Keyword marker arguments.
        rootpath: pytest's rootdir, the base of a relative ``project``.

    Returns:
        The validated case.

    Raises:
        RdeCaseError: With a message naming the offending parameter.
    """
    if args:
        msg = "rde_case takes keyword arguments only (flow=..., project=..., ...)"
        raise RdeCaseError(msg)
    unknown = sorted(set(kwargs) - set(_PARAMETERS))
    if unknown:
        msg = f"rde_case got unknown parameter(s) {', '.join(unknown)}; allowed: {', '.join(_PARAMETERS)}"
        raise RdeCaseError(msg)
    missing = [name for name in _REQUIRED if kwargs.get(name) is None]
    if missing:
        msg = f"rde_case requires {' and '.join(f'{name}=' for name in missing)}"
        raise RdeCaseError(msg)
    expect_status = _status(kwargs.get("expect_status", "success"))
    expect_error_code = _error_code(kwargs.get("expect_error_code"))
    expect_phase = _phase(kwargs.get("expect_phase"))
    if expect_status == "success" and (expect_error_code is not None or expect_phase is not None):
        msg = "rde_case expect_error_code/expect_phase describe a failure; set expect_status='failed' or 'partial'"
        raise RdeCaseError(msg)
    return RdeCase(
        flow=_flow(kwargs["flow"]),
        project=_project(kwargs["project"], rootpath),
        expect_status=expect_status,
        expect_files=_expected_files(kwargs.get("expect_files", ())),
        expect_error_code=expect_error_code,
        expect_phase=expect_phase,
        config=_config(kwargs.get("config")),
    )


def check_case(case: RdeCase, result: RdeTestResult) -> list[str]:
    """Return one message per declared expectation the result violates.

    Args:
        case: The validated case.
        result: The result of running it.

    Returns:
        Failure messages; empty when every expectation holds.
    """
    failures: list[str] = []
    if result.status != case.expect_status:
        failures.append(result.failure_summary(expected_status=case.expect_status))
    if case.expect_error_code is not None:
        codes = sorted(set(_recorded_codes(result)))
        if case.expect_error_code not in codes:
            failures.append(f"rde_case expected error code {case.expect_error_code}; the run recorded {codes or 'none'}")
    if case.expect_phase is not None:
        failures.extend(_phase_failures(case.expect_phase, result))
    missing = [str(name) for name in case.expect_files if not result.artifact_path(name).exists()]
    if missing:
        failures.append(f"rde_case expected artifact(s) missing below data root {result.data_root}: {missing}")
    return failures


def missing_rde_run_message(nodeid: str) -> str:
    """Return the setup failure for a marked test that never requests ``rde_run``."""
    return (
        f"{nodeid} is marked rde_case but does not request the rde_run fixture, so the case would never run; "
        "add an 'rde_run' parameter to the test"
    )


def missing_marker_message(nodeid: str) -> str:
    """Return the setup failure for ``rde_run`` requested without a case."""
    return (
        f"{nodeid} requests the rde_run fixture but has no rde_case marker; decorate the test with "
        "rdetoolkit.testing.rde_case(flow=..., project=...) or use the rde_runner fixture directly"
    )


def _flow(value: object) -> Callable[..., Any]:
    if not callable(value):
        msg = f"rde_case flow= must be a flow callable or ProcessingTemplate subclass, got {type(value).__name__}"
        raise RdeCaseError(msg)
    return value


def _project(value: object, rootpath: Path) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        msg = f"rde_case project= must be a str or os.PathLike, got {type(value).__name__}"
        raise RdeCaseError(msg)
    project = Path(value)
    if not project.is_absolute():
        project = rootpath / project
    if not project.is_dir():
        msg = f"rde_case project= {os.fspath(value)!r} is not an existing directory (resolved to {project})"
        raise RdeCaseError(msg)
    return project


def _config(value: object) -> RdeConfig | Mapping[str, Any] | None:
    from rdetoolkit.types import RdeConfig  # noqa: PLC0415

    if value is None or isinstance(value, (RdeConfig, Mapping)):
        return value
    msg = f"rde_case config= must be an RdeConfig or an override mapping, got {type(value).__name__}"
    raise RdeCaseError(msg)


def _status(value: object) -> str:
    if value not in _STATUSES:
        msg = f"rde_case expect_status= must be one of {', '.join(map(repr, _STATUSES))}, got {value!r}"
        raise RdeCaseError(msg)
    return str(value)


def _error_code(value: object) -> int | None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        msg = f"rde_case expect_error_code= must be an int catalog code, got {type(value).__name__}"
        raise RdeCaseError(msg)
    return value


def _phase(value: object) -> str | None:
    if value is not None and (not isinstance(value, str) or not value):
        msg = f"rde_case expect_phase= must be a non-empty phase name, got {value!r}"
        raise RdeCaseError(msg)
    return value


def _expected_files(value: object) -> tuple[PurePosixPath, ...]:
    # A bare string is iterable too; accepting it would check one-letter paths.
    if isinstance(value, (str, os.PathLike)) or not isinstance(value, Iterable):
        msg = f"rde_case expect_files= must be a sequence of relative paths, got {type(value).__name__}"
        raise RdeCaseError(msg)
    files: list[PurePosixPath] = []
    for name in value:
        try:
            files.append(relative_artifact(name))
        except (TypeError, ValueError) as exc:
            msg = f"rde_case expect_files= entry {name!r} is invalid: {exc}"
            raise RdeCaseError(msg) from exc
    return tuple(files)


def _recorded_codes(result: RdeTestResult) -> Iterator[int]:
    run_code = (result.report.error or {}).get("code")
    if isinstance(run_code, int):
        yield run_code
    for summary in result.iterations:
        if summary.error_code is not None:
            yield summary.error_code


def _phase_failures(expected: str, result: RdeTestResult) -> list[str]:
    if result.diagnostics_path is None:
        return [
            f"rde_case expected diagnostic phase {expected!r}, but the run wrote no diagnostics sidecar "
            f"(logs/diagnostics_{result.report.run_id}.json)",
        ]
    try:
        document = json.loads(result.diagnostics_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"rde_case could not read the diagnostics sidecar {result.diagnostics_path}: {exc}"]
    phases = sorted(set(_phases(document)))
    if expected not in phases:
        return [f"rde_case expected diagnostic phase {expected!r}; the sidecar records {phases or 'none'}"]
    return []


def _phases(document: object) -> Iterator[str]:
    # The sidecar schema is owned by the diagnostics feature; any "phase"
    # string anywhere in it counts, so this check does not pin its layout.
    if isinstance(document, Mapping):
        for key, value in document.items():
            if key == "phase" and isinstance(value, str):
                yield value
            else:
                yield from _phases(value)
    elif isinstance(document, list):
        for item in document:
            yield from _phases(item)
