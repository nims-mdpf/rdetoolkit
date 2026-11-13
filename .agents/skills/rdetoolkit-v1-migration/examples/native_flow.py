# ruff: noqa: INP001
"""Explicit artifact-node version of the source-conversion example."""
from __future__ import annotations

import json
from typing import Any

from rdetoolkit import flow, node
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes.image import save_main_image
from rdetoolkit.nodes.meta import save_meta
from rdetoolkit.nodes.structured import save_text
from rdetoolkit.types import InputPaths, Metadata, OutputContext


@node(id="migration.example.read_measurement")
def read_measurement(paths: InputPaths) -> dict[str, Any]:
    """Read instrument data and retain its existing rejection contract."""
    payload = json.loads((paths.inputdata / "measurement.json").read_text(encoding="utf-8"))
    if payload["fail"]:
        msg = "Measurement rejected by the instrument"
        raise StructuredError(msg, ecode=999)
    return payload


@flow(id="migration.example.native_pipeline")
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    """Write the same values, units, repeated rows and image bytes as v1."""
    payload = read_measurement(paths)
    constant = payload["metadata"]["constant"]
    metadata = Metadata(
        custom={key: cell["value"] for key, cell in constant.items()},
        units={key: cell["unit"] for key, cell in constant.items() if "unit" in cell},
        variable=payload["metadata"]["variable"],
    )
    save_meta(metadata, out)
    save_text(payload["table"], out, "table.csv")
    save_main_image(paths.inputdata / "measurement.png", out, "measurement.png")
