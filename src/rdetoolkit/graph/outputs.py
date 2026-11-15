"""Artifact destinations for the spec API (``render_graph``).

A sink maps an artifact role and file name to a destination. ``resolve`` has no side
effects, so the engine can check every destination before anything is rendered;
``write`` stores the bytes. The legacy facade keeps writing through ``FileWriter``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from rdetoolkit.graph.exceptions import OutputPathError
from rdetoolkit.graph.result import ArtifactRole


def _check_filename(filename: str) -> None:
    """Reject a name that is empty or could address another directory (legacy wording)."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        msg = f"Invalid filename {filename!r}: contains path separators or '..' sequence"
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
        directory = self.directory_for(role).resolve()
        if directory.exists() and not directory.is_dir():
            msg = f"Output path is not a directory: {directory}"
            raise OutputPathError(msg)
        target = directory / filename
        if not target.resolve().is_relative_to(directory):
            msg = f"Security violation: {filename!r} would write outside output directory"
            raise OutputPathError(msg)
        return target

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
