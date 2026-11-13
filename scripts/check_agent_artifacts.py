"""Reject agent instructions inside built runtime wheels and source archives."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def _is_agent_instruction(member: str) -> bool:
    parts = PurePosixPath(member).parts
    return ".agents" in parts or "_agent" in parts


def check_artifact(path: Path) -> None:
    """Validate a wheel or sdist without extracting untrusted archive members.

    Args:
        path: Built wheel or gzipped source archive.

    Raises:
        ValueError: The archive is empty or contains agent instructions.
    """
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as wheel:
            members = wheel.namelist()
    else:
        with tarfile.open(path, "r:gz") as sdist:
            members = sdist.getnames()
    if not members:
        msg = f"Empty runtime artifact: {path}"
        raise ValueError(msg)
    forbidden = [member for member in members if _is_agent_instruction(member)]
    if forbidden:
        msg = f"Agent instructions must ship separately from {path.name}: {forbidden}"
        raise ValueError(msg)


def main() -> None:
    """Check artifacts provided by a local build or CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, nargs="*", default=[])
    parser.add_argument("--sdist", type=Path, nargs="*", default=[])
    args = parser.parse_args()
    paths = args.wheel + args.sdist
    if not paths:
        parser.error("Provide at least one --wheel or --sdist")
    for path in paths:
        check_artifact(path)
        print(f"Agent package boundary OK: {path.name}")


if __name__ == "__main__":
    main()
