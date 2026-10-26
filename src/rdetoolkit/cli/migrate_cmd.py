"""Report source locations that may need v2 migration.

Class findings use a best-effort structural heuristic because v1 defines no
common handler base class. Review those findings manually.
"""

from __future__ import annotations

import ast
import shutil
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


app = typer.Typer(help="Inspect Python source for v1 migration points.")
_HANDLER_POSITIONAL_ARGUMENTS = 3
_CALLBACK_POSITIONAL_ARGUMENTS = 2


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
    typer.echo(f"Converted {len(converted)} file(s) to {destination}")


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
    converted: list[tuple[Path, str]],
) -> None:
    for source_path, text in converted:
        relative = source_path.relative_to(source_root) if source_root.is_dir() else Path(source_path.name)
        typer.echo(f"--- {source_path} -> {destination / relative} (dry-run) ---")
        typer.echo(text)


def _write_conversion(
    source_root: Path,
    destination: Path,
    converted: list[tuple[Path, str]],
) -> None:
    if source_root.is_dir():
        shutil.copytree(source_root, destination)
        for source_path, text in converted:
            target = destination / source_path.relative_to(source_root)
            target.write_text(text, encoding="utf-8")
        return
    destination.mkdir(parents=True)
    (destination / source_root.name).write_text(converted[0][1], encoding="utf-8")


def _convert_source(path: Path) -> str:
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
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return _todo_source(source, f"unparseable source at line {exc.lineno or 0}")
    callback_names = _callback_names(tree)
    transformer = _ApplyTransformer(callback_names)
    converted = transformer.visit(tree)
    ast.fix_missing_locations(converted)
    _insert_v2_imports(converted)
    text = ast.unparse(converted) + "\n"
    if _has_dynamic_dispatch(tree):
        text = _todo_source(text, "dynamic dispatch requires manual review")
    if not transformer.converted_callback:
        text = _todo_source(text, "no custom_dataset_function callback could be converted")
    return text


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


class _RenameLegacyParams(ast.NodeTransformer):
    def __init__(self, names: dict[str, str]) -> None:
        self._names = names

    def visit_Name(self, node: ast.Name) -> ast.Name:  # noqa: N802
        replacement = self._names.get(node.id)
        return ast.copy_location(ast.Name(id=replacement, ctx=node.ctx), node) if replacement else node


class _ApplyTransformer(ast.NodeTransformer):
    def __init__(self, callback_names: set[str]) -> None:
        self._callback_names = callback_names
        self.converted_callback = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        if node.name not in self._callback_names or len(node.args.args) < _CALLBACK_POSITIONAL_ARGUMENTS:
            return self.generic_visit(node)
        first, second = node.args.args[:2]
        replacements = {first.arg: "paths", second.arg: "out"}
        first.arg = "paths"
        first.annotation = ast.Name(id="InputPaths", ctx=ast.Load())
        second.arg = "out"
        second.annotation = ast.Name(id="OutputContext", ctx=ast.Load())
        node.name = "pipeline"
        node.decorator_list.insert(0, ast.Name(id="flow", ctx=ast.Load()))
        node.body = [cast_node for item in node.body if (cast_node := _RenameLegacyParams(replacements).visit(item))]
        self.converted_callback = True
        return self.generic_visit(node)

    def visit_If(self, node: ast.If) -> ast.AST | None:  # noqa: N802
        if _is_main_guard(node) and any(_has_custom_dataset_keyword(item) for item in ast.walk(node)):
            return None
        return self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:  # noqa: N802
        # An expression statement wraps its call: the keyword lives on
        # ``node.value``, never on the ``ast.Expr`` itself.
        return None if _has_custom_dataset_keyword(node.value) else self.generic_visit(node)


def _is_main_guard(node: ast.If) -> bool:
    return (
        isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )


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
