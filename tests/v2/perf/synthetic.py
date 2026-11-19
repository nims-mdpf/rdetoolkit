"""Deterministic synthetic inputs for the resource smoke tests and the GA benchmark (#739).

Everything here is generated from fixed formulas, so no real research data or
secret is needed and two builds of the same size are byte-identical. The module
imports only the installed ``rdetoolkit`` and its dependencies, so the benchmark
can run against a clean wheel installation (``scripts/bench_ga.py``).
"""

from __future__ import annotations

import gc
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OWNER_ID = "0" * 56
_DATE = "2026-11-19"
_INVOICE: dict[str, Any] = {
    "datasetId": "bench-739",
    "basic": {"dateSubmitted": _DATE, "dataOwnerId": OWNER_ID, "dataName": "bench-739"},
}
_EMPTY_SCHEMA: dict[str, Any] = {"properties": {}}
_SAMPLE_SCHEMA: dict[str, Any] = {
    "required": ["sample"],
    "properties": {"sample": {"type": "object", "label": {"ja": "試料情報", "en": "Sample"}, "properties": {}}},
}


def wide_frame(series: int, rows: int = 200) -> pd.DataFrame:
    """Return an x column and ``series`` Y columns with one shared unit.

    Args:
        series: Number of Y columns.
        rows: Number of rows.

    Returns:
        ``x (s)`` followed by ``y0000 (V)``, ``y0001 (V)``, ...
    """
    x = np.linspace(0.0, 10.0, rows)
    columns = {f"y{index:04d} (V)": np.sin(x + index / 7.0) for index in range(series)}
    return pd.DataFrame({"x (s)": x, **columns})


def write_csv(path: Path, series: int, rows: int) -> Path:
    """Write ``wide_frame(series, rows)`` as a header-row CSV.

    Args:
        path: Destination file; its parent is created.
        series: Number of Y columns.
        rows: Number of data rows.

    Returns:
        ``path``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    wide_frame(series, rows).to_csv(path, index=False, float_format="%.6f")
    return path


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _flat_root(root: Path, schema: dict[str, Any], *, extended_mode: str | None = None) -> Path:
    """Create the flat layout; SmartTable and ExcelInvoice are selected by their file names."""
    for name in ("inputdata", "invoice", "tasksupport"):
        (root / name).mkdir(parents=True, exist_ok=True)
    _write_json(root / "invoice" / "invoice.json", _INVOICE)
    _write_json(root / "tasksupport" / "invoice.schema.json", schema)
    if extended_mode is not None:
        config = f"system:\n  extended_mode: {extended_mode}\n"
        (root / "tasksupport" / "rdeconfig.yaml").write_text(config, encoding="utf-8")
    return root


def smarttable_root(root: Path, rows: int) -> Path:
    """Build a flat SmartTable project whose table has ``rows`` data rows.

    Args:
        root: Empty project directory (flat layout: ``root/inputdata`` ...).
        rows: Number of SmartTable data rows, one tile each.

    Returns:
        ``root``.
    """
    _flat_root(root, _SAMPLE_SCHEMA)
    rows_text = (f"row_{index:05d},sample_{index:05d}" for index in range(rows))
    lines = ["Data name,Sample name", "basic/dataName,sample/names", *rows_text]
    (root / "inputdata" / "smarttable_bench.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def excelinvoice_root(root: Path, rows: int) -> Path:
    """Build a flat ExcelInvoice project with ``rows`` rows, each naming one raw file.

    Args:
        root: Empty project directory (flat layout).
        rows: Number of invoice rows, one tile each.

    Returns:
        ``root``.
    """
    _flat_root(root, _EMPTY_SCHEMA)
    names = [f"raw_{index:05d}.txt" for index in range(rows)]
    sheet1 = pd.DataFrame(
        [
            ["data_file_names", "basic", "basic"],
            ["name", "dataName", "dataOwnerId"],
            ["Input filename", "Data name", "Data owner ID"],
            *[[name, f"data_{index:05d}", OWNER_ID] for index, name in enumerate(names)],
        ],
        columns=["invoiceList_format_id", "bench_739", ""],
    )
    with pd.ExcelWriter(root / "inputdata" / "bench_excel_invoice.xlsx") as writer:
        sheet1.to_excel(writer, sheet_name="invoice_form", index=False)
        pd.DataFrame(columns=["term_id", "key_name"]).to_excel(writer, sheet_name="generalTerm", index=False)
        pd.DataFrame(columns=["sample_class_id", "term_id", "key_name"]).to_excel(
            writer, sheet_name="specificTerm", index=False,
        )
    with zipfile.ZipFile(root / "inputdata" / "bench_raw.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 19, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, f"{name}\n")
    return root


def multidatatile_root(root: Path, tiles: int) -> Path:
    """Build a flat MultiDataTile project with ``tiles`` single-file tiles.

    Args:
        root: Empty project directory (flat layout).
        tiles: Number of input files, one tile each.

    Returns:
        ``root``.
    """
    _flat_root(root, _EMPTY_SCHEMA, extended_mode="MultiDataTile")
    for index in range(tiles):
        (root / "inputdata" / f"tile_{index:05d}.txt").write_text(f"{index}\n", encoding="utf-8")
    return root


def live_figures() -> int:
    """Return how many Matplotlib ``Figure`` objects are reachable or awaiting collection.

    Engine figures are never registered with pyplot (GE-09), so
    ``plt.get_fignums()`` cannot see them; this counts the objects themselves
    without forcing a collection first.

    Returns:
        The number of ``matplotlib.figure.Figure`` instances the collector tracks.
    """
    if "matplotlib.figure" not in sys.modules:
        return 0
    figure_type = sys.modules["matplotlib.figure"].Figure
    return sum(1 for item in gc.get_objects() if isinstance(item, figure_type))


def file_manifest(root: Path) -> list[tuple[str, int]]:
    """Return ``(relative posix path, size)`` for every file below ``root``, sorted.

    Args:
        root: Directory to list.

    Returns:
        The sorted manifest; empty when ``root`` does not exist.
    """
    if not root.exists():
        return []
    return sorted((path.relative_to(root).as_posix(), path.stat().st_size) for path in root.rglob("*") if path.is_file())
