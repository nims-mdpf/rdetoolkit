"""Issue #627: ``render_png`` renders images, PDF pages and SVG drawings to PNG.

PDF and SVG need the optional ``render`` extra (pypdfium2, cairosvg) and,
for SVG, the Cairo system library. Tests that need a backend skip when it is
absent; the missing-backend messages are tested without the backends.
"""

from __future__ import annotations

import builtins
import gzip
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from rdetoolkit.types import OutputContext
from tests.v2.nodes.conftest import FIXTURES_DIR

_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="#00ff00"/></svg>'


def _cairo_available() -> bool:
    try:
        import cairosvg  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


needs_pdfium = pytest.mark.skipif(
    importlib.util.find_spec("pypdfium2") is None,
    reason="pypdfium2 (rdetoolkit[render]) is not installed",
)
needs_cairo = pytest.mark.skipif(not _cairo_available(), reason="cairosvg or the Cairo library is not installed")


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    """A 2 x 1 inch PDF: page 1 is red, page 2 is blue."""
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.figure import Figure

    path = tmp_path / "two_pages.pdf"
    with PdfPages(path) as pdf:
        for color in ("red", "blue"):
            figure = Figure(figsize=(2, 1))
            figure.patch.set_facecolor(color)
            pdf.savefig(figure)
    return path


def _png(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image.load()
        assert image.format == "PNG"
        return image.convert("RGB")


@needs_pdfium
class TestPdf:
    def test_defaults_render_page_one_at_350_dpi_into_main_image(self, two_page_pdf: Path, output_context: OutputContext) -> None:
        """Defaults render PDF page 1 at 350 dpi into main_image."""
        from rdetoolkit.nodes import render_png

        result = render_png(two_page_pdf, output_context, "main.png")

        assert result == output_context.main_image / "main.png"
        image = _png(result)
        assert image.size == (700, 350)
        assert image.getpixel((5, 5)) == (255, 0, 0)

    def test_page_dpi_and_kind_select_page_resolution_and_directory(self, two_page_pdf: Path, output_context: OutputContext) -> None:
        """page, dpi and kind select the page, the size and the directory."""
        from rdetoolkit.nodes import render_png

        result = render_png(two_page_pdf, output_context, "page2.png", kind="other_image", page=2, dpi=72)

        assert result.parent == output_context.other_image
        image = _png(result)
        assert image.size == (144, 72)
        assert image.getpixel((5, 5)) == (0, 0, 255)

    def test_uppercase_suffix_is_rendered_as_pdf(self, two_page_pdf: Path, output_context: OutputContext) -> None:
        """The suffix check ignores case."""
        from rdetoolkit.nodes import render_png

        upper = two_page_pdf.with_name("UPPER.PDF")
        upper.write_bytes(two_page_pdf.read_bytes())

        result = render_png(upper, output_context, "upper.png", kind="thumbnail", dpi=36)

        assert result.parent == output_context.thumbnail
        assert _png(result).size == (72, 36)

    def test_page_beyond_the_document_raises(self, two_page_pdf: Path, output_context: OutputContext) -> None:
        """A page past the last one raises ValueError and writes nothing."""
        from rdetoolkit.nodes import render_png

        with pytest.raises(ValueError, match="between 1 and 2"):
            render_png(two_page_pdf, output_context, "missing.png", page=3)
        assert not (output_context.main_image / "missing.png").exists()

    def test_corrupt_pdf_raises(self, tmp_path: Path, output_context: OutputContext) -> None:
        """A file that is not a PDF raises and writes nothing."""
        from rdetoolkit.nodes import render_png

        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"not a pdf")

        with pytest.raises(Exception):  # noqa: B017,PT011 -- pypdfium2.PdfiumError
            render_png(corrupt, output_context, "corrupt.png")
        assert not (output_context.main_image / "corrupt.png").exists()


@needs_cairo
class TestSvg:
    @pytest.mark.parametrize(("name", "content"), [("drawing.svg", _SVG), ("drawing.SVGZ", gzip.compress(_SVG))])
    def test_svg_is_rasterized_at_its_own_size(self, tmp_path: Path, output_context: OutputContext, name: str, content: bytes) -> None:
        """SVG and gzip-compressed SVGZ render at their own size; dpi does not apply."""
        from rdetoolkit.nodes import render_png

        source = tmp_path / name
        source.write_bytes(content)

        result = render_png(source, output_context, "drawing.png", dpi=72)

        assert result.parent == output_context.main_image
        image = _png(result)
        assert image.size == (40, 20)
        assert image.getpixel((1, 1)) == (0, 255, 0)


class TestPillowFormats:
    def test_other_formats_are_converted_like_to_png(self, output_context: OutputContext) -> None:
        """Non-PDF, non-SVG input is converted with Pillow."""
        from rdetoolkit.nodes import render_png

        result = render_png(FIXTURES_DIR / "sample.tif", output_context, "sample.png")

        assert result.parent == output_context.main_image
        assert _png(result).size == (120, 80)

    def test_corrupt_image_raises(self, output_context: OutputContext) -> None:
        """An unreadable image raises."""
        from rdetoolkit.nodes import render_png

        with pytest.raises(Exception):  # noqa: B017,PT011 -- PIL.UnidentifiedImageError
            render_png(FIXTURES_DIR / "sample_corrupt.tif", output_context, "corrupt.png")


class TestArguments:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"kind": "struct"}, "kind must be one of"),
            ({"page": 0}, "page must be 1 or greater"),
            ({"dpi": 0}, "dpi must be positive"),
        ],
    )
    def test_invalid_arguments_raise_before_reading(self, output_context: OutputContext, kwargs: dict[str, Any], match: str) -> None:
        """Invalid kind, page and dpi raise before the source is opened."""
        from rdetoolkit.nodes import render_png

        with pytest.raises(ValueError, match=match):
            render_png(Path("does-not-exist.pdf"), output_context, "x.png", **kwargs)


class TestMissingBackends:
    def test_missing_pypdfium2_names_the_extra(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output_context: OutputContext) -> None:
        """Without pypdfium2 the error names the render extra."""
        from rdetoolkit.nodes import render_png

        monkeypatch.setitem(sys.modules, "pypdfium2", None)
        source = tmp_path / "doc.pdf"
        source.write_bytes(b"%PDF-1.4")

        with pytest.raises(ImportError, match=r"pypdfium2.*rdetoolkit\[render\]"):
            render_png(source, output_context, "doc.png")

    def test_missing_cairosvg_names_the_extra(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output_context: OutputContext) -> None:
        """Without cairosvg the error names the render extra."""
        from rdetoolkit.nodes import render_png

        monkeypatch.setitem(sys.modules, "cairosvg", None)
        source = tmp_path / "drawing.svg"
        source.write_bytes(_SVG)

        with pytest.raises(ImportError, match=r"cairosvg.*rdetoolkit\[render\]"):
            render_png(source, output_context, "drawing.png")

    def test_missing_cairo_library_names_the_system_package(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output_context: OutputContext) -> None:
        """Without the Cairo library the error names the system package and the extra."""
        from rdetoolkit.nodes import render_png

        real_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "cairosvg":
                msg = 'no library called "cairo-2" was found'
                raise OSError(msg)
            return real_import(name, *args, **kwargs)

        monkeypatch.delitem(sys.modules, "cairosvg", raising=False)
        monkeypatch.setattr(builtins, "__import__", fake_import)
        source = tmp_path / "drawing.svg"
        source.write_bytes(_SVG)

        with pytest.raises(ImportError, match=r"Cairo system library.*libcairo2.*rdetoolkit\[render\]") as info:
            render_png(source, output_context, "drawing.png")
        assert isinstance(info.value.__cause__, OSError)


class TestRegistration:
    def test_exported_and_registered_as_builtin(self) -> None:
        """render_png is exported and registered with the builtin tag."""
        import rdetoolkit.nodes
        from rdetoolkit.core import registry

        assert "render_png" in rdetoolkit.nodes.__all__
        specs = [spec for spec in registry.list_nodes() if spec.id.endswith("render_png")]
        assert specs, [spec.id for spec in registry.list_nodes()]
        assert "builtin" in specs[0].tags
