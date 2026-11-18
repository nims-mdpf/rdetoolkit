#!/usr/bin/env python3
"""Check that sharded CI test runs selected exactly the complete test suite.

Usage:
    python scripts/check_test_partition.py FULL_NODEIDS SHARD_NODEIDS [SHARD_NODEIDS ...]

Each file is ``pytest --collect-only -q`` output. Every shard must be non-empty,
no node ID may be selected by two shards, and the union of the shards must
equal the complete collection.

Node IDs are compared exactly. The only exception is a test function listed in
``UNSTABLE_PARAMETRIZATION``, whose parametrization text is not reproducible
between two collections (``drawing.SVGZ`` embeds gzip bytes, which contain a
timestamp). For those functions alone, a missing and an extra ID are accepted
when they name the same function the same number of times. Any other
difference, including a same-count substitution in an ordinary parametrized
function, fails.

Exit code 0 = exact partition, 1 = missing, extra, duplicate or empty selection.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


UNSTABLE_PARAMETRIZATION = frozenset(
    {
        "tests/v2/nodes/test_issue_627_render_png.py::TestSvg::test_svg_is_rasterized_at_its_own_size",
    },
)


def read_nodeids(path: Path) -> list[str]:
    """Return the node IDs in a ``pytest --collect-only -q`` listing.

    Args:
        path: The collection listing.

    Returns:
        The node IDs in collection order, without the summary lines.
    """
    return [line for line in path.read_text(encoding="utf-8").splitlines() if "::" in line]


def _function(nodeid: str) -> str:
    return nodeid.split("[", 1)[0]


def check(full: list[str], shards: dict[str, list[str]]) -> list[str]:
    """Compare the shard selections with the complete collection.

    Args:
        full: Node IDs of the complete collection.
        shards: Node IDs selected by each shard, keyed by the listing name.

    Returns:
        The problems found; empty when the shards partition the suite exactly.
    """
    problems = [f"{name}: no tests selected" for name, ids in shards.items() if not ids]
    if not full:
        problems.append("complete collection: no tests selected")
    owners: dict[str, str] = {}
    for name, ids in shards.items():
        for nodeid, count in Counter(ids).items():
            if nodeid in owners or count > 1:
                problems.append(f"selected more than once: {nodeid} ({owners.get(nodeid, name)}, {name})")
            owners.setdefault(nodeid, name)
    selected = Counter(nodeid for ids in shards.values() for nodeid in ids)
    expected = Counter(full)
    missing = expected - selected
    extra = selected - expected
    for function in sorted({_function(nodeid) for nodeid in missing + extra} & UNSTABLE_PARAMETRIZATION):
        drift_missing = Counter({nodeid: n for nodeid, n in missing.items() if _function(nodeid) == function})
        drift_extra = Counter({nodeid: n for nodeid, n in extra.items() if _function(nodeid) == function})
        if sum(drift_missing.values()) == sum(drift_extra.values()):
            missing -= drift_missing
            extra -= drift_extra
            print(f"Accepted non-reproducible parametrization text in: {function}")
    problems += [f"missing from every shard: {nodeid}" for nodeid in sorted(missing)]
    problems += [f"not in the complete collection: {nodeid}" for nodeid in sorted(extra)]
    return problems


def main(argv: list[str]) -> int:
    """Run the partition check on collection listings.

    Args:
        argv: The complete listing followed by one listing per shard.

    Returns:
        The process exit code.
    """
    if len(argv) < 3:  # noqa: PLR2004
        print(__doc__)
        return 1
    full = read_nodeids(Path(argv[1]))
    shards = {name: read_nodeids(Path(name)) for name in argv[2:]}
    problems = check(full, shards)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        return 1
    print(f"{len(full)} tests: {', '.join(f'{name}={len(ids)}' for name, ids in shards.items())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
