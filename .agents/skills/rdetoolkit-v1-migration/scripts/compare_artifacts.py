# ruff: noqa: INP001
"""Compare preserved RDE data roots without modifying either run."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def _snapshot(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        msg = f"Expected a real data directory: {root}"
        raise ValueError(msg)
    paths = sorted(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        msg = f"Symlinks require manual review: {root}"
        raise ValueError(msg)
    if not (root / "invoice/invoice.json").is_file():
        msg = f"Baseline evidence requires invoice/invoice.json: {root}"
        raise ValueError(msg)
    return {path.relative_to(root).as_posix(): _value(path, path.relative_to(root)) for path in paths if not _below_logs(path.relative_to(root))}


def _below_logs(relative: Path) -> bool:
    return bool(re.match(r"^(?:logs|divided/[0-9]{4,}/logs)/", relative.as_posix()))


def _value(path: Path, relative: Path) -> Any:
    if path.is_dir():
        return {"kind": "directory"}
    if re.fullmatch(r"(?:divided/[0-9]{4,}/)?(?:invoice/invoice\.json|meta/metadata\.json)", relative.as_posix()):
        return {"kind": "json", "value": json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))}
    return {"kind": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def compare(baseline: Path, candidate: Path) -> list[str]:
    """Return every differing artifact path, including empty directories.

    Args:
        baseline: Preserved v1 data directory with invoice evidence.
        candidate: Separate v2 run's data directory.

    Returns:
        Sorted relative paths whose existence, type, values or bytes differ.

    Raises:
        ValueError: If either root is unusable or contains symlinks.
        OSError: If an artifact cannot be read.
        json.JSONDecodeError: If an invoice or metadata file is invalid JSON.
    """
    expected, actual = _snapshot(baseline), _snapshot(candidate)
    return [name for name in sorted(expected.keys() | actual.keys()) if expected.get(name) != actual.get(name)]


def main() -> int:
    """Compare two retained runs and print machine-readable evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        differences = compare(args.baseline, args.candidate)
    except (OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"parity": False, "error": str(error)}, ensure_ascii=False) + "\n")
        return 2
    sys.stdout.write(json.dumps({"parity": not differences, "differences": differences}, ensure_ascii=False, indent=2) + "\n")
    return int(bool(differences))


if __name__ == "__main__":
    raise SystemExit(main())
