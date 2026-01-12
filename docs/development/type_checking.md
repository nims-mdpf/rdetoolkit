# Type Checking in RDE Toolkit

## Overview
The RDE toolkit uses Python's type system with mypy for static type checking.
Enhanced type safety is provided through NewType and validated dataclasses.

## Type Categories

### NewType Definitions
NewType creates distinct types at compile time with zero runtime overhead:

- `ZipFilePath`, `ExcelInvoicePath`, `SmartTablePath`
- `InputDataDir`, `OutputDir`, `TemporaryDir`

Usage:
```python
from rdetoolkit.models.rde2types import ZipFilePath, create_zip_file_path

# Correct usage
zip_path: ZipFilePath = create_zip_file_path(Path("archive.zip"))

# Type error - can't assign Path to ZipFilePath
zip_path: ZipFilePath = Path("archive.zip")  # mypy error
```

### ValidatedPath Classes
Frozen dataclasses with runtime validation:

- `ZipFile`, `ExcelFile`, `CsvFile`, `JsonFile`
- `ValidatedDirectory` with optional existence checking

Usage:
```python
from rdetoolkit.models.rde2types import ZipFile

# Runtime validation of file extension
zip_file = ZipFile(Path("archive.zip"))  # OK
zip_file = ZipFile(Path("data.txt"))     # ValueError at runtime
```

### Collection Types
Type-safe file groupings:

- `FileGroup` - Typed collection of input files
- `ProcessedFileGroup` - Processed file results

## Running Type Checks

```bash
# Check all source code
tox -e mypy

# Check specific module
mypy src/rdetoolkit/models/rde2types.py

# Check with verbose output
mypy --verbose src/rdetoolkit/
```

## Type Checking Best Practices

1. **Prefer NewType for API boundaries** - Use at function signatures
2. **Use ValidatedPath for critical paths** - When validation is important
3. **Leverage FileGroup for collections** - Better than raw tuples
4. **Add type hints to new code** - All new functions should be typed
5. **Use `# type: ignore` sparingly** - Document why when used

## Migration from Legacy Types

Legacy type aliases remain for backward compatibility:
- `ZipFilesPathList`, `UnZipFilesPathList`, etc.

New code should prefer:
- NewType definitions for simple type distinction
- ValidatedPath classes for validated paths
- FileGroup for file collections

Migration should be gradual - no need to update all code at once.
