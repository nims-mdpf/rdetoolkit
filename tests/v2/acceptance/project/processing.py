"""Acceptance-gate user code (#676): one plain eager v2 flow for every RDE mode.

This file stands in for what a coding agent writes by following the shipped
rdetoolkit-flow-authoring Skill: reserved types are injected at the flow
boundary only, node arguments are passed explicitly, and the artifacts come
from public ``rdetoolkit.nodes`` functions. The gate copies it unchanged into
each mode's project as ``processing.py``.

The validation error deliberately quotes the rejected input, so a failing
run's ``job.failed`` and run report carry the raw text. The gate uses that to
prove that the agent-facing JSON views leave it out.
"""

from math import isfinite

from rdetoolkit import flow, node
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes import build_meta, read_text, save_json, save_meta, save_text
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext


@node
def parse_measurement(text: str) -> float:
    """Parse one positive, finite measurement."""
    message = f"Expected a positive measurement, got {text!r}; repair the input."
    try:
        value = float(text)
    except ValueError as error:
        raise StructuredError(message, ecode=1) from error
    if not isfinite(value) or value <= 0:
        raise StructuredError(message, ecode=1)
    return value


@flow
def pipeline(paths: InputPaths, out: OutputContext, iteration: IterationInfo) -> None:
    """Write this tile's measurements, metadata with units, and the injected inputs."""
    sources = sorted(source for source in paths.rawfiles if source.suffix == ".txt")
    save_json({"iteration": iteration.index, "measurements": [source.name for source in sources]}, out, "inputs.json")
    values = [parse_measurement(read_text(source)) for source in sources]
    save_text("".join(f"{value}\n" for value in values), out, "measurement.txt")
    metadata = build_meta(
        {"sample_count": str(len(values))},
        paths.tasksupport / "metadata-def.json",
        repeated={"position": [str(value) for value in values]},
    )
    save_meta(metadata, out)
