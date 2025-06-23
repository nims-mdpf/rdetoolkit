# Thumbnail Processing Processor

The `rdetoolkit.processing.processors.thumbnails` module provides a processor for generating thumbnail images from source images. This processor creates optimized thumbnail versions of images for quick preview and display purposes.

## Overview

The thumbnail processor provides:

- **Automatic Thumbnail Generation**: Create thumbnails from main image files
- **Conditional Processing**: Generate thumbnails only when enabled in configuration
- **Error Tolerance**: Non-critical processing that continues on errors
- **Image Optimization**: Efficient thumbnail creation with appropriate sizing
- **Batch Processing**: Handle multiple images in a single processing run

## Classes

### ThumbnailGenerator

Generates thumbnail images from source images in the main_image directory.

#### Constructor

```python
ThumbnailGenerator()
```

No parameters required. Inherits from `Processor` base class.

#### Methods

##### process(context)

Generate thumbnails if enabled in configuration.

```python
def process(context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing configuration and resource paths

**Returns:**
- `None`

**Raises:**
- Does not raise exceptions for thumbnail generation failures (logs warnings instead)

**Example:**
```python
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator

generator = ThumbnailGenerator()
generator.process(context)  # Generates thumbnails if enabled
```

**Required Context Attributes:**
- `context.srcpaths.config.system.save_thumbnail_image`: Boolean flag to enable/disable thumbnail generation
- `context.resource_paths.thumbnail`: Path to thumbnail output directory
- `context.resource_paths.main_image`: Path to main image source directory

**Processing Logic:**
1. Check if thumbnail generation is enabled in configuration
2. Verify main image directory contains image files
3. Generate thumbnails for all supported image formats
4. Save thumbnails to designated thumbnail directory
5. Handle errors gracefully without interrupting the processing pipeline

## Image Processing Details

### Supported Image Formats

The thumbnail generator supports common image formats:
- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **TIFF** (.tiff, .tif)
- **BMP** (.bmp)
- **GIF** (.gif)

### Thumbnail Specifications

- **Default Size**: Optimized for quick loading and display
- **Aspect Ratio**: Preserved from original images
- **Quality**: Balanced between file size and visual quality
- **Format**: Output format matches input format where possible

### Generation Process

1. **Source Detection**: Scan main_image directory for supported image files
2. **Size Calculation**: Calculate optimal thumbnail dimensions
3. **Image Processing**: Resize images while preserving aspect ratio
4. **Format Conversion**: Convert to appropriate thumbnail format
5. **Output**: Save thumbnails with consistent naming convention

## Complete Usage Examples

### Basic Thumbnail Generation

```python
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator
from rdetoolkit.processing.context import ProcessingContext
from pathlib import Path

# Create thumbnail generator
generator = ThumbnailGenerator()

# Create processing context with thumbnail generation enabled
context = ProcessingContext(
    srcpaths=srcpaths,  # srcpaths.config.system.save_thumbnail_image = True
    resource_paths=resource_paths,  # Contains thumbnail and main_image paths
    # ... other parameters
)

# Generate thumbnails
generator.process(context)
print("Thumbnail generation completed")
```

### Conditional Thumbnail Processing

```python
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator

def process_thumbnails_conditionally(context):
    """Generate thumbnails with configuration check."""

    # Check if thumbnail generation is enabled
    if not context.srcpaths.config.system.save_thumbnail_image:
        print("Thumbnail generation disabled, skipping")
        return

    # Check if main images exist
    main_image_path = context.resource_paths.main_image
    if not main_image_path.exists() or not any(main_image_path.iterdir()):
        print("No main images found for thumbnail generation")
        return

    # Generate thumbnails
    generator = ThumbnailGenerator()
    generator.process(context)
    print("Thumbnails generated successfully")

# Usage
process_thumbnails_conditionally(context)
```

### Thumbnail Generation with Monitoring

```python
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator
from pathlib import Path
import logging

def generate_thumbnails_with_monitoring(context):
    """Generate thumbnails with detailed monitoring."""

    logger = logging.getLogger(__name__)

    # Pre-processing checks
    main_image_dir = context.resource_paths.main_image
    thumbnail_dir = context.resource_paths.thumbnail

    if not main_image_dir.exists():
        logger.warning(f"Main image directory not found: {main_image_dir}")
        return

    # Count source images
    image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif'}
    source_images = [
        f for f in main_image_dir.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]

    logger.info(f"Found {len(source_images)} source images for thumbnail generation")

    # Generate thumbnails
    generator = ThumbnailGenerator()
    generator.process(context)

    # Post-processing verification
    if thumbnail_dir.exists():
        thumbnail_files = list(thumbnail_dir.glob('*'))
        logger.info(f"Generated {len(thumbnail_files)} thumbnail files")

        # Log thumbnail details
        for thumb_file in thumbnail_files:
            size = thumb_file.stat().st_size
            logger.debug(f"Thumbnail: {thumb_file.name} ({size} bytes)")
    else:
        logger.warning("Thumbnail directory not created")

# Usage
generate_thumbnails_with_monitoring(context)
```

### Batch Thumbnail Processing

```python
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator
from pathlib import Path

def batch_thumbnail_processing(contexts):
    """Process thumbnails for multiple datasets."""

    generator = ThumbnailGenerator()
    results = []

    for i, context in enumerate(contexts):
        print(f"Processing thumbnails for dataset {i+1}/{len(contexts)}")

        try:
            # Check configuration
            if context.srcpaths.config.system.save_thumbnail_image:
                generator.process(context)
                results.append({
                    "dataset": i,
                    "status": "completed",
                    "thumbnail_dir": str(context.resource_paths.thumbnail)
                })
            else:
                results.append({
                    "dataset": i,
                    "status": "skipped",
                    "reason": "thumbnail generation disabled"
                })

        except Exception as e:
            # This should rarely happen as ThumbnailGenerator handles errors internally
            results.append({
                "dataset": i,
                "status": "error",
                "error": str(e)
            })

    return results

# Create multiple contexts for batch processing
contexts = [
    ProcessingContext(
        resource_paths=ResourcePaths(
            main_image=Path(f"dataset_{i}/main_image"),
            thumbnail=Path(f"dataset_{i}/thumbnail")
        ),
        srcpaths=srcpaths
    )
    for i in range(5)
]

# Process batch
results = batch_thumbnail_processing(contexts)
completed = len([r for r in results if r['status'] == 'completed'])
print(f"Processed thumbnails for {completed} datasets")
```

### Custom Thumbnail Workflow

```python
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator
from pathlib import Path
import shutil

class ThumbnailWorkflow:
    """Custom workflow for thumbnail processing with additional features."""

    def __init__(self, backup_enabled=False):
        self.backup_enabled = backup_enabled
        self.processing_stats = {
            "processed": 0,
            "skipped": 0,
            "errors": 0
        }

    def process_with_backup(self, context):
        """Process thumbnails with optional backup."""

        thumbnail_dir = context.resource_paths.thumbnail

        # Create backup if enabled
        backup_dir = None
        if self.backup_enabled and thumbnail_dir.exists():
            backup_dir = self._create_backup(thumbnail_dir)

        try:
            # Generate thumbnails
            generator = ThumbnailGenerator()
            generator.process(context)

            self.processing_stats["processed"] += 1
            return True

        except Exception as e:
            self.processing_stats["errors"] += 1

            # Restore backup if generation failed
            if backup_dir:
                self._restore_backup(backup_dir, thumbnail_dir)

            print(f"Thumbnail processing failed: {e}")
            return False

    def _create_backup(self, thumbnail_dir: Path) -> Path:
        """Create backup of existing thumbnails."""
        backup_dir = thumbnail_dir.parent / f"{thumbnail_dir.name}_backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(thumbnail_dir, backup_dir)
        return backup_dir

    def _restore_backup(self, backup_dir: Path, thumbnail_dir: Path):
        """Restore thumbnails from backup."""
        if thumbnail_dir.exists():
            shutil.rmtree(thumbnail_dir)
        shutil.copytree(backup_dir, thumbnail_dir)
        shutil.rmtree(backup_dir)  # Clean up backup

    def get_statistics(self):
        """Get processing statistics."""
        return self.processing_stats.copy()

# Usage
workflow = ThumbnailWorkflow(backup_enabled=True)
success = workflow.process_with_backup(context)
stats = workflow.get_statistics()
print(f"Processing stats: {stats}")
```

### Thumbnail Quality Verification

```python
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator
from pathlib import Path
from PIL import Image
import logging

def verify_thumbnail_quality(context):
    """Generate thumbnails and verify quality."""

    logger = logging.getLogger(__name__)

    # Generate thumbnails
    generator = ThumbnailGenerator()
    generator.process(context)

    # Verify generated thumbnails
    thumbnail_dir = context.resource_paths.thumbnail
    main_image_dir = context.resource_paths.main_image

    if not thumbnail_dir.exists():
        logger.warning("No thumbnail directory created")
        return

    # Check each thumbnail
    verification_results = []

    for thumb_file in thumbnail_dir.iterdir():
        if thumb_file.is_file():
            try:
                # Open and verify thumbnail
                with Image.open(thumb_file) as img:
                    width, height = img.size
                    format_name = img.format

                    # Find corresponding source image
                    source_file = find_source_image(thumb_file.stem, main_image_dir)

                    verification_results.append({
                        "thumbnail": thumb_file.name,
                        "size": f"{width}x{height}",
                        "format": format_name,
                        "source_found": source_file is not None,
                        "file_size": thumb_file.stat().st_size
                    })

            except Exception as e:
                logger.error(f"Failed to verify thumbnail {thumb_file}: {e}")
                verification_results.append({
                    "thumbnail": thumb_file.name,
                    "error": str(e)
                })

    # Log verification results
    valid_thumbnails = [r for r in verification_results if "error" not in r]
    logger.info(f"Verified {len(valid_thumbnails)} valid thumbnails")

    return verification_results

def find_source_image(thumb_stem: str, main_image_dir: Path) -> Path:
    """Find source image for thumbnail."""
    extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif']

    for ext in extensions:
        source_file = main_image_dir / f"{thumb_stem}{ext}"
        if source_file.exists():
            return source_file

    return None

# Usage
results = verify_thumbnail_quality(context)
print(f"Verification completed for {len(results)} thumbnails")
```

## Integration with Processing Pipeline

### Pipeline Integration

```python
from rdetoolkit.processing.pipeline import ProcessingPipeline
from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator

# Create processing pipeline
pipeline = ProcessingPipeline()

# Add processors in logical order
# pipeline.add_processor(FileProcessor())  # Copy images to main_image
# pipeline.add_processor(ImageProcessor())  # Process main images

# Add thumbnail generator after image processing
pipeline.add_processor(ThumbnailGenerator())

# Add final processors
# pipeline.add_processor(ValidationProcessor())

# Execute pipeline
pipeline.process(context)
```

### Conditional Pipeline Processing

```python
def create_image_processing_pipeline(config):
    """Create pipeline with conditional thumbnail generation."""

    pipeline = ProcessingPipeline()

    # Add standard image processors
    pipeline.add_processor(ImageFileProcessor())
    pipeline.add_processor(ImageResizer())

    # Add thumbnail generator only if enabled
    if config.system.save_thumbnail_image:
        pipeline.add_processor(ThumbnailGenerator())

    return pipeline

# Usage
pipeline = create_image_processing_pipeline(config)
pipeline.process(context)
```

## Error Handling

### Error Tolerance

The ThumbnailGenerator is designed to be error-tolerant:

```python
# Internal error handling (from the processor implementation)
try:
    img2thumb.copy_images_to_thumbnail(
        context.resource_paths.thumbnail,
        context.resource_paths.main_image,
    )
    logger.debug("Thumbnail generation completed successfully")
except Exception as e:
    logger.warning(f"Thumbnail generation failed: {str(e)}")
    # Don't raise the exception as thumbnail generation is not critical
```

### Best Practices

1. **Always check configuration** before processing:
   ```python
   if context.srcpaths.config.system.save_thumbnail_image:
       generator.process(context)
   else:
       logger.debug("Thumbnail generation disabled")
   ```

2. **Verify source images exist**:
   ```python
   main_image_dir = context.resource_paths.main_image
   if main_image_dir.exists() and any(main_image_dir.iterdir()):
       generator.process(context)
   else:
       logger.info("No source images found for thumbnail generation")
   ```

3. **Handle thumbnail generation as optional**:
   ```python
   try:
       generator.process(context)
   except Exception as e:
       # Thumbnail generation failures should not stop processing
       logger.warning(f"Thumbnail generation failed, continuing: {e}")
   ```

4. **Monitor disk space for thumbnail storage**:
   ```python
   import shutil

   # Check available space
   total, used, free = shutil.disk_usage(context.resource_paths.thumbnail.parent)
   if free < estimated_thumbnail_size:
       logger.warning("Low disk space, thumbnail generation may fail")
   ```

## Configuration Dependencies

### System Configuration

Thumbnail processing depends on system configuration:

```yaml
system:
  save_thumbnail_image: true  # Enable thumbnail generation
```

### Directory Structure

Thumbnail processing requires:
- **Main Image Directory**: `context.resource_paths.main_image` containing source images
- **Thumbnail Directory**: `context.resource_paths.thumbnail` for output thumbnails

### Image Processing Dependencies

- **img2thumb module**: Core image processing functionality
- **PIL/Pillow**: Image processing library (dependency of img2thumb)
- **Supported formats**: Depends on PIL/Pillow installation

## Performance Notes

- Thumbnail generation is CPU-intensive for large images
- Processing is optimized for batch operations on multiple images
- Memory usage is managed efficiently during image processing
- Error handling is designed to not interrupt the processing pipeline
- Thumbnail generation is performed in parallel where possible

## Use Cases

### Common Use Cases

1. **Web Display**: Generate thumbnails for web-based image galleries
2. **Quick Preview**: Create small images for rapid preview in applications
3. **Index Generation**: Generate image indexes with thumbnail previews
4. **Bandwidth Optimization**: Reduce bandwidth usage for image previews
5. **Mobile Applications**: Provide optimized images for mobile displays

### Example Directory Structure

```
project/
├── main_image/           # Source images
│   ├── image001.jpg
│   ├── image002.png
│   └── image003.tiff
└── thumbnail/            # Generated thumbnails
    ├── image001.jpg      # Thumbnail version
    ├── image002.png      # Thumbnail version
    └── image003.jpg      # Converted thumbnail
```

## See Also

- [Processing Context](../context.md) - For understanding processing context structure
- [Pipeline Documentation](../pipeline.md) - For processor pipeline integration
- [Image Processing](../../img2thumb.md) - For core image processing utilities
- [Configuration Guide](../../config.md) - For system configuration options
