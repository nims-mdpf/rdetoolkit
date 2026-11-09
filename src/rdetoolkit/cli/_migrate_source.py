"""Render supported AST changes as source edits so comments remain intact."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from typing import cast

_Located = ast.expr | ast.stmt | ast.arg
_Edit = tuple[int, int, str]


def _offset(lines: list[str], row: int, byte_column: int) -> int:
    """Translate AST UTF-8 byte columns into source character positions."""
    prefix = lines[row - 1].encode("utf-8")[:byte_column].decode("utf-8")
    return sum(map(len, lines[:row - 1])) + len(prefix)


def _span(lines: list[str], node: _Located) -> tuple[int, int]:
    return _offset(lines, node.lineno, node.col_offset), _offset(lines, cast(int, node.end_lineno), cast(int, node.end_col_offset))


def _replacement_edits(lines: list[str], original: ast.Module, converted: ast.Module) -> list[_Edit]:
    old = {(type(node), node.lineno, node.col_offset): node for node in ast.walk(original) if isinstance(node, (ast.Name, ast.arg, ast.FunctionDef))}
    edits: list[_Edit] = []
    for node in ast.walk(converted):
        if not isinstance(node, (ast.Name, ast.arg, ast.FunctionDef)):
            continue
        before = old.get((type(node), node.lineno, node.col_offset))
        if before is not None:
            edits.extend(_node_edits(lines, node, before))
    return edits


def _node_edits(lines: list[str], node: ast.Name | ast.arg | ast.FunctionDef, before: ast.Name | ast.arg | ast.FunctionDef) -> list[_Edit]:
    if isinstance(node, ast.Name):
        original_name = cast(ast.Name, before)
        if original_name.id != node.id:
            return [(*_span(lines, original_name), node.id)]
    elif isinstance(node, ast.arg):
        original_arg = cast(ast.arg, before)
        if original_arg.arg != node.arg:
            return [(*_span(lines, original_arg), ast.unparse(node))]
    else:
        original_function = cast(ast.FunctionDef, before)
        if original_function.name != node.name:
            return _function_edits(lines, original_function, node.name)
    return []


def _function_edits(lines: list[str], before: ast.FunctionDef, name: str) -> list[_Edit]:
    start = _offset(lines, before.lineno, before.col_offset)
    header = lines[before.lineno - 1][before.col_offset:]
    match = cast(re.Match[str], re.search(r"def\s+(\w+)", header))
    decorator_row = min([before.lineno, *(item.lineno for item in before.decorator_list)])
    decorator_start = _offset(lines, decorator_row, 0)
    return [
        (start + match.start(1), start + match.end(1), name),
        (decorator_start, decorator_start, " " * before.col_offset + "@flow\n"),
    ]


def _removed_statements(original: ast.Module, converted: ast.Module) -> list[ast.stmt]:
    remaining = {(type(node), node.lineno, node.col_offset) for node in ast.walk(converted) if isinstance(node, ast.stmt)}
    return [node for node in ast.walk(original) if isinstance(node, ast.stmt) and (type(node), node.lineno, node.col_offset) not in remaining]


def _removed_edits(source: str, lines: list[str], original: ast.Module, converted: ast.Module) -> list[_Edit]:
    removed = _removed_statements(original, converted)
    edits: list[_Edit] = []
    for node in sorted(removed, key=lambda item: (item.lineno, item.col_offset)):
        start, end = _span(lines, node)
        if any(left <= start < right for left, right, _ in edits):
            continue
        indent = " " * node.col_offset
        replacement = "pass" + "".join(f"\n{indent}{comment}" for comment in _comments(source[start:end]))
        edits.append((start, end, replacement))
    return edits


def _comments(source: str) -> list[str]:
    return [token.string for token in tokenize.generate_tokens(io.StringIO(source).readline) if token.type == tokenize.COMMENT]


def _import_offset(lines: list[str], tree: ast.Module) -> int:
    index = int(ast.get_docstring(tree) is not None)
    while index < len(tree.body) and _is_future_import(tree.body[index]):
        index += 1
    statement = tree.body[index]
    row = statement.lineno
    if isinstance(statement, ast.FunctionDef):
        row = min([row, *(decorator.lineno for decorator in statement.decorator_list)])
    return _offset(lines, row, 0)


def _is_future_import(statement: ast.stmt) -> bool:
    return isinstance(statement, ast.ImportFrom) and statement.module == "__future__"


def _render_conversion(source: str, original: ast.Module, converted: ast.Module) -> str:
    """Apply callback renames and removed entry points without rewriting tokens."""
    lines = source.splitlines(keepends=True)
    removed = _removed_edits(source, lines, original, converted)
    edits = [edit for edit in _replacement_edits(lines, original, converted) if not any(start <= edit[0] < end for start, end, _ in removed)]
    edits.extend(removed)
    index = _import_offset(lines, original)
    edits = _insert_imports(edits, index)
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    # Converted output is UTF-8 even when the original PEP 263 cookie was not.
    return _utf8_cookie(source)


def _insert_imports(edits: list[_Edit], index: int) -> list[_Edit]:
    imports = "from rdetoolkit import flow\nfrom rdetoolkit.types import InputPaths, OutputContext\n"
    decorators = "".join(text for start, end, text in edits if start == end == index)
    result = [edit for edit in edits if not edit[0] == edit[1] == index]
    result.append((index, index, imports + decorators))
    return result


def _utf8_cookie(source: str) -> str:
    lines = source.splitlines(keepends=True)
    lines[:2] = [re.sub(r"^(#[^\n]*coding[:=]\s*)[-\w.]+", r"\g<1>utf-8", line) for line in lines[:2]]
    return "".join(lines)
