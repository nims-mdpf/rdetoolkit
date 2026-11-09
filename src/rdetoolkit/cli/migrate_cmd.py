"""Report source locations that may need v2 migration.

Class findings use a best-effort structural heuristic because v1 defines no
common handler base class. Review those findings manually.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import shutil
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from rdetoolkit.cli._migrate_source import _render_conversion
from rdetoolkit.types import InputPaths

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


app = typer.Typer(help="Inspect Python source for v1 migration points.")
_HANDLER_POSITIONAL_ARGUMENTS = 3
_CALLBACK_POSITIONAL_ARGUMENTS = 2

#: v1 ``RdeOutputResourcePath`` fields that ``OutputContext`` keeps by name.
_OUTPUT_CONTEXT_ATTRIBUTES = frozenset(
    {
        "struct",
        "meta",
        "main_image",
        "other_image",
        "thumbnail",
        "raw",
        "logs",
        "attachment",
        "nonshared_raw",
        "invoice",
    },
)
#: v1 ``RdeOutputResourcePath`` fields that moved to ``InputPaths`` in v2.
_OUTPUT_TO_INPUT_ATTRIBUTES = frozenset({"rawfiles", "smarttable_rawfile"})
#: v1 ``RdeInputDirPaths`` attributes that ``InputPaths`` keeps by name.
_INPUT_PATHS_ATTRIBUTES = frozenset(field.name for field in dataclasses.fields(InputPaths))


@dataclass(frozen=True, slots=True)
class Finding:
    """One source migration finding."""

    line: int
    category: str


def _usage_error(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


@app.command()
def check(path: Annotated[Path, typer.Argument(metavar="[path]")] = Path(".")) -> None:
    """Scan one Python file or all Python files beneath a directory."""
    if not path.exists():
        _usage_error(f"Path does not exist: {path}")
    files = [path] if path.is_file() else sorted(path.rglob("*.py"))
    for source_path in files:
        _report_file(source_path)


@app.command()
def apply(
    path: Annotated[
        Path,
        typer.Argument(
            metavar="[path]",
            exists=True,
            file_okay=True,
            dir_okay=True,
            readable=True,
        ),
    ] = Path("."),
    out: Annotated[Path | None, typer.Option("--out", help="External output directory.")] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--no-dry-run", help="Preview by default; write only with --no-dry-run."),
    ] = True,
) -> None:
    """Convert legacy callbacks into eager v2 flows without editing input files."""
    path = path.resolve()
    files = _python_files(path)
    if not files:
        _usage_error(
            f"No Python files found beneath: {path}. "
            "Remediation: provide a Python file or a directory containing v1 template sources.",
        )
    destination = out or _default_output(path)
    _validate_destination(path, destination)
    converted = [(source_path, _convert_source(source_path)) for source_path in files]
    if dry_run:
        _preview(path, destination, converted)
        return
    _write_conversion(path, destination, converted)
    count = sum(text is not None for _, text in converted)
    typer.echo(f"Converted {count} of {len(converted)} file(s) to {destination}")


def _python_files(path: Path) -> list[Path]:
    return [path] if path.is_file() else sorted(path.rglob("*.py"))


def _default_output(path: Path) -> Path:
    name = path.name if path.is_dir() else path.stem
    return path.with_name(f"{name}_migrated")


def _validate_destination(source: Path, destination: Path) -> None:
    if destination.exists():
        _usage_error(
            f"Output already exists: {destination}. "
            "Remediation: choose a new external directory with --out.",
        )
    if source.is_dir() and destination.resolve().is_relative_to(source.resolve()):
        _usage_error(
            f"Output must be outside the input tree: {destination}. "
            "Remediation: pass --out with a sibling or otherwise external directory.",
        )


def _preview(
    source_root: Path,
    destination: Path,
    converted: list[tuple[Path, str | None]],
) -> None:
    for source_path, text in converted:
        relative = source_path.relative_to(source_root) if source_root.is_dir() else Path(source_path.name)
        typer.echo(f"--- {source_path} -> {destination / relative} (dry-run) ---")
        typer.echo(text if text is not None else "Unchanged; see any manual-migration diagnostic above.")


def _write_conversion(
    source_root: Path,
    destination: Path,
    converted: list[tuple[Path, str | None]],
) -> None:
    if source_root.is_dir():
        shutil.copytree(source_root, destination)
        for source_path, text in converted:
            if text is None:
                continue
            target = destination / source_path.relative_to(source_root)
            target.write_text(text, encoding="utf-8")
        return
    destination.mkdir(parents=True)
    text = converted[0][1]
    if text is None:
        shutil.copy2(source_root, destination / source_root.name)
    else:
        (destination / source_root.name).write_text(text, encoding="utf-8")


def _convert_source(path: Path) -> str | None:
    try:
        with tokenize.open(path) as source_file:
            source = source_file.read()
    except (OSError, SyntaxError, UnicodeError) as exc:
        typer.echo(
            f"Unable to decode source {path}: {exc}. "
            "Remediation: correct the encoding cookie or file bytes, then rerun migrate apply.",
            err=True,
        )
        return _todo_source("", f"source encoding could not be decoded: {exc}")
    return _convert_text(path, source)


def _convert_text(path: Path, source: str) -> str | None:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return _todo_source(source, f"unparseable source at line {exc.lineno or 0}")
    if _callbacks_need_manual(tree):
        _report_unconverted(path, tree)
        return None
    callback_names = _callback_names(tree)
    transformer = _ApplyTransformer(callback_names)
    converted = transformer.visit(copy.deepcopy(tree))
    if not transformer.converted_callback:
        _report_unconverted(path, tree)
        return None
    _repair_empty_bodies(converted)
    ast.fix_missing_locations(converted)
    _insert_v2_imports(converted)
    text = _render_conversion(source, tree, converted)
    _report_removed_entries(path, tree)
    # Prepended last-first so the header lists findings in source line order.
    for reason in reversed(transformer.manual_steps):
        text = _todo_source(text, reason)
    if _has_dynamic_dispatch(tree):
        text = _todo_source(text, "dynamic dispatch requires manual review")
    return text


def _callback_values(tree: ast.AST) -> list[ast.expr]:
    return [keyword.value for call in ast.walk(tree) if isinstance(call, ast.Call) for keyword in call.keywords if keyword.arg == "custom_dataset_function"]


def _local_callback_names(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and len(node.args.args) >= _CALLBACK_POSITIONAL_ARGUMENTS}


def _callbacks_need_manual(tree: ast.AST) -> bool:
    names = _local_callback_names(tree)
    return any(not isinstance(value, ast.Name) or value.id not in names for value in _callback_values(tree))


def _report_removed_entries(path: Path, tree: ast.AST) -> None:
    for call in ast.walk(tree):
        if isinstance(call, ast.Call) and _has_custom_dataset_keyword(call):
            typer.echo(
                f"{path}:{call.lineno}: removed legacy entry {ast.unparse(call)}. "
                "Run the converted flow using rdetoolkit run --flow <module>:pipeline.",
                err=True,
            )


def _report_unconverted(path: Path, tree: ast.AST) -> None:
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        for keyword in call.keywords:
            if keyword.arg == "custom_dataset_function":
                typer.echo(
                    f"{path}:{call.lineno}: manual migration required for {ast.unparse(keyword.value)}; "
                    "source and entry call left unchanged. Convert the callback to a flow and update this entry together.",
                    err=True,
                )


def _callback_names(tree: ast.AST) -> set[str]:
    return {
        keyword.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "custom_dataset_function" and isinstance(keyword.value, ast.Name)
    }


def _has_dynamic_dispatch(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"globals", "locals", "getattr"}
        for node in ast.walk(tree)
    )


def _todo_source(source: str, reason: str) -> str:
    return f"# TODO(rdetoolkit-migrate): {reason}.\n{source}"


def _insert_v2_imports(tree: ast.Module) -> None:
    imports = ast.parse(
        "from rdetoolkit import flow\n"
        "from rdetoolkit.types import InputPaths, OutputContext\n",
    ).body
    index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
    while index < len(tree.body):
        statement = tree.body[index]
        if not isinstance(statement, ast.ImportFrom) or statement.module != "__future__":
            break
        index += 1
    tree.body[index:index] = imports


class _LegacyParamMapper(ast.NodeTransformer):
    """Move v1 path-bundle attribute access onto the v2 bundle that owns it.

    Renaming the parameters alone turned ``resource_paths.rawfiles`` into the
    non-existent ``out.rawfiles`` and reported success (review F08). Mapped
    attributes are rewritten; an attribute with no v2 home is left exactly as
    written, and a bare use of a renamed parameter is renamed -- the callee now
    receives a v2 object -- and both are recorded for a manual-migration TODO
    (Design §10: unsupported constructs are marked, not silently converted).
    """

    def __init__(self, input_name: str, output_name: str) -> None:
        self._input_name = input_name
        self._output_name = output_name
        self.findings: dict[tuple[int, str], str] = {}

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:  # noqa: N802
        owner = node.value
        if not isinstance(owner, ast.Name) or owner.id not in {self._input_name, self._output_name}:
            return self.generic_visit(node)
        target = self._target_for(owner.id, node.attr)
        original = f"{owner.id}.{node.attr}"
        if target is None:
            bundle = "InputPaths" if owner.id == self._input_name else "InputPaths/OutputContext"
            self._record(node, original, f"{original} has no {bundle} equivalent and was left unconverted; migrate it manually")
            return node
        renamed = ast.copy_location(ast.Name(id=target, ctx=ast.Load()), owner)
        return ast.copy_location(ast.Attribute(value=renamed, attr=node.attr, ctx=node.ctx), node)

    def visit_Name(self, node: ast.Name) -> ast.Name:  # noqa: N802
        if node.id == self._input_name:
            return self._rename_bare(node, "paths", "InputPaths")
        if node.id == self._output_name:
            return self._rename_bare(node, "out", "OutputContext")
        return node

    def _target_for(self, owner: str, attribute: str) -> str | None:
        if owner == self._input_name:
            return "paths" if attribute in _INPUT_PATHS_ATTRIBUTES else None
        if attribute in _OUTPUT_CONTEXT_ATTRIBUTES:
            return "out"
        return "paths" if attribute in _OUTPUT_TO_INPUT_ATTRIBUTES else None

    def _rename_bare(self, node: ast.Name, replacement: str, bundle: str) -> ast.Name:
        self._record(
            node,
            node.id,
            f"{node.id} is now passed on as a v2 {bundle} (renamed to {replacement}); update the code that receives it",
        )
        return ast.copy_location(ast.Name(id=replacement, ctx=node.ctx), node)

    def _record(self, node: ast.expr, name: str, reason: str) -> None:
        self.findings.setdefault((node.lineno, name), f"line {node.lineno}: {reason}")


class _ApplyTransformer(ast.NodeTransformer):
    def __init__(self, callback_names: set[str]) -> None:
        self._callback_names = callback_names
        self.converted_callback = False
        self._findings: dict[tuple[int, str], str] = {}

    @property
    def manual_steps(self) -> list[str]:
        """Manual-migration reasons for converted callbacks, in source line order."""
        return [self._findings[key] for key in sorted(self._findings)]

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        if node.name not in self._callback_names or len(node.args.args) < _CALLBACK_POSITIONAL_ARGUMENTS:
            return self.generic_visit(node)
        first, second = node.args.args[:2]
        mapper = _LegacyParamMapper(first.arg, second.arg)
        first.arg = "paths"
        first.annotation = ast.Name(id="InputPaths", ctx=ast.Load())
        second.arg = "out"
        second.annotation = ast.Name(id="OutputContext", ctx=ast.Load())
        node.name = "pipeline"
        node.decorator_list.insert(0, ast.Name(id="flow", ctx=ast.Load()))
        node.body = [cast_node for item in node.body if (cast_node := mapper.visit(item))]
        self._findings.update(mapper.findings)
        self.converted_callback = True
        return self.generic_visit(node)

    def visit_If(self, node: ast.If) -> ast.AST | None:  # noqa: N802
        if _is_main_guard(node) and not node.orelse and _only_legacy_entries(node.body):
            return None
        return self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:  # noqa: N802
        # An expression statement wraps its call: the keyword lives on
        # ``node.value``, never on the ``ast.Expr`` itself.
        return None if _has_custom_dataset_keyword(node.value) else self.generic_visit(node)


def _repair_empty_bodies(tree: ast.AST) -> None:
    """Keep the converted module syntactically valid after statement removal.

    Removing ``run(custom_dataset_function=...)`` from a wrapper such as
    ``def main(): run(...)`` leaves a block with no statements, which
    ``ast.unparse`` renders as a bare header (an IndentationError on import).
    Every emptied block gets a ``pass``.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            continue
        body = getattr(node, "body", None)
        if isinstance(body, list) and not body:
            node.body = [ast.Pass()]  # type: ignore[attr-defined]


def _is_main_guard(node: ast.If) -> bool:
    return (
        isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )


def _only_legacy_entries(statements: list[ast.stmt]) -> bool:
    return all(isinstance(statement, ast.Expr) and _has_custom_dataset_keyword(statement.value) for statement in statements)


def _has_custom_dataset_keyword(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and any(keyword.arg == "custom_dataset_function" for keyword in node.keywords)


def _report_file(path: Path) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        typer.echo(f"{path}:{getattr(exc, 'lineno', 0) or 0}: unparseable: {exc}")
        return
    for finding in _find_migration_points(tree):
        typer.echo(f"{path}:{finding.line}: {finding.category}")


def _find_migration_points(tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and any(keyword.arg == "custom_dataset_function" for keyword in node.keywords):
            findings.append(Finding(node.lineno, "custom_dataset_function keyword"))
        if isinstance(node, ast.Name) and node.id == "RdeOutputResourcePath":
            findings.append(Finding(node.lineno, "direct RdeOutputResourcePath reference"))
        if isinstance(node, ast.ClassDef) and _has_legacy_handler_shape(node):
            findings.append(Finding(node.lineno, f"possible old handler class {node.name}"))
    return findings


def _has_legacy_handler_shape(class_node: ast.ClassDef) -> bool:
    return any(
        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _matches_handler_method(item)
        for item in class_node.body
    )


def _matches_handler_method(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    positional = [*method.args.posonlyargs, *method.args.args]
    if len(positional) != _HANDLER_POSITIONAL_ARGUMENTS or positional[0].arg not in {"self", "cls"}:
        return False
    output_arg = positional[2]
    return output_arg.arg == "resource_paths" or _annotation_name(output_arg.annotation) == "RdeOutputResourcePath"


def _annotation_name(annotation: ast.expr | None) -> str | None:
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    return None
