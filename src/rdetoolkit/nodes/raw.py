"""Builtin nodes that edit the Runner's raw / nonshared_raw copies of inputs.

Before a flow runs, the Runner copies the tile's input files into ``raw/``
when ``system.save_raw`` is on and into ``nonshared_raw/`` when
``system.save_nonshared_raw`` is on, as the v1 pipeline did before the
dataset callback. These nodes remove or replace such a copy from inside the
flow, so the change shows in the call log, and touch only the enabled kinds.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from rdetoolkit.core.node import node
from rdetoolkit.types import OutputContext, OutputKind, RdeConfig


def _enabled_raw_kinds(config: RdeConfig) -> tuple[OutputKind, ...]:
    kinds: list[OutputKind] = []
    if config.system.save_raw:
        kinds.append("raw")
    if config.system.save_nonshared_raw:
        kinds.append("nonshared_raw")
    return tuple(kinds)


def _existing_copies(out: OutputContext, config: RdeConfig, filename: str) -> list[Path]:
    copies = [out.path_for(kind, filename) for kind in _enabled_raw_kinds(config)]
    missing = [str(path) for path in copies if not (path.exists() or path.is_symlink())]
    if missing:
        msg = f"No raw copy of {filename!r} to remove: {', '.join(missing)}"
        raise FileNotFoundError(msg)
    return copies


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _unique_members(members: Sequence[Path]) -> list[Path]:
    unique: list[Path] = []
    names: dict[str, Path] = {}
    for member in members:
        source = Path(member)
        if not source.exists():
            msg = f"Member to copy into the raw directories does not exist: {source}"
            raise FileNotFoundError(msg)
        previous = names.get(source.name)
        if previous is None:
            names[source.name] = source
            unique.append(source)
        elif previous.resolve() != source.resolve():
            msg = f"Members {previous} and {source} have the same name {source.name!r}; raw copies are stored by name"
            raise ValueError(msg)
    return unique


def _reject_sources_inside_copies(sources: list[Path], copies: list[Path]) -> None:
    """Reject members that the replacement itself would delete before reading them."""
    resolved_copies = [copy.resolve() for copy in copies]
    for source in sources:
        resolved = source.resolve()
        for copy in resolved_copies:
            if resolved == copy or resolved.is_relative_to(copy):
                msg = f"Member {source} is the raw copy being replaced or inside it; extract or copy it elsewhere first"
                raise ValueError(msg)


@node(tags=["builtin", "raw"], version="2.0.0")
def remove_raw_copy(out: OutputContext, config: RdeConfig, filename: str) -> list[Path]:
    """Remove the Runner's copy of an input from the enabled raw directories.

    The Runner copies the tile's inputs into ``raw/`` (``system.save_raw``)
    and ``nonshared_raw/`` (``system.save_nonshared_raw``) before the flow
    runs. Use this node when an input becomes another artifact, for example
    an uploaded ``*_meta.json`` saved as ``meta/metadata.json``, and must not
    be stored as raw data. A disabled kind is not touched. A directory copy is
    removed with its contents.

    Args:
        out: Output resource context of the tile.
        config: Run configuration that selects the enabled raw kinds.
        filename: Simple filename of the copy, the input's own name.

    Returns:
        The removed paths, ``raw`` before ``nonshared_raw``. Empty when both
        kinds are disabled.

    Raises:
        ValueError: If ``filename`` is not a simple filename.
        FileNotFoundError: If an enabled kind has no copy named ``filename``.
            Nothing is removed.
    """
    copies = _existing_copies(out, config, filename)
    for path in copies:
        _remove(path)
    return copies


@node(tags=["builtin", "raw"], version="2.0.0")
def replace_raw_copy(
    out: OutputContext,
    config: RdeConfig,
    filename: str,
    members: Sequence[Path],
) -> list[Path]:
    """Replace the Runner's copy of an input with other files.

    Use this node when the stored raw data is the content of an uploaded
    archive rather than the archive itself::

        members = unzip_inputs(archive, Path(tmp))
        replace_raw_copy(out, config, archive.name, members)

    In each enabled raw directory (see :func:`remove_raw_copy`) every member
    is copied by its name, as the Runner copies inputs (file metadata kept,
    directories with their contents), and the copy named ``filename`` is then
    removed. A member named ``filename`` replaces that copy in place. Archive
    subdirectories are not kept; pass a directory member to keep a tree.

    Args:
        out: Output resource context of the tile.
        config: Run configuration that selects the enabled raw kinds.
        filename: Simple filename of the copy to replace.
        members: Files or directories to store instead. A path given more
            than once is copied once.

    Returns:
        The copied member paths, all members for ``raw`` before those for
        ``nonshared_raw``. Empty when both kinds are disabled.

    Raises:
        ValueError: If ``filename`` is not a simple filename, two
            different members have the same name, or a member is one of the
            copies being replaced or lies inside one.
        FileNotFoundError: If an enabled kind has no copy named ``filename``
            or a member does not exist.
        FileExistsError: If a member would overwrite another file in a raw
            directory.

        No file is copied or removed when one of these is raised. With
        both kinds disabled nothing is checked, ``members`` included, and
        ``[]`` is returned.
    """
    copies = _existing_copies(out, config, filename)
    if not copies:
        return []
    sources = _unique_members(members)
    _reject_sources_inside_copies(sources, copies)
    for copy in copies:
        for source in sources:
            target = copy.parent / source.name
            if source.name != filename and (target.exists() or target.is_symlink()):
                msg = f"Member {source.name!r} would overwrite an existing raw file: {target}"
                raise FileExistsError(msg)
    copied: list[Path] = []
    for copy in copies:
        for source in sources:
            target = copy.parent / source.name
            if target == copy:
                _remove(copy)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
            copied.append(target)
        if copy not in copied:
            _remove(copy)
    return copied
