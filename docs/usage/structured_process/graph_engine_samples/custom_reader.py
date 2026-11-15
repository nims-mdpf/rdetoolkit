"""Plot a vendor file format with a custom ``TableReader``.

The fictional ``.instrument`` format starts with ``! key = value`` metadata lines,
followed by a tab-separated header row and numeric data rows. The reader below
implements the three members of the ``TableReader`` protocol (``reader_id``,
``extensions`` and ``read``), is registered in a caller-owned ``ReaderRegistry`` and
is selected by ``render_graph`` from the file suffix. rdetoolkit itself is not
modified, and only the public ``rdetoolkit.graph`` API is imported.

Run it with ``python custom_reader.py <output directory>``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from rdetoolkit.graph import (
    ColumnProvenance,
    DirectorySink,
    GraphResult,
    GraphSpec,
    OutputSpec,
    ReaderRegistry,
    TableData,
    render_graph,
)

SAMPLE = """\
! title = Sample run
! instrument = vendor X-1
time (s)\tsignal (mV)
0\t1.5
1\t2.5
2\t4.0
"""


class InstrumentReader:
    """Read the fictional ``.instrument`` format into a ``TableData``."""

    @property
    def reader_id(self) -> str:
        """Stable id used by ``reader=`` and recorded in ``TableData.reader_id``."""
        return "vendor.instrument"

    @property
    def extensions(self) -> tuple[str, ...]:
        """File suffixes this reader claims under ``reader="auto"``."""
        return (".instrument",)

    def read(self, path: Path) -> TableData:
        """Parse the metadata lines, the header row and the data rows.

        Args:
            path: The ``.instrument`` file.

        Returns:
            The table, one provenance record per column and the metadata block.
        """
        metadata: dict[str, str] = {}
        rows: list[list[str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("!"):
                key, _, value = line[1:].partition("=")
                metadata[key.strip()] = value.strip()
            elif line.strip():
                rows.append(line.split("\t"))
        header, body = rows[0], rows[1:]
        frame = pd.DataFrame([[float(cell) for cell in row] for row in body], columns=header)
        columns = tuple(
            ColumnProvenance(name=name, source="header", source_index=index) for index, name in enumerate(header)
        )
        return TableData(frame=frame, reader_id=self.reader_id, columns=columns, metadata=metadata)


def main(output_dir: Path) -> GraphResult:
    """Write a sample file, then plot it through the custom reader.

    Args:
        output_dir: Directory receiving the sample input and the graphs.

    Returns:
        The graph result; its manifest lists every written file.
    """
    source = output_dir / "sample.instrument"
    output_dir.mkdir(parents=True, exist_ok=True)
    source.write_text(SAMPLE, encoding="utf-8")
    readers = ReaderRegistry([InstrumentReader()])
    return render_graph(
        source,
        GraphSpec(title="Sample run", layout="overlay"),
        output=OutputSpec(sink=DirectorySink(output_dir / "graphs"), formats=("png",), base_name="instrument"),
        readers=readers,
    )


if __name__ == "__main__":
    result = main(Path(sys.argv[1] if len(sys.argv) > 1 else "graph_engine_output"))
    print(result.manifest_json())  # noqa: T201 - command-line demo output
