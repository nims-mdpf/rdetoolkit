# ruff: noqa: INP001, T201
"""GA release-gate benchmark: rendering resources and multi-tile throughput (#739).

Every case runs in its own Python subprocess, so its peak RSS is its own. The
inputs are synthetic (``tests/v2/perf/synthetic.py``): no real dataset and no
secret is read. The result JSON records the hardware, Python, dependency
versions, data sizes, the exact command of every case and the measurements.

Cases (``full`` profile; ``quick`` runs the same cases at tiny sizes):

* ``render_overlay_<N>``: one overlay figure with N = 1, 10, 100, 1000 Y-series.
* ``render_both_<N>``: overlay plus one figure per series, N = 1, 10, 100.
* ``render_repeat``: the same 10-series request rendered 30 times in a row.
* ``csv_parse_rows`` / ``csv_parse_columns``: format detection and reading of
  a 100 000-row and a 1000-column CSV.
* ``plan_<mode>_<N>``: ``preview_registration`` (tile planning only).
* ``run_<mode>_<N>``: a ``Runner.run`` of a no-op flow over N tiles.

Release gate. ``--baseline FILE`` compares the run with a committed baseline
and exits 1 when a metric breaks its threshold:

* exact metrics (image and tile counts, statuses, the artifact manifest digest,
  figures left open or alive after a collection) must equal the baseline;
* time is compared as ``normalized_seconds`` (seconds divided by a fixed CPU
  calibration workload measured in the same run), so a slower runner does not
  fail the gate by itself; a case fails above ``max_ratio`` x baseline;
* memory (``peak_rss_delta_mib``, ``rss_growth_mib`` over repeated renders)
  and ``live_figures_max`` (figures alive at once, uncollected) fail above
  ``max_ratio`` x baseline plus ``slack``.

Independently of any baseline, every rendering case must leave no figure open
in pyplot and none alive after a collection; a violation always exits 1.

Accepting a regression is an explicit review step: rerun with
``--write-baseline scripts/bench_ga_baseline.json`` and commit the changed
baseline in the pull request, where the diff shows every changed number.

Usage from the repository root::

    python scripts/bench_ga.py [--profile full|quick] [--repeat N] [--cases A,B]
                               [--output result.json] [--baseline FILE]
                               [--write-baseline FILE]
"""

from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_VERSION = 1
DEPENDENCIES = (
    "rdetoolkit", "matplotlib", "numpy", "pandas", "polars", "openpyxl", "plotly", "pydantic", "jsonschema",
)
EXACT_METRICS = (
    "images", "figures_open", "live_figures_after_collect", "tiles", "status", "manifest_sha256", "iterations",
)
DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "normalized_seconds": {"max_ratio": 2.0},
    "peak_rss_delta_mib": {"max_ratio": 1.5, "slack": 64.0},
    # Figures awaiting collection depend on GC timing, not on the repetition count;
    # a retained figure per render grows this with every render and fails the gate.
    "live_figures_max": {"max_ratio": 1.5, "slack": 4.0},
    "rss_growth_mib": {"max_ratio": 2.0, "slack": 32.0},
}
_RENDER_DPI = 100


@dataclass(frozen=True)
class Case:
    """One benchmark case: a kind and its parameters."""

    name: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)


def _profile_cases(profile: str) -> list[Case]:
    """Return the cases of one profile, in execution order."""
    full = profile == "full"
    overlay = (1, 10, 100, 1000) if full else (1, 10)
    both = (1, 10, 100) if full else (1, 3)
    tiles = {"smarttable": (100, 1000), "multidatatile": (100, 1000), "excelinvoice": (100, 300)}
    if not full:
        tiles = dict.fromkeys(tiles, (5,))
    cases = [Case(f"render_overlay_{n}", "render", {"series": n, "layout": "overlay"}) for n in overlay]
    cases += [Case(f"render_both_{n}", "render", {"series": n, "layout": "both"}) for n in both]
    cases.append(Case("render_repeat", "render_repeat", {"series": 10, "times": 30 if full else 3}))
    cases.append(Case("csv_parse_rows", "csv_parse", {"series": 10, "rows": 100_000 if full else 1000}))
    cases.append(Case("csv_parse_columns", "csv_parse", {"series": 1000 if full else 20, "rows": 200}))
    for mode, sizes in tiles.items():
        cases += [Case(f"plan_{mode}_{n}", "plan", {"mode": mode, "tiles": n}) for n in sizes]
        cases += [Case(f"run_{mode}_{n}", "run", {"mode": mode, "tiles": n}) for n in sizes]
    return cases


# --- measurement primitives (run inside the case subprocess) ---------------------------


def _peak_rss_mib() -> float | None:
    try:
        import resource  # noqa: PLC0415 -- POSIX only
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB, macOS bytes.
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def _current_rss_mib() -> float | None:
    statm = Path("/proc/self/statm")
    if not statm.exists():
        return None
    resident_pages = int(statm.read_text(encoding="ascii").split()[1])
    return resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)


def calibrate(samples: int = 5) -> float:
    """Return the median seconds of a fixed CPU workload, the unit of ``normalized_seconds``.

    Args:
        samples: Number of timed repetitions.

    Returns:
        Median wall-clock seconds of one repetition.
    """
    import numpy as np  # noqa: PLC0415

    def workload() -> None:
        total = 0
        for value in range(400_000):
            total += value * value % 7
        array = np.sin(np.arange(400_000, dtype=float))
        np.sort(array)
        json.dumps([{"k": index, "v": str(index)} for index in range(20_000)])

    timings = []
    for _ in range(samples):
        started = time.perf_counter()
        workload()
        timings.append(time.perf_counter() - started)
    return statistics.median(timings)


def _synthetic() -> Any:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tests.v2.perf import synthetic  # noqa: PLC0415

    return synthetic


def _figure_state(synthetic: Any) -> dict[str, int]:
    import matplotlib.pyplot as plt  # noqa: PLC0415

    gc.collect()
    return {"figures_open": len(plt.get_fignums()), "live_figures_after_collect": synthetic.live_figures()}


def _timed(repeat: int, action: Callable[[int], Any]) -> tuple[list[float], Any]:
    samples, last = [], None
    for index in range(repeat):
        started = time.perf_counter()
        last = action(index)
        samples.append(time.perf_counter() - started)
    return samples, last


def _render_case(params: Mapping[str, Any], repeat: int, work: Path) -> dict[str, Any]:
    from rdetoolkit.graph.engine import render_graph  # noqa: PLC0415
    from rdetoolkit.graph.outputs import DirectorySink  # noqa: PLC0415
    from rdetoolkit.graph.spec import GraphSpec, OutputSpec  # noqa: PLC0415

    synthetic = _synthetic()
    frame = synthetic.wide_frame(params["series"], 200)
    spec = GraphSpec(layout=params["layout"], unit_policy="allow")
    live_max = [0]

    def render(index: int) -> Any:
        target = work / f"r{index}"
        result = render_graph(frame, spec, output=OutputSpec(DirectorySink(target / "other", main_image_dir=target / "main"), dpi=_RENDER_DPI))
        live_max[0] = max(live_max[0], synthetic.live_figures())
        return result

    rss_before = _current_rss_mib()
    samples, result = _timed(repeat, render)
    files = synthetic.file_manifest(work / f"r{repeat - 1}")
    return {
        "samples": samples,
        "rss_before_mib": rss_before,
        "images": len(files),
        "artifacts": len(result.artifacts),
        "manifest_sha256": hashlib.sha256(result.manifest_json().encode()).hexdigest(),
        "live_figures_max": live_max[0],
        "data": {"series": params["series"], "rows": 200, "layout": params["layout"], "dpi": _RENDER_DPI},
        **_figure_state(synthetic),
    }


def _render_repeat_case(params: Mapping[str, Any], repeat: int, work: Path) -> dict[str, Any]:
    from rdetoolkit.graph.engine import render_graph  # noqa: PLC0415
    from rdetoolkit.graph.outputs import DirectorySink  # noqa: PLC0415
    from rdetoolkit.graph.spec import GraphSpec, OutputSpec  # noqa: PLC0415

    synthetic = _synthetic()
    frame = synthetic.wide_frame(params["series"], 200)
    spec = GraphSpec(layout="both", unit_policy="allow")
    times = params["times"]
    rss: list[float | None] = []
    live: list[int] = []

    def sequence(index: int) -> None:
        for step in range(times):
            target = work / f"s{index}_{step}"
            render_graph(frame, spec, output=OutputSpec(DirectorySink(target / "other", main_image_dir=target / "main"), dpi=_RENDER_DPI))
            live.append(synthetic.live_figures())
            rss.append(_current_rss_mib())

    rss_before = _current_rss_mib()
    samples, _ = _timed(repeat, sequence)
    settled = [value for value in rss[len(rss) // 3 :] if value is not None]
    return {
        "samples": samples,
        "rss_before_mib": rss_before,
        "renders": times * repeat,
        "live_figures_max": max(live),
        # Growth from the end of the first third (allocator warmed up) to the last render.
        "rss_growth_mib": (settled[-1] - settled[0]) if len(settled) > 1 else None,
        "data": {"series": params["series"], "rows": 200, "layout": "both", "dpi": _RENDER_DPI, "times": times},
        **_figure_state(synthetic),
    }


def _csv_parse_case(params: Mapping[str, Any], repeat: int, work: Path) -> dict[str, Any]:
    from rdetoolkit.graph.readers.builtin import StandardReader  # noqa: PLC0415
    from rdetoolkit.graph.readers.detection import detect_table_format  # noqa: PLC0415

    synthetic = _synthetic()
    path = synthetic.write_csv(work / "table.csv", params["series"], params["rows"])
    rss_before = _current_rss_mib()

    def parse(_index: int) -> tuple[str | None, int]:
        decision = detect_table_format(path)
        table = StandardReader().read(path)
        return decision.selected, table.frame.shape[0]

    samples, (selected, rows) = _timed(repeat, parse)
    return {
        "samples": samples,
        "rss_before_mib": rss_before,
        "status": selected,
        "parsed_rows": rows,
        "data": {"series": params["series"], "rows": params["rows"], "bytes": path.stat().st_size},
    }


_BUILDERS = {"smarttable": "smarttable_root", "multidatatile": "multidatatile_root", "excelinvoice": "excelinvoice_root"}


def _plan_case(params: Mapping[str, Any], repeat: int, work: Path) -> dict[str, Any]:
    from rdetoolkit.runner.preview import preview_registration  # noqa: PLC0415

    synthetic = _synthetic()
    root = getattr(synthetic, _BUILDERS[params["mode"]])(work / "project", params["tiles"])
    rss_before = _current_rss_mib()
    samples, preview = _timed(repeat, lambda _index: preview_registration(root))
    return {
        "samples": samples,
        "rss_before_mib": rss_before,
        "tiles": len(preview.tiles),
        "status": preview.decision.chosen_mode.value,
        "data": {"mode": params["mode"], "tiles": params["tiles"]},
    }


def _run_case(params: Mapping[str, Any], repeat: int, work: Path) -> dict[str, Any]:
    from rdetoolkit.core.flow import flow  # noqa: PLC0415
    from rdetoolkit.runner.lifecycle import Runner  # noqa: PLC0415
    from rdetoolkit.types import IterationInfo  # noqa: PLC0415

    synthetic = _synthetic()

    @flow(id="bench_ga.noop")
    def noop(iteration: IterationInfo) -> None:
        del iteration

    builder = getattr(synthetic, _BUILDERS[params["mode"]])
    roots = [builder(work / f"project{index}", params["tiles"]) for index in range(repeat)]
    rss_before = _current_rss_mib()
    samples, report = _timed(repeat, lambda index: Runner(root=roots[index]).run(noop))
    return {
        "samples": samples,
        "rss_before_mib": rss_before,
        "status": report.status,
        "iterations": len(report.iterations),
        "seconds_per_tile": statistics.median(samples) / params["tiles"],
        "data": {"mode": params["mode"], "tiles": params["tiles"]},
    }


_KINDS: dict[str, Callable[[Mapping[str, Any], int, Path], dict[str, Any]]] = {
    "render": _render_case,
    "render_repeat": _render_repeat_case,
    "csv_parse": _csv_parse_case,
    "plan": _plan_case,
    "run": _run_case,
}


def run_case_inline(kind: str, params: Mapping[str, Any], repeat: int) -> dict[str, Any]:
    """Run one case in this process and return its raw metrics (the subprocess entry).

    Args:
        kind: A key of the case kinds (``render``, ``plan`` ...).
        params: The case parameters.
        repeat: Number of timed repetitions.

    Returns:
        The case metrics, including ``samples`` (seconds) and ``peak_rss_mib``.
    """
    with tempfile.TemporaryDirectory(prefix="bench-ga-") as tmp:
        metrics = _KINDS[kind](params, repeat, Path(tmp))
    metrics["peak_rss_mib"] = _peak_rss_mib()
    return metrics


# --- orchestration ---------------------------------------------------------------------


def _case_command(case: Case, repeat: int) -> list[str]:
    return [
        sys.executable, str(Path(__file__).resolve()), "--run-case", case.kind,
        "--params", json.dumps(case.params, sort_keys=True), "--repeat", str(repeat),
    ]


def _execute(case: Case, repeat: int, calibration: float) -> dict[str, Any]:
    command = _case_command(case, repeat)
    env = {**os.environ, "PYTHONWARNINGS": "ignore", "MPLBACKEND": "Agg"}
    completed = subprocess.run(command, capture_output=True, text=True, check=False, env=env)  # noqa: S603
    if completed.returncode != 0:
        msg = f"case {case.name} failed (exit {completed.returncode}):\n{completed.stderr[-4000:]}"
        raise RuntimeError(msg)
    metrics = json.loads(completed.stdout.strip().splitlines()[-1])
    samples = metrics.pop("samples")
    median = statistics.median(samples)
    peak, before = metrics.get("peak_rss_mib"), metrics.get("rss_before_mib")
    return {
        "kind": case.kind,
        "params": case.params,
        "command": command[1:],
        "seconds": {"samples": samples, "median": median, "min": min(samples), "max": max(samples)},
        "normalized_seconds": median / calibration,
        "peak_rss_delta_mib": None if peak is None or before is None else peak - before,
        **metrics,
    }


def _git_revision() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False,  # noqa: S607
        )
    except OSError:
        return None
    return completed.stdout.strip() or None


def _cpu_model() -> str | None:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or None


def _memory_total_mib() -> float | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 * 1024)
    except (AttributeError, ValueError, OSError):
        return None


def _version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def environment(argv: Sequence[str]) -> dict[str, Any]:
    """Describe where and how the benchmark ran.

    Args:
        argv: The command-line arguments of this invocation.

    Returns:
        Hardware, OS, Python, dependency versions, source revision and command.
    """
    import rdetoolkit  # noqa: PLC0415

    return {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "hardware": {
            "machine": platform.machine(),
            "cpu_model": _cpu_model(),
            "cpu_count": os.cpu_count(),
            "memory_total_mib": _memory_total_mib(),
        },
        "os": platform.platform(),
        "python": {"version": platform.python_version(), "implementation": platform.python_implementation(), "executable": sys.executable},
        "dependencies": {name: _version(name) for name in DEPENDENCIES},
        "rdetoolkit_origin": str(Path(rdetoolkit.__file__).resolve().parent),
        "git_revision": _git_revision(),
        "command": [sys.executable, str(Path(__file__).resolve()), *argv],
    }


def figure_violations(cases: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Return the absolute figure-ownership violations, independent of any baseline.

    Args:
        cases: The ``cases`` mapping of a result.

    Returns:
        One message per case that left a figure open in pyplot or alive after a collection.
    """
    problems = []
    for name, metrics in cases.items():
        for key in ("figures_open", "live_figures_after_collect"):
            if metrics.get(key, 0) != 0:
                problems.append(f"{name}: {key} = {metrics[key]} (must be 0)")
    return problems


def compare(result: Mapping[str, Any], baseline: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compare a result with a baseline and return one row per checked metric.

    Args:
        result: A benchmark result (``cases`` and ``calibration_seconds``).
        baseline: A baseline (``cases`` and optional ``thresholds``).

    Returns:
        Rows with ``case``, ``metric``, ``baseline``, ``current``, ``limit`` and
        ``verdict`` (``ok``, ``regression``, ``missing`` or ``unbaselined``).
    """
    thresholds = {**DEFAULT_THRESHOLDS, **baseline.get("thresholds", {})}
    rows: list[dict[str, Any]] = []
    current_cases = result["cases"]
    for name, expected in baseline["cases"].items():
        current = current_cases.get(name)
        if current is None:
            rows.append({"case": name, "metric": "*", "baseline": None, "current": None, "limit": None, "verdict": "missing"})
            continue
        for metric in EXACT_METRICS:
            if metric in expected:
                verdict = "ok" if current.get(metric) == expected[metric] else "regression"
                rows.append({"case": name, "metric": metric, "baseline": expected[metric], "current": current.get(metric), "limit": "==", "verdict": verdict})
        for metric, rule in thresholds.items():
            if expected.get(metric) is None or current.get(metric) is None:
                continue
            # A negative baseline (memory returned during the run) must not tighten the limit below the slack.
            limit = max(expected[metric], 0.0) * rule.get("max_ratio", 1.0) + rule.get("slack", 0.0)
            verdict = "ok" if current[metric] <= limit else "regression"
            rows.append({"case": name, "metric": metric, "baseline": expected[metric], "current": current[metric], "limit": limit, "verdict": verdict})
    rows += [
        {"case": name, "metric": "*", "baseline": None, "current": None, "limit": None, "verdict": "unbaselined"}
        for name in current_cases
        if name not in baseline["cases"]
    ]
    return rows


def baseline_from(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return the baseline document a result establishes.

    Args:
        result: A benchmark result.

    Returns:
        The environment, thresholds and the gated metrics of every case.
    """
    gated = (*EXACT_METRICS, *DEFAULT_THRESHOLDS)
    environment = result["environment"]
    # The baseline is committed: keep the provenance, drop machine-local paths.
    established_on = {
        "timestamp_utc": environment.get("timestamp_utc"),
        "hardware": environment.get("hardware"),
        "os": environment.get("os"),
        "python": {key: value for key, value in environment.get("python", {}).items() if key != "executable"},
        "dependencies": environment.get("dependencies"),
        "git_revision": environment.get("git_revision"),
        "repeat": result.get("repeat"),
    }
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "profile": result["profile"],
        "established_on": established_on,
        "calibration_seconds": result["calibration_seconds"],
        "thresholds": DEFAULT_THRESHOLDS,
        "cases": {
            name: {key: metrics[key] for key in gated if metrics.get(key) is not None}
            for name, metrics in result["cases"].items()
        },
    }


def _format_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    def cell(value: Any) -> str:
        return f"{value:.3f}" if isinstance(value, float) else str(value)

    lines = [f"{'case':<26} {'metric':<28} {'baseline':>14} {'current':>14} {'limit':>14}  verdict"]
    lines += [
        f"{row['case']:<26} {row['metric']:<28} {cell(row['baseline']):>14} {cell(row['current']):>14} {cell(row['limit']):>14}  {row['verdict']}"
        for row in rows
    ]
    return "\n".join(lines)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--profile", choices=("full", "quick"), default="full")
    parser.add_argument("--repeat", type=int, default=3, help="timed repetitions per case (default 3)")
    parser.add_argument("--cases", default=None, help="comma-separated case names (default: the whole profile)")
    parser.add_argument("--output", type=Path, default=None, help="write the result JSON here")
    parser.add_argument("--baseline", type=Path, default=None, help="compare with this baseline; exit 1 on regression")
    parser.add_argument("--write-baseline", type=Path, default=None, help="write the baseline this run establishes")
    parser.add_argument("--run-case", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--params", default="{}", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark, print its JSON and apply the gate.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 when every invariant and threshold holds, 1 otherwise.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(argv)
    if args.run_case is not None:
        print(json.dumps(run_case_inline(args.run_case, json.loads(args.params), args.repeat)))
        return 0

    cases = _profile_cases(args.profile)
    if args.cases:
        wanted = set(args.cases.split(","))
        unknown = wanted - {case.name for case in cases}
        if unknown:
            print(f"unknown case(s) for profile {args.profile}: {sorted(unknown)}", file=sys.stderr)
            return 2
        cases = [case for case in cases if case.name in wanted]
    result = _measure(cases, args, argv)
    exit_code = _apply_gate(result, args.baseline)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.write_baseline is not None:
        baseline_text = json.dumps(baseline_from(result), indent=2, ensure_ascii=False)
        args.write_baseline.write_text(baseline_text + "\n", encoding="utf-8")
    return exit_code


def _measure(cases: Sequence[Case], args: argparse.Namespace, argv: Sequence[str]) -> dict[str, Any]:
    calibration = calibrate()
    measured = {}
    for case in cases:
        print(f"[bench_ga] {case.name} ...", file=sys.stderr, flush=True)
        measured[case.name] = _execute(case, args.repeat, calibration)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "profile": args.profile,
        "repeat": args.repeat,
        "environment": environment(argv),
        "calibration_seconds": calibration,
        "cases": measured,
    }


def _apply_gate(result: dict[str, Any], baseline: Path | None) -> int:
    """Record the figure violations and the baseline comparison in ``result``; return the exit code."""
    exit_code = 0
    violations = figure_violations(result["cases"])
    result["figure_violations"] = violations
    for problem in violations:
        print(f"[bench_ga] FIGURE VIOLATION {problem}", file=sys.stderr)
        exit_code = 1
    if baseline is not None:
        rows = compare(result, json.loads(baseline.read_text(encoding="utf-8")))
        result["comparison"] = rows
        print(_format_rows(rows), file=sys.stderr)
        if any(row["verdict"] in ("regression", "missing") for row in rows):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
