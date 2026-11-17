"""Issue 599 (remaining): image kinds, copy_file and save_image.

EP table

| API | Partition | Rationale | Expected | Test ID |
|---|---|---|---|---|
| to_png / to_jpeg | kind omitted | unchanged default | written to other_image | I599X-EP-001 |
| to_png / to_jpeg | kind main_image / thumbnail | TIF -> main image | written to that directory | I599X-EP-002 |
| to_png / to_jpeg | kind outside the image dirs | invalid | ValueError, nothing written | I599X-NEG-001 |
| to_png / to_jpeg | kind passed positionally | keyword-only | TypeError | I599X-NEG-002 |
| copy_file | struct / other_image / thumbnail / attachment | any kind | byte-identical copy | I599X-EP-003 |
| copy_file | unknown kind / nested filename | invalid | ValueError, nothing copied | I599X-NEG-003 |
| copy_file | missing source / kind omitted | invalid | FileNotFoundError / TypeError | I599X-NEG-004 |
| save_image | RGB / gray / bool / Pillow image | array kinds | pixels round-trip | I599X-EP-004 |
| save_image | channel_order="bgr", BGR and BGRA | OpenCV arrays | channels reordered, input unchanged | I599X-EP-005 |
| save_image | .jpg / .tif suffix, kind | format by suffix | file in that format and directory | I599X-EP-006 |
| save_image | unknown suffix / channel order / kind | invalid | ValueError, nothing written | I599X-NEG-005 |
| save_image | RGBA as JPEG | unsupported mode | OSError, nothing written | I599X-NEG-006 |

BV table

| API | Boundary | Rationale | Expected | Test ID |
|---|---|---|---|---|
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from rdetoolkit.nodes import (
    copy_file,
    save_image,
    to_jpeg,
    to_png,
)
from rdetoolkit.types import OutputContext

# Long enough that charset detection is not ambiguous (short CP932 text can read as UTF-8).
_JA_LINES = ["測定値,単位", "温度,℃", "試料名称,酸化チタン粉末", "測定日時,二〇二六年十一月十七日"]


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _tiff(path: Path) -> Path:
    Image.new("RGB", (4, 3), (10, 20, 30)).save(path, format="TIFF")
    return path


_KINDS = ("struct", "meta", "main_image", "other_image", "thumbnail", "attachment", "nonshared_raw", "raw", "invoice", "logs")


def _files(out: OutputContext) -> list[Path]:
    """Every file under the output directories (the sources live beside them)."""
    return sorted(path for kind in _KINDS for path in Path(getattr(out, kind)).rglob("*") if path.is_file())


class TestImageKind:
    @pytest.mark.parametrize(("convert", "image_format"), [(to_png, "PNG"), (to_jpeg, "JPEG")])
    def test_default_kind_is_other_image__i599x_ep_001(self, tmp_path: Path, output_context: OutputContext, convert: Any, image_format: str) -> None:
        """I599X-EP-001: without kind the converted image goes to other_image, as before."""
        # Given: a TIFF source
        source = _tiff(tmp_path / "in.tif")
        # When: converting it without kind
        written = convert(source, output_context, "a.img")
        # Then: the image is in other_image in the requested format
        assert written == output_context.other_image / "a.img"
        with Image.open(written) as image:
            assert image.format == image_format

    @pytest.mark.parametrize("convert", [to_png, to_jpeg])
    @pytest.mark.parametrize("kind", ["main_image", "thumbnail", "other_image"])
    def test_kind_selects_the_image_directory__i599x_ep_002(self, tmp_path: Path, output_context: OutputContext, convert: Any, kind: str) -> None:
        """I599X-EP-002: kind places the converted image in that image directory."""
        # Given: a TIFF source
        source = _tiff(tmp_path / "in.tif")
        # When: converting it with kind
        written = convert(source, output_context, "a.img", kind=kind)
        # Then: the file is under the selected directory only
        assert written == getattr(output_context, kind) / "a.img"
        assert _files(output_context) == [written]

    @pytest.mark.parametrize("convert", [to_png, to_jpeg])
    @pytest.mark.parametrize("kind", ["struct", "raw", "bogus"])
    def test_non_image_kind_is_rejected__i599x_neg_001(self, tmp_path: Path, output_context: OutputContext, convert: Any, kind: str) -> None:
        """I599X-NEG-001: a kind outside the image directories raises before writing."""
        # Given: a TIFF source
        source = _tiff(tmp_path / "in.tif")
        # When / Then: the conversion is refused and nothing is written
        with pytest.raises(ValueError, match="kind must be one of"):
            convert(source, output_context, "a.img", kind=kind)
        assert _files(output_context) == []

    @pytest.mark.parametrize("convert", [to_png, to_jpeg])
    def test_kind_is_keyword_only__i599x_neg_002(self, tmp_path: Path, output_context: OutputContext, convert: Any) -> None:
        """I599X-NEG-002: kind cannot be passed positionally."""
        source = _tiff(tmp_path / "in.tif")
        with pytest.raises(TypeError):
            convert(source, output_context, "a.img", "main_image")


class TestCopyFile:
    @pytest.mark.parametrize("kind", ["struct", "other_image", "thumbnail", "attachment", "main_image"])
    def test_copies_bytes_into_any_kind__i599x_ep_003(self, tmp_path: Path, output_context: OutputContext, kind: str) -> None:
        """I599X-EP-003: the destination holds the source bytes unchanged."""
        # Given: a binary source
        content = bytes(range(256)) * 5
        source = _write(tmp_path / "in.bin", content)
        # When: copying it into the kind
        written = copy_file(source, output_context, "copy.bin", kind=kind)
        # Then: the bytes are identical and the source is untouched
        assert written == getattr(output_context, kind) / "copy.bin"
        assert written.read_bytes() == content
        assert source.read_bytes() == content

    @pytest.mark.parametrize(("kind", "filename"), [("bogus", "a.bin"), ("struct", "sub/a.bin"), ("struct", "../a.bin")])
    def test_invalid_destination_copies_nothing__i599x_neg_003(self, tmp_path: Path, output_context: OutputContext, kind: str, filename: str) -> None:
        """I599X-NEG-003: an unknown kind or a nested filename raises before copying."""
        source = _write(tmp_path / "in.bin", b"x")
        with pytest.raises(ValueError):  # noqa: PT011 -- two distinct messages
            copy_file(source, output_context, filename, kind=kind)  # type: ignore[arg-type]
        assert _files(output_context) == []

    def test_missing_source_and_missing_kind__i599x_neg_004(self, tmp_path: Path, output_context: OutputContext) -> None:
        """I599X-NEG-004: a missing source raises FileNotFoundError; kind is required."""
        with pytest.raises(FileNotFoundError):
            copy_file(tmp_path / "absent.bin", output_context, "a.bin", kind="struct")
        with pytest.raises(TypeError):
            copy_file(tmp_path / "absent.bin", output_context, "a.bin")  # type: ignore[call-arg]


def _pixels(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image)


class TestSaveImage:
    def test_arrays_and_pillow_images_round_trip__i599x_ep_004(self, output_context: OutputContext) -> None:
        """I599X-EP-004: RGB, grayscale, bool and Pillow images keep their pixels as PNG."""
        # Given: images of each kind
        rgb = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)
        gray = np.arange(20, dtype=np.uint8).reshape(4, 5)
        mask = gray % 2 == 0
        pillow = Image.fromarray(rgb)
        # When: saving them
        paths = [save_image(image, output_context, f"{name}.png") for name, image in (("rgb", rgb), ("gray", gray), ("mask", mask), ("pil", pillow))]
        # Then: every file is in other_image with the original pixels
        assert [path.parent for path in paths] == [output_context.other_image] * 4
        np.testing.assert_array_equal(_pixels(paths[0]), rgb)
        np.testing.assert_array_equal(_pixels(paths[1]), gray)
        np.testing.assert_array_equal(_pixels(paths[2]), mask)
        np.testing.assert_array_equal(_pixels(paths[3]), rgb)

    @pytest.mark.parametrize("channels", [3, 4])
    def test_bgr_arrays_are_reordered__i599x_ep_005(self, output_context: OutputContext, channels: int) -> None:
        """I599X-EP-005: channel_order="bgr" writes OpenCV BGR / BGRA arrays like cv2.imwrite."""
        # Given: an OpenCV-style array whose first channel is blue
        bgr = np.zeros((2, 3, channels), dtype=np.uint8)
        bgr[..., 0] = 200
        if channels == 4:
            bgr[..., 3] = 128
        before = bgr.copy()
        # When: saving it as BGR
        written = save_image(bgr, output_context, "overlay.png", channel_order="bgr")
        # Then: the file is blue in RGB order, alpha kept, and the input unchanged
        pixels = _pixels(written)
        assert pixels[0, 0, :3].tolist() == [0, 0, 200]
        if channels == 4:
            assert pixels[0, 0, 3] == 128
        np.testing.assert_array_equal(bgr, before)

    @pytest.mark.parametrize(("filename", "image_format"), [("a.jpg", "JPEG"), ("a.JPEG", "JPEG"), ("a.tif", "TIFF"), ("a.bmp", "BMP")])
    def test_suffix_selects_the_format__i599x_ep_006(self, output_context: OutputContext, filename: str, image_format: str) -> None:
        """I599X-EP-006: the format follows the suffix, and kind the directory."""
        image = np.full((3, 3, 3), 90, dtype=np.uint8)
        written = save_image(image, output_context, filename, kind="main_image")
        assert written == output_context.main_image / filename
        with Image.open(written) as saved:
            assert saved.format == image_format

    @pytest.mark.parametrize(
        "kwargs",
        [{"filename": "a.unknownext"}, {"filename": "noext"}, {"filename": "a.png", "channel_order": "grb"}, {"filename": "a.png", "kind": "bogus"}, {"filename": "x/a.png"}],
    )
    def test_invalid_options_write_nothing__i599x_neg_005(self, output_context: OutputContext, kwargs: dict[str, Any]) -> None:
        """I599X-NEG-005: an unknown suffix, channel order, kind or nested filename raises before writing."""
        image = np.zeros((2, 2, 3), dtype=np.uint8)
        with pytest.raises(ValueError):  # noqa: PT011 -- several distinct messages
            save_image(image, output_context, **kwargs)
        assert _files(output_context) == []

    def test_mode_the_format_cannot_store__i599x_neg_006(self, output_context: OutputContext) -> None:
        """I599X-NEG-006: RGBA as JPEG raises OSError and writes nothing."""
        rgba = np.zeros((2, 2, 4), dtype=np.uint8)
        with pytest.raises(OSError):  # noqa: PT011 -- Pillow's message
            save_image(rgba, output_context, "a.jpg")
        assert _files(output_context) == []
