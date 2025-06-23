# Image to Thumbnail Module

The `rdetoolkit.img2thumb` module provides specialized functionality for creating and managing thumbnail images in RDE (Research Data Exchange) processing workflows. This module handles image copying, resizing operations, and thumbnail generation with comprehensive error handling and format support.

## Overview

The img2thumb module offers essential image processing capabilities for RDE workflows:

- **Thumbnail Generation**: Automated creation of thumbnail images from source images
- **Image Copying**: Efficient copying of images between directories with format validation
- **Aspect Ratio Preservation**: Intelligent resizing that maintains original image proportions
- **Multiple Format Support**: Support for common image formats (JPG, PNG, GIF, BMP, SVG, WebP)
- **Flexible Target Selection**: Options for selecting specific images or automatic selection
- **Error Handling**: Comprehensive error management with structured exceptions
- **Path Flexibility**: Support for both string and Path object inputs

## Functions

### copy_images_to_thumbnail

Copy image files from main image directories to thumbnail folders with optional filtering.

```python
def copy_images_to_thumbnail(
    out_dir_thumb_img: str | Path,
    out_dir_main_img: str | Path,
    *,
    target_image_name: str | None = None,
    img_ext: str | None = None,
) -> None
```

**Parameters:**
- `out_dir_thumb_img` (str | Path): Directory path where thumbnail images will be saved
- `out_dir_main_img` (str | Path): Directory path where main images are located
- `target_image_name` (str | None): Specific image file name to copy (optional)
- `img_ext` (str | None): Specific image file extension to filter (optional)

**Returns:**
- `None`

**Raises:**
- Decorated with error handling that catches exceptions and converts them to structured errors with code 50

**Supported Image Formats:**
- `.jpg`, `.jpeg` - JPEG images
- `.png` - PNG images
- `.gif` - GIF images
- `.bmp` - Bitmap images
- `.svg` - SVG vector images
- `.webp` - WebP images

**Behavior:**
- If `target_image_name` is specified, searches for that specific image file
- If multiple images exist and no target is specified, copies the first image found
- Performs recursive search in subdirectories when looking for target image
- Preserves original file names in the thumbnail directory

**Example:**

```python
from rdetoolkit.img2thumb import copy_images_to_thumbnail
from pathlib import Path

# Basic usage - copy first available image
thumbnail_dir = Path("data/thumbnail")
main_image_dir = Path("data/main_image")

copy_images_to_thumbnail(
    out_dir_thumb_img=thumbnail_dir,
    out_dir_main_img=main_image_dir
)

# Copy specific image by name
copy_images_to_thumbnail(
    out_dir_thumb_img="data/thumbnail",
    out_dir_main_img="data/main_image",
    target_image_name="sample_image.jpg"
)

# Filter by specific extension
copy_images_to_thumbnail(
    out_dir_thumb_img="data/thumbnail",
    out_dir_main_img="data/main_image",
    img_ext=".png"
)

# Batch processing example
def process_multiple_image_sets(image_sets: list[dict]) -> None:
    """Process multiple sets of images for thumbnail generation."""

    for image_set in image_sets:
        try:
            copy_images_to_thumbnail(
                out_dir_thumb_img=image_set["thumbnail_dir"],
                out_dir_main_img=image_set["main_dir"],
                target_image_name=image_set.get("target_name"),
                img_ext=image_set.get("extension")
            )
            print(f"✓ Processed: {image_set['main_dir']}")
        except Exception as e:
            print(f"✗ Failed: {image_set['main_dir']} - {e}")

# Example usage
image_configurations = [
    {
        "thumbnail_dir": "data/experiment1/thumbnail",
        "main_dir": "data/experiment1/main_image",
        "target_name": "result_plot.png"
    },
    {
        "thumbnail_dir": "data/experiment2/thumbnail",
        "main_dir": "data/experiment2/main_image",
        "extension": ".jpg"
    }
]

process_multiple_image_sets(image_configurations)
```

### resize_image

Resize an image to specified dimensions while maintaining aspect ratio.

```python
def resize_image(
    path: str | Path,
    width: int = 640,
    height: int = 480,
    output_path: str | Path | None = None
) -> str
```

**Parameters:**
- `path` (str | Path): Path to the source image file
- `width` (int): Target width in pixels (default: 640)
- `height` (int): Target height in pixels (default: 480)
- `output_path` (str | Path | None): Output path for resized image (optional, defaults to overwriting original)

**Returns:**
- `str`: Path to the resized image file

**Raises:**
- `StructuredError`: If width or height is less than or equal to 0
- `StructuredError`: If image resizing fails due to file issues or invalid image format

**Features:**
- Maintains original image aspect ratio during resizing
- Supports all common image formats
- Flexible output path specification
- Automatic path type conversion
- Comprehensive error handling with detailed messages

**Example:**

```python
from rdetoolkit.img2thumb import resize_image
from rdetoolkit.exceptions import StructuredError
from pathlib import Path

# Basic resizing with default dimensions (640x480)
try:
    output_path = resize_image("data/images/large_photo.jpg")
    print(f"Image resized and saved to: {output_path}")
except StructuredError as e:
    print(f"Resize failed: {e}")

# Custom dimensions with separate output file
input_image = Path("data/images/high_res_chart.png")
output_image = Path("data/thumbnails/chart_thumb.png")

try:
    result_path = resize_image(
        path=input_image,
        width=320,
        height=240,
        output_path=output_image
    )
    print(f"Thumbnail created: {result_path}")
except StructuredError as e:
    print(f"Thumbnail creation failed: {e}")

# Batch resizing with different sizes
def create_multiple_thumbnails(source_image: Path, output_dir: Path) -> dict[str, str]:
    """Create thumbnails in multiple sizes."""

    output_dir.mkdir(parents=True, exist_ok=True)

    thumbnail_sizes = {
        "small": (160, 120),
        "medium": (320, 240),
        "large": (640, 480),
        "extra_large": (1024, 768)
    }

    results = {}

    for size_name, (width, height) in thumbnail_sizes.items():
        try:
            output_filename = f"{source_image.stem}_{size_name}{source_image.suffix}"
            output_path = output_dir / output_filename

            result_path = resize_image(
                path=source_image,
                width=width,
                height=height,
                output_path=output_path
            )

            results[size_name] = result_path
            print(f"✓ Created {size_name} thumbnail: {width}x{height}")

        except StructuredError as e:
            print(f"✗ Failed to create {size_name} thumbnail: {e}")
            results[size_name] = None

    return results

# Usage example
source_img = Path("data/images/sample_photo.jpg")
thumb_dir = Path("data/thumbnails/sample_photo")

if source_img.exists():
    thumbnail_results = create_multiple_thumbnails(source_img, thumb_dir)

    successful_thumbs = [size for size, path in thumbnail_results.items() if path]
    print(f"Successfully created {len(successful_thumbs)} thumbnails: {successful_thumbs}")

# Validation and error handling example
def safe_resize_with_validation(
    image_path: Path,
    target_width: int,
    target_height: int,
    output_dir: Path
) -> bool:
    """Safely resize image with comprehensive validation."""

    # Validate input parameters
    if target_width <= 0 or target_height <= 0:
        print(f"Invalid dimensions: {target_width}x{target_height}")
        return False

    if not image_path.exists():
        print(f"Source image not found: {image_path}")
        return False

    # Check if file is actually an image
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}
    if image_path.suffix.lower() not in valid_extensions:
        print(f"Invalid image format: {image_path.suffix}")
        return False

    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output path
        output_filename = f"{image_path.stem}_resized_{target_width}x{target_height}{image_path.suffix}"
        output_path = output_dir / output_filename

        # Resize image
        result_path = resize_image(
            path=image_path,
            width=target_width,
            height=target_height,
            output_path=output_path
        )

        print(f"✓ Image resized successfully: {result_path}")
        return True

    except StructuredError as e:
        print(f"✗ Resize operation failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

# Usage
image_file = Path("data/images/test_image.png")
output_directory = Path("data/processed")

success = safe_resize_with_validation(
    image_path=image_file,
    target_width=800,
    target_height=600,
    output_dir=output_directory
)
```

## See Also

- [Core Module](core.md) - For resize_image_aspect_ratio function used internally
- [Error Handling](errors.md) - For catch_exception_with_message decorator
- [Exceptions](exceptions.md) - For StructuredError exception type
- [Workflows](workflows.md) - For integration with RDE processing workflows
- [Mode Processing](modeproc.md) - For image processing in different modes
- [Usage - Structured Process](../usage/structured_process/structured.md) - For image processing in RDE workflows
