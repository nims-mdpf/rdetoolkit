"""Pure-Python builtin nodes for image conversion and copying."""

from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from PIL import Image

from rdetoolkit.core.node import node
from rdetoolkit.types import OutputContext, OutputKind

_THUMBNAIL_BOX = (640, 480)

RenderKind = Literal["main_image", "other_image", "thumbnail"]
_RENDER_KINDS: frozenset[str] = frozenset(("main_image", "other_image", "thumbnail"))
_PDF_SUFFIXES: frozenset[str] = frozenset((".pdf",))
_SVG_SUFFIXES: frozenset[str] = frozenset((".svg", ".svgz"))
_PDF_POINTS_PER_INCH = 72
_RENDER_EXTRA_HINT = "pip install 'rdetoolkit[render]'"
_CHANNEL_ORDERS: frozenset[str] = frozenset(("rgb", "bgr"))
_COLOUR_CHANNELS = (3, 4)


def _check_image_kind(kind: str) -> None:
    if kind not in _RENDER_KINDS:
        msg = f"kind must be one of {sorted(_RENDER_KINDS)}, got {kind!r}"
        raise ValueError(msg)


def _encoded_image(source_path: Path, image_format: str) -> bytes:
    buffer = BytesIO()
    with Image.open(source_path) as source:
        image = source.convert("RGB") if image_format == "JPEG" else source.copy()
        image.save(buffer, format=image_format)
    return buffer.getvalue()


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def to_png(source_path: Path, out: OutputContext, filename: str, *, kind: RenderKind = "other_image") -> Path:
    """Convert an image to PNG, by default under ``out.other_image``.

    This pure-Pillow implementation ports the format-conversion requirement
    from the v1 thumbnail pipeline without using its compiled resize path.
    Pass ``kind="main_image"`` to make, for example, a TIFF upload the
    representative image.

    Args:
        source_path: Source image.
        out: Output resource context.
        filename: Simple PNG output filename.
        kind: Output directory: ``other_image`` (default), ``main_image``, or
            ``thumbnail``.

    Returns:
        Path to the converted PNG.

    Raises:
        ValueError: If ``kind`` is not an image directory.
    """
    _check_image_kind(kind)
    return out.write_bytes(kind, filename, _encoded_image(Path(source_path), "PNG"))


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def to_jpeg(source_path: Path, out: OutputContext, filename: str, *, kind: RenderKind = "other_image") -> Path:
    """Convert an image to RGB JPEG, by default under ``out.other_image``.

    This pure-Pillow implementation ports the format-conversion requirement
    from the v1 thumbnail pipeline without using its compiled resize path.
    Pass ``kind="main_image"`` to make, for example, a TIFF upload the
    representative image.

    Args:
        source_path: Source image.
        out: Output resource context.
        filename: Simple JPEG output filename.
        kind: Output directory: ``other_image`` (default), ``main_image``, or
            ``thumbnail``.

    Returns:
        Path to the converted JPEG.

    Raises:
        ValueError: If ``kind`` is not an image directory.
    """
    _check_image_kind(kind)
    return out.write_bytes(kind, filename, _encoded_image(Path(source_path), "JPEG"))


def _import_pdfium() -> Any:
    try:
        import pypdfium2  # noqa: PLC0415 -- optional backend (rdetoolkit[render])
    except ImportError as exc:
        msg = f"render_png needs pypdfium2 to render PDF files. Install it with: {_RENDER_EXTRA_HINT}"
        raise ImportError(msg) from exc
    return pypdfium2


def _import_cairosvg() -> Any:
    try:
        import cairosvg  # noqa: PLC0415 -- optional backend (rdetoolkit[render])
    except ImportError as exc:
        msg = f"render_png needs cairosvg to render SVG files. Install it with: {_RENDER_EXTRA_HINT}"
        raise ImportError(msg) from exc
    except OSError as exc:
        # cairocffi raises OSError when the native Cairo library is absent.
        msg = f"render_png needs the Cairo system library to render SVG files (for example `apt install libcairo2` or `brew install cairo`). cairosvg is installed with: {_RENDER_EXTRA_HINT}"
        raise ImportError(msg) from exc
    return cairosvg


def _render_pdf_page(source_path: Path, page: int, dpi: int) -> bytes:
    pdfium = _import_pdfium()
    document = pdfium.PdfDocument(source_path)
    try:
        # Without a form environment PDFium skips form fields, so a filled
        # AcroForm would render blank. It must be set up before any page loads.
        document.init_forms()
        page_count = len(document)
        if not 1 <= page <= page_count:
            msg = f"page must be between 1 and {page_count} for {source_path.name}, got {page}"
            raise ValueError(msg)
        pdf_page = document[page - 1]
        try:
            image = pdf_page.render(scale=dpi / _PDF_POINTS_PER_INCH).to_pil()
        finally:
            pdf_page.close()
    finally:
        document.close()
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _render_svg(source_path: Path) -> bytes:
    cairosvg = _import_cairosvg()
    # Pass the bytes, not ``url=``: cairosvg parses a URL, so ``#`` or ``%xx``
    # in a local filename would change the path it opens. No base URL is lost,
    # because cairosvg >= 2.7 fetches only data: URLs unless ``unsafe=True``.
    png: bytes = cairosvg.svg2png(bytestring=source_path.read_bytes())
    return png


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def render_png(
    source_path: Path,
    out: OutputContext,
    filename: str,
    *,
    kind: RenderKind = "main_image",
    page: int = 1,
    dpi: int = 350,
) -> Path:
    """Render an image, a PDF page, or an SVG drawing to PNG.

    The file type is chosen by suffix: ``.pdf`` renders one page with
    pypdfium2 at ``dpi``; ``.svg`` / ``.svgz`` is rasterized with cairosvg at
    its own size; any other file is converted like ``to_png``. PDF and SVG
    need the optional ``render`` extra (``pip install 'rdetoolkit[render]'``);
    SVG also needs the Cairo system library. ``page`` and ``dpi`` apply to PDF
    input only. The defaults (page 1, 350 dpi) match the v1
    simple-registration template.

    Args:
        source_path: Source image, PDF, or SVG file.
        out: Output resource context.
        filename: Simple PNG output filename.
        kind: Output directory: ``main_image`` (default), ``other_image``, or
            ``thumbnail``.
        page: 1-based PDF page number.
        dpi: PDF rendering resolution in dots per inch.

    Returns:
        Path to the rendered PNG.

    Raises:
        ImportError: If the PDF or SVG backend is not installed.
        ValueError: If ``kind``, ``page`` or ``dpi`` is invalid.
    """
    _check_image_kind(kind)
    if dpi <= 0:
        msg = f"dpi must be positive, got {dpi}"
        raise ValueError(msg)
    if page < 1:
        msg = f"page must be 1 or greater, got {page}"
        raise ValueError(msg)
    source = Path(source_path)
    suffix = source.suffix.lower()
    if suffix in _PDF_SUFFIXES:
        content = _render_pdf_page(source, page, dpi)
    elif suffix in _SVG_SUFFIXES:
        content = _render_svg(source)
    else:
        content = _encoded_image(source, "PNG")
    return out.write_bytes(kind, filename, content)


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


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def copy_file(source_path: Path, out: OutputContext, filename: str, *, kind: OutputKind) -> Path:
    """Copy a file byte for byte into any output directory.

    Use this for images and attachments that are registered unchanged, for
    example an uploaded PNG copied to ``other_image`` or a converter result
    copied to ``struct``. Only the bytes are copied, as by
    ``shutil.copyfile``; permissions and timestamps are not.

    Args:
        source_path: Source file.
        out: Output resource context.
        filename: Simple destination filename.
        kind: Output directory, such as ``other_image``, ``struct``,
            ``thumbnail`` or ``attachment``.

    Returns:
        Path to the copy.

    Raises:
        ValueError: If ``kind`` is unknown or ``filename`` is not a simple
            filename. Nothing is copied.
        FileNotFoundError: If ``source_path`` does not exist.
        shutil.SameFileError: If the destination is the source file itself.
    """
    destination = out.path_for(kind, filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(source_path), destination)
    return destination


def _image_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    image_format = Image.registered_extensions().get(suffix)
    if image_format is None:
        msg = f"save_image cannot infer an image format from the suffix of {filename!r}; use a suffix such as .png, .jpg or .tif"
        raise ValueError(msg)
    return image_format


def _as_pillow_image(image: npt.NDArray[Any] | Image.Image, channel_order: str) -> Image.Image:
    if isinstance(image, Image.Image):
        return image
    array = np.asarray(image)
    if channel_order == "bgr" and array.ndim == 3 and array.shape[2] in _COLOUR_CHANNELS:  # noqa: PLR2004
        # OpenCV stores colour as BGR or BGRA; Pillow expects RGB or RGBA.
        array = array[..., [2, 1, 0, *range(3, array.shape[2])]]
    return Image.fromarray(np.ascontiguousarray(array))


@node(tags=["builtin", "image"], version="2.0.0", idempotent=True)
def save_image(
    image: npt.NDArray[Any] | Image.Image,
    out: OutputContext,
    filename: str,
    *,
    kind: OutputKind = "other_image",
    channel_order: Literal["rgb", "bgr"] = "rgb",
) -> Path:
    """Save an in-memory image, such as an analysis overlay or a mask.

    ``image`` is a Pillow image or a NumPy array as accepted by
    ``PIL.Image.fromarray``: ``(H, W)`` grayscale, or ``(H, W, 3)`` /
    ``(H, W, 4)`` colour, usually ``uint8``; a ``bool`` mask is saved as a
    1-bit image. Arrays from OpenCV (``cv2.imread``, ``cv2.cvtColor``) are BGR
    or BGRA: pass ``channel_order="bgr"`` and they are written like
    ``cv2.imwrite``. The file format follows the filename suffix
    (``.png``, ``.jpg``, ``.tif``, ...). The input is not modified.

    Args:
        image: Image to save.
        out: Output resource context.
        filename: Simple output filename whose suffix selects the format.
        kind: Output directory, ``other_image`` by default.
        channel_order: Channel order of a colour array, ``"rgb"`` or
            ``"bgr"``. Ignored for grayscale arrays and Pillow images.

    Returns:
        Path to the saved image.

    Raises:
        ValueError: If ``kind``, ``channel_order`` or the filename suffix is
            invalid. Nothing is written.
        TypeError: If Pillow cannot interpret the array's shape or dtype.
        OSError: If the format cannot store the image mode, for example
            RGBA as JPEG.
    """
    if channel_order not in _CHANNEL_ORDERS:
        msg = f"channel_order must be one of {sorted(_CHANNEL_ORDERS)}, got {channel_order!r}"
        raise ValueError(msg)
    out.path_for(kind, filename)
    image_format = _image_format(filename)
    buffer = BytesIO()
    _as_pillow_image(image, channel_order).save(buffer, format=image_format)
    return out.write_bytes(kind, filename, buffer.getvalue())
