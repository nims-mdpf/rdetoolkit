"""Tests for rdetoolkit v2 builtin image nodes (Session F1.5, TC-F1-IMAGE-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f1.md
Conflict #2 (argument order; ``make_thumbnail``'s literal example signature),
Conflict #3 (OutputKind guidance), Conflict #5 (PIL available transitively
via matplotlib), Conflict #6 (pure-Python PIL implementation -- NEVER
``resize_image_aspect_ratio``/``rdetoolkit.img2thumb``/``rdetoolkit._core``),
Known Trap 8 (never compare images by raw byte equality).

Pinned API shapes (binding contract for this file):

    to_png(source_path: Path, out: OutputContext, filename: str) -> Path
    to_jpeg(source_path: Path, out: OutputContext, filename: str) -> Path
    make_thumbnail(source_path: Path, out: OutputContext, filename: str | None = None) -> Path
    save_main_image(source_path: Path, out: OutputContext, filename: str) -> Path
    copy_raw(source_path: Path, out: OutputContext, filename: str) -> Path

OutputKind targets (Conflict #3 -- guidance, with two genuinely open
choices this file accommodates rather than over-pinning):
    - ``to_png``/``to_jpeg``: default to ``other_image`` (asserted directly;
      if Codex additionally exposes an optional ``kind`` parameter, calling
      without it must still default to ``other_image`` per the ruling's own
      wording).
    - ``make_thumbnail`` -> ``thumbnail``; ``save_main_image`` -> ``main_image``.
    - ``copy_raw`` -> either ``raw`` or ``nonshared_raw`` is acceptable
      (Codex's documented choice) -- this file asserts membership in that
      2-element set, not a single hardcoded directory.

Thumbnail default box (Conflict #2's "matches v1 img2thumb's default
width/height convention"): v1 ``img2thumb.resize_image``'s default is
``width=640, height=480`` (read directly from the v1 source, a read-only
porting reference, never imported). ``sample_large.tif`` is a solid-color
1280x960 fixture -- exactly 2x the 640x480 box on both axes (identical 4:3
aspect ratio) -- so a correct aspect-preserving fit-within-box resize lands
on an exact, rounding-free ``(640, 480)``.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rdetoolkit.types import OutputContext
from tests.v2.nodes.conftest import FIXTURES_DIR


class TestToPng:
    """TC-F1-IMAGE-TOPNG-*."""

    def test_tif_converts_to_valid_png(self, output_context: OutputContext) -> None:
        """EP: a small .tif fixture converts to a correctly-formatted PNG file (verified via PIL.Image.open(...).format)."""
        from rdetoolkit.nodes.image import to_png

        result_path = to_png(FIXTURES_DIR / "sample.tif", output_context, "result.png")

        assert result_path.exists()
        assert result_path.suffix == ".png"
        with Image.open(result_path) as img:
            img.load()
            assert img.format == "PNG"
            assert img.size == (120, 80)

    def test_defaults_to_other_image_output_kind(self, output_context: OutputContext) -> None:
        """EP: without an explicit kind, to_png lands under out.other_image (Conflict #3 default)."""
        from rdetoolkit.nodes.image import to_png

        result_path = to_png(FIXTURES_DIR / "sample.tif", output_context, "result_kind.png")

        assert result_path.parent == output_context.other_image

    def test_corrupt_input_raises(self, output_context: OutputContext) -> None:
        """BV: an unsupported/corrupt input raises."""
        from rdetoolkit.nodes.image import to_png

        with pytest.raises(Exception):  # noqa: B017,PT011 -- PIL.UnidentifiedImageError or similar
            to_png(FIXTURES_DIR / "sample_corrupt.tif", output_context, "should_not_exist.png")

    def test_registered_as_builtin_node(self) -> None:
        """Registration: to_png appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("to_png") for node_id in ids), ids


class TestToJpeg:
    """TC-F1-IMAGE-TOJPEG-*."""

    def test_tif_converts_to_valid_jpeg(self, output_context: OutputContext) -> None:
        """EP: a small .tif fixture converts to a correctly-formatted JPEG file."""
        from rdetoolkit.nodes.image import to_jpeg

        result_path = to_jpeg(FIXTURES_DIR / "sample.tif", output_context, "result.jpg")

        assert result_path.exists()
        with Image.open(result_path) as img:
            img.load()
            assert img.format == "JPEG"
            assert img.size == (120, 80)

    def test_defaults_to_other_image_output_kind(self, output_context: OutputContext) -> None:
        """EP: without an explicit kind, to_jpeg lands under out.other_image (Conflict #3 default)."""
        from rdetoolkit.nodes.image import to_jpeg

        result_path = to_jpeg(FIXTURES_DIR / "sample.tif", output_context, "result_kind.jpg")

        assert result_path.parent == output_context.other_image

    def test_corrupt_input_raises(self, output_context: OutputContext) -> None:
        """BV: an unsupported/corrupt input raises."""
        from rdetoolkit.nodes.image import to_jpeg

        with pytest.raises(Exception):  # noqa: B017,PT011
            to_jpeg(FIXTURES_DIR / "sample_corrupt.tif", output_context, "should_not_exist.jpg")

    def test_registered_as_builtin_node(self) -> None:
        """Registration: to_jpeg appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("to_jpeg") for node_id in ids), ids


class TestMakeThumbnail:
    """TC-F1-IMAGE-THUMB-*."""

    def test_resizes_preserving_aspect_ratio_to_v1_default_box(self, output_context: OutputContext) -> None:
        """EP: a 1280x960 (4:3) source is resized down to fit the v1-default
        640x480 bounding box, landing exactly on (640, 480) since the source
        aspect ratio exactly matches the box's ratio (no rounding ambiguity)."""
        from rdetoolkit.nodes.image import make_thumbnail

        result_path = make_thumbnail(FIXTURES_DIR / "sample_large.tif", output_context, "thumb.png")

        assert result_path.exists()
        assert result_path.parent == output_context.thumbnail
        with Image.open(result_path) as img:
            img.load()
            assert img.size == (640, 480)

    def test_default_filename_when_omitted(self, output_context: OutputContext) -> None:
        """EP: filename is optional (Conflict #2's pinned signature: filename: str | None = None); a file is still produced."""
        from rdetoolkit.nodes.image import make_thumbnail

        result_path = make_thumbnail(FIXTURES_DIR / "sample_large.tif", output_context)

        assert result_path.exists()
        assert result_path.parent == output_context.thumbnail

    def test_corrupt_input_raises(self, output_context: OutputContext) -> None:
        """BV: an unsupported/corrupt input raises."""
        from rdetoolkit.nodes.image import make_thumbnail

        with pytest.raises(Exception):  # noqa: B017,PT011
            make_thumbnail(FIXTURES_DIR / "sample_corrupt.tif", output_context, "should_not_exist.png")

    def test_registered_as_builtin_node(self) -> None:
        """Registration: make_thumbnail appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("make_thumbnail") for node_id in ids), ids


class TestSaveMainImage:
    """TC-F1-IMAGE-MAIN-*."""

    def test_copies_to_main_image_directory_preserving_filename(self, output_context: OutputContext) -> None:
        """EP: file copied to out.main_image, original filename preserved, same size/mode as source (Known Trap 8: never compare by raw bytes)."""
        from rdetoolkit.nodes.image import save_main_image

        result_path = save_main_image(FIXTURES_DIR / "sample.tif", output_context, "sample.tif")

        assert result_path.exists()
        assert result_path.parent == output_context.main_image
        assert result_path.name == "sample.tif"
        with Image.open(FIXTURES_DIR / "sample.tif") as src, Image.open(result_path) as dst:
            src.load()
            dst.load()
            assert src.size == dst.size
            assert src.mode == dst.mode

    def test_registered_as_builtin_node(self) -> None:
        """Registration: save_main_image appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("save_main_image") for node_id in ids), ids


class TestCopyRaw:
    """TC-F1-IMAGE-RAW-*."""

    def test_copies_to_raw_or_nonshared_raw_directory(self, output_context: OutputContext) -> None:
        """EP: file copied to out.raw or out.nonshared_raw (Conflict #3: Codex's documented choice), original filename preserved."""
        from rdetoolkit.nodes.image import copy_raw

        result_path = copy_raw(FIXTURES_DIR / "sample.tif", output_context, "sample.tif")

        assert result_path.exists()
        assert result_path.parent in (output_context.raw, output_context.nonshared_raw)
        assert result_path.name == "sample.tif"
        with Image.open(FIXTURES_DIR / "sample.tif") as src, Image.open(result_path) as dst:
            src.load()
            dst.load()
            assert src.size == dst.size
            assert src.mode == dst.mode

    def test_registered_as_builtin_node(self) -> None:
        """Registration: copy_raw appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("copy_raw") for node_id in ids), ids


class TestImageModuleNegativeGuard:
    """Conflict #6's exact-string negative guard, pinned as an executable
    test (not just a shell grep) -- the module source must never reference
    the Rust-backed v1-compat resize path."""

    def test_image_module_never_uses_rust_core_resize_path(self) -> None:
        """nodes/image.py's source contains none of the forbidden strings:
        resize_image_aspect_ratio, rdetoolkit.img2thumb, rdetoolkit._core."""
        import rdetoolkit.nodes.image as image_module

        source = Path(image_module.__file__).read_text(encoding="utf-8")

        assert "resize_image_aspect_ratio" not in source
        assert "rdetoolkit.img2thumb" not in source
        assert "rdetoolkit._core" not in source
        assert "from rdetoolkit import _core" not in source
