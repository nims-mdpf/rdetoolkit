import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from rdetoolkit.img2thumb import copy_images_to_thumbnail, resize_image
from rdetoolkit.exceptions import StructuredError


@pytest.fixture
def dummy_out_dir_thumb():
    temp_dir_path = Path("tests", "img")
    temp_dir_path.mkdir(parents=True, exist_ok=True)

    OUT_DIR_THUB_IMG = temp_dir_path.joinpath("thumb_img")
    OUT_DIR_THUB_IMG.mkdir(parents=True, exist_ok=True)

    yield OUT_DIR_THUB_IMG

    if os.path.exists(temp_dir_path):
        shutil.rmtree(temp_dir_path)


@pytest.fixture
def dummy_out_dir_main():
    temp_dir_path = Path("tests", "img")
    temp_dir_path.mkdir(parents=True, exist_ok=True)

    OUT_DIR_MAIN_IMG = temp_dir_path.joinpath("main_img")
    OUT_DIR_MAIN_IMG.mkdir(parents=True, exist_ok=True)

    yield OUT_DIR_MAIN_IMG

    if os.path.exists(temp_dir_path):
        shutil.rmtree(temp_dir_path)


@pytest.fixture
def dummy_out_dir_other():
    temp_dir_path = Path("tests", "img")
    temp_dir_path.mkdir(parents=True, exist_ok=True)

    OUT_DIR_OTHER_IMG = temp_dir_path.joinpath("other_img")
    OUT_DIR_OTHER_IMG.mkdir(parents=True, exist_ok=True)

    yield OUT_DIR_OTHER_IMG

    if os.path.exists(temp_dir_path):
        shutil.rmtree(temp_dir_path)


def test_copy_images_to_thumbnail(dummy_out_dir_thumb, dummy_out_dir_main, dummy_out_dir_other):
    """Main画像フォルダにあるファイル1つがサムネイルフォルダにファイルがコピーされるかテスト"""
    # Create dummy image file
    with open(dummy_out_dir_main.joinpath("dummy_main_img.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_other.joinpath("dummy_other_img.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_other.joinpath("dummy_other_img2.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_other.joinpath("dummy_other_img3.png"), "w") as f:
        f.write("dummy")
    # Run the function
    copy_images_to_thumbnail(dummy_out_dir_thumb, dummy_out_dir_main)

    assert len(list(dummy_out_dir_thumb.glob("*"))) == 1


def test_only_one_representative_image_exists(dummy_out_dir_thumb, dummy_out_dir_main, dummy_out_dir_other):
    """thumbnailフォルダにファイル名!_とついたファイル数が0かチェックするテスト
    RDE v5に伴う仕様の変更により、!_をファイルの先頭に付与する必要がなくなったため
    """
    # Create dummy image file
    with open(dummy_out_dir_main.joinpath("dummy_main_img.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_other.joinpath("dummy_other_img.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_other.joinpath("dummy_other_img2.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_other.joinpath("dummy_other_img3.png"), "w") as f:
        f.write("dummy")
    # Run the function
    copy_images_to_thumbnail(dummy_out_dir_thumb, dummy_out_dir_main)

    representative_imgs = list(dummy_out_dir_thumb.glob("!_*"))
    assert len(representative_imgs) == 0


def test_specifying_a_file(dummy_out_dir_thumb, dummy_out_dir_main, dummy_out_dir_other):
    """main_imageに存在する指定したファイル名の画像が代表画像にコピーされるかテスト"""
    # Create dummy image file
    with open(dummy_out_dir_main.joinpath("dummy_main_img1.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_main.joinpath("dummy_main_img2.png"), "w") as f:
        f.write("dummy")
    with open(dummy_out_dir_main.joinpath("dummy_main_img3.png"), "w") as f:
        f.write("dummy")
    # Run the function
    copy_images_to_thumbnail(dummy_out_dir_thumb, dummy_out_dir_main, target_image_name="dummy_main_img3.png")

    assert dummy_out_dir_thumb.joinpath("dummy_main_img3.png").exists()


def test_copy_images_to_thumbnail_mismatch_extension(dummy_out_dir_thumb, dummy_out_dir_main):
    """拡張子が指定と違った場合、ファイルがコピーされないことを確認するテスト"""
    # Create dummy image file
    with open(dummy_out_dir_main.joinpath("dummy_main_img.jpg"), "w") as f:
        f.write("dummy")
    # Run the function
    copy_images_to_thumbnail(dummy_out_dir_thumb, dummy_out_dir_main)

    assert not os.path.isfile(dummy_out_dir_thumb.joinpath("!_dummy_main_img.png"))


def test_resize_image():
    """resize_image_aspect_ratioが正しく呼び出され、画像がリサイズされるかテスト"""
    image_path = "dummy_image.jpg"
    output_path = "dummy_image_resized.jpg"
    width = 300
    height = 300

    with patch("rdetoolkit.img2thumb.resize_image_aspect_ratio") as mock_resize_image_aspect_ratio:
        mock_resize_image_aspect_ratio.return_value = None  # Set mock return value

        result = resize_image(image_path, width, height, output_path)

        mock_resize_image_aspect_ratio.assert_called_once_with(image_path, output_path, width, height)
        assert result == output_path


def test_resize_image_invalid_dimensions():
    """無効な画像サイズが指定された場合に例外が発生するかテスト"""
    image_path = "dummy_image.jpg"
    width = 0
    height = 300

    with pytest.raises(StructuredError, match="Width and height must be greater than 0."):
        resize_image(image_path, width, height)


def test_resize_image_exception_handling():
    """resize_image_aspect_ratioで例外が発生した場合にStructuredErrorが発生するかテスト"""
    image_path = "dummy_image.jpg"
    output_path = "dummy_image_resized.jpg"
    width = 300
    height = 300

    with patch("rdetoolkit.img2thumb.resize_image_aspect_ratio") as mock_resize_image_aspect_ratio:
        mock_resize_image_aspect_ratio.side_effect = Exception("Mocked exception")

        with pytest.raises(StructuredError, match="Failed to resize image: Mocked exception"):
            resize_image(image_path, width, height, output_path)
