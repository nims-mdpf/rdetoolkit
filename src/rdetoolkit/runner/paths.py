"""V2 runner output path resolution.

This module ports the directory naming rule used by v1
``workflows.generate_folder_paths_iterator`` / ``DirectoryOps``:
tile index ``0`` writes directly under ``data/{dirname}``, while tile indexes
``>= 1`` write under ``data/divided/{idx:04d}/{dirname}``. It resolves paths
only; directory creation is owned by Runner step 4a (Design §6.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TileOutputPaths:
    """Output path bundle compatible with ``OutputContext.from_resource_paths``.

    ``temp`` and ``invoice_patch`` complete the twelve directories v1 creates
    per tile (Design §6.3 addendum). They are deliberately absent from
    ``OutputContext``: the directories are part of the artifact contract, but
    the public v2 output API stays at ten fields (types.py design note).
    """

    struct: Path
    meta: Path
    main_image: Path
    other_image: Path
    thumbnail: Path
    attachment: Path
    nonshared_raw: Path
    raw: Path
    invoice: Path
    logs: Path
    temp: Path
    invoice_patch: Path


_NDIGIT = 4
_DIRNAMES = {
    "struct": "structured",
    "meta": "meta",
    "main_image": "main_image",
    "other_image": "other_image",
    "thumbnail": "thumbnail",
    "attachment": "attachment",
    "nonshared_raw": "nonshared_raw",
    "raw": "raw",
    "invoice": "invoice",
    "logs": "logs",
    "temp": "temp",
    "invoice_patch": "invoice_patch",
}


def resolve_data_root(root: Path) -> Path:
    """Resolve either a project root or an already-flat ``data`` root.

    Resolution priority is: an explicitly named ``data`` root, an existing
    nested ``data`` child, an alias-flat root identified by an RDE marker
    directory, then a bare project root's future ``data`` child.

    Args:
        root: Runner-owned project or data directory.

    Returns:
        The directory that directly owns RDE input and output subdirectories.
    """
    if root.name == "data":
        return root
    candidate = root / "data"
    if candidate.exists():
        return candidate
    markers = ("inputdata", "invoice", "tasksupport")
    if any((root / marker).is_dir() for marker in markers):
        return root
    return candidate


def resolve_tile_paths(base_dir: Path, idx: int) -> TileOutputPaths:
    """Resolve v1-compatible output directories for one tile.

    Args:
        base_dir: The ``data`` directory root.
        idx: Tile index. ``0`` uses the root tile; indexes ``>= 1`` use
            ``divided/{idx:04d}``.

    Returns:
        Path bundle exposing the twelve canonical output directory attributes.
    """
    root = base_dir if idx == 0 else base_dir / "divided" / f"{idx:0{_NDIGIT}d}"
    return TileOutputPaths(
        struct=root / _DIRNAMES["struct"],
        meta=root / _DIRNAMES["meta"],
        main_image=root / _DIRNAMES["main_image"],
        other_image=root / _DIRNAMES["other_image"],
        thumbnail=root / _DIRNAMES["thumbnail"],
        attachment=root / _DIRNAMES["attachment"],
        nonshared_raw=root / _DIRNAMES["nonshared_raw"],
        raw=root / _DIRNAMES["raw"],
        invoice=root / _DIRNAMES["invoice"],
        logs=root / _DIRNAMES["logs"],
        temp=root / _DIRNAMES["temp"],
        invoice_patch=root / _DIRNAMES["invoice_patch"],
    )
