"""Artifact destinations for the spec API (``render_graph``).

A sink maps an artifact role and file name to a destination. ``resolve`` has no side
effects, so the engine can check every destination before anything is rendered;
``write`` stores the bytes. ``DirectorySink`` writes into plain directories,
``OutputContextSink`` into the directories of an RDE ``OutputContext``. Both decide
containment with the same path-aware rule as the legacy ``PathValidator``; the legacy
facade keeps writing through ``FileWriter``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Protocol, get_args, runtime_checkable

from rdetoolkit.graph.exceptions import OutputPathError, PlotRequestError
from rdetoolkit.graph.io.path_validator import PathValidator
from rdetoolkit.graph.result import ArtifactRole
from rdetoolkit.graph.spec import INVALID_SPEC
from rdetoolkit.types import OutputContext, OutputKind

_ROLES: Final[tuple[str, ...]] = get_args(ArtifactRole)
_OUTPUT_KINDS: Final[frozenset[str]] = frozenset(get_args(OutputKind))
_DEFAULT_KINDS: Final[Mapping[ArtifactRole, OutputKind]] = MappingProxyType(
    {"main_image": "main_image", "individual": "other_image", "html": "struct"},
)


def _check_filename(filename: str) -> None:
    """Reject a name that is empty or could address another directory (legacy wording)."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        msg = f"Invalid filename {filename!r}: contains path separators or '..' sequence"
        raise OutputPathError(msg)


def _check_destination(directory: Path, filename: str) -> None:
    """Fail unless ``directory/filename`` is usable and stays inside ``directory``.

    The containment rule is the legacy ``PathValidator``'s (path components, not a
    string prefix), so the spec API and the legacy facade accept the same names.
    The directory need not exist yet, but its nearest existing ancestor must be a
    directory, and the destination must not be an existing directory: both would
    otherwise fail only while writing, after earlier artifacts were written.
    """
    resolved = directory.resolve()
    existing = next(path for path in (resolved, *resolved.parents) if path.exists())
    if not existing.is_dir():
        msg = f"Output path is not a directory: {existing}"
        raise OutputPathError(msg)
    try:
        target = PathValidator().resolve_within(resolved, filename)
    except ValueError as exc:
        raise OutputPathError(str(exc)) from None
    if target.is_dir():
        msg = f"Artifact destination is an existing directory: {target}"
        raise OutputPathError(msg)


@runtime_checkable
class ArtifactSink(Protocol):
    """Destination of rendered artifacts."""

    def resolve(self, role: ArtifactRole, filename: str) -> Path:
        """Return the destination of an artifact without touching the filesystem.

        Args:
            role: ``"main_image"``, ``"individual"`` or ``"html"``.
            filename: File name without directory.

        Returns:
            The destination path.

        Raises:
            OutputPathError: If the destination is unsafe or unusable.
        """
        ...

    def write(self, role: ArtifactRole, filename: str, content: bytes) -> Path:
        """Store the artifact bytes and return where they went.

        Args:
            role: ``"main_image"``, ``"individual"`` or ``"html"``.
            filename: File name without directory.
            content: Artifact bytes.

        Returns:
            The written path.
        """
        ...


@dataclass(frozen=True, slots=True)
class DirectorySink:
    """Write artifacts into plain directories, routed by role like the legacy facade.

    Overlay images go to ``main_image_dir``, individual images to ``output_dir`` and
    HTML to ``html_dir``; an unset directory falls back to ``output_dir``.

    Attributes:
        output_dir: Default directory (individual figures).
        main_image_dir: Directory of overlay images (``None`` = ``output_dir``).
        html_dir: Directory of HTML artifacts (``None`` = ``output_dir``).
    """

    output_dir: Path
    main_image_dir: Path | None = None
    html_dir: Path | None = None

    def __post_init__(self) -> None:
        """Accept ``str`` directories by converting them to ``Path``."""
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        for name in ("main_image_dir", "html_dir"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, Path(value))

    def directory_for(self, role: ArtifactRole) -> Path:
        """Return the directory an artifact of ``role`` is written to.

        Args:
            role: Artifact role.

        Returns:
            The directory (not resolved, not created).
        """
        if role == "main_image" and self.main_image_dir is not None:
            return self.main_image_dir
        if role == "html" and self.html_dir is not None:
            return self.html_dir
        return self.output_dir

    def resolve(self, role: ArtifactRole, filename: str) -> Path:
        """Return the destination of an artifact without creating anything.

        Args:
            role: Artifact role.
            filename: File name without directory.

        Returns:
            The destination path inside the role's directory.

        Raises:
            OutputPathError: If the name is empty or contains a separator or ``..``,
                if the directory exists but is not a directory, or if the
                destination (for example through a symlink) leaves the directory.
        """
        _check_filename(filename)
        _check_destination(self.directory_for(role), filename)
        return self.directory_for(role).resolve() / filename

    def write(self, role: ArtifactRole, filename: str, content: bytes) -> Path:
        """Create the role's directory if needed and write the bytes.

        Args:
            role: Artifact role.
            filename: File name without directory.
            content: Artifact bytes.

        Returns:
            The written path.
        """
        target = self.resolve(role, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target


def _default_kinds() -> Mapping[ArtifactRole, OutputKind]:
    return MappingProxyType(dict(_DEFAULT_KINDS))


@dataclass(frozen=True, slots=True)
class OutputContextSink:
    """Write artifacts into the directories of an RDE ``OutputContext``.

    Writing goes through ``OutputContext.write_bytes``, so artifact ownership and its
    basename rule are those of every other node output. The default routing puts
    overlay images into ``main_image``, individual images into ``other_image`` and
    HTML into ``struct`` (the legacy csv2graph destinations inside an RDE tree).

    Attributes:
        out: The output context.
        kinds: ``OutputContext`` kind per artifact role; must name exactly the roles
            ``main_image``, ``individual`` and ``html``.
    """

    out: OutputContext
    kinds: Mapping[ArtifactRole, OutputKind] = field(default_factory=_default_kinds)

    def __post_init__(self) -> None:
        """Validate the context and freeze the role mapping.

        Raises:
            TypeError: If ``out`` is not an ``OutputContext``.
            PlotRequestError: ``reason="invalid_spec"`` if ``kinds`` is not a mapping,
                does not name exactly the three roles, or names an unknown kind.
        """
        if not isinstance(self.out, OutputContext):
            msg = f"out must be an OutputContext, got {type(self.out).__name__}"
            raise TypeError(msg)
        if not isinstance(self.kinds, Mapping):
            msg = f"kinds must be a mapping of artifact role to OutputContext kind, got {type(self.kinds).__name__}"
            raise PlotRequestError(msg, reason=INVALID_SPEC)
        _check_kinds(self.kinds)
        object.__setattr__(self, "kinds", MappingProxyType(dict(self.kinds)))

    def resolve(self, role: ArtifactRole, filename: str) -> Path:
        """Return the destination of an artifact without creating anything.

        Args:
            role: Artifact role.
            filename: File name without directory.

        Returns:
            The destination path inside the role's ``OutputContext`` directory.

        Raises:
            OutputPathError: If the name is empty or contains a separator or ``..``,
                if the directory exists but is not a directory, or if the
                destination (for example through a symlink) leaves the directory.
        """
        _check_filename(filename)
        try:
            target = self.out.path_for(self.kinds[role], filename)
        except ValueError as exc:
            raise OutputPathError(str(exc)) from exc
        _check_destination(target.parent, filename)
        return target

    def write(self, role: ArtifactRole, filename: str, content: bytes) -> Path:
        """Write the bytes through ``OutputContext.write_bytes``.

        Args:
            role: Artifact role.
            filename: File name without directory.
            content: Artifact bytes.

        Returns:
            The written path.
        """
        self.resolve(role, filename)
        return self.out.write_bytes(self.kinds[role], filename, content)


def _check_kinds(kinds: Mapping[Any, Any]) -> None:
    """The mapping must route every role, and only roles, to a known OutputContext kind."""
    if set(kinds) != set(_ROLES):
        msg = f"kinds must map exactly the artifact roles {list(_ROLES)}, got {sorted(map(str, kinds))}"
        raise PlotRequestError(msg, reason=INVALID_SPEC)
    unknown = sorted(str(kind) for kind in kinds.values() if kind not in _OUTPUT_KINDS)
    if unknown:
        msg = f"Unknown OutputContext kind(s) {unknown}; expected one of {sorted(_OUTPUT_KINDS)}"
        raise PlotRequestError(msg, reason=INVALID_SPEC)
