"""Readable assertions on the artifacts of an isolated test run.

Every function takes an :class:`~rdetoolkit.testing.runner.RdeTestResult` as
its first argument; the same names are available as methods on the result
(``run.assert_json_subset(...)``). Artifact names are always relative to the
isolated data root and are validated by ``RdeTestResult.artifact_path``, so an
absolute or ``..`` name is refused before any file is opened.

Failures raise ``AssertionError`` whose message names the artifact, the
difference (missing/extra paths, JSON pointers, CSV rows and columns) and
where the retained run lives (data root and run report). Values are compared
strictly: ``1`` and ``1.0``, ``1`` and ``true``, and ``null`` and an absent
key are all different.

The module never imports pytest.
"""

from __future__ import annotations

import csv
import fnmatch
import io
import json
import math
import os
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rdetoolkit.testing.runner import RdeTestResult

#: Default read limit of the read and assert helpers (16 MiB). Larger
#: artifacts need an explicit ``max_bytes`` (``None`` means unlimited), so a
#: check never loads an unbounded payload by accident.
DEFAULT_MAX_BYTES = 16 * 1024 * 1024

_STATUSES = ("success", "partial", "failed")
#: Maximum number of individual differences listed in one message.
_MAX_LISTED = 20
_SHORT_LIMIT = 80


# ------------------------------------------------------------------ reading


def read_bytes(result: RdeTestResult, name: str | os.PathLike[str], *, max_bytes: int | None = DEFAULT_MAX_BYTES) -> bytes:
    """Return the bytes of an artifact, refusing files above ``max_bytes``.

    Args:
        result: The test run.
        name: Artifact path relative to the data root.
        max_bytes: Size limit; ``None`` reads any size.

    Returns:
        The file content.

    Raises:
        AssertionError: If the artifact is missing, not a file, or too large.
        ValueError: If ``name`` is absolute or leaves the data root.
    """
    path = _existing_file(result, name)
    size = path.stat().st_size
    if max_bytes is not None and size > max_bytes:
        msg = (
            f"artifact {_label(name)} is {size} bytes, above the read limit of {max_bytes} bytes; "
            "pass max_bytes=<larger limit> (or None) to read it"
        )
        raise AssertionError(_with_context(result, msg))
    return path.read_bytes()


def read_text(
    result: RdeTestResult,
    name: str | os.PathLike[str],
    *,
    encoding: str = "utf-8",
    max_bytes: int | None = DEFAULT_MAX_BYTES,
) -> str:
    """Return the decoded text of an artifact (see :func:`read_bytes`).

    Raises:
        AssertionError: If the artifact is missing, too large, or not valid
            text in ``encoding``.
    """
    data = read_bytes(result, name, max_bytes=max_bytes)
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise AssertionError(_with_context(result, f"artifact {_label(name)} is not valid {encoding} text: {exc}")) from exc


def read_json(result: RdeTestResult, name: str | os.PathLike[str], *, max_bytes: int | None = DEFAULT_MAX_BYTES) -> Any:
    """Return the parsed JSON content of an artifact (see :func:`read_bytes`).

    Raises:
        AssertionError: If the artifact is missing, too large, or not JSON.
    """
    text = read_text(result, name, max_bytes=max_bytes)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise AssertionError(_with_context(result, f"artifact {_label(name)} is not valid JSON: {exc}")) from exc


def read_csv(
    result: RdeTestResult,
    name: str | os.PathLike[str],
    *,
    encoding: str = "utf-8",
    max_bytes: int | None = DEFAULT_MAX_BYTES,
) -> list[dict[str, str]]:
    """Return the rows of a CSV artifact as ``{column: cell}`` mappings.

    Cells stay strings: converting them is the test's decision.

    Raises:
        AssertionError: If the artifact is missing, too large, or not text,
            or if its header repeats a column name.
    """
    return list(_dict_reader(result, name, io.StringIO(read_text(result, name, encoding=encoding, max_bytes=max_bytes), newline="")))


def iter_csv(result: RdeTestResult, name: str | os.PathLike[str], *, encoding: str = "utf-8") -> Iterator[dict[str, str]]:
    """Stream the rows of a CSV artifact without loading the whole file.

    Use it for artifacts above the read limit of :func:`read_csv`.

    Raises:
        AssertionError: If the artifact is missing, or if its header repeats a
            column name.
    """
    path = _existing_file(result, name)
    with path.open(encoding=encoding, newline="") as handle:
        yield from _dict_reader(result, name, handle)


def _dict_reader(result: RdeTestResult, name: str | os.PathLike[str], handle: Iterable[str]) -> csv.DictReader[str]:
    """Return a ``DictReader`` after refusing a header that repeats a column name.

    A mapping per row keeps only the last of two equal names, so a change in
    the other column would go unnoticed.
    """
    reader = csv.DictReader(handle)
    header = reader.fieldnames or []
    duplicated = sorted({column for column in header if header.count(column) > 1})
    if duplicated:
        msg = (
            f"CSV artifact {_label(name)} has duplicate column name(s) {duplicated}: rows read as mappings would keep "
            "only the last of them. Compare it cell by cell by position with assert_snapshot, or read it with csv.reader"
        )
        raise AssertionError(_with_context(result, msg))
    return reader


# --------------------------------------------------------------- run state


def assert_status(result: RdeTestResult, expected: str) -> None:
    """Assert the run status.

    Args:
        result: The test run.
        expected: ``"success"``, ``"partial"`` or ``"failed"``.

    Raises:
        ValueError: If ``expected`` is not a run status.
        AssertionError: If the status differs; the message explains the run.
    """
    if expected not in _STATUSES:
        msg = f"expected status must be one of {', '.join(map(repr, _STATUSES))}, got {expected!r}"
        raise ValueError(msg)
    if result.status != expected:
        raise AssertionError(result.failure_summary(expected_status=expected))


def assert_error_code(result: RdeTestResult, code: int) -> None:
    """Assert that the run or one of its tiles recorded the catalog ``code``.

    Raises:
        TypeError: If ``code`` is not an ``int``.
        AssertionError: If no such code was recorded; the recorded ones are listed.
    """
    if isinstance(code, bool) or not isinstance(code, int):
        msg = f"error code must be an int catalog code, got {type(code).__name__}"
        raise TypeError(msg)
    recorded = sorted(set(recorded_error_codes(result)))
    if code not in recorded:
        raise AssertionError(_with_context(result, f"expected error code {code}; the run recorded {recorded or 'none'}"))


def recorded_error_codes(result: RdeTestResult) -> Iterator[int]:
    """Yield the run-level error code, then every tile error code."""
    run_code = (result.report.error or {}).get("code")
    if isinstance(run_code, int):
        yield run_code
    for summary in result.iterations:
        if summary.error_code is not None:
            yield summary.error_code


# --------------------------------------------------------------- the tree


def assert_artifact(result: RdeTestResult, name: str | os.PathLike[str], *, exists: bool = True) -> None:
    """Assert that an artifact exists (default) or is absent.

    Raises:
        AssertionError: If the existence differs from ``exists``.
    """
    path = result.artifact_path(name)
    if path.exists() == exists:
        return
    if exists:
        parent = path.parent
        detail = ""
        if parent.is_dir():
            # Listing the siblings turns a typo or a wrong directory into an obvious diff.
            siblings = sorted(entry.name for entry in parent.iterdir())
            detail = f"; {parent.relative_to(result.data_root).as_posix()}/ contains {siblings}"
        raise AssertionError(_with_context(result, f"expected artifact {_label(name)} to exist, but it is missing{detail}"))
    raise AssertionError(_with_context(result, f"expected artifact {_label(name)} to be absent, but it exists"))


def assert_tree(
    result: RdeTestResult,
    expected: Iterable[str | os.PathLike[str]],
    *,
    root: str | os.PathLike[str] | None = None,
    ignore: Iterable[str] = (),
) -> None:
    """Assert the exact set of files below the data root (or ``root`` within it).

    Args:
        result: The test run.
        expected: File paths relative to ``root`` (directories are implied).
        root: Optional subdirectory of the data root, e.g. ``"structured"``.
        ignore: ``fnmatch`` patterns of files to leave out of the comparison,
            e.g. ``("logs/*",)``. Nothing is ignored unless listed here.

    Raises:
        AssertionError: Listing missing and unexpected files.
    """
    base = result.data_root if root is None else result.artifact_path(root)
    patterns = _string_items(ignore, "ignore")
    wanted = {_posix(item) for item in _path_items(expected, "expected")}
    actual = {path for path in _files_below(base) if not _ignored(path, patterns)}
    missing = sorted(wanted - actual)
    extra = sorted(actual - wanted)
    if not missing and not extra:
        return
    lines = [f"file tree below {_label(root) if root is not None else 'the data root'} differs from the expectation"]
    lines.extend(_listed("missing", missing))
    lines.extend(_listed("unexpected", extra))
    raise AssertionError(_with_context(result, "\n".join(lines)))


# ------------------------------------------------------------------- JSON


def assert_json_subset(result: RdeTestResult, name: str | os.PathLike[str], expected: Mapping[str, Any]) -> None:
    """Assert that a JSON artifact contains ``expected`` (recursively).

    Objects may carry extra keys; lists must have the expected length and
    each element is compared the same way. Scalars must be equal and of the
    same JSON type.

    Raises:
        AssertionError: Listing each differing JSON pointer.
    """
    _assert_json(result, name, expected, subset=True)


def assert_json_equal(result: RdeTestResult, name: str | os.PathLike[str], expected: Any) -> None:
    """Assert that a JSON artifact equals ``expected`` exactly.

    Raises:
        AssertionError: Listing each differing, missing or unexpected JSON pointer.
    """
    _assert_json(result, name, expected, subset=False)


def json_differences(expected: Any, actual: Any, *, subset: bool, pointer: str = "") -> list[str]:
    """Return one line per difference between two JSON values, by JSON pointer.

    Args:
        expected: Reference value.
        actual: Observed value.
        subset: Whether ``actual`` objects may carry keys ``expected`` lacks.
        pointer: JSON pointer of the compared values.

    Returns:
        Difference lines such as ``"/custom/temperature: expected 300, got 301"``.
    """
    if isinstance(expected, Mapping):
        return _object_differences(expected, actual, subset=subset, pointer=pointer)
    if isinstance(expected, (list, tuple)):
        return _array_differences(expected, actual, subset=subset, pointer=pointer)
    if _same_scalar(expected, actual):
        return []
    return [f"{pointer or '/'}: expected {_short(expected)}, got {_short(actual)}"]


def _assert_json(result: RdeTestResult, name: str | os.PathLike[str], expected: Any, *, subset: bool) -> None:
    actual = read_json(result, name)
    differences = json_differences(expected, actual, subset=subset)
    if differences:
        kind = "does not contain the expected subset" if subset else "differs from the expected content"
        lines = [f"JSON artifact {_label(name)} {kind}:", *_capped(differences)]
        raise AssertionError(_with_context(result, "\n".join(lines)))


def _object_differences(expected: Mapping[str, Any], actual: Any, *, subset: bool, pointer: str) -> list[str]:
    if not isinstance(actual, Mapping):
        return [f"{pointer or '/'}: expected an object, got {_short(actual)}"]
    differences: list[str] = []
    for key, value in expected.items():
        child = f"{pointer}/{_escape(str(key))}"
        if key not in actual:
            differences.append(f"{child}: missing (expected {_short(value)})")
        else:
            differences.extend(json_differences(value, actual[key], subset=subset, pointer=child))
    if not subset:
        differences.extend(
            f"{pointer}/{_escape(str(key))}: unexpected (got {_short(value)})" for key, value in actual.items() if key not in expected
        )
    return differences


def _array_differences(expected: Sequence[Any], actual: Any, *, subset: bool, pointer: str) -> list[str]:
    if not isinstance(actual, list):
        return [f"{pointer or '/'}: expected an array, got {_short(actual)}"]
    differences: list[str] = []
    if len(actual) != len(expected):
        differences.append(f"{pointer or '/'}: expected {len(expected)} item(s), got {len(actual)}")
    for index, (want, got) in enumerate(zip(expected, actual, strict=False)):
        differences.extend(json_differences(want, got, subset=subset, pointer=f"{pointer}/{index}"))
    return differences


def _same_scalar(expected: Any, actual: Any) -> bool:
    # bool is an int subclass and 1 == 1.0 in Python; in a scientific artifact
    # true/1/1.0 are different recorded values, so the JSON type must match.
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, float) and math.isnan(expected):
        return math.isnan(actual)
    return bool(expected == actual)


def _escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


# -------------------------------------------------------------------- CSV


def assert_csv_columns(
    result: RdeTestResult,
    name: str | os.PathLike[str],
    columns: Iterable[str],
    *,
    exact: bool = False,
) -> None:
    """Assert the header of a CSV artifact.

    Args:
        result: The test run.
        name: CSV artifact path.
        columns: Column names that must be present.
        exact: Also refuse columns that are not listed.

    Raises:
        TypeError: If ``columns`` is a bare string.
        AssertionError: Listing missing (and, with ``exact``, unexpected) columns.
    """
    wanted = _string_items(columns, "columns")
    header = _csv_header(result, name)
    missing = [column for column in wanted if column not in header]
    extra = [column for column in header if column not in wanted] if exact else []
    if not missing and not extra:
        return
    lines = [f"CSV artifact {_label(name)} header {header} does not match the expected columns"]
    lines.extend(_listed("missing column(s)", missing))
    lines.extend(_listed("unexpected column(s)", extra))
    raise AssertionError(_with_context(result, "\n".join(lines)))


def assert_csv_rows(result: RdeTestResult, name: str | os.PathLike[str], expected: Sequence[Mapping[str, str]]) -> None:
    """Assert every data row of a CSV artifact, cell by cell.

    Args:
        result: The test run.
        name: CSV artifact path.
        expected: One ``{column: cell}`` mapping per row, cells as strings
            exactly as written (``"1.0"`` and ``"1"`` differ).

    Raises:
        TypeError: If a row is not a mapping or a cell is not a string.
        AssertionError: Naming the row count and each differing cell.
    """
    rows = [_expected_row(row, index) for index, row in enumerate(expected)]
    actual = read_csv(result, name)
    differences = csv_differences(rows, actual)
    if differences:
        lines = [f"CSV artifact {_label(name)} rows differ from the expectation:", *_capped(differences)]
        raise AssertionError(_with_context(result, "\n".join(lines)))


def csv_differences(expected: Sequence[Mapping[str, str]], actual: Sequence[Mapping[str, str | None]]) -> list[str]:
    """Return one line per row-count or cell difference (rows numbered from 1)."""
    differences: list[str] = []
    if len(actual) != len(expected):
        differences.append(f"expected {len(expected)} data row(s), got {len(actual)}")
    for number, (want, got) in enumerate(zip(expected, actual, strict=False), start=1):
        for column in sorted(set(want) | set(got), key=lambda key: (key is None, str(key))):
            if want.get(str(column)) != got.get(column):
                differences.append(f"row {number}, column {column!r}: expected {want.get(str(column))!r}, got {got.get(column)!r}")
    return differences


def _csv_header(result: RdeTestResult, name: str | os.PathLike[str]) -> list[str]:
    reader = csv.reader(io.StringIO(read_text(result, name), newline=""))
    return next(reader, [])


def _expected_row(row: object, index: int) -> dict[str, str]:
    if not isinstance(row, Mapping):
        msg = f"expected row {index + 1} must be a mapping of column to cell, got {type(row).__name__}"
        raise TypeError(msg)
    for column, cell in row.items():
        if not isinstance(cell, str):
            msg = f"expected row {index + 1}, column {column!r}: cells are compared as written, pass a str, got {type(cell).__name__}"
            raise TypeError(msg)
    return {str(column): cell for column, cell in row.items()}


# ------------------------------------------------------ invoice / metadata


def assert_metadata_valid(
    result: RdeTestResult,
    name: str | os.PathLike[str] = "meta/metadata.json",
    *,
    definition: str | os.PathLike[str] | None = "tasksupport/metadata-def.json",
) -> None:
    """Assert that a metadata artifact is valid and uses only defined keys.

    The structure is checked with :func:`rdetoolkit.validation.metadata_validate`;
    every ``constant`` and ``variable`` key must then be defined in
    ``definition`` (pass ``None`` to skip the key check).

    Raises:
        AssertionError: Naming the validation error or the undefined keys.
    """
    from rdetoolkit.validation import metadata_validate  # noqa: PLC0415

    path = _existing_file(result, name)
    try:
        metadata_validate(path)
    except Exception as exc:  # noqa: BLE001 - every validator failure becomes the assertion message
        raise AssertionError(_with_context(result, f"metadata artifact {_label(name)} is invalid: {exc}")) from exc
    if definition is None:
        return
    defined = read_json(result, definition)
    used = _metadata_keys(read_json(result, name))
    undefined = sorted(used - set(defined if isinstance(defined, Mapping) else ()))
    if undefined:
        msg = f"metadata artifact {_label(name)} uses key(s) not defined in {_label(definition)}: {undefined}"
        raise AssertionError(_with_context(result, msg))


def assert_invoice_valid(
    result: RdeTestResult,
    name: str | os.PathLike[str] = "invoice/invoice.json",
    *,
    schema: str | os.PathLike[str] = "tasksupport/invoice.schema.json",
) -> None:
    """Assert that an invoice artifact validates against the project's invoice schema.

    Raises:
        AssertionError: Naming the validation error.
    """
    from rdetoolkit.validation import invoice_validate  # noqa: PLC0415

    invoice = _existing_file(result, name)
    schema_path = _existing_file(result, schema)
    try:
        invoice_validate(invoice, schema_path)
    except Exception as exc:  # noqa: BLE001 - every validator failure becomes the assertion message
        msg = f"invoice artifact {_label(name)} does not validate against {_label(schema)}: {exc}"
        raise AssertionError(_with_context(result, msg)) from exc


def _metadata_keys(document: object) -> set[str]:
    if not isinstance(document, Mapping):
        return set()
    keys = set(document.get("constant") or {})
    for entry in document.get("variable") or []:
        if isinstance(entry, Mapping):
            keys.update(entry)
    return keys


# ----------------------------------------------------------------- shared


def context_lines(result: RdeTestResult) -> list[str]:
    """Return where the retained run lives, for the end of an assertion message."""
    lines = [f"data root: {result.data_root}"]
    if result.report_path is not None:
        lines.append(f"run report: {result.report_path}")
    return lines


def _with_context(result: RdeTestResult, message: str) -> str:
    return "\n".join([message, *context_lines(result)])


def _existing_file(result: RdeTestResult, name: str | os.PathLike[str]) -> Path:
    path = result.artifact_path(name)
    if not path.is_file():
        state = "is a directory, not a file" if path.is_dir() else "is missing"
        raise AssertionError(_with_context(result, f"artifact {_label(name)} {state}"))
    return path


def _files_below(base: Path) -> set[str]:
    if not base.is_dir():
        return set()
    return {path.relative_to(base).as_posix() for path in sorted(base.rglob("*")) if path.is_file()}


def _ignored(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _path_items(value: object, label: str) -> list[str | os.PathLike[str]]:
    if isinstance(value, (str, os.PathLike)) or not isinstance(value, Iterable):
        msg = f"{label} must be an iterable of relative paths, not {type(value).__name__}"
        raise TypeError(msg)
    return list(value)


def _string_items(value: object, label: str) -> list[str]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        msg = f"{label} must be an iterable of strings, not {type(value).__name__}"
        raise TypeError(msg)
    items = list(value)
    for item in items:
        if not isinstance(item, str):
            msg = f"{label} entries must be strings, got {type(item).__name__}"
            raise TypeError(msg)
    return items


def _posix(name: str | os.PathLike[str]) -> str:
    from rdetoolkit.testing.runner import relative_artifact  # noqa: PLC0415

    return relative_artifact(name).as_posix()


def _label(name: object) -> str:
    text = os.fspath(name) if isinstance(name, (str, os.PathLike)) else str(name)
    return repr(str(text).replace("\\", "/"))


def _listed(title: str, items: Sequence[str]) -> list[str]:
    if not items:
        return []
    return [f"{title}:", *_capped(items)]


def _capped(items: Sequence[str]) -> list[str]:
    shown = [f"  {item}" for item in items[:_MAX_LISTED]]
    if len(items) > _MAX_LISTED:
        shown.append(f"  ... and {len(items) - _MAX_LISTED} more")
    return shown


def _short(value: Any) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=True)
    except (TypeError, ValueError):
        text = repr(value)
    return text if len(text) <= _SHORT_LIMIT else text[: _SHORT_LIMIT - 3] + "..."
