"""A third-party instrument reader written only against the public reader contract.

File format (``.instrument``): leading ``! key = value`` metadata lines, then one
tab-separated header row and tab-separated numeric rows. Nothing in rdetoolkit is
edited or monkeypatched to support it.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pandas as pd

from rdetoolkit.graph import ColumnProvenance, TableData

READER_ID = "vendor.instrument"


class InstrumentReader:
    """Read the fictional vendor ``.instrument`` format."""

    def __init__(self, reader_id: str = READER_ID, extensions: tuple[str, ...] = (".instrument",)) -> None:
        self._reader_id = reader_id
        self._extensions = extensions

    @property
    def reader_id(self) -> str:
        return self._reader_id

    @property
    def extensions(self) -> tuple[str, ...]:
        return self._extensions

    def read(self, path: Path) -> TableData:
        lines = path.read_text(encoding="utf-8").splitlines()
        metadata: dict[str, str] = {}
        rows: list[list[str]] = []
        for line in lines:
            if line.startswith("!"):
                key, _, value = line[1:].partition("=")
                metadata[key.strip()] = value.strip()
            elif line.strip():
                rows.append(line.split("\t"))
        header, body = rows[0], rows[1:]
        frame = pd.DataFrame([[float(cell) for cell in row] for row in body], columns=header)
        columns = tuple(ColumnProvenance(name=name, source="header", source_index=index) for index, name in enumerate(header))
        return TableData(frame=frame, reader_id=self._reader_id, columns=columns, metadata=metadata)


#: Entry-point target form 1: a ready ``TableReader`` instance.
READER = InstrumentReader()


def make_reader() -> InstrumentReader:
    """Entry-point target form 2: a zero-argument factory returning a reader."""
    return InstrumentReader()


def make_other_reader() -> InstrumentReader:
    """A second vendor reader that claims the same suffix under another id."""
    return InstrumentReader(reader_id="other.instrument")


def make_mismatched_reader() -> InstrumentReader:
    """A factory whose reader id disagrees with any entry-point name but its own."""
    return InstrumentReader(reader_id="not.the.entry.point.name")


def make_failing_reader() -> InstrumentReader:
    """A factory that fails when called."""
    msg = "vendor licence file missing"
    raise RuntimeError(msg)


#: Not a reader at all.
NOT_A_READER = object()


class ReturnsNoTableData(InstrumentReader):
    """A reader that violates the contract by returning a bare DataFrame."""

    def read(self, path: Path) -> TableData:
        # Deliberately wrong at runtime; cast so the typed-consumer check stays clean.
        return cast("TableData", pd.DataFrame({"x": [1.0]}))
