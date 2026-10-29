"""Pure-Python builtin nodes for image conversion and copying."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from rdetoolkit.core.node import node
from rdetoolkit.types import OutputContext

_THUMBNAIL_BOX = (640, 480)


def _encoded_image(source_path: Path, image_format: str) -> bytes:
    buffer = BytesIO()
    with Image.open(source_path) as source:
        image = source.convert("RGB") if image_format == "JPEG" else source.copy()
        image.save(buffer, format=image_format)
    return buffer.getvalue()


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def to_png(source_path: Path, out: OutputContext, filename: str) -> Path:
    """Convert an image to PNG under ``out.other_image``.

    This pure-Pillow implementation ports the format-conversion requirement
    from the v1 thumbnail pipeline without using its compiled resize path.

    Args:
        source_path: Source image.
        out: Output resource context.
        filename: Simple PNG output filename.

    Returns:
        Path to the converted PNG.
    """
    return out.write_bytes("other_image", filename, _encoded_image(Path(source_path), "PNG"))


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def to_jpeg(source_path: Path, out: OutputContext, filename: str) -> Path:
    """Convert an image to RGB JPEG under ``out.other_image``.

    This pure-Pillow implementation ports the format-conversion requirement
    from the v1 thumbnail pipeline without using its compiled resize path.

    Args:
        source_path: Source image.
        out: Output resource context.
        filename: Simple JPEG output filename.

    Returns:
        Path to the converted JPEG.
    """
    return out.write_bytes("other_image", filename, _encoded_image(Path(source_path), "JPEG"))


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def make_thumbnail(source_path: Path, out: OutputContext, filename: str | None = None) -> Path:
    """Create an aspect-preserving thumbnail within a 640×480 box.

    The bounding box matches the defaults in v1 ``img2thumb.resize_image``;
    resizing itself is implemented with Pillow for the v2 node surface.

    Args:
        source_path: Source image.
        out: Output resource context.
        filename: Optional simple output filename. Defaults to ``<stem>.png``.

    Returns:
        Path to the PNG thumbnail under ``out.thumbnail``.
    """
    source = Path(source_path)
    target_name = filename or f"{source.stem}.png"
    buffer = BytesIO()
    with Image.open(source) as image:
        thumbnail = image.copy()
        thumbnail.thumbnail(_THUMBNAIL_BOX, Image.Resampling.LANCZOS)
        thumbnail.save(buffer, format="PNG")
    return out.write_bytes("thumbnail", target_name, buffer.getvalue())


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def save_main_image(source_path: Path, out: OutputContext, filename: str) -> Path:
    """Copy image bytes to the canonical main-image directory.

    Migrated from
    ``retired/outputcontext_save_methods_v20.py::save_main_image``.

    Args:
        source_path: Source image.
        out: Output resource context.
        filename: Simple destination filename.

    Returns:
        Path to the copied main image.
    """
    return out.write_bytes("main_image", filename, Path(source_path).read_bytes())


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def copy_raw(source_path: Path, out: OutputContext, filename: str) -> Path:
    """Copy source bytes to the run-shared raw-data directory.

    Migrated from ``retired/outputcontext_save_methods_v20.py::copy_raw``.
    The ``raw`` kind is used because this operation preserves shared source
    assets; tile-local assets should be written explicitly as
    ``nonshared_raw`` through the low-level context API.

    Args:
        source_path: Source file.
        out: Output resource context.
        filename: Simple destination filename.

    Returns:
        Path to the copied raw file.
    """
    return out.write_bytes("raw", filename, Path(source_path).read_bytes())
