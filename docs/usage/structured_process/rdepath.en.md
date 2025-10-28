# Directory Path Retrieval Methods

## Purpose

This guide explains how to manage directory paths used for file I/O in RDE structured processing. The new `RdeDatasetPaths` class unifies `RdeInputDirPaths` and `RdeOutputResourcePath`; new implementations should prefer this single-object interface while legacy code can continue to rely on the separate classes.

## Recommended: Use `RdeDatasetPaths`

`RdeDatasetPaths` bundles input- and output-side paths into one object so dataset callbacks can accept a single argument. Configuration accessors and helper shortcuts are exposed on the same instance, keeping callback code concise.

### Preferred Dataset Signature

```python title="Preferred signature"
from rdetoolkit.models.rde2types import RdeDatasetPaths


def dataset(paths: RdeDatasetPaths) -> None:
    # List incoming CSV files
    for csv_file in paths.inputdata.glob("*.csv"):
        print(f"Input CSV: {csv_file}")

    # Structured data output directory
    struct_dir = paths.struct
    print(f"Structured output: {struct_dir}")
```

### Frequently Used Properties

- `paths.inputdata`: Input data directory; works with `Path.glob()` and similar utilities.
- `paths.invoice`: Input-side invoice directory.
- `paths.tasksupport`: Directory containing auxiliary data such as `metadata-def.json`.
- `paths.struct`: Structured data output directory.
- `paths.meta`: Metadata output directory.
- `paths.rawfiles`: Collected input files (per tile) after extraction or copying. Use this to determine the exact processing targets.
- `paths.raw` / `paths.nonshared_raw`: Output locations for raw data.
- `paths.main_image`, `paths.other_image`, `paths.thumbnail`: Image output locations.
- `paths.logs`: Directory for workflow log files.
- `paths.metadata_def_json`: Shortcut to `tasksupport/metadata-def.json`.

### Example: Reading Input Files

```python title="Reading with RdeDatasetPaths"
import pandas as pd
from rdetoolkit.models.rde2types import RdeDatasetPaths


def read_inputs(paths: RdeDatasetPaths) -> None:
    # rawfiles contains the finalized list of input artifacts for this tile
    for source in paths.rawfiles:
        df = pd.read_csv(source)
        print(f"{source.name} loaded: {df.shape}")
```

### Example: Writing Outputs

```python title="Saving with RdeDatasetPaths"
import json
from rdetoolkit.models.rde2types import RdeDatasetPaths


def save_results(paths: RdeDatasetPaths, payload: dict) -> None:
    output_path = paths.struct / "results.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta_path = paths.meta / "metadata.json"
    meta_path.write_text(
        json.dumps({"count": len(payload)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

## Compatibility and Legacy Style

Existing callbacks may still accept two arguments (`RdeInputDirPaths`, `RdeOutputResourcePath`). The toolkit keeps this signature for backward compatibility, but new structured processing code should adopt the unified single-argument form.

### Legacy Signature Example

```python title="Legacy usage (maintenance only)"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    print(srcpaths.inputdata)
    print(resource_paths.struct)
```

### Splitting Back into Legacy Arguments

When you must call older helpers, use `as_legacy_args()` to recover the original pair.

```python title="Bridging to legacy helpers"
from rdetoolkit.models.rde2types import RdeDatasetPaths


def dataset(paths: RdeDatasetPaths) -> None:
    srcpaths, resource_paths = paths.as_legacy_args()
    legacy_dataset(srcpaths, resource_paths)
```

## Verifying Outputs

`RdeDatasetPaths` also works for existence checks and file counts.

```python title="Output directory verification"
from rdetoolkit.models.rde2types import RdeDatasetPaths


def verify_outputs(paths: RdeDatasetPaths) -> None:
    for name, directory in {
        "structured": paths.struct,
        "meta": paths.meta,
        "raw": paths.raw,
        "main_image": paths.main_image,
    }.items():
        if directory.exists():
            print(f"{name} directory: {len(list(directory.iterdir()))} items")
        else:
            print(f"⚠️ {name} directory is missing")
```

## Related Information

- [Structuring Processing Concepts](structured.en.md)
- [Directory Structure Specification](directory.en.md)
- [Error Handling](errorhandling.en.md)
