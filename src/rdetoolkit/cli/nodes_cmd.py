"""Commands for inspecting and linting registered v2 nodes."""

from __future__ import annotations

import ast
import inspect
import json
import sys
import textwrap
from collections import Counter
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
from typing import Annotated, Any, cast

import typer
import rdetoolkit.nodes  # noqa: F401  # Design v2.1 §5.1: builtin nodes must always appear in `nodes list`, no --module required

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, EXIT_OK, CommandHelp
from rdetoolkit.cli._v2_common import IMPORT_REMEDIATION, import_project_module, load_modules
from rdetoolkit.core import registry
from rdetoolkit.core.injection import find_duplicate_reserved_annotations
from rdetoolkit.core.node import NodeSpec
from rdetoolkit.errors import ERROR_CATALOG, WARNING_CATALOG, RdeRegistryError
from rdetoolkit.report.diagnostics import diagnostic, envelope

_MODULE_INPUT = (
    "`--module`: import a project module first so its nodes are registered (repeatable). "
    "Builtin nodes are always registered."
)

NODES_HELP = CommandHelp(
    summary="List, show, and lint registered nodes (functions decorated with node()).",
    examples=(
        "rdetoolkit nodes list --module modules.processing",
        "rdetoolkit nodes show rdetoolkit.nodes.io.read_json",
        "rdetoolkit nodes lint --module modules.processing",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unknown node id, module import failure, or lint violations")),
    see_also=("rdetoolkit flows list", "rdetoolkit run"),
)

LIST_HELP = CommandHelp(
    summary="List registered node ids, one per line.",
    inputs=(_MODULE_INPUT, "`--plugin`: only nodes registered by discovered plugins (adds a `plugin` field)."),
    outputs=("Prints node ids, or a JSON array of node specs with `--json`. Writes no files.",),
    examples=("rdetoolkit nodes list", "rdetoolkit nodes list --module modules.processing --json"),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "a module given with `--module` fails to import")),
    see_also=("rdetoolkit nodes show", "rdetoolkit nodes lint"),
)

SHOW_HELP = CommandHelp(
    summary="Show one registered node: id, version, tags, and input/output schema.",
    inputs=("`ID`: a node id as printed by `rdetoolkit nodes list`.", _MODULE_INPUT),
    outputs=("Prints `field: value` lines, or one JSON object with `--json`. Writes no files.",),
    examples=("rdetoolkit nodes show rdetoolkit.nodes.io.read_json", "rdetoolkit nodes show rdetoolkit.nodes.io.read_json --json"),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unknown node id or a module that fails to import")),
    see_also=("rdetoolkit nodes list",),
)

LINT_HELP = CommandHelp(
    summary="Check registered nodes and flows for problems that break runs or reproducibility.",
    details=(
        "Reports duplicate node ids (E2001), unstable node ids (E2005), parameters without type annotations, "
        "flows with two parameters of one reserved type (E2006), skeleton declaration errors (E2101-E2105), "
        "and skeleton slots that read instance state (W1101)."
    ),
    inputs=(
        _MODULE_INPUT + " Importing a module runs its top-level code; lint is not a sandbox.",
        (
            "`--json`: print the versioned diagnostics envelope instead (`schema_version`, `status`, `diagnostics`); "
            "an import failure becomes a `ModuleImportFailed` finding, and import output goes to stderr."
        ),
    ),
    outputs=("Prints one line per violation, or `0 violations`; with `--json`, one JSON object. Writes no files.",),
    examples=(
        "rdetoolkit nodes lint --module modules.processing",
        "rdetoolkit nodes lint --module modules.processing --json",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "one or more violations (warnings included), or a module that fails to import")),
    see_also=("rdetoolkit nodes list", "rdetoolkit run"),
)

app = typer.Typer(help=NODES_HELP.render(), short_help=NODES_HELP.summary, no_args_is_help=True)


def find_duplicate_node_ids(specs: Sequence[NodeSpec]) -> Sequence[str]:
    """Return node ids that occur more than once."""
    counts = Counter(spec.id for spec in specs)
    return tuple(node_id for node_id, count in counts.items() if count > 1)


def _emit_usage_error(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


@app.command("list", help=LIST_HELP.render(), short_help=LIST_HELP.summary)
def list_nodes(
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    plugin_only: Annotated[
        bool,
        typer.Option("--plugin", help="List only nodes registered by discovered plugins."),
    ] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before listing; repeatable."),
    ] = None,
) -> None:
    """List nodes in the current process registry."""
    load_modules(modules or [])
    plugin_by_node = {
        node_id: plugin.name
        for plugin in _discover_plugins()
        for node_id in plugin.node_ids
    } if plugin_only else {}
    specs = cast(tuple[NodeSpec, ...], registry.list_nodes())
    values = _node_values(specs, plugin_by_node, plugin_only=plugin_only)
    if as_json:
        typer.echo(json.dumps(values, sort_keys=True))
        return
    for value in values:
        typer.echo(value["id"])


def _discover_plugins() -> tuple[Any, ...]:
    from rdetoolkit.plugin import discover_plugins  # noqa: PLC0415

    return discover_plugins()


def _node_values(
    specs: tuple[NodeSpec, ...],
    plugin_by_node: dict[str, str],
    *,
    plugin_only: bool,
) -> list[dict[str, Any]]:
    if not plugin_only:
        return [asdict(spec) for spec in specs]
    return [
        {**asdict(spec), "plugin": plugin_by_node[spec.id]}
        for spec in specs
        if spec.id in plugin_by_node
    ]


@app.command("show", help=SHOW_HELP.render(), short_help=SHOW_HELP.summary)
def show(
    node_id: Annotated[str, typer.Argument(metavar="ID")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before showing; repeatable."),
    ] = None,
) -> None:
    """Show a registered node."""
    load_modules(modules or [])
    try:
        value = asdict(cast(NodeSpec, registry.get_node(node_id)))
    except KeyError:
        _emit_usage_error(
            f"Unknown node id: {node_id}\n"
            "Remediation: run 'rdetoolkit nodes list' for registered ids, and pass --module for the module that defines the node.",
        )
    if as_json:
        typer.echo(json.dumps(value, sort_keys=True))
        return
    for name, field_value in value.items():
        typer.echo(f"{name}: {field_value}")


@dataclass(frozen=True)
class _LintFinding:
    """One lint result: its text-mode line and its ``--json`` finding."""

    text: str
    value: dict[str, Any]


def _catalog_finding(code: int, subject: str, text: str, *, message: str, location: dict[str, str] | None = None) -> _LintFinding:
    entry = ERROR_CATALOG[code]
    return _LintFinding(text, diagnostic(
        code=code, severity="error", name=entry.name, message=message,
        remediation=entry.remediation, subject=subject, location=location,
    ))


def _annotation_findings(spec: NodeSpec) -> list[_LintFinding]:
    # The signature, not ``input_schema``: the schema renders an absent
    # annotation and an explicit ``typing.Any`` identically (#601).
    parameters = inspect.signature(registry.get_node_function(spec.id)).parameters
    findings = []
    for name, parameter in parameters.items():
        if parameter.annotation is not inspect.Parameter.empty:
            continue
        text = f"Missing type annotation: {spec.id}.{name}"
        findings.append(_LintFinding(text, diagnostic(
            code=None, severity="error", name="MissingTypeAnnotation", message=text,
            remediation="Annotate the node parameter; use typing.Any to accept any value on purpose.",
            subject=f"{spec.id}.{name}", location={"source": spec.source_location, "parameter": name},
        )))
    return findings


def _lint_findings() -> list[_LintFinding]:
    nodes = cast(tuple[NodeSpec, ...], registry.list_nodes())
    findings = [
        _catalog_finding(
            2001, node_id, f"E2001 duplicate node id {node_id}. {ERROR_CATALOG[2001].remediation}",
            message=ERROR_CATALOG[2001].message_template.format(node_id=node_id),
        )
        for node_id in find_duplicate_node_ids(nodes)
    ]
    for spec in nodes:
        findings.extend(_annotation_findings(spec))
    sources = {spec.id: spec.source_location for spec in nodes}
    findings.extend(
        _catalog_finding(
            2005, node_id, f"E2005 unstable node id {node_id}. {ERROR_CATALOG[2005].remediation}",
            message=ERROR_CATALOG[2005].message_template.format(node_id=node_id),
            location={"source": sources[node_id]} if node_id in sources else None,
        )
        for node_id in registry.find_unstable_node_ids()
    )
    for flow_spec in registry.list_flows():
        duplicates = find_duplicate_reserved_annotations(registry.get_flow_function(flow_spec.id))
        for reserved_type, parameter_names in duplicates.items():
            type_name = getattr(reserved_type, "__name__", str(reserved_type))
            message = ERROR_CATALOG[2006].message_template.format(type_name=type_name, param_names=", ".join(parameter_names))
            findings.append(_catalog_finding(
                2006, flow_spec.id,
                f"E2006 duplicate reserved annotation {type_name} on "
                f"{flow_spec.id}: {', '.join(parameter_names)}. {ERROR_CATALOG[2006].remediation}",
                message=message, location={"source": flow_spec.source_location},
            ))
    findings.extend(_template_self_state_findings())
    return findings


def _self_attributes(method: object) -> set[str]:
    try:
        source = textwrap.dedent(inspect.getsource(cast(Any, method)))
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return set()
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }


def _template_self_state_findings() -> list[_LintFinding]:
    from rdetoolkit.templates import registry as template_registry

    warning = WARNING_CATALOG[1101]
    findings: list[_LintFinding] = []
    for template_cls in template_registry.list_concrete_templates():
        init_attributes = _self_attributes(vars(template_cls).get("__init__"))
        for method_name, method in vars(template_cls).items():
            if not callable(method) or not hasattr(method, "__node_spec__"):
                continue
            for attribute_name in sorted(_self_attributes(method) - init_attributes):
                qualified_name = f"{template_cls.__module__}.{template_cls.__qualname__}.{method_name}"
                detail = warning.message_template.format(
                    qualified_name=qualified_name,
                    attribute_name=attribute_name,
                )
                findings.append(_LintFinding(f"W1101 {warning.name}: {detail}", diagnostic(
                    code=1101, severity="warning", name=warning.name, message=detail,
                    remediation="Initialize the attribute in __init__, or pass the state through slot arguments and return values.",
                    subject=f"{qualified_name}.{attribute_name}",
                    location={"source": f"{template_cls.__module__}:{template_cls.__qualname__}.{method_name}"},
                )))
    return findings


#: Registry errors that text-mode lint reports as violations; any other
#: ``RdeRegistryError`` raised by an import propagates, as before ``--json``.
_TEXT_REPORTED_IMPORT_CODES = frozenset({2101, 2102, 2103, 2104, 2105})


def _import_failure(module_name: str) -> _LintFinding:
    message = f"Unable to import module {module_name}."
    return _LintFinding(message, diagnostic(
        code=None, severity="error", name="ModuleImportFailed", message=message,
        remediation=IMPORT_REMEDIATION.removeprefix("Remediation: "), subject=module_name,
    ))


def _import_findings(module_names: Sequence[str], *, as_json: bool) -> list[_LintFinding]:
    """Import ``--module`` modules; failures become findings (always, with ``--json``).

    The JSON finding carries the catalog message template, never ``exc.message``
    or ``str(exc)``: an import error can quote arbitrary project data.
    """
    findings: list[_LintFinding] = []
    for module_name in module_names:
        try:
            import_project_module(module_name)
        except RdeRegistryError as exc:
            code = exc.code if isinstance(exc.code, int) and exc.code in ERROR_CATALOG else None
            if not as_json and code not in _TEXT_REPORTED_IMPORT_CODES:
                raise
            findings.append(_import_failure(module_name) if code is None else _catalog_finding(
                code, module_name, f"{ERROR_CATALOG[code].name} (E{code}): {exc.message}",
                message=ERROR_CATALOG[code].message_template,
            ))
        except Exception as exc:  # noqa: BLE001
            if as_json:
                findings.append(_import_failure(module_name))
                continue
            typer.echo(f"Unable to import module {module_name}: {exc}\n{IMPORT_REMEDIATION}", err=True)
            raise typer.Exit(code=3) from exc
    return findings


@app.command("lint", help=LINT_HELP.render(), short_help=LINT_HELP.summary)
def lint(
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before linting; repeatable."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the versioned diagnostics envelope.")] = False,
) -> None:
    """Run checks over the current node and flow registries (importing modules runs their code)."""
    if as_json:
        # Imports are ordinary Python, not sandboxed: keep anything they print
        # off stdout so stdout stays one JSON document.
        with redirect_stdout(sys.stderr):
            findings = _import_findings(modules or [], as_json=True) + _lint_findings()
        payload = envelope([finding.value for finding in findings], command="nodes lint")
        typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        findings = _import_findings(modules or [], as_json=False) + _lint_findings()
        typer.echo("\n".join(finding.text for finding in findings) if findings else "0 violations")
    if findings:
        raise typer.Exit(code=3)
