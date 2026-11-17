from pathlib import Path
from typing import Any, Literal

import numpy.typing as npt
from PIL import Image

from rdetoolkit.types import OutputContext, OutputKind

RenderKind = Literal["main_image", "other_image", "thumbnail"]

def to_png(source_path: Path, out: OutputContext, filename: str, *, kind: RenderKind = "other_image") -> Path: ...
def to_jpeg(source_path: Path, out: OutputContext, filename: str, *, kind: RenderKind = "other_image") -> Path: ...
def render_png(
    source_path: Path,
    out: OutputContext,
    filename: str,
    *,
    kind: RenderKind = "main_image",
    page: int = 1,
    dpi: int = 350,
) -> Path: ...
def make_thumbnail(source_path: Path, out: OutputContext, filename: str | None = None) -> Path: ...
def save_main_image(source_path: Path, out: OutputContext, filename: str) -> Path: ...
def copy_raw(source_path: Path, out: OutputContext, filename: str) -> Path: ...
def copy_file(source_path: Path, out: OutputContext, filename: str, *, kind: OutputKind) -> Path: ...
def save_image(
    image: npt.NDArray[Any] | Image.Image,
    out: OutputContext,
    filename: str,
    *,
    kind: OutputKind = "other_image",
    channel_order: Literal["rgb", "bgr"] = "rgb",
) -> Path: ...
