"""Concrete output context construction for v2 domain workflows."""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.types import OutputContext, _build_output_context


def create_output_context(output_root: str | Path, *, create: bool = True) -> OutputContext:
    """Create an ``OutputContext`` using the standard RDE output layout.

    All ten canonical directories (Design §4.2) are rooted under
    ``output_root``; none may fall back to a relative default.

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

    context = _build_output_context(
        struct=root / "structured",
        meta=root / "meta",
        main_image=root / "main_image",
        other_image=root / "other_image",
        thumbnail=root / "thumbnail",
        raw=root / "raw",
        logs=root / "logs",
        attachment=root / "attachment",
        nonshared_raw=root / "nonshared_raw",
        invoice=root / "invoice",
    )
    if create:
        for path in (
            context.struct,
            context.meta,
            context.main_image,
            context.other_image,
            context.thumbnail,
            context.raw,
            context.logs,
            context.attachment,
            context.nonshared_raw,
            context.invoice,
        ):
            path.mkdir(parents=True, exist_ok=True)
    return context
