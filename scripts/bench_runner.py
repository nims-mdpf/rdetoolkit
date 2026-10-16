# ruff: noqa: INP001
"""Non-gating wall-clock baseline for the unified Runner (Session K3 ruling #7).

Measures, in fresh temporary directories:

* the five imported canary cases (``excelinvoice``, ``invoice``,
  ``multidatatile``, ``rdeformat``, ``smarttable``) run through the public v1
  callback entry ``workflows.run(custom_dataset_function=...)`` with a no-op
  callback, so the timing is the Runner's own ceremony; and
* one 1000-tile MultiDataTile run of a three-node ``@flow`` through ``Runner``.

The result is printed as JSON (and optionally written with ``--output``). It is
**not** a gate: CI never runs it, and the only enforced time limit is the wall
clock assertion in ``tests/v2/runner/test_scale_k3.py``.

Usage from the repository root::

    python scripts/bench_runner.py [--repeat N] [--tiles N] [--output bench.json]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

_INVOICE: dict[str, Any] = {
    "datasetId": "bench",
    "basic": {"dateSubmitted": "2026-10-16", "dataOwnerId": "0" * 56, "dataName": "bench"},
}


@contextlib.contextmanager
def _chdir(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _noop_callback(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths


def _time_canary(mode: str) -> float:
    """Assemble one canary case in a fresh directory and time the public entry."""
    from rdetoolkit import workflows  # noqa: PLC0415
    from tests.v2.compat.canary_assembly import assemble_canary_case  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix=f"bench-{mode}-") as tmp:
        root = Path(tmp)
        assemble_canary_case(mode, root)
        with _chdir(root):
            started = time.perf_counter()
            try:
                workflows.run(custom_dataset_function=_noop_callback)
            except SystemExit as exit_error:
                msg = f"canary {mode} failed with exit {exit_error.code}"
                raise RuntimeError(msg) from exit_error
            return time.perf_counter() - started


def _build_tiles(data_root: Path, tiles: int) -> None:
    inputdata = data_root / "inputdata"
    inputdata.mkdir(parents=True)
    for index in range(tiles):
        (inputdata / f"tile_{index:04d}.txt").write_text(str(index), encoding="utf-8")
    (data_root / "invoice").mkdir()
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (data_root / "tasksupport").mkdir()
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "properties": {}}
    (data_root / "tasksupport" / "invoice.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (data_root / "temp").mkdir()


def _scale_flow() -> Callable[..., Any]:
    from rdetoolkit.core.flow import flow  # noqa: PLC0415
    from rdetoolkit.core.node import node  # noqa: PLC0415
    from rdetoolkit.types import IterationInfo  # noqa: PLC0415

    @node(id="bench_read")
    def read(iteration: IterationInfo) -> int:
        return iteration.index

    @node(id="bench_transform")
    def transform(value: int) -> int:
        return value + 1

    @node(id="bench_write")
    def write(value: int) -> None:
        del value

    @flow
    def pipeline(iteration: IterationInfo) -> None:
        write(transform(read(iteration)))

    return pipeline


def _time_tiles(pipeline: Callable[..., Any], tiles: int) -> dict[str, Any]:
    from rdetoolkit.runner.lifecycle import Runner  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="bench-mdt-") as tmp:
        root = Path(tmp)
        data_root = root / "data"
        _build_tiles(data_root, tiles)
        with _chdir(root):
            runner = Runner(root=root, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp")
            started = time.perf_counter()
            report = runner.run(pipeline, system={"extended_mode": "MultiDataTile"})
            elapsed = time.perf_counter() - started
        logs = data_root / "logs"
        return {
            "seconds": elapsed,
            "status": report.status,
            "events_bytes": (logs / f"events_{report.run_id}.jsonl").stat().st_size,
            "run_report_bytes": (logs / f"run_report_{report.run_id}.json").stat().st_size,
        }


def _summary(samples: list[float]) -> dict[str, Any]:
    return {"samples": samples, "median": statistics.median(samples), "min": min(samples), "max": max(samples)}


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark and print its JSON result.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (always 0 unless a case fails to run).
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeat", type=int, default=3, help="runs per case (default 3)")
    parser.add_argument("--tiles", type=int, default=1000, help="MultiDataTile tile count (default 1000)")
    parser.add_argument("--output", type=Path, default=None, help="also write the JSON here")
    args = parser.parse_args(argv)

    for path in (REPO_ROOT / "src", REPO_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from tests.v2.compat.canary_assembly import CANARY_MODES  # noqa: PLC0415

    canary = {mode: _summary([_time_canary(mode) for _ in range(args.repeat)]) for mode in CANARY_MODES}
    pipeline = _scale_flow()
    scale_runs = [_time_tiles(pipeline, args.tiles) for _ in range(args.repeat)]
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "repeat": args.repeat,
        "canary_seconds": canary,
        "multidatatile": {
            "tiles": args.tiles,
            "seconds": _summary([run["seconds"] for run in scale_runs]),
            "statuses": sorted({run["status"] for run in scale_runs}),
            "events_bytes_max": max(run["events_bytes"] for run in scale_runs),
            "run_report_bytes_max": max(run["run_report_bytes"] for run in scale_runs),
        },
    }
    text = json.dumps(result, indent=2)
    print(text)  # noqa: T201
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
