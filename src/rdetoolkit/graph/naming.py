"""File-name policy for graph artifacts (GE-02).

Every destination stem is derived and reserved before any figure is rendered or any
file is written, so two series can never overwrite each other's artifact and an
unsafe header can no longer fail half-way through a run.

The policy is deterministic: it depends only on the order of the candidates, never on
time, hashes or directory contents.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from rdetoolkit.graph.textutils import sanitize_filename, to_snake_case

DEFAULT_BASE_STEM: Final = "plot"
FILENAME_COLLISION: Final = "filename_collision"


@dataclass(frozen=True, slots=True)
class GraphDiagnostic:
    """A non-fatal finding attached to a graph plan or result.

    It lives in this leaf module because the planner imports the naming policy;
    defining it next to the plan would make the two modules import each other.

    Attributes:
        code: Stable identifier, for example ``"filename_collision"``.
        severity: ``"info"`` or ``"warning"``.
        message: Human-readable explanation.
        series_ids: Series the finding refers to, in plan order.
    """

    code: str
    severity: Literal["info", "warning"]
    message: str
    series_ids: tuple[str, ...] = ()


def sanitize_stem(text: str) -> str:
    """Make a stem safe to use as a single file name inside an output directory.

    Characters invalid in file names (including both path separators) become
    ``_`` and every ``..`` pair becomes ``_``, so the result can never address a
    parent or sibling directory.

    Args:
        text: Raw stem text.

    Returns:
        The sanitized stem; empty when ``text`` is empty.
    """
    return sanitize_filename(text).replace("..", "_")


def collision_key(stem: str) -> str:
    """Return the key under which two stems are considered the same file name.

    NFC normalization plus case folding, so names that would clash on
    case-insensitive or normalizing filesystems (macOS, Windows) count as equal.

    Args:
        stem: File stem.

    Returns:
        The collision key.
    """
    return unicodedata.normalize("NFC", stem).casefold()


def series_stem(base: str, header_series: str | None, raw_header: str) -> str:
    """Derive the candidate stem of an individual figure.

    The rule is the v1 rule (``{base}_{to_snake_case(series prefix or header)}``)
    with the series part sanitized, so a safe, non-colliding name is unchanged.

    Args:
        base: Base file name of the plot (title or explicit name).
        header_series: Series prefix parsed from the header, if any.
        raw_header: The raw column header.

    Returns:
        The candidate stem (not yet reserved).
    """
    base_part = sanitize_stem(base) or DEFAULT_BASE_STEM
    series_part = sanitize_stem(to_snake_case(header_series or raw_header))
    return f"{base_part}_{series_part}"


def reserve_stems(
    candidates: Sequence[tuple[str, str]],
) -> tuple[tuple[str, ...], tuple[GraphDiagnostic, ...]]:
    """Reserve one unique stem per series.

    A candidate whose collision key is unique is kept byte-identical. Every member
    of a collision group gets ``_{series_id}`` appended; if a suffixed stem still
    collides with another final stem, its id is appended again until it is unique.
    Stems that were unique from the start are never changed.

    Args:
        candidates: ``(series_id, candidate_stem)`` pairs in plan order.

    Returns:
        The final stems in candidate order, and one ``filename_collision`` warning
        diagnostic per collision group that had to be resolved.

    Raises:
        TypeError: If a series id or stem is not a ``str``.
        ValueError: If a stem is empty or contains a path separator or ``..``, or
            if a series id is empty, unsafe or duplicated (under the collision key).
    """
    _validate_candidates(candidates)
    series_ids = tuple(series_id for series_id, _ in candidates)
    stems = [stem for _, stem in candidates]
    movable = [False] * len(stems)
    diagnostics: list[GraphDiagnostic] = []
    while True:
        groups = _collision_groups(stems)
        if not groups:
            return tuple(stems), tuple(diagnostics)
        for members in groups:
            diagnostics.append(_resolve_group(members, series_ids, stems, movable))


def _validate_candidates(candidates: Sequence[tuple[str, str]]) -> None:
    """Reject candidates that cannot name a file safely, before reserving anything."""
    seen_ids: set[str] = set()
    for series_id, stem in candidates:
        if not isinstance(series_id, str) or not isinstance(stem, str):
            msg = f"series id and stem must be str, got {series_id!r}, {stem!r}"
            raise TypeError(msg)
        _check_part(stem, "stem")
        _check_part(series_id, "series id")
        key = collision_key(series_id)
        if key in seen_ids:
            msg = f"duplicate series id {series_id!r}"
            raise ValueError(msg)
        seen_ids.add(key)


def _check_part(value: str, what: str) -> None:
    """Reject an empty value or one that could leave the output directory."""
    if not value:
        msg = f"{what} must not be empty"
        raise ValueError(msg)
    if "/" in value or "\\" in value or ".." in value:
        msg = f"{what} {value!r} contains a path separator or '..'"
        raise ValueError(msg)


def _collision_groups(stems: Sequence[str]) -> list[tuple[int, ...]]:
    """Return the indices of each group of stems sharing a key, in first-index order."""
    by_key: dict[str, list[int]] = {}
    for index, stem in enumerate(stems):
        by_key.setdefault(collision_key(stem), []).append(index)
    return [tuple(members) for members in by_key.values() if len(members) > 1]


def _resolve_group(
    members: tuple[int, ...],
    series_ids: tuple[str, ...],
    stems: list[str],
    movable: list[bool],
) -> GraphDiagnostic:
    """Suffix the members of one collision group in place and describe the change.

    In the first round every member is suffixed: under the v1 overwrite the shared
    name held the LAST series, so letting the first keep it would silently change
    what an existing file name means. In later rounds only already-suffixed members
    move, so a name that was unique from the start is never changed.
    """
    original = stems[members[0]]
    first_round = not any(movable[index] for index in members)
    moved = [index for index in members if first_round or movable[index]]
    for index in moved:
        stems[index] = f"{stems[index]}_{series_ids[index]}"
        movable[index] = True
    renamed = ", ".join(f"{series_ids[i]} -> {stems[i]!r}" for i in moved)
    message = (
        f"File name stem {original!r} is shared by series "
        f"{', '.join(series_ids[i] for i in members)} (case-insensitive); "
        f"series ids appended so no artifact overwrites another: {renamed}"
    )
    return GraphDiagnostic(
        code=FILENAME_COLLISION,
        severity="warning",
        message=message,
        series_ids=tuple(series_ids[i] for i in members),
    )
