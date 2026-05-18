"""Concrete output context construction for v2 domain workflows."""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.types import OutputContext


def create_output_context(output_root: str | Path, *, create: bool = True) -> OutputContext:
    """Create an ``OutputContext`` using the standard RDE output layout.

    Args:
        output_root: Root directory for output resources.
        create: Whether to create the root and child directories.

    Returns:
        Output context with v1-compatible child directory names.

    Raises:
        NotADirectoryError: If ``output_root`` already exists as a file.
    """
    root = Path(output_root)
    if root.exists() and not root.is_dir():
        msg = f"Output root is not a directory: {root}"
        raise NotADirectoryError(msg)

    context = OutputContext(
        raw=root / "raw",
        struct=root / "structured",
        main_image=root / "main_image",
        other_image=root / "other_image",
        meta=root / "meta",
        thumbnail=root / "thumbnail",
        logs=root / "logs",
    )
    if create:
        for path in (
            context.raw,
            context.struct,
            context.main_image,
            context.other_image,
            context.meta,
            context.thumbnail,
            context.logs,
        ):
            path.mkdir(parents=True, exist_ok=True)
    return context
