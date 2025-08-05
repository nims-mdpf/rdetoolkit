"""Build search index for rdetoolkit codebase.

This script generates a JSONL index file containing metadata about Python and Markdown
files in the project, including extracted symbols (functions, classes, headings).
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import re
from typing import Any

# Configuration - only modify this section as needed
EXCLUDE_DIRS: set[str] = {
    "docs",
    ".venv",
    "venv",
    "local",
    "dist",
    "build",
    "node_modules",
    ".git",
    ".gitignore",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
}

TARGET_EXTS: set[str] = {".py", ".md"}
MIN_LINES_FOR_SYMBOL_CHECK: int = 10
PKG_ROOT: str = "src"
PKG_NAME: str = "rdetoolkit"

ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parents[1]
OUT_PATH: pathlib.Path = ROOT / "docs" / "search" / "rdetoolkit_code_index.jsonl"

# Regex patterns for fallback symbol extraction
_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.M)
_ASYNC_DEF_RE = re.compile(r"^\s*async\s+def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.M)
_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\(|:)", re.M)


def is_excluded(rel_path: str) -> bool:
    """Check if a path should be excluded from indexing.

    Args:
        rel_path: Relative path to check.

    Returns:
        True if the path should be excluded, False otherwise.
    """
    parts = pathlib.PurePosixPath(rel_path).parts
    for segment in parts:
        if segment in EXCLUDE_DIRS:
            return True
        # Exclude hidden directories starting with '.' except for .github
        if segment.startswith(".") and segment not in {".github"}:
            return True
    return False


def py_symbols(text: str) -> list[str]:
    """Extract function and class names from Python source code.

    Uses AST parsing as the primary method, with regex fallback for malformed code.

    Args:
        text: Python source code as string.

    Returns:
        Sorted list of unique symbol names (functions and classes).
    """
    symbols: list[str] = []
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(node.name)

        # Fallback to regex if AST extraction yields no results
        if not symbols:
            symbols = regex_py_symbols(text)
        return sorted(set(symbols))
    except Exception:
        # Fallback to regex parsing on AST errors
        return sorted(set(regex_py_symbols(text)))


def regex_py_symbols(text: str) -> list[str]:
    """Extract Python symbols using regex patterns as fallback.

    Args:
        text: Python source code as string.

    Returns:
        List of symbol names found via regex.
    """
    names: list[str] = []
    names.extend(_DEF_RE.findall(text))
    names.extend(_ASYNC_DEF_RE.findall(text))

    # _CLASS_RE returns tuples (name, delimiter), extract just the names
    class_matches = _CLASS_RE.findall(text)
    names.extend(match[0] if isinstance(match, tuple) else match for match in class_matches)

    return names


def md_symbols(text: str) -> list[str]:
    """Extract heading symbols from Markdown text.

    Args:
        text: Markdown source code as string.

    Returns:
        List of H1 and H2 headings (limited to first 5).
    """
    headings = re.findall(r"^#{1,2}\s+(.+)$", text, re.M)
    return [heading.strip() for heading in headings[:5]]


def to_module(path: str) -> str | None:
    """Convert file path to Python module name.

    Args:
        path: File path (e.g., 'src/rdetoolkit/foo/bar.py').

    Returns:
        Module name (e.g., 'rdetoolkit.foo.bar') or None if not a valid Python module.
    """
    file_path = pathlib.PurePosixPath(path)
    if file_path.suffix != ".py":
        return None

    try:
        relative_path = file_path.relative_to(PKG_ROOT)  # e.g., rdetoolkit/foo/bar.py
    except ValueError:
        return None

    if not str(relative_path).startswith(PKG_NAME + "/"):
        return None

    return ".".join(relative_path.with_suffix("").parts)


def index_one(path: str) -> dict[str, Any]:
    """Create index entry for a single file.

    Args:
        path: Relative path to the file.

    Returns:
        Dictionary containing file metadata and extracted symbols.
    """
    file_path = pathlib.PurePosixPath(path)
    ext = file_path.suffix

    try:
        text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        text = ""

    if ext == ".py":
        symbols = py_symbols(text)
        module = to_module(path)
    elif ext == ".md":
        symbols = md_symbols(text)
        module = None
    else:
        symbols = []
        module = None

    return {
        "path": path,
        "ext": ext,
        "symbols": symbols,
        "module": module,
        "lines": text.count("\n") + 1 if text else 0,
    }


def collect_target_files() -> list[str]:
    """Collect all target files for indexing.

    Returns:
        List of relative file paths to be indexed.
    """
    files: list[str] = []

    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""

        # Exclude directories to prevent os.walk from recursing into them
        dirnames[:] = [dirname for dirname in dirnames if not is_excluded(os.path.join(rel_dir, dirname).replace("\\", "/"))]

        for filename in filenames:
            rel_path = os.path.join(rel_dir, filename).replace("\\", "/")
            if is_excluded(rel_path):
                continue
            if pathlib.PurePosixPath(rel_path).suffix in TARGET_EXTS:
                files.append(rel_path)

    return files


def main() -> None:
    """Generate search index for the codebase."""
    files = collect_target_files()

    # Ensure output directory exists
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Statistics tracking
    count_py = count_md = parse_failures = 0

    with OUT_PATH.open("w", encoding="utf-8") as output_file:
        for file_path in sorted(files):
            record = index_one(file_path)

            if record["ext"] == ".py":
                count_py += 1
                # Detect potential parsing failures: no symbols extracted from substantial files
                if record["lines"] > MIN_LINES_FOR_SYMBOL_CHECK and not record["symbols"]:
                    parse_failures += 1
            elif record["ext"] == ".md":
                count_md += 1

            json.dump(record, output_file, ensure_ascii=False)
            output_file.write("\n")

    # Using print is acceptable for a CLI tool's output
    print(f"[index] wrote: {OUT_PATH}")  # noqa: T201
    print(f"[stats] py={count_py} md={count_md} symbols_empty_py={parse_failures}")  # noqa: T201


if __name__ == "__main__":
    main()
