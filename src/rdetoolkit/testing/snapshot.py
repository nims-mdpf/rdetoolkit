"""Golden-artifact snapshots: compare a run's output with user-approved files.

``assert_snapshot(result, artifact, golden)`` compares one artifact file or a
whole artifact directory with a golden copy the user reviewed and committed.
Nothing is derived from production code at assertion time: the golden files
are the expectation.

Comparison by file type (decided by the suffix, never by sniffing content):

* ``.json``: parsed and compared by JSON pointer, with strict JSON types.
* ``.csv``: compared cell by cell (header included).
* other text suffixes (``.txt``, ``.md``, ``.yaml`` ...): line diff.
* everything else: byte length and sha256 -- binary data is never decoded.

Only what the caller lists is normalized: JSON pointers in ``ignore_fields``
and CSV columns in ``ignore_columns`` have their values replaced by a
placeholder on both sides (the key or column itself must still exist), and
files matching ``ignore_files`` are left out of a directory comparison.

Golden files change only through the local pytest option
``--rde-update-snapshots``; the assertion itself takes no argument that could
approve a change. Updating is refused whenever the ``CI`` environment variable
is truthy, so CI can never approve a change. Symlinks are refused on both
sides: an artifact link could publish a file from outside the run, and a
golden link could be compared against, or written through to, a file outside
the golden root. The module never imports pytest.
"""

from __future__ import annotations

import csv
import difflib
import fnmatch
import hashlib
import io
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from rdetoolkit.testing.assertions import DEFAULT_MAX_BYTES, context_lines, csv_differences, json_differences

if TYPE_CHECKING:
    from rdetoolkit.testing.runner import RdeTestResult

#: Value written in place of an ignored JSON field or CSV cell.
IGNORED_PLACEHOLDER = "<rde-snapshot:ignored>"
#: Name of the pytest option that approves snapshot changes.
UPDATE_OPTION = "--rde-update-snapshots"

_TEXT_SUFFIXES = frozenset({".txt", ".md", ".yaml", ".yml", ".xml", ".html", ".htm", ".log", ".ini", ".toml", ".tsv", ".svg"})
#: Top-level data-root directories that hold the submitted raw inputs.
_RAW_DIRECTORIES = frozenset({"inputdata", "raw", "nonshared_raw"})
_FALSY = frozenset({"", "0", "false", "no", "off"})
_MAX_LINES = 20

_state: dict[str, Any] = {"update": False, "updates": []}


class SnapshotError(AssertionError):
    """A snapshot that cannot be compared or updated (size, symlink, raw data, CI)."""


@dataclass(frozen=True)
class SnapshotUpdate:
    """One golden file written or removed by an approved update.

    Attributes:
        path: The golden file.
        action: ``"created"``, ``"changed"`` or ``"removed"``.
    """

    path: Path
    action: str


def ci_is_active(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the ``CI`` environment variable is set to a truthy value."""
    value = (os.environ if environ is None else environ).get("CI")
    return value is not None and value.strip().lower() not in _FALSY


def set_update_mode(enabled: bool) -> None:  # noqa: FBT001 - mirrors a boolean command-line flag
    """Turn snapshot approval on or off (the pytest plugin calls this for ``--rde-update-snapshots``)."""
    _state["update"] = bool(enabled)


def update_mode() -> bool:
    """Return whether changed snapshots are currently approved instead of failing."""
    return bool(_state["update"])


def recorded_updates() -> tuple[SnapshotUpdate, ...]:
    """Return the golden files written or removed so far, in order."""
    return tuple(_state["updates"])


def update_summary_lines() -> list[str]:
    """Return one ``"<action>: <golden file>"`` line per recorded update."""
    return [f"{update.action}: {update.path}" for update in recorded_updates()]


def ci_refusal_message() -> str:
    """Return why an update is refused while ``CI`` is set."""
    return (
        f"{UPDATE_OPTION} is refused because the CI environment variable is set: CI must not approve snapshot "
        "changes. Review the change and update the golden files locally, then commit them"
    )


def reset() -> None:
    """Forget the update mode and the recorded updates (end of a pytest session)."""
    _state["update"] = False
    _state["updates"] = []


def assert_snapshot(
    result: RdeTestResult,
    artifact: str | os.PathLike[str],
    golden: str | os.PathLike[str],
    *,
    ignore_fields: Iterable[str] = (),
    ignore_columns: Iterable[str] = (),
    ignore_files: Iterable[str] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
    allow_raw: bool = False,
) -> None:
    """Assert that an artifact file or directory matches its golden copy.

    A difference fails the test unless the run uses ``pytest
    --rde-update-snapshots`` locally, which rewrites the golden copy instead.
    There is deliberately no argument that approves: a call site must not be
    able to bypass the explicit, CI-refused command-line approval.

    Args:
        result: The test run.
        artifact: File or directory relative to the data root.
        golden: Golden file or directory; a relative path is resolved against
            the current working directory (pytest's invocation directory).
        ignore_fields: JSON pointers (``/basic/dateSubmitted``; ``*`` matches
            any key or index) whose values are not compared.
        ignore_columns: CSV columns whose cells are not compared.
        ignore_files: ``fnmatch`` patterns, relative to ``artifact``, of
            files left out of a directory comparison (e.g. ``"*.log"``).
        max_bytes: Per-file size limit for both sides.
        allow_raw: Allow snapshots of ``inputdata/``, ``raw/`` and
            ``nonshared_raw/`` (golden files are usually committed, so raw
            data is refused unless explicitly allowed).

    Raises:
        SnapshotError: If the snapshot cannot be taken (missing artifact, a
            file above ``max_bytes``, a symlink on the artifact or the golden
            side, raw data, or an update while ``CI`` is set).
        AssertionError: Listing every changed, missing and unexpected file.
    """
    options = _Options(
        fields=tuple(_pointer(item) for item in _strings(ignore_fields, "ignore_fields")),
        columns=tuple(_strings(ignore_columns, "ignore_columns")),
        files=tuple(_strings(ignore_files, "ignore_files")),
        max_bytes=max_bytes,
    )
    name = _relative(artifact)
    golden_path = Path(golden)
    actual = _actual_files(result, name, options, allow_raw=allow_raw)
    expected = _golden_files(result, golden_path, options, is_dir=result.artifact_path(name).is_dir())
    changes = _changes(actual, expected, options)
    if not changes:
        return
    if update_mode():
        _approve(result, golden_path, actual, changes, options)
        return
    raise AssertionError(_mismatch_message(result, name, golden_path, changes, has_golden=golden_path.exists()))


# ----------------------------------------------------------------- inputs


@dataclass(frozen=True)
class _Options:
    fields: tuple[tuple[str, ...], ...]
    columns: tuple[str, ...]
    files: tuple[str, ...]
    max_bytes: int


@dataclass(frozen=True)
class _Change:
    key: str
    kind: str  # "changed" | "missing" | "unexpected"
    details: tuple[str, ...] = ()


def _relative(artifact: str | os.PathLike[str]) -> PurePosixPath:
    from rdetoolkit.testing.runner import relative_artifact  # noqa: PLC0415

    return relative_artifact(artifact)


def _strings(value: object, label: str) -> list[str]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        msg = f"{label} must be an iterable of strings, not {type(value).__name__}"
        raise TypeError(msg)
    items = list(value)
    for item in items:
        if not isinstance(item, str) or not item:
            msg = f"{label} entries must be non-empty strings, got {item!r}"
            raise TypeError(msg)
    return items


def _pointer(text: str) -> tuple[str, ...]:
    if not text.startswith("/"):
        msg = f"ignore_fields entry {text!r} must be a JSON pointer starting with '/'"
        raise ValueError(msg)
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in text[1:].split("/"))


def _actual_files(result: RdeTestResult, name: PurePosixPath, options: _Options, *, allow_raw: bool) -> dict[str, Path]:
    path = result.artifact_path(name)
    if path.is_symlink():
        raise SnapshotError(_with_context(result, f"snapshot refuses the symlinked artifact {name.as_posix()!r}"))
    if path.is_file():
        files = {"": path}
    elif path.is_dir():
        files = _tree(path, options.files)
    else:
        raise SnapshotError(_with_context(result, f"snapshot artifact {name.as_posix()!r} does not exist"))
    for key, file in files.items():
        relative = PurePosixPath(name, key) if key else name
        if file.is_symlink():
            raise SnapshotError(_with_context(result, f"snapshot refuses the symlinked file {relative.as_posix()!r}"))
        if not allow_raw and relative.parts[0] in _RAW_DIRECTORIES:
            msg = (
                f"snapshot of {relative.as_posix()!r} would copy raw input data into a golden file; "
                "golden files are usually committed and published. Pass allow_raw=True only if this data may be shared"
            )
            raise SnapshotError(_with_context(result, msg))
        _check_size(result, file, options.max_bytes)
    return files


def _golden_files(result: RdeTestResult, golden: Path, options: _Options, *, is_dir: bool) -> dict[str, Path]:
    # Checked before ``exists()``: a dangling link does not "exist", and an
    # approval would otherwise create the file it points to.
    _refuse_golden_links(result, golden, golden)
    if not golden.exists():
        return {}
    if golden.is_dir() != is_dir:
        kinds = ("directory", "file") if is_dir else ("file", "directory")
        raise SnapshotError(_with_context(result, f"artifact is a {kinds[0]} but golden {golden} is a {kinds[1]}"))
    files = _tree(golden, options.files) if is_dir else {"": golden}
    # Every link is refused before any size is read, whatever the walk order.
    for file in files.values():
        _refuse_golden_links(result, golden, file)
    for file in files.values():
        _check_size(result, file, options.max_bytes)
    return files


def _refuse_golden_links(result: RdeTestResult, golden: Path, target: Path) -> None:
    """Refuse ``target`` if it, the golden root, or any directory between them is a symlink.

    Each component is checked, not just ``target``: a linked sub-directory
    lets a golden path escape the golden root although the file itself is not
    a link.
    """
    chain = [golden]
    for part in target.relative_to(golden).parts:
        chain.append(chain[-1] / part)
    for current in chain:
        if current.is_symlink():
            msg = (
                f"snapshot refuses the symlinked golden path {current}: golden files are compared and "
                "written in place, never through a link. Replace the link with a regular file or directory"
            )
            raise SnapshotError(_with_context(result, msg))


def _tree(root: Path, patterns: Sequence[str]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        if (path.is_file() or path.is_symlink()) and not any(fnmatch.fnmatchcase(key, pattern) for pattern in patterns):
            files[key] = path
    return files


def _check_size(result: RdeTestResult, path: Path, max_bytes: int) -> None:
    size = path.stat().st_size
    if size > max_bytes:
        msg = f"snapshot file {path} is {size} bytes, above max_bytes={max_bytes}; snapshot a smaller artifact or raise max_bytes"
        raise SnapshotError(_with_context(result, msg))


# ------------------------------------------------------------- comparison


def _changes(actual: dict[str, Path], expected: dict[str, Path], options: _Options) -> list[_Change]:
    changes: list[_Change] = []
    for key in sorted(set(actual) | set(expected)):
        if key not in actual:
            changes.append(_Change(key, "missing"))
        elif key not in expected:
            changes.append(_Change(key, "unexpected"))
        else:
            details = _file_differences(actual[key], expected[key], options)
            if details:
                changes.append(_Change(key, "changed", tuple(details)))
    return changes


def _file_differences(actual: Path, golden: Path, options: _Options) -> list[str]:
    suffix = actual.suffix.lower()
    new, old = actual.read_bytes(), golden.read_bytes()
    if suffix == ".json":
        return _json_file_differences(new, old, options)
    if suffix == ".csv":
        return _csv_file_differences(new, old, options)
    if suffix in _TEXT_SUFFIXES:
        return _text_differences(new, old)
    return _binary_differences(new, old)


def _json_file_differences(new: bytes, old: bytes, options: _Options) -> list[str]:
    try:
        actual, golden = json.loads(new), json.loads(old)
    except ValueError:
        return _text_differences(new, old)
    return json_differences(_mask_json(golden, options.fields), _mask_json(actual, options.fields), subset=False)


def _csv_file_differences(new: bytes, old: bytes, options: _Options) -> list[str]:
    if not options.columns and new == old:
        return []
    try:
        actual, golden = _csv_rows(new, options.columns), _csv_rows(old, options.columns)
    except UnicodeDecodeError:
        return _binary_differences(new, old)
    if actual == golden:
        # Equal cells after masking: differences are only in ignored columns,
        # or only in quoting / line endings when nothing is ignored.
        return [] if options.columns else ["cells are equal but the bytes differ (quoting or line endings)"]
    header_actual, header_golden = actual[0] if actual else [], golden[0] if golden else []
    if header_actual != header_golden:
        return [f"header: golden {header_golden}, actual {header_actual}"]
    return csv_differences(_as_dicts(golden), _as_dicts(actual))


def _csv_rows(data: bytes, ignored: Sequence[str]) -> list[list[str]]:
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"), newline="")))
    if not rows or not ignored:
        return rows
    positions = [index for index, column in enumerate(rows[0]) if column in ignored]
    return [rows[0]] + [[IGNORED_PLACEHOLDER if index in positions else cell for index, cell in enumerate(row)] for row in rows[1:]]


def _as_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    header = rows[0]
    return [dict(zip(header, row, strict=False)) for row in rows[1:]]


def _text_differences(new: bytes, old: bytes) -> list[str]:
    if new == old:
        return []
    try:
        new_lines, old_lines = new.decode("utf-8").splitlines(), old.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return _binary_differences(new, old)
    diff = list(difflib.unified_diff(old_lines, new_lines, "golden", "actual", lineterm="", n=1))
    return diff or ["lines are equal but the bytes differ (line endings or trailing newline)"]


def _binary_differences(new: bytes, old: bytes) -> list[str]:
    if new == old:
        return []
    return [
        (f"binary content differs: golden {len(old)} bytes sha256 {hashlib.sha256(old).hexdigest()}, "
        f"actual {len(new)} bytes sha256 {hashlib.sha256(new).hexdigest()}"),
    ]


def _mask_json(value: Any, pointers: Sequence[tuple[str, ...]]) -> Any:
    for pointer in pointers:
        value = _mask(value, pointer)
    return value


def _mask(value: Any, pointer: tuple[str, ...]) -> Any:
    if not pointer:
        return IGNORED_PLACEHOLDER
    head, rest = pointer[0], pointer[1:]
    if isinstance(value, dict):
        return {key: _mask(item, rest) if head in ("*", key) else item for key, item in value.items()}
    if isinstance(value, list):
        return [_mask(item, rest) if head in ("*", str(index)) else item for index, item in enumerate(value)]
    return value


# ----------------------------------------------------------------- update


def _approve(result: RdeTestResult, golden: Path, actual: dict[str, Path], changes: list[_Change], options: _Options) -> None:
    if ci_is_active():
        msg = f"refusing to update snapshot {golden}: {ci_refusal_message()}"
        raise SnapshotError(_with_context(result, "\n".join([msg, *_change_lines(changes)])))
    targets = [golden / change.key if change.key else golden for change in changes]
    # All targets are checked before the first write: a refused update leaves
    # the golden copy exactly as it was, and nothing is written through a link.
    for target in targets:
        _refuse_golden_links(result, golden, target)
    for change, target in zip(changes, targets, strict=True):
        if change.kind == "missing":
            target.unlink()
            _state["updates"].append(SnapshotUpdate(target, "removed"))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_approved_bytes(actual[change.key], options))
        _state["updates"].append(SnapshotUpdate(target, "created" if change.kind == "unexpected" else "changed"))


def _approved_bytes(path: Path, options: _Options) -> bytes:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    # Ignored values are written as the placeholder, so the run-specific
    # value (a run ID, a timestamp) never reaches the committed golden file.
    if suffix == ".json" and options.fields:
        try:
            document = json.loads(data)
        except ValueError:
            return data
        return (json.dumps(_mask_json(document, options.fields), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if suffix == ".csv" and options.columns:
        buffer = io.StringIO(newline="")
        csv.writer(buffer, lineterminator="\n").writerows(_csv_rows(data, options.columns))
        return buffer.getvalue().encode("utf-8")
    return data


# --------------------------------------------------------------- messages


def _mismatch_message(result: RdeTestResult, name: PurePosixPath, golden: Path, changes: list[_Change], *, has_golden: bool) -> str:
    head = (
        f"artifact {name.as_posix()!r} differs from golden snapshot {golden}"
        if has_golden
        else f"golden snapshot {golden} for artifact {name.as_posix()!r} does not exist"
    )
    lines = [
        head,
        *_change_lines(changes),
        f"review the artifact, then approve with 'pytest {UPDATE_OPTION}' locally (refused when CI is set)",
    ]
    return _with_context(result, "\n".join(lines))


def _change_lines(changes: list[_Change]) -> list[str]:
    labels = {"changed": "changed", "missing": "missing (in golden, not produced)", "unexpected": "unexpected (produced, not in golden)"}
    lines: list[str] = []
    for change in changes:
        lines.append(f"  {labels[change.kind]}: {change.key or '<file>'}")
        lines.extend(f"      {detail}" for detail in change.details[:_MAX_LINES])
        if len(change.details) > _MAX_LINES:
            lines.append(f"      ... {len(change.details) - _MAX_LINES} more diff line(s)")
    return lines


def _with_context(result: RdeTestResult, message: str) -> str:
    return "\n".join([message, *context_lines(result)])
