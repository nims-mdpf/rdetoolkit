"""Implementation helpers for the v2 ``run --flow`` CLI path."""

from __future__ import annotations

import importlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import typer
import yaml

from rdetoolkit import workflows
from rdetoolkit.api.request import build_run_request
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.paths import resolve_data_root


#: Exit status for a run that completed some tiles and failed others
#: (Design §9.3). Named so the legacy mapping cannot be mistaken for the
#: ``failed`` code 1.
_PARTIAL_EXIT_CODE = 2


def usage_error(message: str) -> None:
    """Print a CLI usage error and exit with the v2 usage-error code."""
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def load_config_overrides(config_path: Path | None) -> dict[str, Any] | None:
    """Load optional YAML overrides as a plain mapping."""
    if config_path is None:
        return None
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        usage_error(f"Unable to load --config {config_path}: {exc}")
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        usage_error("--config must contain a top-level YAML mapping")
    return cast(dict[str, Any], loaded)


def resolve_flow(flow_ref: str) -> Callable[..., Any]:
    """Resolve a dotted ``module:attribute`` reference to a flow callable."""
    module_name, separator, attribute_path = flow_ref.partition(":")
    if not separator or not module_name or not attribute_path or ":" in attribute_path:
        usage_error("--flow must use the form pkg.mod:callable")
    try:
        value: Any = importlib.import_module(module_name)
        for attribute in attribute_path.split("."):
            value = getattr(value, attribute)
    except (ImportError, AttributeError) as exc:
        usage_error(f"Unable to resolve --flow {flow_ref}: {exc}")
    if inspect.isclass(value):
        from rdetoolkit.templates.base import is_template_class

        if not is_template_class(value):
            usage_error("--flow class target is not a ProcessingTemplate subclass")
        return cast(Callable[..., Any], value)
    if not callable(value):
        usage_error(f"--flow target is not callable: {flow_ref}")
    return cast(Callable[..., Any], value)


def determine_exit_code(report: RunReport) -> int:
    """Map a run report status to the v2 CLI exit-code contract."""
    return {"success": 0, "failed": 1, "partial": 2}.get(report.status, 1)


def legacy_exit_code(result: object) -> int:
    """Map the v1 entry point's return value to the uniform CLI exit contract.

    Design §9.3 gives every ``run`` form the same 0/1/2/3 codes, while the v1
    *Python* API keeps its own contract: a failed run raises ``SystemExit(1)``
    and a partial run returns normally (process status 0, Session J2 ruling #3).
    The CLI therefore recovers "partial" from the returned statuses — a
    ``failed`` entry in a payload that came back at all means some tiles ran and
    some did not.

    Args:
        result: Whatever ``workflows.run(custom_dataset_function=...)``
            returned. A value that is not the documented legacy payload is
            treated as success, because only that payload carries per-tile
            outcomes.

    Returns:
        ``2`` when the payload reports at least one failed tile, else ``0``.
    """
    if not isinstance(result, str):
        return 0
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return 0
    statuses = payload.get("statuses") if isinstance(payload, dict) else None
    if not isinstance(statuses, list):
        return 0
    failed = any(
        isinstance(status, dict) and status.get("status") == "failed"
        for status in statuses
    )
    return _PARTIAL_EXIT_CODE if failed else 0


def validate_only(flow_fn: Callable[..., Any], config: dict[str, Any] | None) -> None:
    """Validate config, mode, and the source invoice without calling the flow.

    This goes through ``Runner.run(RunRequest(validate_only=True))`` instead of
    driving ``load_config`` / ``resolve_mode`` / ``pre_validate`` by hand
    (Session J2 ruling #4). The step-by-step form left ``run_id`` empty, so
    ``resolve_mode``'s W1001 mode-override warning could not be published at
    all; one Runner call fixes that and routes failures through the Runner's own
    report instead of a bare exception.

    The data root comes from ``resolve_data_root`` rather than a hardcoded
    ``<cwd>/data`` so this path agrees with ``workflows.run(flow=...)`` and the
    Runner about which directory owns the run (Session I-REVIEW-A ruling #1);
    an alias-flat project otherwise validated a tree that does not exist.

    Args:
        flow_fn: The resolved flow. It is never called; it only identifies the
            request's target so the report names the right ``flow_id``.
        config: Optional ``--config`` overrides.
    """
    root = Path.cwd()
    data_root = resolve_data_root(root)
    runner = Runner(
        root=root,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
    )
    request = build_run_request(
        flow=flow_fn,
        custom_dataset_function=None,
        config=config,
        root=root,
        validate_only=True,
    )
    report = runner.run(request)
    if report.status != "success":
        reason = (report.error or {}).get("message", report.status)
        typer.echo(f"Validation failed: {reason}", err=True)
        raise typer.Exit(code=1)
    typer.echo("Validation succeeded")


def run_flow(flow_ref: str, *, validate_only_requested: bool, config_path: Path | None) -> None:
    """Execute or validate a v2 flow selected by CLI string reference."""
    config = load_config_overrides(config_path)
    flow_fn = resolve_flow(flow_ref)
    if validate_only_requested:
        validate_only(flow_fn, config)
        return
    result = workflows.run(flow=flow_fn, config=config)
    report = cast(RunReport, result)
    typer.echo(report.to_json())
    exit_code = determine_exit_code(report)
    if exit_code:
        raise typer.Exit(code=exit_code)
