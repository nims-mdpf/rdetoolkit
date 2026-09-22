"""Implementation helpers for the v2 ``run --flow`` CLI path."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import typer
import yaml

from rdetoolkit import workflows
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.paths import resolve_data_root


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


def validate_only(config: dict[str, Any] | None) -> None:
    """Run config, mode, and pre-flow validation without resolving a flow.

    The data root comes from ``resolve_data_root`` rather than a hardcoded
    ``<cwd>/data`` so this path agrees with ``workflows.run(flow=...)`` and the
    Runner about which directory owns the run (Session I-REVIEW-A ruling #1);
    an alias-flat project otherwise validated a tree that does not exist.
    """
    root = Path.cwd()
    data_root = resolve_data_root(root)
    runner = Runner(
        root=root,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
    )
    try:
        effective_config = runner.load_config(config)
        runner.resolve_mode(effective_config)
        runner.pre_validate(effective_config)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Validation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("Validation succeeded")


def run_flow(flow_ref: str, *, validate_only_requested: bool, config_path: Path | None) -> None:
    """Execute or validate a v2 flow selected by CLI string reference."""
    config = load_config_overrides(config_path)
    if validate_only_requested:
        validate_only(config)
        return
    flow_fn = resolve_flow(flow_ref)
    result = workflows.run(flow=flow_fn, config=config)
    report = cast(RunReport, result)
    typer.echo(report.to_json())
    exit_code = determine_exit_code(report)
    if exit_code:
        raise typer.Exit(code=exit_code)
