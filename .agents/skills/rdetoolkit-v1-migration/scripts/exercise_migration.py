# ruff: noqa: INP001
"""Execute the checked-in migration example in a new, isolated work directory.

The baseline runs the unchanged callback through the supported v1 entry point,
``workflows.run(custom_dataset_function=...)``. The converted and artifact-node
flows run through ``rdetoolkit.testing.run_flow`` on separate copies of the same
inputs, and every artifact is compared with ``compare_artifacts.compare``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from compare_artifacts import compare
from rdetoolkit import workflows
from rdetoolkit.testing import make_invoice, run_flow

_USER_ERROR_CODE = 999
SKILL = Path(__file__).resolve().parents[1]
_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aKz8AAAAASUVORK5CYII="


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        msg = f"Cannot import example: {path}"
        raise ValueError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _cli(work: Path, name: str, args: list[str]) -> None:
    result = subprocess.run([sys.executable, "-m", "rdetoolkit", *args], capture_output=True, text=True, check=False)  # noqa: S603 -- fixed module in this interpreter, no shell
    (work / f"{name}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        msg = f"{name} failed: see {work / f'{name}.log'}"
        raise RuntimeError(msg)


def _inputs(root: Path, *, fail: bool) -> None:
    for name in ("inputdata", "invoice", "tasksupport"):
        (root / name).mkdir(parents=True)
    invoice = make_invoice({"datasetId": "migration-example", "basic": {"dataOwnerId": "0" * 56, "dataName": "measurement", "dateSubmitted": "2026-07-20"}})
    (root / "invoice/invoice.json").write_text(json.dumps(invoice.raw), encoding="utf-8")
    (root / "tasksupport/invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (root / "tasksupport/rdeconfig.yaml").write_text("system:\n  save_raw: true\n  save_nonshared_raw: true\n  save_thumbnail_image: false\n  magic_variable: false\n", encoding="utf-8")
    payload = {
        "fail": fail,
        "metadata": {
            "constant": {"temperature": {"value": 25, "unit": "degC"}},
            "variable": [{"time": {"value": 1, "unit": "s"}}, {"time": {"value": 2, "unit": "s"}}],
        },
        "table": "time,value\n1,2\n2,3\n",
    }
    (root / "inputdata/measurement.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "inputdata/measurement.png").write_bytes(base64.b64decode(_IMAGE))


def _run_v1_entry(callback: Any, project: Path) -> str:
    """Run the supported v1 entry point from ``project``; return its outcome."""
    previous = Path.cwd()
    os.chdir(project)
    try:
        workflows.run(custom_dataset_function=callback)
    except SystemExit as error:
        if error.code != 1:
            raise
        return "failed"
    finally:
        os.chdir(previous)
    return "success"


def _outcome(report: Any) -> tuple[Any, ...]:
    def error_view(error: dict[str, Any] | None) -> Any:
        return {key: error.get(key) for key in ("code", "name", "message")} if error else None

    return (report.status, report.exit_code, error_view(report.error), [(item["status"], error_view(item.get("error"))) for item in report.iterations])


def _case(work: Path, label: str, legacy: Any, converted: Any, native: Any) -> dict[str, Any]:
    roots = [work / f"{label}-{name}" for name in ("legacy", "converted", "native")]
    for project in roots:
        _inputs(project / "data", fail=label == "failure")
    baseline = _run_v1_entry(legacy, roots[0])
    reports = [run_flow(converted, data_root=roots[1]), run_flow(native, data_root=roots[2])]
    for project in roots[1:]:
        differences = compare(roots[0] / "data", project / "data")
        if differences:
            msg = f"{label}: artifact differences from the v1 entry: {differences}"
            raise AssertionError(msg)
    expected = "failed" if label == "failure" else "success"
    if baseline != expected or any(report.status != expected for report in reports):
        msg = f"{label}: expected {expected}; v1 entry {baseline}, flows {[report.to_dict() for report in reports]}"
        raise AssertionError(msg)
    if _outcome(reports[0]) != _outcome(reports[1]):
        msg = f"{label}: outcome semantics differ: {[_outcome(report) for report in reports]}"
        raise AssertionError(msg)
    report = reports[0]
    error_code = report.error.get("code") if report.error else None
    if label == "failure" and error_code != _USER_ERROR_CODE:
        msg = f"Legacy user error code changed: {error_code}"
        raise AssertionError(msg)
    return {"status": report.status, "exit_code": report.exit_code, "error_code": error_code, "iterations": len(report.iterations)}


def exercise(work: Path) -> dict[str, Any]:
    """Check, preview, explicitly apply and compare the synthetic example."""
    work.mkdir(parents=True, exist_ok=False)
    source = work / "source.py"
    shutil.copy2(SKILL / "examples/legacy_callback.py", source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = work / "migrated"
    _cli(work, "check", ["migrate", "check", str(source)])
    _cli(work, "preview", ["migrate", "apply", str(source), "-o", str(destination)])
    if destination.exists():
        msg = "Preview created its output"
        raise AssertionError(msg)
    _cli(work, "apply", ["migrate", "apply", str(source), "-o", str(destination), "--no-dry-run"])
    converted_path = destination / source.name
    if "TODO(rdetoolkit-migrate)" in converted_path.read_text(encoding="utf-8"):
        msg = "Example still requires manual migration"
        raise AssertionError(msg)
    legacy = _load(source, "migration_example_legacy").dataset
    converted = _load(converted_path, "migration_example_converted").pipeline
    native = _load(SKILL / "examples/native_flow.py", "migration_example_native").pipeline
    summary: dict[str, Any] = {label: _case(work, label, legacy, converted, native) for label in ("success", "failure")}
    if hashlib.sha256(source.read_bytes()).hexdigest() != before:
        msg = "Source was modified"
        raise AssertionError(msg)
    summary.update({"source_unchanged": True, "parity": True, "output_path": str(destination)})
    (work / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    """Run the exercise, refusing to reuse or overwrite a work directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    sys.stdout.write(json.dumps(exercise(args.work_dir.absolute()), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
