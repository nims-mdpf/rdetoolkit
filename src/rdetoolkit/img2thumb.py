from __future__ import annotations

import itertools
import os
import shutil
from glob import glob
from pathlib import Path

from rdetoolkit.core import resize_image_aspect_ratio
from rdetoolkit.errors import catch_exception_with_message
from rdetoolkit.exceptions import StructuredError


def __copy_img_to_thumb(out_dir_thumb_img: str, source_img_paths: str | list[str]) -> None:
    """Copies the other images to the thumbnail directory.

    Args:
        out_dir_thumb_img (str): The directory path where the thumbnail images will be saved.
        source_img_paths (str | list[str]): The list of paths of the source image files.

    output_path (str | Path | None, optional): The path where the resized image will be saved. If None, the original image will be overwritten.

    """
    if isinstance(source_img_paths, str):
        source_img_paths = [source_img_paths]
    for path in source_img_paths:
        basename = os.path.basename(path)
        thumb_img_path = os.path.join(out_dir_thumb_img, basename)
        shutil.copy(path, thumb_img_path)


def __find_img_path(dirname: str, target_name: str) -> str:
    search_pattern = os.path.join(dirname, "**", target_name)
    matching_files = list(glob(search_pattern, recursive=True))
    if matching_files:
        return matching_files[0]
    return ""


@catch_exception_with_message(error_message="ERROR: failed to copy image files", error_code=50)
def copy_images_to_thumbnail(
    out_dir_thumb_img: str | Path,
    out_dir_main_img: str | Path,
    *,
    target_image_name: str | None = None,
    img_ext: str | None = None,
) -> None:
    """Copy the image files in the other image folder and the main image folder to the thumbnail folder.

    Args:
        out_dir_thumb_img (str): directory path where thumbnail image is saved
        out_dir_main_img (str): directory path where main image is saved
        target_image_name (str, optional): Specify the name of the image file to be copied to the thumbnail folder.
        img_ext (str, optional): image file extension.
    """
    default_img_exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tif", ".tiff"]
    img_exts = (
        default_img_exts + [ext.upper() for ext in default_img_exts]
        if img_ext is None
        else [img_ext]
    )

    img_paths_main = [glob(os.path.join(out_dir_main_img, "*" + ext)) for ext in img_exts]
    img_path_main = list(itertools.chain.from_iterable(img_paths_main))

    # When there are multiple images in the main image folder, copy one at the leading index as the representative image.
    __main_img_path: str = ""
    if target_image_name is not None:
        __main_img_path = __find_img_path(str(out_dir_main_img), target_image_name)
    elif len(img_path_main) >= 1:
        __main_img_path = img_path_main[0]

    if __main_img_path:
        __copy_img_to_thumb(str(out_dir_thumb_img), __main_img_path)


def resize_image(path: str | Path, width: int = 640, height: int = 480, output_path: str | Path | None = None) -> str:
    """Resize an image to the specified width and height while maintaining its aspect ratio.

    Args:
        path (str | Path): The path to the image file.
        width (int, optional): The target width of the resized image. Defaults to 640.
        height (int, optional): The target height of the resized image. Defaults to 480.
        output_path (str | Path | None, optional): The path where the resized image will be saved. If None, the original image will be overwritten.

    Raises:
        StructuredError: If the width or height is less than or equal to 0.

    Returns:
        NoReturn: This function does not return a value.

    """
    if width <= 0 or height <= 0:
        msg = "Width and height must be greater than 0."
        raise StructuredError(msg)

    image_path = str(path) if isinstance(path, Path) else path
    if output_path is None:
        _output_path = image_path
    elif isinstance(output_path, Path):
        _output_path = str(output_path)
    else:
        _output_path = output_path

    try:
        resize_image_aspect_ratio(image_path, _output_path, width, height)
    except Exception as e:
        msg = f"Failed to resize image: {e}"
        raise StructuredError(msg) from e

    return _output_path
