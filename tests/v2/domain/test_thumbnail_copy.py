"""Issue #633: separate thumbnail copying from legacy exception translation.

EP table:
| Test ID | Partition | Expected |
|---------|-----------|----------|
| TC-633-EP-001 | internal/service copy raises 3004 | same exception and code |
| TC-633-EP-002 | internal copy raises OSError/3001 | same exception |
| TC-633-EP-003 | public copy raises OSError/3004 | StructuredError(50), legacy message |
| TC-633-EP-004 | public copy raises StructuredError | original code/message/object |
| TC-633-EP-005 | sorted selection, extension variants, recursive target | same file and bytes |

BV table:
| Test ID | Boundary | Expected |
|---------|----------|----------|
| TC-633-BV-001 | absent/file/empty main, unsupported/mismatched extension, absent target | no copy |
| TC-633-BV-002 | disabled generation, one main image | no copy call |
| TC-633-BV-003 | one main image, missing thumbnail directory | raw FileNotFoundError or legacy 50 |
| TC-633-BV-004 | public signature | unchanged positional and keyword-only parameters |
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Literal

import pytest

from rdetoolkit import img2thumb
from rdetoolkit.domain.artifacts import ImageArtifactService
from rdetoolkit.domain.service_errors import execution_error
from rdetoolkit.errors import RdeExecutionError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.types import RdeConfig


@pytest.fixture
def image_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create thumbnail and main-image directories with one source image."""
    thumbnail, main = tmp_path / "thumbnail", tmp_path / "main_image"
    thumbnail.mkdir()
    main.mkdir()
    (main / "source.PNG").write_bytes(b"original image bytes")
    return thumbnail, main


@pytest.mark.parametrize("entry", ["internal", "service"])
def test_copy_interruption_is_preserved__tc_633_ep_001(
    image_dirs: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
) -> None:
    """TC-633-EP-001: interruptions survive both internal entry points."""
    # Given: an interruption raised inside the real copy implementation
    thumbnail, main = image_dirs
    interrupt = execution_error(3004, "interrupted while copying")

    def interrupt_copy(*_args: object, **_kwargs: object) -> None:
        raise interrupt

    monkeypatch.setattr(img2thumb.shutil, "copy", interrupt_copy)

    # When: invoking the internal implementation or its domain service
    with pytest.raises(RdeExecutionError) as exc_info:
        if entry == "internal":
            img2thumb._copy_images_to_thumbnail_impl(thumbnail, main)
        else:
            ImageArtifactService().generate(
                main_image_dir=main,
                thumbnail_dir=thumbnail,
                config=RdeConfig(system={"save_thumbnail_image": True}),
            )

    # Then: no exception translation or suppression obscures the interruption
    assert exc_info.value is interrupt
    assert exc_info.value.code == 3004


@pytest.mark.parametrize("error", [OSError("disk failure"), execution_error(3001, "ordinary")], ids=["oserror", "execution-3001"])
def test_internal_copy_preserves_ordinary_errors__tc_633_ep_002(
    image_dirs: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    """TC-633-EP-002: the implementation leaves ordinary errors untouched."""
    # Given: a failing copy leaf and the undecorated implementation
    thumbnail, main = image_dirs

    def fail_copy(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(img2thumb.shutil, "copy", fail_copy)

    # When: copying a selected image
    with pytest.raises(type(error)) as exc_info:
        img2thumb._copy_images_to_thumbnail_impl(thumbnail, main)

    # Then: failure tolerance remains the caller's responsibility
    assert exc_info.value is error
    if isinstance(error, RdeExecutionError):
        assert error.code == 3001


@pytest.mark.parametrize("error", [OSError("disk failure"), execution_error(3004, "interrupted")], ids=["oserror", "execution-3004"])
def test_public_copy_preserves_legacy_error_contract__tc_633_ep_003(
    image_dirs: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    """TC-633-EP-003: the public API retains legacy exception translation."""
    # Given: a leaf failure reached through the legacy public API
    thumbnail, main = image_dirs

    def fail_copy(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(img2thumb.shutil, "copy", fail_copy)

    # When: calling the public wrapper
    with pytest.raises(StructuredError) as exc_info:
        img2thumb.copy_images_to_thumbnail(thumbnail, main)

    # Then: the original legacy code, message and traceback format are retained
    assert exc_info.value.ecode == 50
    assert exc_info.value.emsg == "Error: ERROR: failed to copy image files"
    assert str(exc_info.value) == exc_info.value.emsg
    assert exc_info.value.__cause__ is error
    assert exc_info.value.traceback_info is not None
    assert "failed to copy image files" in exc_info.value.traceback_info


def test_public_copy_preserves_structured_error_fields__tc_633_ep_004(
    image_dirs: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-633-EP-004: existing structured fields take precedence."""
    # Given: a preexisting structured failure with a custom code and payload
    thumbnail, main = image_dirs
    payload = {"source": "image"}
    error = StructuredError("original message", 73, payload)

    def fail_copy(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(img2thumb.shutil, "copy", fail_copy)

    # When: the public wrapper translates the failure using the legacy decorator
    with pytest.raises(StructuredError) as exc_info:
        img2thumb.copy_images_to_thumbnail(thumbnail, main)

    # Then: the decorator still prefers existing structured fields
    assert exc_info.value.ecode == 73
    assert exc_info.value.emsg == "Error: original message"
    assert exc_info.value.eobj is payload
    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize("entry", ["public", "internal"])
@pytest.mark.parametrize("string_paths", [False, True], ids=["path", "str"])
@pytest.mark.parametrize(
    ("img_ext", "target", "expected"),
    [
        (None, None, "b.JPG"),
        ("PNG", None, "c.PnG"),
        (".pNg", None, "c.PnG"),
        ("jpg", "nested/chosen.dat", "chosen.dat"),
        (None, "chosen.dat", "chosen.dat"),
    ],
    ids=["sorted", "extension-without-dot", "extension-with-dot", "explicit-relative-target", "recursive-target"],
)
def test_image_selection_is_unchanged__tc_633_ep_005(
    tmp_path: Path,
    entry: str,
    string_paths: bool,
    img_ext: str | None,
    target: str | None,
    expected: str,
) -> None:
    """TC-633-EP-005: both entry points retain image-selection semantics."""
    # Given: mixed-case images, an unsupported file, a directory and a nested target
    thumbnail, main = tmp_path / "thumbnail", tmp_path / "main_image"
    thumbnail.mkdir()
    main.mkdir()
    (main / "a.PNG").mkdir()
    for name in ("z.webp", "c.PnG", "a.txt", "b.JPG", "nested/chosen.dat"):
        source = main / name
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(name.encode())
    copy = img2thumb.copy_images_to_thumbnail if entry == "public" else img2thumb._copy_images_to_thumbnail_impl

    # When: selecting an image through either entry point
    copy(str(thumbnail) if string_paths else thumbnail, str(main) if string_paths else main, target_image_name=target, img_ext=img_ext)

    # Then: selection and copied bytes match the established behavior
    assert [path.name for path in thumbnail.iterdir()] == [expected]
    original = main / (f"nested/{expected}" if target else expected)
    assert (thumbnail / expected).read_bytes() == original.read_bytes()


@pytest.mark.parametrize("entry", ["public", "internal"])
@pytest.mark.parametrize("boundary", ["missing", "file", "empty", "unsupported", "extension", "target"])
def test_no_matching_image_is_a_noop__tc_633_bv_001(tmp_path: Path, entry: str, boundary: str) -> None:
    """TC-633-BV-001: absent or unmatched sources remain harmless."""
    # Given: a source boundary at which the legacy API performs no copy
    thumbnail, main = tmp_path / "thumbnail", tmp_path / "main_image"
    thumbnail.mkdir()
    if boundary == "file":
        main.touch()
    elif boundary != "missing":
        main.mkdir()
        if boundary != "empty":
            (main / ("source.txt" if boundary == "unsupported" else "source.png")).touch()
    copy = img2thumb.copy_images_to_thumbnail if entry == "public" else img2thumb._copy_images_to_thumbnail_impl

    # When: attempting thumbnail generation without a matching image
    result = copy(thumbnail, main, img_ext="jpg" if boundary == "extension" else None, target_image_name="absent.png" if boundary == "target" else None)

    # Then: nothing is copied and no exception is raised
    assert result is None
    assert list(thumbnail.iterdir()) == []


def test_disabled_thumbnails_skip_copy__tc_633_bv_002(image_dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-633-BV-002: disabled generation performs no copy."""
    # Given: an otherwise copyable source and disabled thumbnail generation
    thumbnail, main = image_dirs
    calls: list[object] = []
    monkeypatch.setattr(img2thumb.shutil, "copy", lambda *args: calls.append(args))

    # When: generating optional image artifacts
    ImageArtifactService().generate(main_image_dir=main, thumbnail_dir=thumbnail, config=RdeConfig())

    # Then: no copy was attempted even though a source image exists
    assert calls == []
    assert list(thumbnail.iterdir()) == []


@pytest.mark.parametrize("entry", ["public", "internal"])
def test_missing_destination_error__tc_633_bv_003(image_dirs: tuple[Path, Path], entry: Literal["public", "internal"]) -> None:
    """TC-633-BV-003: filesystem failures follow the entry point's contract."""
    # Given: one source image and a missing destination directory
    thumbnail, main = image_dirs
    destination = thumbnail / "absent" / "thumbnail"

    # When: the real filesystem copy fails
    if entry == "public":
        with pytest.raises(StructuredError) as exc_info:
            img2thumb.copy_images_to_thumbnail(destination, main)
        # Then: the public API retains the legacy translation and code
        assert exc_info.value.ecode == 50
        assert exc_info.value.emsg == "Error: ERROR: failed to copy image files"
        assert isinstance(exc_info.value.__cause__, FileNotFoundError)
    else:
        with pytest.raises(FileNotFoundError):
            img2thumb._copy_images_to_thumbnail_impl(destination, main)
        # Then: the internal implementation neither translates nor creates directories
    assert not destination.exists()


def test_public_signature_is_unchanged__tc_633_bv_004() -> None:
    """TC-633-BV-004: preserve the inspectable legacy signature."""
    # Given: the decorated legacy function's inspectable signature
    signature = inspect.signature(img2thumb.copy_images_to_thumbnail)

    # When: inspecting parameter names, order, kinds and defaults
    parameters = list(signature.parameters.values())

    # Then: both paths remain positional and both optional arguments keyword-only
    assert [parameter.name for parameter in parameters] == ["out_dir_thumb_img", "out_dir_main_img", "target_image_name", "img_ext"]
    assert [parameter.kind for parameter in parameters] == [inspect.Parameter.POSITIONAL_OR_KEYWORD] * 2 + [inspect.Parameter.KEYWORD_ONLY] * 2
    assert [parameter.default for parameter in parameters] == [inspect.Parameter.empty] * 2 + [None] * 2
