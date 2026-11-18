"""Value-free graph input preview for ``run --validate-only --explain`` (#735).

For every tabular raw file of every planned tile this reports how the Graph
Engine's builtin content detection (``detect_table_format``) would read it:
the selected reader or the reason none was selected, the candidates with their
confidence and structural evidence, and the sampled shape. Detection reads a
bounded sample through a read-only handle, so nothing in the input tree is
written.

Only the builtin readers are consulted. Entry-point reader plugins are never
loaded, because the explanation promises not to import code beyond rdetoolkit,
and the plot configuration of the user's flow is unknown before the flow runs.
Column names and cell values are never reported; the column count stands in
for them, like the rest of the explanation, which carries no input values.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import pandas as pd

from rdetoolkit.graph.exceptions import AmbiguousFormatError, InvalidCSVFormatError
from rdetoolkit.graph.readers.base import DetectionDecision, FormatCandidate
from rdetoolkit.graph.readers.detection import detect_table_format
from rdetoolkit.runner.input_snapshot import InputGroup, InputReference

#: Suffixes the preview treats as tables a plot node may read.
TABULAR_SUFFIXES: Final = (".csv", ".tsv")
GRAPH_CHECKS: Final = ("table_format_detection",)
GRAPH_NOT_CHECKED: Final = ("plugin_readers", "flow_plot_configuration", "rendering")


@dataclass(frozen=True, slots=True)
class GraphFilePreview:
    """How builtin detection would read one tabular input, without its values."""

    name: str
    status: str
    reason: str
    reader: str | None = None
    candidates: tuple[FormatCandidate, ...] = ()
    encoding: str | None = None
    delimiter: str | None = None
    column_count: int | None = None
    data_rows: int | None = None
    sampled_rows: int = 0
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the explain-schema representation."""
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "reader": self.reader,
            "candidates": [
                {"reader_id": c.reader_id, "confidence": c.confidence, "evidence": list(c.evidence)} for c in self.candidates
            ],
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "column_count": self.column_count,
            "data_rows": self.data_rows,
            "sampled_rows": self.sampled_rows,
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class GraphTilePreview:
    """Graph input previews of one planned tile, in tile input order."""

    index: int
    files: tuple[GraphFilePreview, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the explain-schema representation."""
        return {"index": self.index, "files": [item.to_dict() for item in self.files]}


@dataclass(frozen=True, slots=True)
class GraphPreview:
    """What the pre-flow snapshot says about graph inputs, and what it cannot say."""

    status: str
    reason: str
    tiles: tuple[GraphTilePreview, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the explain-schema representation."""
        return {
            "status": self.status,
            "reason": self.reason,
            "checks": list(GRAPH_CHECKS),
            "not_checked": list(GRAPH_NOT_CHECKED),
            "tiles": [tile.to_dict() for tile in self.tiles],
        }


def _outcome(decision: DetectionDecision) -> tuple[str, str]:
    if decision.selected is not None:
        return "detected", "confident_builtin_reader"
    return "ambiguous", "no_confident_candidate" if decision.candidates else "layout_undetermined"


def _from_decision(name: str, decision: DetectionDecision) -> GraphFilePreview:
    status, reason = _outcome(decision)
    return GraphFilePreview(
        name=name,
        status=status,
        reason=reason,
        reader=decision.selected,
        candidates=decision.candidates,
        encoding=decision.encoding,
        delimiter=decision.delimiter,
        column_count=len(decision.preview_columns) if decision.preview_columns else None,
        data_rows=decision.data_rows,
        sampled_rows=decision.sampled_rows,
        truncated=decision.truncated,
    )


def _preview_file(ref: InputReference) -> GraphFilePreview:
    if ref.member is not None:
        return GraphFilePreview(ref.name, "skipped", "archive_member_not_extracted")
    try:
        decision = detect_table_format(ref.source)
    except AmbiguousFormatError as exc:
        undecided = DetectionDecision(selected=None, forced=False, candidates=())
        decision = exc.decision if isinstance(exc.decision, DetectionDecision) else undecided
    except (InvalidCSVFormatError, OSError):
        return GraphFilePreview(ref.name, "unreadable", "empty_oversized_or_unreadable")
    except (csv.Error, pd.errors.ParserError):
        # The bounded sample does not parse (CR-only newlines, a quoted field
        # crossing the sniff window), although a named reader may read the
        # whole file. Report it per file instead of aborting the explanation.
        return GraphFilePreview(ref.name, "ambiguous", "sample_not_parseable")
    return _from_decision(ref.name, decision)


def _is_tabular(ref: InputReference) -> bool:
    name = ref.member if ref.member is not None else ref.source.name
    return name.lower().endswith(TABULAR_SUFFIXES)


def preview_graph_inputs(groups: Sequence[InputGroup]) -> GraphPreview:
    """Preview how builtin table detection reads each tile's tabular inputs.

    Args:
        groups: The planned tiles' input groups, in tile order.

    Returns:
        ``previewed`` with one entry per tile when any ``.csv`` or ``.tsv``
        input was sampled; ``deferred`` when every such input is a member of an
        archive that is extracted only at run time; otherwise
        ``no_tabular_inputs`` with no tiles.
    """
    tiles = tuple(
        GraphTilePreview(index, tuple(_preview_file(ref) for ref in group.files if _is_tabular(ref))) for index, group in enumerate(groups)
    )
    statuses = {item.status for tile in tiles for item in tile.files}
    if not statuses:
        return GraphPreview("no_tabular_inputs", "no_csv_or_tsv_inputs")
    if statuses == {"skipped"}:
        return GraphPreview("deferred", "tabular_inputs_inside_archives", tiles)
    return GraphPreview("previewed", "pre_flow_snapshot", tiles)
