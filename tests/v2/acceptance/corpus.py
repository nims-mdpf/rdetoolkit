"""Deterministic five-mode acceptance corpus of the agent readiness gate (#676).

Every project is built the way a user (or a coding agent) builds one, through
the installed public CLI: ``new config --preset`` writes ``rdeconfig.yaml``,
``new invoice`` writes ``invoice.json`` from the schema and, for ExcelInvoice,
``new excelinvoice`` writes the workbook that is then filled in. Only the raw
measurements, the SmartTable table and the RDEFormat archive are written by
hand, in their documented layouts. The module imports neither ``src/``
nor rdetoolkit itself, so the gate runs unchanged against an installed wheel.

A *bad* corpus differs from the good one in exactly one measurement: the file
:data:`FAILING_SOURCE` holds :data:`FAKE_SECRET` instead of a number. The user
code quotes the rejected text in its error, so the secret reaches the run's own
``job.failed`` and run report; the gate checks it never reaches an
agent-facing JSON view. :func:`repair` restores the good value in place.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl

PROJECT_TEMPLATE = Path(__file__).with_name("project")

#: Fake credential planted in the failing measurement and in the environment.
FAKE_SECRET = "FAKE-SECRET-676-sk-acceptance-0000"  # noqa: S105 -- deliberately fake
#: Environment variable that carries :data:`FAKE_SECRET` into every CLI process.
SECRET_ENV = "RDETOOLKIT_ACCEPTANCE_API_TOKEN"  # noqa: S105 -- a variable name

#: The measurement each source file holds in a good corpus.
GOOD_VALUES = {"m0.txt": "2.5", "m1.txt": "4.0"}

#: Fixed ZIP member timestamp: a wall-clock time would make inputs non-reproducible.
_ZIP_TIME = (2026, 11, 19, 0, 0, 0)
OWNER_ID = "0" * 56


@dataclass(frozen=True)
class ModeSpec:
    """What one mode's corpus contains and the tiles the Runner must make of it.

    Attributes:
        mode: RunReport / doctor mode name.
        preset: ``rdetoolkit new config --preset`` value.
        tile_sources: Measurement file of each tile, in iteration order.
        tile_names: Per-tile invoice ``basic.dataName``.
        raw_dir: Directory under each tile that keeps the raw measurement.
    """

    mode: str
    preset: str
    tile_sources: tuple[str, ...]
    tile_names: tuple[str, ...]
    raw_dir: str

    @property
    def failing_index(self) -> int:
        """Iteration index of the tile whose measurement is broken in a bad corpus."""
        return self.tile_sources.index(FAILING_SOURCE[self.mode])


MODES: dict[str, ModeSpec] = {
    "invoice": ModeSpec("invoice", "minimal", ("m0.txt",), ("acceptance",), "nonshared_raw"),
    # One workbook row per file, in row order.
    "excelinvoice": ModeSpec("excelinvoice", "minimal", ("m0.txt", "m1.txt"), ("row-m0", "row-m1"), "nonshared_raw"),
    # One tile per input file, in file-name order; every tile keeps the source invoice.
    "multidatatile": ModeSpec("multidatatile", "multitile", ("m0.txt", "m1.txt"), ("acceptance", "acceptance"), "nonshared_raw"),
    # One tile per numbered archive directory; its raw/ files are published as raw/.
    "rdeformat": ModeSpec("rdeformat", "rdeformat", ("m0.txt", "m1.txt"), ("acceptance", "acceptance"), "raw"),
    # The frozen v1 SmartTable contract (tests/v2/contract/fixtures/expected/v1/
    # smarttable/ok.json) runs the last table row as tile 0 (data/) and the
    # earlier rows as divided/0001.. in order, so row-m1 comes first.
    "smarttable": ModeSpec("smarttable", "smarttable", ("m1.txt", "m0.txt"), ("row-m1", "row-m0"), "nonshared_raw"),
}

#: The source file broken in each mode's bad corpus. Multi-tile modes break the
#: second row/file, so a fail-fast run must keep the earlier tile's results.
FAILING_SOURCE = {mode: ("m0.txt" if mode == "invoice" else "m1.txt") for mode in MODES}


def cli_env(home: Path) -> dict[str, str]:
    """Return the environment of every gate CLI process (fake secret included)."""
    env = dict(os.environ)
    env[SECRET_ENV] = FAKE_SECRET
    env["MPLCONFIGDIR"] = str(home / "mplconfig")
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("PYTHONPATH", None)
    return env


def rdetoolkit(project: Path, *args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run ``python -m rdetoolkit ARGS`` from ``project`` with the installed interpreter."""
    return subprocess.run(  # noqa: S603 -- fixed interpreter, arguments built by the gate
        [sys.executable, "-m", "rdetoolkit", *args],
        cwd=project,
        env=cli_env(project.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )


def _checked(result: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    assert result.returncode == 0, f"{result.args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}"
    return result


def measurements(mode: str, *, bad: bool) -> dict[str, str]:
    """Return the raw measurement files of a corpus."""
    names = MODES[mode].tile_sources
    values = {name: GOOD_VALUES[name] for name in sorted(names)}
    if bad:
        values[FAILING_SOURCE[mode]] = FAKE_SECRET
    return values


def _zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, text in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, text.encode("utf-8"))


def _write_raw_inputs(mode: str, inputdata: Path, values: dict[str, str]) -> None:
    if mode in {"invoice", "multidatatile"}:
        for name, text in values.items():
            (inputdata / name).write_text(text, encoding="utf-8")
    elif mode in {"excelinvoice", "smarttable"}:
        _zip(inputdata / "measurements.zip", values)
    elif mode == "rdeformat":
        members: dict[str, str] = {}
        for index, name in enumerate(sorted(values)):
            members[f"{index:04d}/raw/{name}"] = values[name]
            members[f"{index:04d}/structured/prepared.csv"] = f"tile,{index}\n"
        _zip(inputdata / "rdeformat_measurements.zip", members)
    else:  # pragma: no cover -- MODES is closed
        raise AssertionError(mode)


def _fill_excelinvoice(workbook: Path) -> None:
    """Fill the generated ExcelInvoice template: one row per measurement file."""
    book = openpyxl.load_workbook(workbook)
    sheet = book["invoice_form"]
    keys = [cell.value for cell in sheet[3]]
    first_data_row = 5
    for offset, name in enumerate(sorted(GOOD_VALUES)):
        stem = Path(name).stem
        row = {
            "name": name,
            "dataset_title": "acceptance",
            "dataOwnerId": OWNER_ID,
            "dataName": f"row-{stem}",
            "names": "sample",
            "ownerId": OWNER_ID,
            "operator": "agent",
        }
        for column, key in enumerate(keys, start=1):
            if key in row:
                sheet.cell(row=first_data_row + offset, column=column, value=row[key])
    book.save(workbook)


def _write_smarttable(inputdata: Path) -> None:
    rows = "".join(f"row-{Path(name).stem},{name},agent\n" for name in sorted(GOOD_VALUES))
    table = "データ名,入力ファイル,測定者\nbasic/dataName,inputdata1,custom/operator\n" + rows
    (inputdata / "smarttable_acceptance.csv").write_text(table, encoding="utf-8")


def _fill_invoice(path: Path) -> None:
    invoice: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    invoice["datasetId"] = "acceptance-dataset"
    invoice["basic"].update({"dateSubmitted": "2026-11-19", "dataName": "acceptance"})
    invoice["custom"]["operator"] = "agent"
    invoice["sample"]["names"] = ["sample"]
    path.write_text(json.dumps(invoice, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


#: Scaffolded projects without raw inputs, one per mode, built once per process.
_SCAFFOLDS: dict[str, Path] = {}


def build(mode: str, project: Path, *, bad: bool) -> Path:
    """Create a complete project for ``mode`` under ``project`` and return it.

    The first project of a mode is scaffolded through the CLI next to
    ``project``; later ones copy that scaffold (each CLI start costs seconds)
    and only write their own raw inputs.

    Args:
        mode: One of :data:`MODES`.
        project: New project root; ``project/data`` becomes the data root.
        bad: Break the measurement :data:`FAILING_SOURCE` names.

    Returns:
        ``project``.
    """
    scaffold = _SCAFFOLDS.get(mode)
    if scaffold is None or not scaffold.is_dir():
        scaffold = _scaffold(mode, project.parent / f"scaffold-{mode}")
        _SCAFFOLDS[mode] = scaffold
    shutil.copytree(scaffold, project)
    _write_raw_inputs(mode, project / "data" / "inputdata", measurements(mode, bad=bad))
    return project


def _scaffold(mode: str, project: Path) -> Path:
    """Generate a project's config, invoice, schema files and tables; no raw inputs."""
    spec = MODES[mode]
    data = project / "data"
    inputdata, invoice, tasksupport = data / "inputdata", data / "invoice", data / "tasksupport"
    for directory in (inputdata, invoice, tasksupport):
        directory.mkdir(parents=True)
    shutil.copyfile(PROJECT_TEMPLATE / "processing.py", project / "processing.py")
    for name in ("invoice.schema.json", "metadata-def.json"):
        shutil.copyfile(PROJECT_TEMPLATE / name, tasksupport / name)

    _checked(rdetoolkit(project, "new", "config", "--preset", spec.preset, "-o", "data/tasksupport"))
    config = tasksupport / "rdeconfig.yaml"
    # Pin the v2 iteration policy and skip thumbnails (no image inputs) explicitly.
    with config.open("a", encoding="utf-8") as stream:
        stream.write("\nexecution:\n  on_iteration_error: fail_fast\n")
    text = config.read_text(encoding="utf-8").replace("save_thumbnail_image: true", "save_thumbnail_image: false")
    config.write_text(text, encoding="utf-8")

    _checked(rdetoolkit(project, "new", "invoice", "data/tasksupport/invoice.schema.json", "-o", "data/invoice/invoice.json"))
    _fill_invoice(invoice / "invoice.json")

    if mode == "excelinvoice":
        workbook = inputdata / "acceptance_excel_invoice.xlsx"
        _checked(rdetoolkit(project, "new", "excelinvoice", "data/tasksupport/invoice.schema.json", "-o", str(workbook.relative_to(project))))
        _fill_excelinvoice(workbook)
    if mode == "smarttable":
        _write_smarttable(inputdata)
    return project


def repair(mode: str, project: Path) -> None:
    """Replace a bad corpus's broken measurement by its good value, in place."""
    for path in (project / "data" / "inputdata").iterdir():
        if path.suffix in {".txt", ".zip"}:
            path.unlink()
    _write_raw_inputs(mode, project / "data" / "inputdata", measurements(mode, bad=False))


def tile_dir(data: Path, index: int) -> Path:
    """Return the output root of iteration ``index`` (tile 0 is the data root itself)."""
    return data if index == 0 else data / "divided" / f"{index:04d}"
