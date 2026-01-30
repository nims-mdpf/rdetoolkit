#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "tomli>=2.0 ; python_version < '3.11'"
# ]
# ///
"""Utility to bump semantic version strings across code and config files.

The script focuses on source and configuration files (e.g., `src/`, `pyproject.toml`)
and skips documentation, virtual environments, and cache artifacts by default.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
from typing import Iterable, Sequence

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_INCLUDE = [
    pathlib.Path("pyproject.toml"),
    pathlib.Path("src"),
    pathlib.Path("tests"),
    pathlib.Path("tox.ini"),
    pathlib.Path("uv.lock"),
    pathlib.Path("Cargo.toml"),
    pathlib.Path("Cargo.lock"),
    pathlib.Path("requirements.lock"),
    pathlib.Path("requirements-dev.lock"),
]

DEFAULT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "__pycache__",
    "build",
    "claudedocs",
    "data",
    "dist",
    "docs",
    "htmlcov",
    "site",
    "target",
    "tmp-test-gen",
}

DEFAULT_SKIP_FILES = {
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
}

ALLOWED_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".lock",
    ".md",
    ".py",
    ".pyi",
    ".rs",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

SEMVER_PATTERN = re.compile(r"^v?(?P<num>\d+\.\d+\.\d+)$")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Optional argument vector for testing; defaults to sys.argv.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Replace semantic versions (vX.Y.Z or X.Y.Z) in source/config files."
    )
    parser.add_argument(
        "new_version",
        help="New version (with or without leading 'v'), e.g., v1.5.3 or 1.5.3.",
    )
    parser.add_argument(
        "--old-version",
        dest="old_version",
        help="Old version to replace. Defaults to the project version in pyproject.toml.",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        type=pathlib.Path,
        default=None,
        help="Additional paths to scan. Defaults to code/config files only.",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        type=pathlib.Path,
        default=None,
        help="Additional files or directories to skip.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-file replacement counts.",
    )
    return parser.parse_args(argv)


def parse_version(raw: str) -> tuple[str, bool]:
    """Validate and normalize a semantic version string.

    Args:
        raw: Version string, with or without leading 'v'.

    Returns:
        A tuple of (core_version, has_v_prefix).

    Raises:
        ValueError: If the version does not follow v?X.Y.Z format.
    """
    match = SEMVER_PATTERN.match(raw.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {raw!r}")
    return match.group("num"), raw.strip().startswith(("v", "V"))


def load_version_from_pyproject(repo_root: pathlib.Path) -> str | None:
    """Read the project version from pyproject.toml if present.

    Args:
        repo_root: Repository root path.

    Returns:
        Version string if found; otherwise None.
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return None

    try:
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    project = data.get("project", {})
    version = project.get("version")
    return version if isinstance(version, str) else None


def build_pattern(old_core: str) -> re.Pattern[str]:
    """Build a regex that matches the old version with optional leading 'v'.

    Args:
        old_core: Semantic version without leading 'v'.

    Returns:
        Compiled regular expression ready for substitution.
    """
    return re.compile(rf"\bv?{re.escape(old_core)}\b")


def path_is_under(path: pathlib.Path, prefixes: set[pathlib.Path]) -> bool:
    """Check if path is under any given prefix paths.

    Args:
        path: Candidate path.
        prefixes: Paths that define excluded areas.

    Returns:
        True if the candidate is within any excluded prefix.
    """
    for prefix in prefixes:
        try:
            path.relative_to(prefix)
            return True
        except ValueError:
            continue
    return False


def iter_target_files(
    roots: Iterable[pathlib.Path],
    repo_root: pathlib.Path,
    extra_excludes: Iterable[pathlib.Path],
    skip_dirs: set[str],
    skip_files: set[str],
) -> Iterable[pathlib.Path]:
    """Yield files to process based on include and exclude rules.

    Args:
        roots: Roots to scan.
        repo_root: Repository root path.
        extra_excludes: Additional absolute or relative paths to skip.
        skip_dirs: Directory names to prune.
        skip_files: File names to skip.

    Yields:
        Paths to files that should be inspected for replacements.
    """
    excluded_paths = {p.resolve() for p in extra_excludes}

    for root in roots:
        absolute_root = (repo_root / root).resolve() if not root.is_absolute() else root
        if not absolute_root.exists():
            continue

        if absolute_root.is_file():
            if absolute_root.name not in skip_files:
                yield absolute_root
            continue

        for current, dirnames, filenames in os.walk(absolute_root):
            current_path = pathlib.Path(current)

            if path_is_under(current_path, excluded_paths):
                dirnames.clear()
                continue

            dirnames[:] = [
                d
                for d in dirnames
                if d not in skip_dirs
                and not path_is_under(current_path / d, excluded_paths)
            ]

            for filename in filenames:
                if filename in skip_files:
                    continue
                candidate = current_path / filename
                if candidate.suffix not in ALLOWED_SUFFIXES:
                    continue
                if path_is_under(candidate, excluded_paths):
                    continue
                yield candidate


def replace_versions_in_file(
    path: pathlib.Path,
    pattern: re.Pattern[str],
    new_with_v: str,
    new_without_v: str,
    dry_run: bool,
) -> int:
    """Replace version occurrences in a single file.

    Args:
        path: File to update.
        pattern: Compiled regex for the old version.
        new_with_v: Replacement when the matched string includes a leading 'v'.
        new_without_v: Replacement when the matched string has no 'v'.
        dry_run: If True, do not write changes.

    Returns:
        Number of replacements performed in the file.
    """

    def _replacement(match: re.Match[str]) -> str:
        matched = match.group(0)
        return new_with_v if matched.startswith("v") else new_without_v

    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    updated, count = pattern.subn(_replacement, original)
    if count > 0 and not dry_run:
        path.write_text(updated, encoding="utf-8")
    return count


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument vector for testing; defaults to sys.argv.

    Returns:
        Exit status code.
    """
    args = parse_args(argv)
    repo_root = pathlib.Path(__file__).resolve().parent.parent

    try:
        new_core, _ = parse_version(args.new_version)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.old_version:
        try:
            old_core, _ = parse_version(args.old_version)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
    else:
        detected = load_version_from_pyproject(repo_root)
        if not detected:
            print(
                "Could not determine current version; specify --old-version explicitly.",
                file=sys.stderr,
            )
            return 1
        old_core, _ = parse_version(detected)

    if old_core == new_core:
        print("Old and new versions are identical; nothing to do.", file=sys.stderr)
        return 1

    include_paths = args.include if args.include else DEFAULT_INCLUDE
    include_paths = [p for p in include_paths if (repo_root / p).exists()]

    extra_excludes = args.exclude or []
    skip_dirs = DEFAULT_SKIP_DIRS | {p.name for p in extra_excludes if p.is_dir()}
    skip_files = DEFAULT_SKIP_FILES | {p.name for p in extra_excludes if p.is_file()}

    pattern = build_pattern(old_core)
    new_with_v = f"v{new_core}"
    new_without_v = new_core

    total_replacements = 0
    files_changed = 0

    for file_path in iter_target_files(
        include_paths, repo_root, extra_excludes, skip_dirs, skip_files
    ):
        replaced = replace_versions_in_file(
            file_path, pattern, new_with_v, new_without_v, args.dry_run
        )
        if replaced:
            files_changed += 1
            total_replacements += replaced
            if args.verbose:
                print(f"{file_path}: {replaced} replacements")

    action = "Would update" if args.dry_run else "Updated"
    print(
        f"{action} {files_changed} file(s); {total_replacements} replacement(s). "
        f"{old_core} -> {new_core}"
    )

    if files_changed == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

