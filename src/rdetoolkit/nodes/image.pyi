from pathlib import Path
from typing import Literal

from rdetoolkit.types import OutputContext

RenderKind = Literal["main_image", "other_image", "thumbnail"]

def to_png(source_path: Path, out: OutputContext, filename: str) -> Path: ...
def to_jpeg(source_path: Path, out: OutputContext, filename: str) -> Path: ...
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
