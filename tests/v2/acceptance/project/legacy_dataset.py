"""Retained v1 compatibility smoke (#676): the measurement step as a v1 callback.

``rdetoolkit run --legacy legacy_dataset.py::dataset`` must keep working for
existing projects. The gate compares the structured artifact, invoices, raw
copies and ``job.failed`` it produces with those of ``processing.py`` on the
same input.
"""

from math import isfinite
from pathlib import Path

from rdetoolkit.exceptions import StructuredError


def dataset(srcpaths, resource_paths):  # noqa: ANN001, ANN201, ARG001 -- the v1 callback signature
    """Write the tile's measurements exactly as ``processing.pipeline`` does."""
    sources = sorted(Path(source) for source in resource_paths.rawfiles if Path(source).suffix == ".txt")
    values = []
    for source in sources:
        text = source.read_text(encoding="utf-8")
        message = f"Expected a positive measurement, got {text!r}; repair the input."
        try:
            value = float(text)
        except ValueError as error:
            raise StructuredError(message, ecode=1) from error
        if not isfinite(value) or value <= 0:
            raise StructuredError(message, ecode=1)
        values.append(value)
    # Bytes, as save_text writes them: text mode would turn "\n" into "\r\n" on Windows.
    Path(resource_paths.struct, "measurement.txt").write_bytes("".join(f"{value}\n" for value in values).encode("utf-8"))
