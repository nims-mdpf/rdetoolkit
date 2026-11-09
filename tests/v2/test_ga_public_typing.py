"""GA-TYPE EP/BV: installed stubs expose and constrain the new public APIs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _check(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )


def test_public_ga_api_is_typed_for_consumers__ga_type_ep_1(tmp_path: Path) -> None:
    """GA-TYPE-EP-1: source-only type checking cannot hide stale distribution stubs."""
    # Given: a standalone consumer using the supported v2 surface
    source = '''from pathlib import Path
from typing import Any
from rdetoolkit import flow
from rdetoolkit.nodes import build_meta, read_excel, read_json, save_csv, save_json, save_text, save_invoice, save_figure, plot_lines, unzip_inputs
from rdetoolkit.types import InputPaths, OutputContext, InvoiceData, Metadata

@flow(error_code=7, error_message="mapped")
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    metadata = Metadata(units={"x": "g"}, variable=[{"x": {"value": 1}}])
    metadata.set("x", 1, unit="g")
    extracted: list[Path] = unzip_inputs(paths.rawfiles[0], out.struct)
    build_meta({"x": "1"}, Path("metadata-def.json"), repeated={"x": [1, 2]})
    if paths.invoice_org is not None:
        read_json(paths.invoice_org)
    read_excel(Path("data.xlsx"), sheet_name="data", header=None, skiprows=1, nrows=2, usecols=[0])
    save_text("text", out, "text.txt", kind="attachment")
    save_json({}, out, "data.json", kind="attachment")
    save_invoice(InvoiceData(raw={}), out)

def plots(frame: Any, figure: Any, out: OutputContext) -> None:
    save_csv(frame, out, "data.csv", float_format="%.2f", header=False, index=True)
    plot_lines(frame, out, "plot.png", x="x", y=["y"], title="Plot", yscale="log", dpi=100, kind="other_image")
    save_figure(figure, out, "figure.png", dpi=100, kind="other_image")
'''
    # When: checking against the installed package, outside the repository config
    result = _check(tmp_path, source)
    # Then: all exported names, fields and keyword options are available
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("source, diagnostic", [
    ('from rdetoolkit.types import Metadata\nMetadata().set("x", 1, unit=7)\n', "[arg-type]"),
    ('from rdetoolkit import flow\n@flow(error_code="bad")\ndef pipeline() -> None:\n    pass\n', "[call-overload]"),
    ('from rdetoolkit.nodes import save_json\nfrom rdetoolkit.types import OutputContext\ndef invalid(out: OutputContext) -> None:\n    save_json({}, out, "x.json", kind="bad")\n', "[arg-type]"),
    ('from pathlib import Path\nfrom rdetoolkit.nodes import read_excel\nread_excel(Path("x.xlsx"), sheet_name=object())\n', "[arg-type]"),
])
def test_invalid_ga_arguments_are_rejected__ga_type_neg_1_2_3_4(tmp_path: Path, source: str, diagnostic: str) -> None:
    """GA-TYPE-NEG-1..4: new APIs retain useful type constraints for consumers."""
    # Given: a standalone consumer with an invalid public argument
    # When: checking its declared types
    result = _check(tmp_path, source)
    # Then: the precise argument/overload violation is reported
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout
