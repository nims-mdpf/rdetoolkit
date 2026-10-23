"""Observe the PUBLIC ``workflows.run`` callback entry point (Session J2 / I7).

The ``CB`` cells of the unified matrix run v1's own loop, and the ``CB-V2`` cells
run ``Runner.run(RunRequest(target=LegacyCallbackTarget(...)))``. Neither of them
exercises the thing an existing RDE structured program actually calls:
``rdetoolkit.workflows.run(custom_dataset_function=...)``. The ``CB-ENTRY`` cells
do, and this module owns their subject under test.

Why a subprocess: the public entry's failure contract is ``sys.exit(1)`` and its
inputs are the process CWD, so an in-process call would both pollute the test
session's working directory and make the exit code unobservable. The worker is
therefore the generator's own ``_generate.execute_case`` with the public entry in
place of the v1 oracle — same registered case, same callbacks, same observation
keys and extras, same ``normalize_snapshot`` rules — so the observation is
comparable field by field with the frozen snapshot of that case (Session K1).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tests.v2.contract.fixtures import _generate  # noqa: E402
from tests.v2.contract.observe import LOGS_PREFIX  # noqa: E402

#: File the worker writes its raw observation to, inside the run root.
OBSERVATION_FILENAME = ".entry_observation.json"

#: Normalized ``data/logs`` entry both v1 and the unified callback entry produce.
#: Phase J ruling #3 keeps the ``rdesys_<ts>.log`` file logger on the v1 entry
#: point, and this is the observable that proves it.
RDESYS_LOG_ENTRY = "data/logs/rdesys_<LOG_TIMESTAMP>.log"


def run_entry_worker(case_id: str, root: Path, callback: str | None = None) -> int:
    """Execute the public v1 entry point once, in this process, and observe it.

    Args:
        case_id: Registered ``_generate`` case; its configuration source and
            callback are the ones the frozen v1 observation was made with.
        root: Already-materialized run root; it becomes the process CWD, because
            the public entry resolves its data root from the CWD.
        callback: Optional ``_generate.ORACLE_CALLBACKS`` name replacing the
            case's own callback.

    Returns:
        ``0`` — the worker's own exit status says nothing about the run, whose
        exit code is recorded in the observation instead.
    """
    from rdetoolkit.workflows import run as public_run  # noqa: PLC0415

    observation = _generate.execute_case(_generate.oracle_case(case_id), root, public_run, callback=callback)
    (root / OBSERVATION_FILENAME).write_text(
        json.dumps(observation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def execute_entry_observation(case_id: str, root: Path, *, callback: str | None = None) -> dict[str, Any]:
    """Run the isolated public-entry worker against a materialized case.

    Args:
        case_id: Registered ``_generate`` case.
        root: Already-materialized run root the worker executes in.
        callback: Optional ``_generate.ORACLE_CALLBACKS`` name replacing the
            case's own callback.

    Returns:
        The normalized observation of the public entry point.

    Raises:
        RuntimeError: If the worker process produced no observation.
    """
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--entry-worker",
        case_id,
        str(root),
    ]
    if callback is not None:
        command.extend(["--callback", callback])
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    observation_path = root / OBSERVATION_FILENAME
    if completed.returncode != 0 or not observation_path.exists():
        message = (
            f"public entry worker failed for {case_id}: "
            f"exit={completed.returncode}; stderr={completed.stderr[-1000:]}"
        )
        raise RuntimeError(message)
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    return dict(_generate.normalize_snapshot(observation, roots=(root,)))


def observe_public_entry(case_id: str, root: Path, *, callback: str | None = None) -> dict[str, Any]:
    """Materialize a registered case into ``root`` and observe the public entry on it.

    The SUT-side counterpart of the generator's frozen v1 observation: same
    inputs, same configuration, same callback (unless ``callback`` names
    another), same observation keys including the case's extras.
    """
    _generate.materialize_case(_generate.oracle_case(case_id), root)
    return execute_entry_observation(case_id, root, callback=callback)


def entry_parity_view(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Project one observation onto the keys the two entry points must share.

    The single excluded region is the *content* of ``data/logs/``: v1 writes
    ``rdesys_<ts>.log`` there while the unified Runner additionally writes its
    RunReport and per-iteration details (Design §6.3 addendum, Session I6-1
    ruling #2). The directory entry itself is kept, and the ``rdesys`` log is
    asserted separately through :func:`has_rdesys_log`, so the Phase J ruling #3
    contract stays observable rather than excluded along with the rest.

    Args:
        observation: A frozen ``observed`` mapping or a live observation.

    Returns:
        A new mapping with ``output_tree`` narrowed; every other key untouched.
    """
    tree = observation["output_tree"]
    return {
        **observation,
        "output_tree": {
            "directories": [path for path in tree["directories"] if not _below_logs(path)],
            "files": [path for path in tree["files"] if not _below_logs(path)],
        },
    }


def has_rdesys_log(observation: Mapping[str, Any]) -> bool:
    """Return whether an observation recorded the v1 ``rdesys`` log file."""
    return RDESYS_LOG_ENTRY in observation["output_tree"]["files"]


def tree_entries(observation: Mapping[str, Any]) -> set[str]:
    """Return every normalized directory and file entry of one output tree."""
    tree = observation["output_tree"]
    return set(tree["directories"]) | set(tree["files"])


#: Second path component of a per-tile output directory. v1 creates all twelve
#: of them (plus ``divided/`` for tile >= 1) while building tile 0, so their
#: absence is the observable "the run stopped before any tile existed".
#: ``invoice``, ``logs`` and ``temp`` are deliberately absent: the first two are
#: input/report directories that exist either way, and ``temp`` is pre-created
#: before parsing by both versions (contracts.md §J0-3).
_TILE_OUTPUT_COMPONENTS = frozenset(
    {
        "attachment",
        "divided",
        "main_image",
        "meta",
        "nonshared_raw",
        "other_image",
        "invoice_patch",
        "raw",
        "structured",
        "thumbnail",
    },
)

#: Classification of the ``temp`` entry that is the invoice backup, not an
#: unpacked input.
_INVOICE_BACKUP_ENTRY = "data/temp/invoice_org.json"


def frontload_gap_kind(path: str) -> str | None:
    """Classify one tree entry v1 produced and the front-loaded Runner did not.

    The unified Runner rejects an invalid source invoice in ``pre_validate``,
    before tile 0 is created and before any input is unpacked, whereas v1
    validated mid-pipeline and therefore left those artifacts behind. Every
    element of the difference must fall into one of three classes; anything else
    is a real parity defect rather than "v2 failed earlier"
    (Session J2 B-ruling #2).

    Args:
        path: One normalized ``data/``-relative entry, directories keeping their
            trailing slash.

    Returns:
        ``"tile-artifact"``, ``"invoice-backup"``, ``"temp-unpack"``, or ``None``
        when the entry is none of those.
    """
    normalized = path.rstrip("/")
    parts = normalized.split("/")
    if len(parts) < 2 or parts[0] != "data":
        return None
    if parts[1] in _TILE_OUTPUT_COMPONENTS:
        return "tile-artifact"
    if parts[1] == "temp":
        return "invoice-backup" if normalized == _INVOICE_BACKUP_ENTRY else "temp-unpack"
    return None


def _below_logs(path: str) -> bool:
    return path.startswith(LOGS_PREFIX) and path != LOGS_PREFIX


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entry-worker",
        nargs=2,
        metavar=("CASE_ID", "ROOT"),
        required=True,
    )
    parser.add_argument("--callback", default=None)
    return parser.parse_args()


def main() -> int:
    """Run the isolated public-entry worker for one case."""
    args = _parse_args()
    case_id, root = args.entry_worker
    return run_entry_worker(case_id, Path(root), args.callback)


if __name__ == "__main__":
    raise SystemExit(main())
