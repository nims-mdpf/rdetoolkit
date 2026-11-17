"""Issue 599 (remaining): image kinds, copy_file, save_image, read_lines,
list_excel_sheets, detect_encoding and tar archives.

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
| read_lines | LF / CRLF / CR, keepends | text-mode lines | same as readlines / splitlines | I599X-EP-007 |
| read_lines | U+2028 / form feed in a line | no extra split | one line | I599X-EP-008 |
| read_lines | detected / explicit encoding | same as read_text | decoded text | I599X-EP-009 |
| detect_encoding | BOM / CP932 / UTF-8 / ASCII | reader rule | canonical name of the codec read_text uses | I599X-EP-010 |
| list_excel_sheets | several sheets, one hidden | sheet listing | names in workbook order | I599X-EP-011 |
| unzip_inputs | .tar / .tar.gz / .tar.bz2 / .tar.xz | tar uploads | files extracted in archive order | I599X-EP-012 |
| unzip_inputs | tar with include_dirs | directory entries | directories listed | I599X-EP-013 |
| unzip_inputs | tar traversal / absolute / link / outward dst link | containment | skipped with warning | I599X-NEG-007 |
| unzip_inputs | neither ZIP nor tar | invalid | BadZipFile | I599X-NEG-008 |
| all new nodes | flow with strict type check | recorded calls | success | I599X-EP-017 |

BV table

| API | Boundary | Rationale | Expected | Test ID |
|---|---|---|---|---|
| read_lines | empty file / no final newline | zero and last line | [] / last line kept | I599X-BV-001 |
| detect_encoding | empty file | zero bytes | "utf-8" | I599X-BV-002 |
"""

from __future__ import annotations

import io
import json
import logging
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from rdetoolkit.nodes import (
    copy_file,
    detect_encoding,
    list_excel_sheets,
    read_excel,
    read_lines,
    read_text,
    save_image,
    to_jpeg,
    to_png,
    unzip_inputs,
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


class TestReadLines:
    @pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
    def test_lines_match_text_mode_reading__i599x_ep_007(self, tmp_path: Path, newline: bytes) -> None:
        """I599X-EP-007: lines split like readlines; without keepends like splitlines."""
        # Given: a file with three lines and a final line ending
        source = _write(tmp_path / "a.txt", newline.join([b"a", b"", b"c"]) + newline)
        # When: reading it as lines
        lines = read_lines(source)
        kept = read_lines(source, keepends=True)
        # Then: both views match text-mode open()
        with source.open(encoding="utf-8") as fin:
            expected_kept = fin.readlines()
        assert kept == expected_kept == ["a\n", "\n", "c\n"]
        assert lines == source.read_text(encoding="utf-8").splitlines() == ["a", "", "c"]

    def test_unicode_separators_do_not_split__i599x_ep_008(self, tmp_path: Path) -> None:
        """I599X-EP-008: U+2028 and form feed stay inside their line, as with readlines."""
        source = _write(tmp_path / "a.txt", "x y\x0cz\nnext".encode())
        assert read_lines(source) == ["x y\x0cz", "next"]

    def test_decoding_matches_read_text__i599x_ep_009(self, tmp_path: Path) -> None:
        """I599X-EP-009: detected and explicit encodings decode like read_text."""
        # Given: a UTF-8 BOM file and a CP932 file
        bom = _write(tmp_path / "bom.txt", "﻿温度\n湿度\n".encode())
        sjis = _write(tmp_path / "sjis.txt", "\n".join(_JA_LINES).encode("cp932"))
        # When / Then: the lines are those of read_text
        assert read_lines(bom) == read_text(bom).splitlines() == ["温度", "湿度"]
        assert read_lines(sjis) == _JA_LINES
        assert read_lines(sjis, encoding="cp932") == _JA_LINES
        with pytest.raises(UnicodeDecodeError):
            read_lines(sjis, encoding="utf-8")

    def test_boundaries__i599x_bv_001(self, tmp_path: Path) -> None:
        """I599X-BV-001: an empty file gives []; a last line without newline is kept."""
        assert read_lines(_write(tmp_path / "e.txt", b"")) == []
        assert read_lines(_write(tmp_path / "n.txt", b"a\nb")) == ["a", "b"]
        assert read_lines(_write(tmp_path / "k.txt", b"a\nb"), keepends=True) == ["a\n", "b"]


class TestDetectEncoding:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("﻿温度,湿度\n".encode(), "utf-8-sig"),
            ("測定値,単位\n温度,℃\n".encode("cp932") * 5, "cp932"),
            ("測定値,単位\n温度,℃\n".encode() * 5, "utf-8"),
            (b"plain,ascii\n", "ascii"),
        ],
    )
    def test_reader_rule__i599x_ep_010(self, tmp_path: Path, content: bytes, expected: str) -> None:
        """I599X-EP-010: the codec is the one read_text uses without encoding."""
        source = _write(tmp_path / "a.txt", content)
        detected = detect_encoding(source)
        assert detected == expected
        assert source.read_text(encoding=detected) == read_text(source)

    def test_empty_file__i599x_bv_002(self, tmp_path: Path) -> None:
        """I599X-BV-002: an empty file is reported as UTF-8."""
        assert detect_encoding(_write(tmp_path / "e.txt", b"")) == "utf-8"


class TestListExcelSheets:
    def test_names_in_workbook_order__i599x_ep_011(self, tmp_path: Path) -> None:
        """I599X-EP-011: names follow workbook order, include hidden sheets, and index read_excel."""
        # Given: a workbook with three sheets, the middle one hidden
        path = tmp_path / "book.xlsx"
        with pd.ExcelWriter(path) as writer:
            for name in ("summary", "raw data 1", "測定"):
                pd.DataFrame({"v": [name]}).to_excel(writer, sheet_name=name, index=False)
            writer.book["raw data 1"].sheet_state = "hidden"
        # When: listing the sheets
        names = list_excel_sheets(path)
        # Then: the order is the workbook's and positions select the same sheet
        assert names == ["summary", "raw data 1", "測定"]
        wanted = next(name for name in names if "raw" in name)
        assert read_excel(path, sheet_name=names.index(wanted))["v"].tolist() == ["raw data 1"]


def _tar(path: Path, mode: str, members: list[tuple[str, bytes | None]]) -> Path:
    with tarfile.open(path, mode) as archive:
        for name, content in members:
            info = tarfile.TarInfo(name)
            if content is None:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
    return path


class TestUnzipTar:
    @pytest.mark.parametrize(("suffix", "mode"), [(".tar", "w"), (".tar.gz", "w:gz"), (".tgz", "w:gz"), (".tar.bz2", "w:bz2"), (".tar.xz", "w:xz")])
    def test_tar_variants_extract__i599x_ep_012(self, tmp_path: Path, suffix: str, mode: str) -> None:
        """I599X-EP-012: tar archives extract their files in archive order."""
        # Given: a tar archive with nested and Japanese names
        archive = _tar(tmp_path / f"upload{suffix}", mode, [("b.txt", b"b"), ("sub/", None), ("sub/測定.csv", b"x,y\n")])
        # When: extracting it
        extracted = unzip_inputs(archive, tmp_path / "out")
        # Then: the files are extracted and returned in order
        base = (tmp_path / "out").resolve()
        assert extracted == [base / "b.txt", base / "sub" / "測定.csv"]
        assert (base / "sub" / "測定.csv").read_bytes() == b"x,y\n"

    def test_tar_include_dirs__i599x_ep_013(self, tmp_path: Path) -> None:
        """I599X-EP-013: include_dirs also returns directory entries."""
        archive = _tar(tmp_path / "a.tar", "w", [("empty/", None), ("f.txt", b"1")])
        base = (tmp_path / "out").resolve()
        assert unzip_inputs(archive, tmp_path / "out", include_dirs=True) == [base / "empty", base / "f.txt"]
        assert (base / "empty").is_dir()

    def test_unsafe_tar_members_are_skipped__i599x_neg_007(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """I599X-NEG-007: traversal, absolute, link and outward-link members are skipped with a warning."""
        # Given: a destination holding an outward symlink and an archive with unsafe members
        outside = tmp_path / "outside"
        outside.mkdir()
        dst = tmp_path / "out"
        dst.mkdir()
        (dst / "escape").symlink_to(outside, target_is_directory=True)
        archive = tmp_path / "evil.tar"
        with tarfile.open(archive, "w") as tar:
            for name in ("../up.txt", "/abs.txt", "escape/through.txt", "ok.txt"):
                info = tarfile.TarInfo(name)
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
            link = tarfile.TarInfo("link")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tar.addfile(link)
        # When: extracting it
        with caplog.at_level(logging.WARNING):
            extracted = unzip_inputs(archive, dst)
        # Then: only the safe member is extracted and nothing escaped
        assert extracted == [dst.resolve() / "ok.txt"]
        assert list(outside.iterdir()) == []
        assert not (tmp_path / "up.txt").exists()
        assert not (dst / "link").exists()
        assert caplog.text.count("Skipping") == 4

    def test_neither_zip_nor_tar__i599x_neg_008(self, tmp_path: Path) -> None:
        """I599X-NEG-008: a file that is no archive raises BadZipFile, as before."""
        with pytest.raises(zipfile.BadZipFile):
            unzip_inputs(_write(tmp_path / "a.tar.xz", b"not an archive at all"), tmp_path / "out")

    def test_zip_is_still_extracted(self, tmp_path: Path) -> None:
        """ZIP archives keep their extraction path, including the CP932 repair."""
        archive = tmp_path / "a.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("m.txt", "x")
        assert [path.name for path in unzip_inputs(archive, tmp_path / "out")] == ["m.txt"]


def _dataset(root: Path, metadef: dict[str, Any]) -> None:
    from tests.v2.runner.test_event_log_robustness_k4 import _INVOICE, _build_tree

    _build_tree(root / "data")
    invoice = json.loads(json.dumps(_INVOICE))
    invoice["basic"]["description"] = "既存"
    (root / "data/invoice/invoice.json").write_text(json.dumps(invoice, ensure_ascii=False), encoding="utf-8")
    (root / "data/tasksupport/metadata-def.json").write_text(json.dumps(metadef, ensure_ascii=False), encoding="utf-8")


def test_new_nodes_in_a_strict_flow__i599x_ep_017(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I599X-EP-017: the new nodes run in a recorded flow with strict type checks."""
    from rdetoolkit import flow, workflows
    from rdetoolkit.nodes import save_text
    from rdetoolkit.types import InputPaths

    # Given: a dataset with a text, a workbook, a tar archive and a TIFF
    _dataset(tmp_path, {})
    inputs = tmp_path / "data/inputdata"
    (inputs / "file_0.txt").unlink()
    _write(inputs / "a.txt", "\r\n".join(_JA_LINES).encode("cp932"))
    with pd.ExcelWriter(inputs / "b.xlsx") as writer:
        pd.DataFrame({"v": [1]}).to_excel(writer, sheet_name="first", index=False)
    _tar(inputs / "c.tar.gz", "w:gz", [("in.txt", b"t")])
    _tiff(inputs / "d.tif")
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline(paths: InputPaths, out: OutputContext) -> None:
        by_name = {path.name: path for path in paths.rawfiles}
        lines = read_lines(by_name["a.txt"])
        encoding = detect_encoding(by_name["a.txt"])
        sheets = list_excel_sheets(by_name["b.xlsx"])
        members = unzip_inputs(by_name["c.tar.gz"], out.struct)
        to_png(by_name["d.tif"], out, "d.png", kind="main_image")
        copy_file(by_name["d.tif"], out, "d.tif", kind="attachment")
        save_image(np.zeros((2, 2, 3), dtype=np.uint8), out, "mask.png", channel_order="bgr")
        summary = {"lines": lines, "encoding": encoding, "sheets": sheets, "members": [member.name for member in members]}
        save_text(json.dumps(summary, ensure_ascii=False), out, "summary.json")

    # When: running it with strict type checks
    report = workflows.run(flow=pipeline, config={"execution": {"type_check": "strict"}})
    # Then: the run succeeds with the expected values and files
    assert report.status == "success", report.error
    data = tmp_path / "data"
    summary = json.loads((data / "structured/summary.json").read_text(encoding="utf-8"))
    assert summary == {"lines": _JA_LINES, "encoding": "cp932", "sheets": ["first"], "members": ["in.txt"]}
    assert (data / "main_image/d.png").is_file()
    assert (data / "attachment/d.tif").read_bytes() == (inputs / "d.tif").read_bytes()
    assert (data / "other_image/mask.png").is_file()
