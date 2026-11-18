"""Implementation helpers for ``rdetoolkit run`` with a v2 flow reference."""

from __future__ import annotations

import inspect
from contextlib import redirect_stdout
from io import StringIO
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, cast

import typer
import yaml

from rdetoolkit import workflows
from rdetoolkit.api.request import build_run_request
from rdetoolkit.cli._v2_common import import_project_module
from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError, RdeError, RdeRegistryError
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.paths import resolve_data_root


#: Exit status for a run that completed some tiles and failed others
#: (Design §9.3). Named so the legacy mapping cannot be mistaken for the
#: ``failed`` code 1.
_PARTIAL_EXIT_CODE = 2
_SOURCE_ARTIFACT_ERROR_CODE = 4003


def usage_error(message: str) -> NoReturn:
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
        usage_error(f"Unable to load --config {config_path}: {exc}\nRemediation: pass a readable YAML file.")
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        usage_error("--config must contain a top-level YAML mapping\nRemediation: write the overrides as keys such as 'system:' at the top level.")
    return cast(dict[str, Any], loaded)


def resolve_flow(flow_ref: str) -> Callable[..., Any]:
    """Resolve a dotted ``module:attribute`` reference to a flow callable."""
    module_name, separator, attribute_path = flow_ref.partition(":")
    if not separator or not module_name or not attribute_path or ":" in attribute_path:
        usage_error(
            f"Invalid flow reference '{flow_ref}': it must use the form pkg.mod:callable\n"
            "Remediation: name the module and the flow, e.g. 'rdetoolkit run modules.processing:pipeline'.",
        )
    try:
        value: Any = import_project_module(module_name)
        for attribute in attribute_path.split("."):
            value = getattr(value, attribute)
    except (ImportError, AttributeError) as exc:
        usage_error(
            f"Unable to resolve flow {flow_ref}: {exc}\n"
            "Remediation: run from the project root and check the module path and attribute name "
            "('rdetoolkit flows list --module <module>' lists registered flows).",
        )
    except RdeRegistryError as exc:
        usage_error(f"Unable to resolve flow {flow_ref}: {exc}")
    if inspect.isclass(value):
        from rdetoolkit.templates.base import is_template_class

        if not is_template_class(value):
            usage_error(
                f"Flow class target {flow_ref} is not a ProcessingTemplate subclass\n"
                "Remediation: reference a flow function, or a class derived from a processing skeleton.",
            )
        return cast(Callable[..., Any], value)
    if not callable(value):
        usage_error(f"Flow target is not callable: {flow_ref}\nRemediation: reference a flow function such as modules.processing:pipeline.")
    return cast(Callable[..., Any], value)


def determine_exit_code(report: RunReport) -> int:
    """Return the public run report's process exit status.

    Args:
        report: Finalized run result.

    Returns:
        0 for success, 2 for partial, and 1 for failed or unknown status.
    """
    return report.exit_code


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


def validate_explain_options(validate_only_requested: bool, explain_requested: bool, output_format: str) -> None:
    """Reject explain options outside the read-only validation workflow.

    Args:
        validate_only_requested: Whether validation was requested.
        explain_requested: Whether explanation was requested.
        output_format: Requested explanation format.
    """
    if output_format not in {"text", "json"}:
        usage_error("--format must be text or json")
    if explain_requested and not validate_only_requested:
        usage_error("--explain requires --validate-only")
    if output_format != "text" and not explain_requested:
        usage_error("--format applies only with --explain")


def validate_explain_reference(flow_ref: str) -> None:
    """Check reference syntax without importing or inspecting its user module.

    Args:
        flow_ref: A ``module:attribute`` reference.
    """
    module_name, _, attribute_path = flow_ref.partition(":")
    if not module_name or not attribute_path or ":" in attribute_path:
        usage_error("Invalid flow reference. Use pkg.mod:callable.")


def _explain_overrides(config_path: Path | None) -> dict[str, Any] | None:
    if config_path is None:
        return None
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        message = "Cannot read --config YAML. Use a readable UTF-8 mapping."
        raise RdeConfigError(code=1002, message=message) from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        message = "--config must contain a top-level YAML mapping."
        raise RdeConfigError(code=1002, message=message)
    return cast(dict[str, Any], loaded)


def explain_registration(config_path: Path | None, output_format: str) -> None:
    """Print a read-only snapshot explanation with stable JSON failure output.

    Args:
        config_path: Optional YAML configuration overrides.
        output_format: ``text`` or ``json``.
    """
    from rdetoolkit.runner.preview import preview_registration

    try:
        with redirect_stdout(StringIO()):
            overrides = _explain_overrides(config_path)
            payload = preview_registration(Path.cwd(), overrides=overrides).to_dict()
    except RdeError as exc:
        payload = {"schema_version": "1", "status": "failed", "error": _explanation_error(exc)}
    if output_format == "json":
        typer.echo(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        _print_explanation(payload)
    if payload["status"] != "success":
        raise typer.Exit(code=1)


def _explanation_error(exc: RdeError) -> dict[str, Any]:
    if not isinstance(exc.code, int) or exc.code not in {4001, 4002, 4003}:
        return exc.to_dict()
    # Legacy schema validators include rejected values in their human messages.
    definition = ERROR_CATALOG[exc.code]
    artifact = (exc.detail or {}).get("artifact")
    sources = {"invoice/invoice.json", "tasksupport/invoice.schema.json"}
    if exc.code == _SOURCE_ARTIFACT_ERROR_CODE and isinstance(artifact, str) and artifact in sources:
        return {"code": exc.code, "name": definition.name,
                "message": f"Required input artifact missing: {artifact}. Provide it before validation.",
                "detail": {"artifact": artifact}}
    return {"code": exc.code, "name": definition.name,
            "message": f"Source validation failed ({definition.name}). Remediation: check invoice/invoice.json and tasksupport/invoice.schema.json locally; correct required fields and schema types. Rejected values are omitted."}


def _print_explanation(payload: dict[str, Any]) -> None:
    if payload["status"] == "failed":
        error = payload["error"]
        typer.echo(f"Validation failed [{error['code']}]: {error['message']}")
        return
    decision = payload["decision"]
    typer.echo(f"Mode: {decision['chosen_mode']}")
    typer.echo(f"Reasons: {', '.join(decision['reason_codes'])}")
    typer.echo(f"Config source: {payload['config_source']}")
    typer.echo(f"Tiles: {payload['tile_count']} ({payload['iteration_policy']})")
    for tile in payload["tiles"]:
        typer.echo(f"  {tile['index']}: {', '.join(tile['input_names']) or '(no raw files)'}")
    _print_magic_preview(payload["magic_preview"])
    _print_graph_preview(payload["graph_preview"])
    for warning in payload["warnings"]:
        typer.echo(f"Warning: {warning}")


def _print_magic_preview(magic: dict[str, Any]) -> None:
    typer.echo(f"Magic preview: {magic['status']} ({magic['reason']})")
    counts = Counter((tile["status"], tile["reason"]) for tile in magic["tiles"])
    for (status, reason), count in sorted(counts.items()):
        typer.echo(f"  {status} ({reason}): {count} tile(s)")
    for tile in magic["tiles"]:
        for item in tile["diagnostics"]:
            code = f" [{item['code']}]" if item["code"] is not None else ""
            remedy = f" Remedy: {item['remediation']}" if item["code"] is not None else ""
            typer.echo(f"  tile {tile['index']} {item['destination']}: {item['status']}{code} {item['reason']}.{remedy}")
    if magic["status"] != "not_applicable":
        typer.echo(f"  Checked: {', '.join(magic['checks'])}")
        typer.echo(f"  Not checked: {', '.join(magic['not_checked'])}")


def _print_graph_preview(graph: dict[str, Any]) -> None:
    typer.echo(f"Graph preview: {graph['status']} ({graph['reason']})")
    for tile in graph["tiles"]:
        for item in tile["files"]:
            reader = f" -> {item['reader']}" if item["reader"] is not None else ""
            shape = f", {item['column_count']} column(s)" if item["column_count"] is not None else ""
            typer.echo(f"  tile {tile['index']} {item['name']}: {item['status']}{reader} ({item['reason']}{shape})")
            if item["status"] == "ambiguous":
                candidates = ", ".join(f"{c['reader_id']} {c['confidence']:.2f}" for c in item["candidates"]) or "none"
                typer.echo(f"    Candidates: {candidates}. Remedy: name the reader with csv_format=<id> or --csv-format <id>.")
    if graph["status"] != "no_tabular_inputs":
        typer.echo(f"  Checked: {', '.join(graph['checks'])}")
        typer.echo(f"  Not checked: {', '.join(graph['not_checked'])}")


def run_flow(
    flow_ref: str,
    *,
    validate_only_requested: bool,
    config_path: Path | None,
    explain_requested: bool = False,
    output_format: str = "text",
) -> None:
    """Execute, validate, or explain a v2 flow selected by CLI reference."""
    if explain_requested:
        explain_registration(config_path, output_format)
        return
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
