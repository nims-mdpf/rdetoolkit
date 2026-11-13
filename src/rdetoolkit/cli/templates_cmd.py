"""``rdetoolkit skeletons``: list and show registered processing skeletons.

A processing skeleton is a ``ProcessingTemplate`` subclass whose slots a
project implements. ``rdetoolkit new processing`` renders the code for one;
the rendering helpers live here so both commands share one skeleton lookup.
"""

from __future__ import annotations

import json
import ast
import tokenize
import re
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, EXIT_OK, CommandHelp
from rdetoolkit.cli._v2_common import load_modules
from rdetoolkit.templates import registry
from rdetoolkit.templates.registry import TemplateMethodSpec, TemplateParameterSpec, TemplateSpec

_SOURCES = (
    "`--module`: import a module that declares skeletons first (repeatable). Without it, skeletons are "
    "found in `*.py` files of the current directory, its `modules/` package, and installed plugins."
)

SKELETONS_HELP = CommandHelp(
    summary="List and show registered processing skeletons (ProcessingTemplate subclasses).",
    details="A skeleton declares the slots a structured process implements; `rdetoolkit new processing` generates code for one.",
    examples=(
        "rdetoolkit skeletons list",
        "rdetoolkit skeletons show XrdTemplate --module modules.skeletons",
        "rdetoolkit skeletons list --json",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unknown skeleton or a module that fails to import")),
    see_also=("rdetoolkit new processing",),
)

LIST_HELP = CommandHelp(
    summary="List registered processing skeletons, one id per line.",
    inputs=(_SOURCES,),
    outputs=("Prints skeleton ids, or a JSON array of skeleton specs with `--json`. Writes no files.",),
    examples=("rdetoolkit skeletons list", "rdetoolkit skeletons list --module modules.skeletons --json"),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "a module given with `--module` fails to import")),
    see_also=("rdetoolkit skeletons show", "rdetoolkit new processing"),
)

SHOW_HELP = CommandHelp(
    summary="Show one processing skeleton: its id, slots, and slot signatures.",
    inputs=("`NAME`: a skeleton id or unambiguous class name from `rdetoolkit skeletons list`.", _SOURCES),
    outputs=("Prints `field: value` lines, or one JSON object with `--json`. Writes no files.",),
    examples=("rdetoolkit skeletons show XrdTemplate", "rdetoolkit skeletons show modules.skeletons.XrdTemplate --json"),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unknown skeleton or a module that fails to import")),
    see_also=("rdetoolkit new processing",),
)

app = typer.Typer(help=SKELETONS_HELP.render(), short_help=SKELETONS_HELP.summary, no_args_is_help=True)


def _emit_usage_error(message: str, remediation: str) -> NoReturn:
    typer.echo(f"{message}\nRemediation: {remediation}", err=True)
    raise typer.Exit(code=3)


def _load_template_sources(modules: Sequence[str]) -> None:
    """Register every template source a templates command can resolve.

    ``list``, ``show`` and ``new processing`` share this so
    a template that ``list`` shows (project modules plus installed
    ``rdetoolkit.plugins`` entry points) is never unknown to the others.
    """
    load_modules(modules or _project_template_modules())
    from rdetoolkit.plugin import discover_plugins  # noqa: PLC0415 -- plugin discovery stays off the CLI import path

    discover_plugins()


def _project_template_modules() -> list[str]:
    """Find skeleton declarations in root modules and the conventional modules package."""
    root = Path.cwd()
    paths = sorted([*root.glob("*.py"), *(root / "modules").rglob("*.py")])
    modules = [_template_module_name(path.relative_to(root)) for path in paths if _declares_skeleton(path)]
    return list(dict.fromkeys(module for module in modules if module))


def _template_module_name(path: Path) -> str:
    parts = path.with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _declares_skeleton(path: Path) -> bool:
    try:
        with tokenize.open(path) as source:
            tree = ast.parse(source.read())
    except (OSError, SyntaxError, UnicodeError):
        return False
    names = _skeleton_base_names(tree)
    return any(
        isinstance(node, ast.ClassDef) and any(ast.unparse(base).split(".")[-1] in names for base in node.bases)
        for node in ast.walk(tree)
    )


def _skeleton_base_names(tree: ast.AST) -> set[str]:
    names = {"ProcessingTemplate"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "rdetoolkit.templates":
            names.update(alias.asname or alias.name for alias in node.names if alias.name == "ProcessingTemplate")
    return names


def _find_template(name: str) -> TemplateSpec:
    try:
        return registry.get_template(name)
    except KeyError:
        _emit_usage_error(
            f"Unknown processing skeleton: {name}",
            "run 'rdetoolkit skeletons list' to see registered skeletons, and pass --module "
            "for a module that is not found automatically.",
        )


@app.command("list", help=LIST_HELP.render(), short_help=LIST_HELP.summary)
def list_templates(
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before listing; repeatable."),
    ] = None,
) -> None:
    """List registered processing skeletons."""
    _load_template_sources(modules or [])
    values = [asdict(spec) for spec in registry.list_templates()]
    if as_json:
        typer.echo(json.dumps(values, sort_keys=True))
        return
    for value in values:
        typer.echo(value["id"])


@app.command("show", help=SHOW_HELP.render(), short_help=SHOW_HELP.summary)
def show(
    template_id: Annotated[str, typer.Argument(metavar="NAME")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before showing; repeatable."),
    ] = None,
) -> None:
    """Show a registered processing skeleton."""
    _load_template_sources(modules or [])
    value = asdict(_find_template(template_id))
    if as_json:
        typer.echo(json.dumps(value, sort_keys=True))
        return
    for name, field_value in value.items():
        typer.echo(f"{name}: {field_value}")


def _identifier(value: str) -> str:
    words = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    candidate = "".join(word[:1].upper() + word[1:] for word in words)
    return candidate or "GeneratedProcessing"


_NONE_TYPE_NAMES = frozenset({"None", "NoneType", "builtins.NoneType"})
# A (possibly dotted) identifier that is not part of a string literal.
_DOTTED_NAME = re.compile(r"(?<![\w'\"])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?![\w'\"])")

# Module -> names the generated module must import, filled while rendering.
_Imports = dict[str, set[str]]


def _annotation(type_name: str, imports: _Imports) -> str:
    """Render one registry type name as source text and record its import.

    ``typing.get_type_hints`` resolves a ``-> None`` declaration to
    ``NoneType``, which is not a name a module can use, so every spelling of
    it renders as ``None``. Every dotted name inside the expression
    (``typing.`` ones included) renders as its last segment and records
    ``from <module> import <Name>``: the generated subclass must define the
    same annotation text the skeleton declares, and those names have to
    resolve when the module is imported.
    """
    if type_name in _NONE_TYPE_NAMES:
        return "None"

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in _NONE_TYPE_NAMES:
            return "None"
        module, _, name = token.rpartition(".")
        if module:
            imports.setdefault(module, set()).add(name)
        return name

    # The annotation may be an expression (``pathlib.Path | None``,
    # ``list[pkg.X]``): only its dotted names are imported; the operators,
    # brackets and literals around them are kept verbatim.
    return _DOTTED_NAME.sub(replace, type_name)


_STAR_PREFIX = {"var_positional": "*", "var_keyword": "**"}
_DEFAULT_HELPER = "_skeleton_default"


def _needs_default_helper(parameter: TemplateParameterSpec) -> bool:
    """Whether a default cannot be written as source and must come from the skeleton."""
    return parameter.default is not None and not parameter.default_literal


def _render_parameter(method_name: str, parameter: TemplateParameterSpec, imports: _Imports) -> str:
    """Render one parameter with its star prefix, annotation and default.

    A literal default is its ``repr``. Any other default (a module constant,
    ``Path("x")``, NaN) is read back from the skeleton's own signature at
    import time, so the generated class carries the identical object rather
    than a ``...``/``None`` stand-in (review F07).
    """
    prefix = _STAR_PREFIX.get(parameter.kind, "")
    text = f"{prefix}{parameter.name}: {_annotation(parameter.type_name, imports)}"
    if parameter.default is None:
        return text
    if _needs_default_helper(parameter):
        return f"{text} = {_DEFAULT_HELPER}({method_name!r}, {parameter.name!r})"
    return f"{text} = {parameter.default}"


def _render_parameters(method: TemplateMethodSpec, imports: _Imports) -> list[str]:
    """Render parameters with the ``/`` and bare ``*`` markers their kinds imply.

    ``_signatures_match`` compares names, kinds and annotations, so dropping a
    marker turns a valid slot into a 2102 import failure (review F07).
    """
    items: list[str] = []
    keyword_only_open = False
    parameters = method.parameters
    for index, parameter in enumerate(parameters):
        if parameter.kind == "keyword_only" and not keyword_only_open:
            items.append("*")
        keyword_only_open = keyword_only_open or parameter.kind in {"var_positional", "keyword_only"}
        items.append(_render_parameter(method.name, parameter, imports))
        following = parameters[index + 1].kind if index + 1 < len(parameters) else None
        if parameter.kind == "positional_only" and following != "positional_only":
            items.append("/")
    return items


def _render_slot(method: TemplateMethodSpec, imports: _Imports) -> str:
    parameters = ", ".join(_render_parameters(method, imports))
    separator = ", " if parameters else ""
    return_type = _annotation(method.return_type, imports)
    return (
        f"    def {method.name}(self{separator}{parameters}) -> {return_type}:\n"
        f"        # TODO: implement the {method.name} template slot.\n"
        "        raise NotImplementedError\n"
    )


def _render_imports(imports: _Imports) -> str:
    """Render one sorted, deduplicated ``from`` import line per module."""
    return "".join(
        f"from {module} import {', '.join(sorted(names))}\n"
        for module, names in sorted(imports.items())
    )


def _render_default_helper(spec: TemplateSpec, skeleton_name: str, imports: _Imports) -> str:
    """Render the import-time lookup of non-literal skeleton defaults, if any slot needs it."""
    if not any(_needs_default_helper(parameter) for method in spec.slots for parameter in method.parameters):
        return ""
    imports.setdefault("inspect", set()).add("signature")
    imports.setdefault("typing", set()).add("Any")
    return (
        f"def {_DEFAULT_HELPER}(slot: str, parameter: str) -> Any:\n"
        '    """Return the skeleton\'s own default object for one slot parameter."""\n'
        f"    return signature(getattr({skeleton_name}, slot)).parameters[parameter].default\n\n\n"
    )


def _render_processing_module(spec: TemplateSpec) -> str:
    module_name, _, skeleton_name = spec.id.rpartition(".")
    class_name = _identifier(skeleton_name.removesuffix("Template") + "Processing")
    imports: _Imports = {module_name: {skeleton_name}}
    methods = "\n".join(_render_slot(method, imports) for method in spec.slots)
    helper = _render_default_helper(spec, skeleton_name, imports)
    return (
        '"""Generated ProcessingTemplate implementation."""\n\n'
        "from __future__ import annotations\n\n"
        f"{_render_imports(imports)}\n\n"
        f"{helper}"
        f"class {class_name}({skeleton_name}):\n"
        '    """TODO: implement each required domain slot."""\n\n'
        f"{methods}"
    )


def _render_sample_test(spec: TemplateSpec) -> str:
    skeleton_name = spec.name
    class_name = _identifier(skeleton_name.removesuffix("Template") + "Processing")
    return (
        '"""Sample tests for the generated processing template."""\n\n'
        "from processing import "
        f"{class_name}\n\n\n"
        "def test_generated_processing(rde_paths, rde_out, rde_config, rde_invoice) -> None:\n"
        f"    processing = {class_name}()\n"
        "    # TODO: build domain fixtures matching the slot signatures and assert results.\n"
        "    assert processing is not None\n"
    )


def _render_main(spec: TemplateSpec) -> str:
    class_name = _identifier(spec.name.removesuffix("Template") + "Processing")
    return (
        '\"\"\"Run the generated ProcessingTemplate after implementing its slots.\"\"\"\n\n'
        "from rdetoolkit import workflows\n"
        f"from processing import {class_name}\n\n"
        'if __name__ == "__main__":\n'
        f"    report = workflows.run(flow={class_name})\n"
        '    raise SystemExit(report.exit_code)\n'
    )


def generate_processing_template(
    name: str,
    modules: Sequence[str],
    output_dir: Path,
    *,
    force: bool = False,
) -> None:
    """Generate a TODO implementation and sample test for a skeleton.

    Args:
        name: Full template id or unambiguous skeleton class name.
        modules: Dotted provider modules imported before registry lookup;
            installed plugins are discovered as well.
        output_dir: Directory receiving generated files.
        force: Whether to replace existing generated files.
    """
    _load_template_sources(modules)
    spec = _find_template(name)
    processing_path = output_dir / "processing.py"
    test_path = output_dir / "tests" / "test_processing.py"
    main_path = output_dir / "main.py"
    existing_paths = [path for path in (processing_path, test_path, main_path) if path.exists()]
    if existing_paths and not force:
        rendered_paths = ", ".join(str(path) for path in existing_paths)
        _emit_usage_error(
            f"Refusing to overwrite existing file(s): {rendered_paths}.",
            "rerun with --force to overwrite them, or pass -o with another directory.",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)
    processing_path.write_text(_render_processing_module(spec), encoding="utf-8")
    test_path.write_text(_render_sample_test(spec), encoding="utf-8")
    main_path.write_text(_render_main(spec), encoding="utf-8")
    typer.echo(f"Generated {processing_path}")
    typer.echo(f"Generated {test_path}")
    typer.echo(f"Generated {main_path}")
