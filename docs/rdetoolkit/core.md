# Core Module

The `rdetoolkit.core` module provides essential functionality implemented in Rust for high-performance operations. This module includes directory management utilities, image processing functions, and file encoding detection capabilities.

## Overview

The core module is built using PyO3 and provides Python bindings for Rust implementations of performance-critical operations:

- **Directory Management**: Efficient directory creation and management with support for indexed subdirectories
- **Image Processing**: High-performance image resizing with aspect ratio preservation
- **File Operations**: Fast encoding detection and file reading with automatic encoding handling

## Classes

### ManagedDirectory

A directory manager that handles index-based subdirectories with automatic path construction.

#### Constructor

```python
ManagedDirectory(base_dir: str, dirname: str, n_digit: Optional[int] = None, idx: Optional[int] = None)
```

**Parameters:**
- `base_dir` (str): Base directory path
- `dirname` (str): Directory name to manage
- `n_digit` (Optional[int]): Number of digits for index formatting (default: 4)
- `idx` (Optional[int]): Initial index (default: 0)

#### Attributes

- `path` (str): The full path to the managed directory
- `idx` (int): Current index of the directory

#### Methods

##### create()

Create the managed directory if it doesn't exist.

```python
def create() -> None
```

**Raises:**
- `OSError`: If directory creation fails

**Example:**
```python
from rdetoolkit.core import ManagedDirectory

# Create a managed directory
managed_dir = ManagedDirectory("/data", "output")
managed_dir.create()  # Creates /data/output
```

##### list()

List all files and directories in the managed directory.

```python
def list() -> list[str]
```

**Returns:**
- `list[str]`: List of paths as strings

**Raises:**
- `FileNotFoundError`: If the directory does not exist
- `OSError`: If reading the directory fails

**Example:**
```python
# List contents of the managed directory
contents = managed_dir.list()
print(contents)  # ['file1.txt', 'subdir', ...]
```

##### \_\_call\_\_(idx)

Create a new ManagedDirectory instance with the specified index.

```python
def __call__(idx: int) -> ManagedDirectory
```

**Parameters:**
- `idx` (int): Index for the new directory

**Returns:**
- `ManagedDirectory`: New instance with the specified index

**Raises:**
- `ValueError`: If idx is negative
- `OSError`: If directory creation fails

**Example:**
```python
# Create indexed subdirectories
base_dir = ManagedDirectory("/data", "output")
indexed_dir = base_dir(1)  # Creates /data/divided/0001/output
```

#### Directory Path Structure

The directory path is constructed as follows:

- **For idx=0**: `{base_dir}/{dirname}`
- **For idx>0**: `{base_dir}/divided/{idx:0{n_digit}d}/{dirname}`

**Example:**
```python
# Base directory (idx=0)
dir0 = ManagedDirectory("/data", "docs")
print(dir0.path)  # "/data/docs"

# Indexed directory
dir1 = dir0(1)
print(dir1.path)  # "/data/divided/0001/docs"

dir2 = dir0(10)
print(dir2.path)  # "/data/divided/0010/docs"
```

### DirectoryOps

Utility class for managing multiple directories with support for indexed subdirectories.

#### Constructor

```python
DirectoryOps(base_dir: str, n_digit: Optional[int] = None)
```

**Parameters:**
- `base_dir` (str): Base directory path
- `n_digit` (Optional[int]): Number of digits for index formatting (default: 4)

#### Methods

##### \_\_getattr\_\_(name)

Access directories via attribute-style notation.

```python
def __getattr__(name: str) -> ManagedDirectory
```

**Parameters:**
- `name` (str): Directory name

**Returns:**
- `ManagedDirectory`: New ManagedDirectory instance for the specified directory

**Example:**
```python
from rdetoolkit.core import DirectoryOps

ops = DirectoryOps("/data")
invoice_dir = ops.invoice  # Creates ManagedDirectory for "invoice"
raw_dir = ops.raw         # Creates ManagedDirectory for "raw"
```

##### all(idx)

Create all supported directories and optionally their indexed subdirectories.

```python
def all(idx: Optional[int] = None) -> list[str]
```

**Parameters:**
- `idx` (Optional[int]): Maximum index for divided subdirectories

**Returns:**
- `list[str]`: List of created directory paths

**Raises:**
- `ValueError`: If idx is negative
- `OSError`: If directory creation fails

**Example:**
```python
# Create all base directories
ops = DirectoryOps("/data")
created_dirs = ops.all()

# Create base directories and indexed subdirectories
indexed_dirs = ops.all(2)  # Creates base + divided/0001, divided/0002 subdirs
```

#### Supported Directory Types

The following directories are automatically supported:

- `invoice`
- `raw`
- `structured`
- `main_image`
- `other_image`
- `thumbnail`
- `meta`
- `logs`
- `temp`
- `nonshared_raw`
- `invoice_patch`
- `attachment`

## Functions

### resize_image_aspect_ratio

Resize an image while preserving aspect ratio.

```python
def resize_image_aspect_ratio(input_path: str, output_path: str, width: int, height: int) -> None
```

**Parameters:**
- `input_path` (str): Path to the input image file
- `output_path` (str): Path where the resized image will be saved
- `width` (int): Target width in pixels
- `height` (int): Target height in pixels

**Raises:**
- `ValueError`: If width or height is zero or negative
- `IOError`: If input file cannot be read or output file cannot be written
- `OSError`: If file operations fail

**Example:**
```python
from rdetoolkit.core import resize_image_aspect_ratio

# Resize image to fit within 800x600 while preserving aspect ratio
resize_image_aspect_ratio(
    "input.jpg",
    "output.jpg",
    800,
    600
)
```

### detect_encoding

Detect the character encoding of a text file.

```python
def detect_encoding(path: str) -> str
```

**Parameters:**
- `path` (str): Path to the file

**Returns:**
- `str`: Detected encoding name (e.g., "utf-8", "shift_jis", "euc-jp")

**Raises:**
- `IOError`: If file not found or cannot be read
- `OSError`: If file operations fail

**Example:**
```python
from rdetoolkit.core import detect_encoding

# Detect encoding of a text file
encoding = detect_encoding("data.csv")
print(f"File encoding: {encoding}")  # File encoding: utf-8
```

### read_file_with_encoding

Read a file with automatic encoding detection.

```python
def read_file_with_encoding(file_path: str) -> str
```

**Parameters:**
- `file_path` (str): Path to the file to read

**Returns:**
- `str`: File contents as a string

**Raises:**
- `IOError`: If file not found or cannot be read
- `UnicodeDecodeError`: If file cannot be decoded
- `OSError`: If file operations fail

**Example:**
```python
from rdetoolkit.core import read_file_with_encoding

# Read file with automatic encoding detection
content = read_file_with_encoding("data.txt")
print(content)
```

## Complete Usage Examples

### Basic Directory Management

```python
from rdetoolkit.core import DirectoryOps

# Initialize directory operations
ops = DirectoryOps("/project/data")

# Create individual directories
invoice_dir = ops.invoice
invoice_dir.create()

raw_dir = ops.raw
raw_dir.create()

# Create all standard directories
all_dirs = ops.all()
print(f"Created {len(all_dirs)} directories")
```

### Working with Indexed Directories

```python
from rdetoolkit.core import DirectoryOps

ops = DirectoryOps("/project/data")

# Create directories for multiple datasets
for i in range(1, 4):
    # Create indexed subdirectories
    invoice_dir = ops.invoice(i)
    raw_dir = ops.raw(i)

    invoice_dir.create()  # /project/data/divided/0001/invoice
    raw_dir.create()      # /project/data/divided/0001/raw

    print(f"Created directories for dataset {i}")
```

### Image Processing Workflow

```python
from rdetoolkit.core import resize_image_aspect_ratio, DirectoryOps
from pathlib import Path

# Setup directories
ops = DirectoryOps("/project/data")
main_image_dir = ops.main_image
thumbnail_dir = ops.thumbnail

main_image_dir.create()
thumbnail_dir.create()

# Process images
input_images = Path("input").glob("*.jpg")

for img_path in input_images:
    # Create main image (resized)
    main_output = Path(main_image_dir.path) / img_path.name
    resize_image_aspect_ratio(
        str(img_path),
        str(main_output),
        1920, 1080
    )

    # Create thumbnail
    thumb_output = Path(thumbnail_dir.path) / f"thumb_{img_path.name}"
    resize_image_aspect_ratio(
        str(img_path),
        str(thumb_output),
        300, 200
    )
```

### File Encoding Detection and Processing

```python
from rdetoolkit.core import detect_encoding, read_file_with_encoding
from pathlib import Path

def process_text_files(directory: str):
    """Process all text files in a directory with encoding detection."""

    for file_path in Path(directory).glob("*.txt"):
        try:
            # Detect encoding
            encoding = detect_encoding(str(file_path))
            print(f"{file_path.name}: {encoding}")

            # Read with automatic encoding handling
            content = read_file_with_encoding(str(file_path))

            # Process content
            lines = content.splitlines()
            print(f"  Lines: {len(lines)}")

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

# Usage
process_text_files("/data/input")
```

## Error Handling

### Common Exceptions

The core module functions may raise the following exceptions:

#### OSError
Raised for general file system operations failures:
```python
try:
    managed_dir.create()
except OSError as e:
    print(f"Failed to create directory: {e}")
```

#### ValueError
Raised for invalid parameter values:
```python
try:
    resize_image_aspect_ratio("input.jpg", "output.jpg", 0, 100)
except ValueError as e:
    print(f"Invalid dimensions: {e}")
```

#### IOError
Raised for file I/O operations:
```python
try:
    encoding = detect_encoding("nonexistent.txt")
except IOError as e:
    print(f"File not found: {e}")
```

### Best Practices

1. **Always handle exceptions** when working with file operations:
   ```python
   try:
       content = read_file_with_encoding(file_path)
   except (IOError, UnicodeDecodeError) as e:
       print(f"Failed to read {file_path}: {e}")
   ```

2. **Validate inputs** before calling functions:
   ```python
   if width > 0 and height > 0:
       resize_image_aspect_ratio(input_path, output_path, width, height)
   else:
       print("Invalid dimensions")
   ```

3. **Use Path objects** for better path handling:
   ```python
   from pathlib import Path

   input_path = Path("data") / "input.jpg"
   if input_path.exists():
       resize_image_aspect_ratio(str(input_path), str(output_path), 800, 600)
   ```

4. **Create parent directories** when needed:
   ```python
   output_path = Path("output") / "processed" / "image.jpg"
   output_path.parent.mkdir(parents=True, exist_ok=True)
   resize_image_aspect_ratio(str(input_path), str(output_path), 800, 600)
   ```

## Performance Notes

- All functions in this module are implemented in Rust for optimal performance
- Image processing operations use efficient algorithms with minimal memory allocation
- Directory operations are optimized for batch creation of multiple directories
- Encoding detection uses fast heuristic algorithms suitable for large files

## See Also

- [Configuration Guide](../config.md) - For configuring directory structures
- [Workflows](../workflows.md) - For integrating core functions into processing workflows
- [File Operations](../fileops.md) - For additional file handling utilities
