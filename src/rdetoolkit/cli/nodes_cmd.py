"""Commands for inspecting and linting registered v2 nodes."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import textwrap
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from typing import Annotated, Any, cast

import typer
import rdetoolkit.nodes  # noqa: F401  # Design v2.1 §5.1: builtin nodes must always appear in `nodes list`, no --module required

from rdetoolkit.cli._v2_common import load_modules
from rdetoolkit.core import registry
from rdetoolkit.core.injection import find_duplicate_reserved_annotations
from rdetoolkit.core.node import NodeSpec
from rdetoolkit.errors import ERROR_CATALOG, WARNING_CATALOG, RdeRegistryError

app = typer.Typer(help="Inspect and lint registered v2 nodes.")


def find_duplicate_node_ids(specs: Sequence[NodeSpec]) -> Sequence[str]:
    """Return node ids that occur more than once."""
    counts = Counter(spec.id for spec in specs)
    return tuple(node_id for node_id, count in counts.items() if count > 1)


def _emit_usage_error(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


@app.command("list")
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


@app.command()
def describe(
    node_id: Annotated[str, typer.Argument(metavar="<id>")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before describing; repeatable."),
    ] = None,
) -> None:
    """Describe a registered node."""
    load_modules(modules or [])
    try:
        value = asdict(cast(NodeSpec, registry.get_node(node_id)))
    except KeyError:
        _emit_usage_error(f"Unknown node id: {node_id}")
    if as_json:
        typer.echo(json.dumps(value, sort_keys=True))
        return
    for name, field_value in value.items():
        typer.echo(f"{name}: {field_value}")


def _lint_messages() -> list[str]:
    nodes = cast(tuple[NodeSpec, ...], registry.list_nodes())
    messages = [
        f"E2001 duplicate node id {node_id}. {ERROR_CATALOG[2001].remediation}"
        for node_id in find_duplicate_node_ids(nodes)
    ]
    for spec in nodes:
        for parameter, schema in spec.input_schema.items():
            if schema["type_name"] == "typing.Any":
                messages.append(f"Missing type annotation: {spec.id}.{parameter}")
    messages.extend(
        f"E2005 unstable node id {node_id}. {ERROR_CATALOG[2005].remediation}"
        for node_id in registry.find_unstable_node_ids()
    )
    for flow_spec in registry.list_flows():
        duplicates = find_duplicate_reserved_annotations(registry.get_flow_function(flow_spec.id))
        for reserved_type, parameter_names in duplicates.items():
            type_name = getattr(reserved_type, "__name__", str(reserved_type))
            messages.append(
                f"E2006 duplicate reserved annotation {type_name} on "
                f"{flow_spec.id}: {', '.join(parameter_names)}. {ERROR_CATALOG[2006].remediation}",
            )
    messages.extend(_template_self_state_messages())
    return messages


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


def _template_self_state_messages() -> list[str]:
    from rdetoolkit.templates import registry as template_registry

    warning = WARNING_CATALOG[1101]
    messages: list[str] = []
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
                messages.append(f"W1101 {warning.name}: {detail}")
    return messages


def _load_modules_for_lint(module_names: Sequence[str]) -> list[str]:
    messages: list[str] = []
    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except RdeRegistryError as exc:
            code = exc.code
            if not isinstance(code, int) or code not in {2101, 2102, 2103, 2104, 2105}:
                raise
            messages.append(f"{ERROR_CATALOG[code].name} (E{code}): {exc.message}")
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Unable to import module {module_name}: {exc}", err=True)
            raise typer.Exit(code=3) from exc
    return messages


@app.command()
def lint(
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before linting; repeatable."),
    ] = None,
) -> None:
    """Run static checks over the current node and flow registries."""
    messages = _load_modules_for_lint(modules or [])
    messages.extend(_lint_messages())
    if not messages:
        typer.echo("0 violations")
        return
    for message in messages:
        typer.echo(message)
    raise typer.Exit(code=3)
