#!/usr/bin/env python3
"""Verify that a built rdetoolkit wheel is usable by strict-typed consumers.

Checks (issue #642, RDE-009):

1. The wheel ships ``py.typed`` and every ``.pyi`` stub of the source tree,
   and no ``X.py``/``X.pyi`` module that a package directory ``X/`` shadows
   (type checkers read the package and never the sibling, #642/#736).
2. Installed into a fresh virtual environment, ``mypy --strict`` run on a
   consumer sample against that environment (not the source checkout) is
   clean and infers the expected types for ``rdetoolkit.cli`` /
   ``rdetoolkit.graph`` / ``rdetoolkit.invoicefile``, and accepts the GA
   GraphSpec, magic and ModeDecision APIs.

The wheel build compiles the Rust extension, so this is kept out of the tox
suite (where ``tests/v2/test_rde009_stub_consolidation.py`` already checks the
wheel tox installs); CI runs it on the built wheels in
``.github/workflows/build-test-develop.yml``. Requires ``uv`` on PATH and mypy
in the running interpreter.

Usage:
    python scripts/check_typed_distribution.py                 # build + check
    python scripts/check_typed_distribution.py --wheel X.whl   # check a wheel
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PACKAGE = PROJECT_ROOT / "src" / "rdetoolkit"
REQUIRED_MEMBERS = (
    "rdetoolkit/py.typed",
    "rdetoolkit/invoicefile/__init__.py",
    *sorted(f"rdetoolkit/{stub.relative_to(SOURCE_PACKAGE).as_posix()}" for stub in SOURCE_PACKAGE.rglob("*.pyi")),
)

CONSUMER = """\
from pathlib import Path
import rdetoolkit.cli as cli
import rdetoolkit.invoicefile as inv
from rdetoolkit.graph import GraphPlottingError, PlotConfig, PlotMode, csv2graph
from rdetoolkit.invoicefile import ExcelInvoiceFile, InvoiceFile, SmartTableFile, apply_magic_variable
from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, ResolutionPreview, preview_invoice
from rdetoolkit.domain.mode_selection import ModeDecision, ModeKind, decide_mode
from rdetoolkit.graph import GraphSpec, SeriesSpec
from rdetoolkit.types import RdeConfig

def use_ga(path: Path) -> None:
    decision: ModeDecision = decide_mode(RdeConfig(), path, contract="v2")
    chosen: ModeKind = decision.chosen_mode
    context = ResolutionContext.from_sources(original_invoice={}, current_invoice={})
    preview: ResolutionPreview = preview_invoice(context, options=MagicOptions(policy="enabled"))
    GraphSpec(x="x", series=(SeriesSpec(y="y"),), layout="overlay")

def use(path: Path) -> None:
    invoice = InvoiceFile(path)
    data: dict[str, object] = invoice.read()
    ExcelInvoiceFile(path)
    SmartTableFile(path)
    apply_magic_variable(path, path)
    PlotConfig(mode=PlotMode.OVERLAY)
    try:
        csv2graph(path)
    except GraphPlottingError:
        pass

reveal_type(cli.run)
reveal_type(cli.app)
reveal_type(inv.InvoiceFile)
"""
EXPECTED_REVEALS = (
    "typer.core.TyperCommand",
    "typer.main.Typer",
    "def (invoice_path: pathlib.Path, *, schema_path: pathlib.Path | None =) -> rdetoolkit.invoicefile._invoice.InvoiceFile",
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    # Every command is assembled from fixed arguments plus paths this script created.
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)  # noqa: S603


def build_wheel(uv: str, out_dir: Path) -> Path:
    """Build a wheel for the running interpreter from the project root with ``uv build``."""
    # Pin the build interpreter to the one check_consumer uses for the venv;
    # otherwise uv follows .python-version and the wheel may not install.
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    result = _run([uv, "build", "--wheel", "--python", version, "--out-dir", str(out_dir)], PROJECT_ROOT)
    if result.returncode != 0:
        sys.exit(f"wheel build failed:\n{result.stderr[-4000:]}")
    wheels = sorted(out_dir.glob("rdetoolkit-*.whl"))
    if len(wheels) != 1:
        sys.exit(f"expected exactly one wheel, got {wheels}")
    return wheels[0]


def check_members(wheel: Path) -> list[str]:
    """Return problems with the wheel's stub/marker contents."""
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    packages = {name.rsplit("/", 1)[0] for name in names if name.endswith("/__init__.py")}
    problems = [f"missing {member}" for member in REQUIRED_MEMBERS if member not in names]
    problems += [
        f"unexpected {name} (shadowed by package {name.rsplit('.', 1)[0]}/)"
        for name in sorted(names)
        if name.endswith((".py", ".pyi")) and name.rsplit(".", 1)[0] in packages
    ]
    return problems


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check_consumer(uv: str, wheel: Path, work: Path) -> list[str]:
    """Install ``wheel`` into a fresh venv and type check the consumer against it."""
    venv = work / "venv"
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    for cmd in ([uv, "venv", "--python", version, str(venv)], [uv, "pip", "install", "--python", str(_venv_python(venv)), str(wheel)]):
        result = _run(cmd, work)
        if result.returncode != 0:
            return [f"{cmd[1]} failed: {result.stderr[-2000:]}"]
    consumer = work / "consumer.py"
    consumer.write_text(CONSUMER, encoding="utf-8")
    (work / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")
    result = _run(
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", "--config-file", str(work / "mypy.ini"),
         "--python-executable", str(_venv_python(venv)), str(consumer)],
        work,
    )
    print(result.stdout)
    problems = [] if result.returncode == 0 else [f"mypy exit {result.returncode}"]
    # mypy 2.x prints ``str`` where 1.x printed ``builtins.str``.
    revealed = [text.replace("builtins.", "") for text in re.findall(r'Revealed type is "(.*)"', result.stdout)]
    if tuple(revealed) != tuple(text.replace("builtins.", "") for text in EXPECTED_REVEALS):
        problems.append(f"unexpected revealed types: {revealed}")
    return problems


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wheel", type=Path, help="check an existing wheel instead of building one")
    args = parser.parse_args()
    uv = shutil.which("uv")
    if uv is None:
        sys.exit("uv is required on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        wheel = args.wheel.resolve() if args.wheel else build_wheel(uv, work / "dist")
        problems = check_members(wheel) + check_consumer(uv, wheel, work)
    for problem in problems:
        print("FAIL:", problem)
    print("OK: typed distribution check passed" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
