"""Phase-aware failure diagnostics and their versioned sidecar document (#686).

The run report records *that* a run failed and with which catalog code. This
module records *where*: the lifecycle phase, the exception chain, a source
location, and the tile / node / parameter / artifact the failure belongs to.
It is written next to the run report as ``logs/diagnostics_<run_id>.json``, a
separately versioned document, so the RunReport v2 shape stays unchanged.

Privacy (documented in ``docs/usage/diagnostics``): a frame is recorded as
file, line and function only -- never local variables, source lines, argument
values or environment variables. Exception messages are kept (bounded),
because the run report and ``job.failed`` already carry the same text.
"""

from __future__ import annotations

import sys
import sysconfig
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from rdetoolkit import __version__

FAILURE_DIAGNOSTICS_SCHEMA_VERSION = "1"
FAILURE_DIAGNOSTICS_FORMAT = "rdetoolkit.failure-diagnostics"

FailurePhase = Literal[
    "config_load",
    "mode_resolution",
    "pre_validate",
    "tile_prepare",
    "node_execution",
    "node_argument_validation",
    "artifact_publish",
    "post_validate",
    "finalize",
]

#: The canonical phase vocabulary, in lifecycle order.
FAILURE_PHASES: tuple[FailurePhase, ...] = (
    "config_load",
    "mode_resolution",
    "pre_validate",
    "tile_prepare",
    "node_execution",
    "node_argument_validation",
    "artifact_publish",
    "post_validate",
    "finalize",
)

#: ``RdeError.detail["kind"]`` of a strict-mode node argument rejection (#688).
NODE_ARGUMENT_REJECTION = "node_argument_rejection"

#: Diagnostics kept per document; later ones only set ``truncated``.
MAX_DIAGNOSTICS = 200
#: Innermost frames kept per exception.
MAX_FRAMES = 64
#: Exceptions kept per chain, the primary one included.
MAX_CHAIN = 8
#: Characters kept per exception message.
MAX_MESSAGE_LENGTH = 2000

_TRUNCATION_MARK = " [truncated]"
_PASSTHROUGH_NAME = "StructuredError"
_CATEGORY_BY_THOUSANDS = {1: "config", 2: "registry", 3: "execution", 4: "validation", 5: "internal"}
_LIBRARY_DIR_NAMES = frozenset({"site-packages", "dist-packages"})


@dataclass(frozen=True, slots=True)
class SourceFrame:
    """One traceback frame: where, never what.

    Attributes:
        file: Path relative to the project root or to the ``sys.path`` entry
            holding it; otherwise the path Python reported.
        line: Line number, or ``None`` when Python did not record one.
        function: Function (qualified) name.
    """

    file: str
    line: int | None
    function: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the frame.

        Returns:
            ``file``, ``line`` and ``function``.
        """
        return {"file": self.file, "line": self.line, "function": self.function}


@dataclass(frozen=True, slots=True)
class ExceptionSummary:
    """Type, bounded message and frames of one exception in a chain.

    Attributes:
        relation: ``primary``, ``cause`` (``raise ... from``) or ``context``
            (raised while handling another exception).
        type: Qualified exception class name.
        message: ``str(exc)``, cut at :data:`MAX_MESSAGE_LENGTH`.
        frames: Innermost :data:`MAX_FRAMES` frames, outermost first.
        frames_truncated: Whether outer frames were dropped.
    """

    relation: Literal["primary", "cause", "context"]
    type: str
    message: str
    frames: tuple[SourceFrame, ...]
    frames_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize the summary.

        Returns:
            A JSON-compatible mapping.
        """
        return {
            "relation": self.relation,
            "type": self.type,
            "message": self.message,
            "frames": [frame.to_dict() for frame in self.frames],
            "frames_truncated": self.frames_truncated,
        }


@dataclass(frozen=True, slots=True)
class FailureDiagnostic:
    """One failure, attributed to its lifecycle phase.

    Unknown fields are ``None``: a value is never invented to fill a gap.

    Attributes:
        phase: Lifecycle phase from :data:`FAILURE_PHASES`.
        code: Published error code (catalog or v1 ``StructuredError`` code).
        name: Published error name.
        category: ``config``, ``registry``, ``execution``, ``validation``,
            ``internal``, ``structured_error`` or ``unknown``.
        message: Published error message.
        exception: The exception the failure originated as, if one exists.
        causes: Its ``__cause__`` / ``__context__`` chain, nearest first.
        causes_truncated: Whether the chain was cut at :data:`MAX_CHAIN`.
        location: The originating source frame, if any frame was recorded.
        iteration_index: Tile index, when the failure belongs to a tile.
        node_id: Node the failure belongs to, when known.
        call_id: Executed call that failed, when one was recorded.
        parameter: Rejected parameter (``node_argument_validation``).
        expected_type: Annotation the argument had to satisfy.
        actual_type: Type name of the rejected argument (never its value).
        artifact_path: Data-root-relative artifact involved, when known.
    """

    phase: FailurePhase
    code: int | None
    name: str | None
    category: str
    message: str | None
    exception: ExceptionSummary | None = None
    causes: tuple[ExceptionSummary, ...] = field(default_factory=tuple)
    causes_truncated: bool = False
    location: SourceFrame | None = None
    iteration_index: int | None = None
    node_id: str | None = None
    call_id: str | None = None
    parameter: str | None = None
    expected_type: str | None = None
    actual_type: str | None = None
    artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the diagnostic with a fixed key order.

        Returns:
            A JSON-compatible mapping.
        """
        return {
            "phase": self.phase,
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "message": self.message,
            "iteration_index": self.iteration_index,
            "node_id": self.node_id,
            "call_id": self.call_id,
            "parameter": self.parameter,
            "expected_type": self.expected_type,
            "actual_type": self.actual_type,
            "artifact_path": self.artifact_path,
            "location": self.location.to_dict() if self.location is not None else None,
            "exception": self.exception.to_dict() if self.exception is not None else None,
            "causes": [cause.to_dict() for cause in self.causes],
            "causes_truncated": self.causes_truncated,
        }


def failure_diagnostic(
    exc: BaseException | None,
    *,
    phase: FailurePhase,
    error: Mapping[str, Any] | None = None,
    root: Path | None = None,
    iteration_index: int | None = None,
    node_id: str | None = None,
    call_id: str | None = None,
    artifact_path: str | None = None,
) -> FailureDiagnostic:
    """Build the diagnostic of one failure.

    Args:
        exc: The exception the failure originated as. Pass the user's
            exception rather than a framework wrapper when both exist.
        phase: Lifecycle phase the failure happened in.
        error: The published error record (``code``/``name``/``message``),
            which wins over the exception's own attributes.
        root: Project root that frame paths are made relative to.
        iteration_index: Tile index, when the failure belongs to a tile.
        node_id: Node id, when known.
        call_id: Executed call id, when one was recorded.
        artifact_path: Data-root-relative artifact path, when known.

    Returns:
        The diagnostic. A strict-mode argument rejection (#688) contributes
        its node, parameter and type names.
    """
    record = dict(error) if error is not None else _error_of(exc)
    code = _int_code(record.get("code"))
    name = record.get("name") if isinstance(record.get("name"), str) else None
    message = record.get("message") if isinstance(record.get("message"), str) else None
    chain, chain_truncated = _chain(exc, root)
    rejection = node_argument_rejection(exc)
    return FailureDiagnostic(
        phase=phase,
        code=code,
        name=name,
        category=_category(code, name),
        message=_bounded(message) if message is not None else None,
        exception=chain[0] if chain else None,
        causes=tuple(chain[1:]),
        causes_truncated=chain_truncated,
        location=_origin_frame(exc, root),
        iteration_index=iteration_index,
        node_id=_rejected(rejection, "node_id") or node_id,
        call_id=call_id,
        parameter=_rejected(rejection, "parameter"),
        expected_type=_rejected(rejection, "expected_type"),
        actual_type=_rejected(rejection, "actual_type"),
        artifact_path=artifact_path,
    )


def node_argument_rejection(exc: BaseException | None) -> dict[str, Any] | None:
    """Return the rejection detail of a strict-mode argument mismatch (#688).

    Args:
        exc: Candidate exception.

    Returns:
        The ``detail`` mapping ``CallLogRecorder`` attached (``node_id``,
        ``parameter``, ``expected_type``, ``actual_type``,
        ``iteration_index``), or ``None`` for any other exception -- the
        return-value mismatch included, which belongs to an executed call.
    """
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict) and detail.get("kind") == NODE_ARGUMENT_REJECTION:
        return detail
    return None


def diagnostics_filename(run_id: str) -> str:
    """Return the sidecar's file name below ``<data_root>/logs``.

    Args:
        run_id: Run identifier.

    Returns:
        ``diagnostics_<run_id>.json``.
    """
    return f"diagnostics_{run_id}.json"


def diagnostics_document(
    diagnostics: list[FailureDiagnostic],
    *,
    run_id: str,
    run_status: str,
    truncated: bool = False,
) -> dict[str, Any]:
    """Wrap diagnostics in the versioned sidecar document.

    Args:
        diagnostics: Diagnostics in the order they happened.
        run_id: Run identifier.
        run_status: Final ``RunReport.status``.
        truncated: The caller already dropped diagnostics.

    Returns:
        ``schema_version``, ``format``, ``producer``, ``run_id``,
        ``run_status``, the first :data:`MAX_DIAGNOSTICS` diagnostics, and
        ``truncated``.
    """
    return {
        "schema_version": FAILURE_DIAGNOSTICS_SCHEMA_VERSION,
        "format": FAILURE_DIAGNOSTICS_FORMAT,
        "producer": {"name": "rdetoolkit", "version": __version__},
        "run_id": run_id,
        "run_status": run_status,
        "diagnostics": [item.to_dict() for item in diagnostics[:MAX_DIAGNOSTICS]],
        "truncated": truncated or len(diagnostics) > MAX_DIAGNOSTICS,
    }


def _error_of(exc: BaseException | None) -> dict[str, Any]:
    """Read code/name/message from an exception when no record was published."""
    if exc is None:
        return {}
    return {
        "code": getattr(exc, "code", None),
        "name": getattr(exc, "name", None),
        "message": getattr(exc, "message", None),
    }


def _int_code(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _category(code: int | None, name: str | None) -> str:
    if name == _PASSTHROUGH_NAME:
        return "structured_error"
    if code is None:
        return "unknown"
    return _CATEGORY_BY_THOUSANDS.get(code // 1000, "unknown")


def _rejected(rejection: dict[str, Any] | None, key: str) -> str | None:
    if rejection is None:
        return None
    value = rejection.get(key)
    return value if isinstance(value, str) else None


def _bounded(text: str) -> str:
    if len(text) <= MAX_MESSAGE_LENGTH:
        return text
    return text[:MAX_MESSAGE_LENGTH] + _TRUNCATION_MARK


def _walk_chain(exc: BaseException | None) -> Iterator[tuple[Literal["primary", "cause", "context"], BaseException]]:
    """Yield ``exc`` and its explicit / implicit causes, nearest first, cycle-safe."""
    seen: set[int] = set()
    relation: Literal["primary", "cause", "context"] = "primary"
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield relation, current
        if current.__cause__ is not None:
            relation, current = "cause", current.__cause__
        elif current.__context__ is not None and not current.__suppress_context__:
            relation, current = "context", current.__context__
        else:
            current = None


def _chain(exc: BaseException | None, root: Path | None) -> tuple[list[ExceptionSummary], bool]:
    summaries: list[ExceptionSummary] = []
    for relation, item in _walk_chain(exc):
        if len(summaries) == MAX_CHAIN:
            return summaries, True
        frames = _frames(item.__traceback__, root)
        summaries.append(
            ExceptionSummary(
                relation=relation,
                type=_qualified_type(item),
                message=_bounded(_safe_str(item)),
                frames=tuple(frames[-MAX_FRAMES:]),
                frames_truncated=len(frames) > MAX_FRAMES,
            ),
        )
    return summaries, False


def _safe_str(exc: BaseException) -> str:
    try:
        return str(exc)
    except Exception:  # noqa: BLE001 -- a broken __str__ must not hide the failure
        return f"<{type(exc).__name__}: message unavailable>"


def _qualified_type(exc: BaseException) -> str:
    cls = type(exc)
    module = getattr(cls, "__module__", "") or ""
    return cls.__qualname__ if module == "builtins" else f"{module}.{cls.__qualname__}"


def _raw_frames(tb: TracebackType | None) -> list[tuple[str, int | None, str]]:
    """Walk a traceback reading code-object metadata only (no linecache I/O)."""
    frames: list[tuple[str, int | None, str]] = []
    while tb is not None:
        code = tb.tb_frame.f_code
        frames.append((code.co_filename, tb.tb_lineno, getattr(code, "co_qualname", code.co_name)))
        tb = tb.tb_next
    return frames


def _frames(tb: TracebackType | None, root: Path | None) -> list[SourceFrame]:
    return [SourceFrame(file=_display_path(file, root), line=line, function=function) for file, line, function in _raw_frames(tb)]


def _origin_frame(exc: BaseException | None, root: Path | None) -> SourceFrame | None:
    """Pick the frame the failure originated in, not the translator that wrapped it.

    The chain is searched from its deepest exception outwards and each
    traceback from its innermost frame. The first frame in the project wins;
    then the first frame of user code (neither rdetoolkit, nor an installed
    library, nor the standard library) -- so an argument rejected inside the
    call log is located at the caller; then the first rdetoolkit frame (a
    validator, for a validation failure); then the innermost frame at all.
    """
    candidates = [frame for _, item in reversed(list(_walk_chain(exc))) for frame in reversed(_raw_frames(item.__traceback__))]
    if not candidates:
        return None
    package = _package_dir()
    preferences = (
        lambda file: _under(file, root),
        lambda file: not _under(file, package) and not _is_library(file),
        lambda file: _under(file, package),
    )
    chosen = next(
        (frame for prefers in preferences for frame in candidates if prefers(frame[0])),
        candidates[0],
    )
    file, line, function = chosen
    return SourceFrame(file=_display_path(file, root), line=line, function=function)


def _under(file: str, directory: Path | None) -> bool:
    if directory is None:
        return False
    try:
        Path(file).resolve().relative_to(directory.resolve())
    except (ValueError, OSError):
        return False
    return True


def _package_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _stdlib_dirs() -> tuple[Path, ...]:
    paths = sysconfig.get_paths()
    return tuple(Path(paths[key]).resolve() for key in ("stdlib", "platstdlib") if key in paths)


def _is_library(file: str) -> bool:
    if file.startswith("<"):
        return True
    if _LIBRARY_DIR_NAMES & set(Path(file).parts):
        return True
    return any(_under(file, directory) for directory in _stdlib_dirs())


def _display_path(file: str, root: Path | None) -> str:
    """Make a frame path relative to the project, else to its ``sys.path`` entry."""
    if file.startswith("<"):
        return file
    resolved = _resolve(file)
    if root is not None and _under(file, root):
        return resolved.relative_to(root.resolve()).as_posix()
    best: Path | None = None
    for entry in sys.path:
        base = _resolve(entry or ".")
        if _is_relative(resolved, base) and (best is None or len(base.parts) > len(best.parts)):
            best = base
    return resolved.relative_to(best).as_posix() if best is not None else file


def _resolve(path: str) -> Path:
    try:
        return Path(path).resolve()
    except OSError:
        return Path(path)


def _is_relative(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return path != base
