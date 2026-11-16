"""Reader registries, entry-point discovery and reader resolution (GE-04).

Registries are plain values created on demand: nothing is registered at import time
and there is no process-global registry or cache. Resolution order is fixed and
recorded in the returned ``DetectionDecision``:

1. a ``TableReader`` instance is used as is;
2. an id is looked up in the caller registry, then the builtin ids, then the
   ``rdetoolkit.graph.readers`` entry points (discovered only when needed);
3. ``"auto"`` selects the one reader of the caller registry or the entry points that
   claims the file suffix; two claimants are ambiguous; with no claimant the content is
   sniffed over the builtin readers (``detection.detect_table_format``) and an
   unconfident result is ambiguous rather than guessed (GE-05).
"""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Final

from rdetoolkit.graph.exceptions import (
    AmbiguousFormatError,
    DuplicateReaderError,
    GraphUserWarning,
    ReaderPluginError,
    UnknownReaderError,
)
from rdetoolkit.graph.readers.base import DetectionDecision, FormatCandidate, TableData, TableReader
from rdetoolkit.graph.readers.builtin import BUILTIN_READER_TYPES, configured_builtin_reader
from rdetoolkit.graph.readers.detection import detect_table_format, require_selection

READER_ENTRY_POINT_GROUP: Final = "rdetoolkit.graph.readers"
#: The selector for automatic selection; never a reader id.
AUTO: Final = "auto"


def _target_of(reader: object) -> str:
    kind = type(reader)
    return f"{kind.__module__}.{kind.__qualname__}"


@dataclass(frozen=True, slots=True)
class _PendingEntry:
    """An entry point not loaded yet."""

    name: str
    value: str
    load: Callable[[], object]


class ReaderRegistry:
    """An explicit, caller-owned set of table readers keyed by id.

    Entry-point readers (from ``discover_readers``) are loaded on first request.
    """

    def __init__(self, readers: Iterable[TableReader] = ()) -> None:
        """Create a registry holding ``readers``.

        Args:
            readers: Readers to register, in order.

        Raises:
            DuplicateReaderError: If two readers share an id, or an id is ``"auto"``.
            TypeError: If an item is not a ``TableReader`` instance.
            ValueError: If a reader id is empty.
        """
        self._readers: dict[str, TableReader] = {}
        self._origins: dict[str, str] = {}
        self._pending: dict[str, _PendingEntry] = {}
        for reader in readers:
            self.register(reader)

    def register(self, reader: TableReader, *, replace: bool = False) -> None:
        """Add ``reader`` under its ``reader_id``.

        Args:
            reader: The reader instance.
            replace: Replace an existing reader with the same id instead of failing.

        Raises:
            DuplicateReaderError: If the id exists and ``replace`` is false, or is ``"auto"``.
            TypeError: If ``reader`` is not a ``TableReader`` instance.
            ValueError: If the reader id is empty.
        """
        reader_id = _checked_id(reader)
        target = _target_of(reader)
        if reader_id in self and not replace:
            msg = f"Reader id {reader_id!r} is already registered by {self._origins[reader_id]}; cannot also register {target} (pass replace=True to replace it)"
            raise DuplicateReaderError(msg)
        self._pending.pop(reader_id, None)
        self._readers[reader_id] = reader
        self._origins[reader_id] = target

    def __contains__(self, reader_id: object) -> bool:
        """Return whether ``reader_id`` is registered (loaded or not)."""
        return reader_id in self._readers or reader_id in self._pending

    def get(self, reader_id: str) -> TableReader:
        """Return the reader registered as ``reader_id``, loading an entry point if needed.

        Args:
            reader_id: The id.

        Returns:
            The reader.

        Raises:
            UnknownReaderError: If no reader has this id.
            ReaderPluginError: If the entry point cannot be loaded or breaks the contract.
        """
        if reader_id in self._readers:
            return self._readers[reader_id]
        pending = self._pending.get(reader_id)
        if pending is None:
            msg = f"Unsupported CSV format: {reader_id!r}. Available readers: {list(self.ids())}"
            raise UnknownReaderError(msg)
        reader = _load_entry_point(pending)
        del self._pending[reader_id]
        self._readers[reader_id] = reader
        return reader

    def ids(self) -> tuple[str, ...]:
        """Return every registered id, sorted."""
        return tuple(sorted({*self._readers, *self._pending}))

    def origin(self, reader_id: str) -> str:
        """Describe where ``reader_id`` came from (a class path or an entry point).

        Raises:
            UnknownReaderError: If no reader has this id.
        """
        if reader_id not in self:
            msg = f"Unsupported CSV format: {reader_id!r}. Available readers: {list(self.ids())}"
            raise UnknownReaderError(msg)
        return self._origins[reader_id]

    def for_extension(self, suffix: str) -> tuple[TableReader, ...]:
        """Return the readers claiming ``suffix`` (case-insensitive), sorted by id.

        Entry points are loaded to learn their suffixes; one that cannot be loaded is
        skipped with a ``GraphUserWarning`` (it still fails when requested by id).

        Args:
            suffix: A file suffix with its dot, for example ``".instrument"``.
        """
        wanted = suffix.lower()
        claimants: list[TableReader] = []
        for reader_id in self.ids():
            reader = self._get_or_warn(reader_id)
            if wanted and reader is not None and wanted in (ext.lower() for ext in reader.extensions):
                claimants.append(reader)
        return tuple(claimants)

    def _get_or_warn(self, reader_id: str) -> TableReader | None:
        try:
            return self.get(reader_id)
        except ReaderPluginError as exc:
            warnings.warn(f"Skipping reader plugin {reader_id!r} under 'auto': {exc}", GraphUserWarning, stacklevel=3)
            return None


class _DiscoveredRegistry(ReaderRegistry):
    """A registry whose entry-point readers are listed now and loaded on first request."""

    def __init__(self, entries: Iterable[_PendingEntry]) -> None:
        super().__init__()
        for entry in entries:
            self._pending[entry.name] = entry
            self._origins[entry.name] = f"entry point {entry.name!r} = {entry.value}"


def _checked_id(reader: object) -> str:
    if inspect.isclass(reader) or not isinstance(reader, TableReader):
        msg = f"Expected a TableReader instance (reader_id, extensions, read), got {reader!r}"
        raise TypeError(msg)
    reader_id = reader.reader_id
    if not isinstance(reader_id, str) or not reader_id:
        msg = f"A TableReader needs a non-empty string reader_id, got {reader_id!r} from {_target_of(reader)}"
        raise ValueError(msg)
    if reader_id == AUTO:
        msg = f"Reader id {AUTO!r} is reserved for automatic selection ({_target_of(reader)})"
        raise DuplicateReaderError(msg)
    return reader_id


def _load_entry_point(entry: _PendingEntry) -> TableReader:
    """Load an entry point: a ``TableReader`` instance or a zero-argument factory returning one.

    A reader class is such a factory and is always called: a class with class-level
    ``reader_id`` / ``extensions`` / ``read`` passes the runtime-checkable
    ``TableReader`` check itself, so the class test must come before the protocol test.
    """
    where = f"Reader plugin {entry.name!r} ({entry.value})"
    try:
        target = entry.load()
        reader = target() if isinstance(target, type) or (callable(target) and not isinstance(target, TableReader)) else target
    except Exception as exc:
        msg = f"{where} failed to load: {exc}. Install the plugin's dependencies or remove the entry point."
        raise ReaderPluginError(msg) from exc
    if inspect.isclass(reader) or not isinstance(reader, TableReader):
        msg = f"{where} is not a TableReader instance or a zero-argument factory returning one: {reader!r}"
        raise ReaderPluginError(msg)
    if reader.reader_id != entry.name:
        msg = f"{where} provides reader_id {reader.reader_id!r}; the entry-point name must equal the reader id"
        raise ReaderPluginError(msg)
    return reader


def builtin_readers() -> ReaderRegistry:
    """Return a new registry of the builtin readers.

    Returns:
        ``"meta_block"``, ``"noheader"``, ``"standard"`` and ``"transpose"``, as fresh
        instances (no state is shared between calls).
    """
    return ReaderRegistry(reader_type() for reader_type in BUILTIN_READER_TYPES)


def _builtin_targets() -> dict[str, str]:
    return {reader_type.reader_id: f"{reader_type.__module__}.{reader_type.__qualname__}" for reader_type in BUILTIN_READER_TYPES}


def discover_readers() -> ReaderRegistry:
    """Return a new registry of the installed ``rdetoolkit.graph.readers`` entry points.

    Entry points are listed now and loaded on first request; nothing is cached between
    calls. The entry-point name is the reader id; the target is a ``TableReader``
    instance or a zero-argument callable returning one (a reader class is
    instantiated with no arguments).

    Returns:
        The registry (empty when no entry point is installed).

    Raises:
        DuplicateReaderError: If an entry point takes a builtin id or ``"auto"``, or two
            entry points share a name (both targets are named).
    """
    builtin = _builtin_targets()
    found: dict[str, str] = {}
    pending: list[_PendingEntry] = []
    entries = sorted(metadata.entry_points(group=READER_ENTRY_POINT_GROUP), key=lambda ep: (ep.name, ep.value))
    for entry_point in entries:
        name, value = str(entry_point.name), str(entry_point.value)
        _check_entry_point_name(name, value, builtin, found)
        found[name] = value
        pending.append(_PendingEntry(name=name, value=value, load=entry_point.load))
    return _DiscoveredRegistry(pending)


def _check_entry_point_name(name: str, value: str, builtin: dict[str, str], found: dict[str, str]) -> None:
    if name == AUTO:
        msg = f"Reader entry point {name!r} ({value}) uses the reserved selector id {AUTO!r}"
        raise DuplicateReaderError(msg)
    if name in builtin:
        msg = f"Reader entry point {name!r} ({value}) shadows the builtin reader {name!r} ({builtin[name]})"
        raise DuplicateReaderError(msg)
    if name in found:
        msg = f"Two reader entry points are named {name!r}: {found[name]} and {value}"
        raise DuplicateReaderError(msg)


def _forced(reader_id: str, evidence: str) -> DetectionDecision:
    return DetectionDecision(
        selected=reader_id,
        forced=True,
        candidates=(FormatCandidate(reader_id, 1.0, (evidence, "named by the caller")),),
    )


def resolve_reader(
    reader: str | TableReader,
    path: Path,
    *,
    readers: ReaderRegistry | None = None,
) -> tuple[TableReader, DetectionDecision]:
    """Select the reader for ``path`` deterministically and say why.

    Args:
        reader: A reader id, ``"auto"``, or a ``TableReader`` instance.
        path: The file (its suffix, and under ``"auto"`` without a claimant its content).
        readers: Caller registry, consulted before builtins and entry points.

    Returns:
        The reader and the decision recording the selection and its evidence.

    Raises:
        TypeError: If ``reader`` is neither a string nor a ``TableReader`` instance.
        UnknownReaderError: If the id is not registered anywhere.
        AmbiguousFormatError: Under ``"auto"``, if several readers claim the suffix, or no
            reader claims it and content detection is not confident (``.decision`` says why).
        InvalidCSVFormatError: Under ``"auto"``, if the file is empty or too large to sniff.
        DuplicateReaderError: If the installed entry points conflict (when consulted).
        ReaderPluginError: If the requested entry-point reader cannot be loaded.
    """
    if isinstance(reader, str):
        return _resolve_auto(path, readers) if reader == AUTO else _resolve_named(reader, readers)
    if inspect.isclass(reader) or not isinstance(reader, TableReader):
        msg = f"reader must be a reader id, 'auto' or a TableReader instance, got {reader!r}"
        raise TypeError(msg)
    return reader, _forced(reader.reader_id, f"instance passed by the caller: {_target_of(reader)}")


def _named_sources(readers: ReaderRegistry | None) -> Iterator[tuple[str, ReaderRegistry]]:
    """Yield the registries in precedence order; entry points are discovered only if reached."""
    if readers is not None:
        yield "caller registry", readers
    yield "builtin", builtin_readers()
    yield "entry point", discover_readers()


def _resolve_named(reader_id: str, readers: ReaderRegistry | None) -> tuple[TableReader, DetectionDecision]:
    searched: list[ReaderRegistry] = []
    for label, registry in _named_sources(readers):
        if reader_id in registry:
            return registry.get(reader_id), _forced(reader_id, f"{label}: {registry.origin(reader_id)}")
        searched.append(registry)
    available = sorted({AUTO}.union(*(registry.ids() for registry in searched)))
    msg = f"Unsupported CSV format: {reader_id!r}. Available readers: {available}"
    raise UnknownReaderError(msg)


def _claimants(suffix: str, readers: ReaderRegistry | None) -> dict[str, tuple[TableReader, str]]:
    """Readers claiming ``suffix``: caller registry first, so it wins an id shared with an entry point."""
    claimed: dict[str, tuple[TableReader, str]] = {}
    sources: list[tuple[str, ReaderRegistry]] = []
    if readers is not None:
        sources.append(("caller registry", readers))
    sources.append(("entry point", discover_readers()))
    for label, registry in sources:
        for reader in registry.for_extension(suffix):
            claimed.setdefault(reader.reader_id, (reader, f"{label}: {registry.origin(reader.reader_id)}"))
    return claimed


def _resolve_auto(path: Path, readers: ReaderRegistry | None) -> tuple[TableReader, DetectionDecision]:
    suffix = path.suffix.lower()
    claimed = _claimants(suffix, readers)
    candidates = tuple(FormatCandidate(reader_id, 1.0, (f"claims the suffix {suffix!r}", origin)) for reader_id, (_, origin) in sorted(claimed.items()))
    if len(claimed) > 1:
        decision = DetectionDecision(selected=None, forced=False, candidates=candidates)
        names = ", ".join(candidate.reader_id for candidate in candidates)
        msg = f"Ambiguous table format for {path.name!r}: readers {names} all claim the suffix {suffix!r}. Name one with --csv-format <id>, csv_format=<id> or reader=<id>.\n" + decision.explain()
        raise AmbiguousFormatError(msg, decision=decision)
    if claimed:
        ((reader_id, (reader, _)),) = claimed.items()
        return reader, DetectionDecision(selected=reader_id, forced=False, candidates=candidates)
    # No claimant: sniff the content; the builtin reader reads with the detected options.
    decision = detect_table_format(path)
    reader_id = require_selection(path, decision)
    return configured_builtin_reader(reader_id, encoding=decision.encoding, delimiter=decision.delimiter), decision


def _read_resolved(reader: TableReader, path: Path) -> TableData:
    """Read ``path`` with ``reader`` and check the result honours the contract."""
    data = reader.read(path)
    if not isinstance(data, TableData):
        msg = f"Reader {reader.reader_id!r} ({_target_of(reader)}) returned {type(data).__name__}, expected TableData"
        raise TypeError(msg)
    return data


def _load_table(
    path: str | Path,
    *,
    reader: str | TableReader = AUTO,
    readers: ReaderRegistry | None = None,
) -> tuple[TableData, DetectionDecision]:
    """Resolve the reader for ``path``, read it, and return the table with the decision.

    Args:
        path: The file.
        reader: A reader id, ``"auto"`` or a ``TableReader`` instance.
        readers: Caller registry, consulted first.

    Returns:
        The table and the decision that selected its reader.

    Raises:
        TypeError: If ``path`` is not a ``str``/``Path``, ``reader`` is invalid, or the
            reader returns something other than ``TableData``.
    """
    if not isinstance(path, (str, Path)):
        msg = f"path must be a str or pathlib.Path, got {type(path).__name__}"
        raise TypeError(msg)
    selected, decision = resolve_reader(reader, Path(path), readers=readers)
    return _read_resolved(selected, Path(path)), decision


def read_table(
    path: str | Path,
    *,
    reader: str | TableReader = AUTO,
    readers: ReaderRegistry | None = None,
) -> TableData:
    """Read one table file with a registered, named or automatically selected reader.

    Args:
        path: The file.
        reader: A reader id, ``"auto"`` (default) or a ``TableReader`` instance.
        readers: Caller registry, consulted before builtins and entry points.

    Returns:
        The table.

    Raises:
        TypeError: If ``path`` is not a ``str``/``Path``, ``reader`` is invalid, or the
            reader returns something other than ``TableData``.
        UnknownReaderError: If the id is not registered anywhere.
        AmbiguousFormatError: Under ``"auto"``, if several readers claim the suffix, or no
            reader claims it and content detection is not confident (``.decision`` says why).
        InvalidCSVFormatError: Under ``"auto"``, if the file is empty or too large to sniff.
    """
    return _load_table(path, reader=reader, readers=readers)[0]
