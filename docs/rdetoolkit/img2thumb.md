# Img2Thumb API

## Purpose

This module handles processing of representative images (thumbnail images) in RDEToolKit. It provides functionality for identifying main images, generating thumbnails, and managing image files.

## Key Features

### Image Processing
- Automatic identification of main images
- Generation and copying of thumbnail images
- Image file format conversion and resizing

### File Management
- Image extraction from raw data files
- Placement in thumbnail directory
- Standardization of image paths

---

::: src.rdetoolkit.img2thumb.copy_images_to_thumbnail

---

::: src.rdetoolkit.img2thumb.resize_image

---

## Practical Usage

### Basic Thumbnail Generation

```python title="basic_thumbnail.py"
from rdetoolkit.img2thumb import copy_images_to_thumbnail, resize_image
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from pathlib import Path

# Configure resource paths
resource_paths = RdeOutputResourcePath(
    rawfiles=Path("data/rawfiles"),
    thumbnail=Path("data/thumbnail"),
    meta=Path("data/meta"),
    invoice=Path("data/invoice")
)

# Copy image files to thumbnail directory
copy_images_to_thumbnail(resource_paths)
print("Copied image files to thumbnail directory")
```

### Image Resize Processing

```python title="image_resize.py"
from rdetoolkit.img2thumb import resize_image
from pathlib import Path

# Resize image
input_image = Path("data/rawfiles/large_image.jpg")
output_image = Path("data/thumbnail/resized_image.jpg")

# Resize to specified dimensions
resize_image(input_image, output_image, width=800, height=600)
print(f"Image resized: {output_image}")

# Resize while maintaining aspect ratio
resize_image(input_image, output_image, max_size=500)
print(f"Image resized maintaining aspect ratio: {output_image}")
```

### Batch Image File Processing

```python title="batch_image_processing.py"
from rdetoolkit.img2thumb import copy_images_to_thumbnail, resize_image
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from pathlib import Path

def process_experiment_images(experiment_dir: Path):
    """Batch process images in experiment directory"""
    
    # Configure resource paths
    resource_paths = RdeOutputResourcePath(
        rawfiles=experiment_dir / "rawfiles",
        thumbnail=experiment_dir / "thumbnail",
        meta=experiment_dir / "meta",
        invoice=experiment_dir / "invoice"
    )
    
    # Create thumbnail directory
    resource_paths.thumbnail.mkdir(parents=True, exist_ok=True)
    
    # Copy image files
    try:
        copy_images_to_thumbnail(resource_paths)
        print(f"✓ Image copy completed: {resource_paths.thumbnail}")
        
        # Resize each image
        for image_file in resource_paths.thumbnail.glob("*.{jpg,jpeg,png,gif}"):
            resized_file = resource_paths.thumbnail / f"resized_{image_file.name}"
            resize_image(image_file, resized_file, max_size=300)
            print(f"✓ Resize completed: {resized_file}")
            
        return {"status": "success", "processed_count": len(list(resource_paths.thumbnail.glob("resized_*")))}
            
    except Exception as e:
        print(f"✗ Image processing error: {e}")
        return {"status": "error", "error": str(e)}

# Usage example
experiment_dirs = [
    Path("experiments/exp_001"),
    Path("experiments/exp_002"),
    Path("experiments/exp_003")
]

for exp_dir in experiment_dirs:
    if exp_dir.exists():
        print(f"\nProcessing experiment directory: {exp_dir}")
        result = process_experiment_images(exp_dir)
        print(f"Processing result: {result}")
```
