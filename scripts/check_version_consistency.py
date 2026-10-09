#!/usr/bin/env python3
"""Check that every version declaration in this repository agrees.

Compared sources:
  * pyproject.toml  ``[project].version``  — maturin stamps the wheel/sdist with this
  * src/rdetoolkit/__init__.py  ``__version__``
  * (optional) a git tag passed via ``--tag``, e.g. ``--tag v2.0.0a1``

Every value must be written in canonical PEP 440 form (``2.0.0a1``, not
``2.0.0.a1`` / ``2.0.0-alpha1``) so that the tag name, the strings in the
sources, and the artifact filenames on PyPI are byte-identical.

Usage:
    python scripts/check_version_consistency.py                # sources only
    python scripts/check_version_consistency.py --tag v2.0.0a1 # before tagging

Exit code 0 = consistent, 1 = mismatch or malformed version.
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGE_INIT = REPO_ROOT / "src" / "rdetoolkit" / "__init__.py"

# Canonical-form regex from the PEP 440 appendix ("Appendix B: canonical form").
CANONICAL_PEP440 = re.compile(
    r"^([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*"
    r"((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?(\.dev(0|[1-9][0-9]*))?$",
)


def read_pyproject_version() -> str:
    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str):
        msg = f"{PYPROJECT}: [project].version is missing"
        raise SystemExit(msg)
    return version


def read_package_version() -> str:
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', PACKAGE_INIT.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        msg = f"{PACKAGE_INIT}: __version__ assignment not found"
        raise SystemExit(msg)
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        help="git tag to verify against the sources (must be 'v' + version, e.g. v2.0.0a1)",
    )
    args = parser.parse_args()

    versions: dict[str, str] = {
        "pyproject.toml [project].version": read_pyproject_version(),
        "src/rdetoolkit/__init__.py __version__": read_package_version(),
    }
    if args.tag is not None:
        if not args.tag.startswith("v"):
            print(f"ERROR: tag '{args.tag}' must start with 'v' (expected form: v2.0.0a1)")
            return 1
        versions[f"git tag {args.tag}"] = args.tag[1:]

    errors: list[str] = []
    for source, value in versions.items():
        if not CANONICAL_PEP440.match(value):
            errors.append(
                f"{source}: '{value}' is not a canonical PEP 440 version "
                "(write pre-releases as 2.0.0a1 / 2.0.0b1 / 2.0.0rc1 — no dot or dash before the suffix)",
            )

    if len(set(versions.values())) > 1:
        listing = "\n".join(f"  {source}: {value}" for source, value in versions.items())
        errors.append(f"version mismatch:\n{listing}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"OK: all version declarations agree: {versions['pyproject.toml [project].version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
