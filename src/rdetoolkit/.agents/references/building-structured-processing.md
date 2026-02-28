# Building Structured Processing — Complete Pattern Guide

This reference enables an AI agent to autonomously build a complete RDE structured
processing program from scratch, given a user's input data file and requirements.

If the user provides specific directory structures or coding patterns, ALWAYS follow
the user's instructions. Use the patterns below only as defaults when the user does
not specify preferences.

## Development Process Overview

Follow these steps in order:

```
1. Analyze input data → understand file format, extract metadata candidates
2. Define metadata       → create metadata-def.json
3. Define schema         → create invoice.schema.json
4. Create invoice        → create invoice.json matching the schema
5. Implement dataset()   → build the processing function using Result type
6. Wire main.py          → connect dataset function to workflows.run()
7. Validate & test       → run CLI validation, then execute locally
```

---

## Step 1: Project Layout (Default Structure)

When the user does not specify a directory structure, use this standard layout:

```
.
├── modules/
│   └── custom_modules.py          # dataset() function and helpers
├── data/
│   ├── inputdata/
│   │   └── <user's data file>     # e.g., sample_data.ras, spectrum.csv
│   ├── invoice/
│   │   └── invoice.json           # Registration metadata (Step 4)
│   └── tasksupport/
│       ├── invoice.schema.json    # Schema definition (Step 3)
│       └── metadata-def.json      # Metadata field definitions (Step 2)
├── main.py                        # Entry point (Step 6)
├── rdeconfig.yaml                 # Optional: mode & behavior config
└── requirements.txt               # Additional Python dependencies
```

Initialize with:
```bash
python3 -m rdetoolkit init
```

---

## Step 2: RDE Support Directories (Output)

After running structured processing, rdetoolkit automatically creates these output
directories under `data/`. The agent must write outputs to the correct directories.

| Directory | Purpose | Agent writes here? |
|-----------|---------|-------------------|
| `inputdata/` | Input data files | No (read-only) |
| `invoice/` | Invoice (invoice.json) | No (pre-existing) |
| `tasksupport/` | Schema + metadata-def | No (pre-existing) |
| `structured/` | **Structured output files (CSV, JSON, etc.)** | **YES** |
| `meta/` | **Metadata file (metadata.json)** | **YES** (via Meta class) |
| `raw/` | Copy of original raw files | Optional |
| `main_image/` | Primary image for RDE dataset detail | Optional |
| `other_image/` | Additional images | Optional |
| `thumbnail/` | Thumbnail for RDE dataset list | Auto-generated |
| `nonshared_raw/` | Non-sharable raw files | Optional |
| `logs/` | Processing logs | Auto-generated |
| `temp/` | Temporary files | Auto-generated |

**Critical**: Always use `paths.struct` for structured output and `paths.meta` for
metadata. Never hardcode paths.

### Full directory after execution

```
data/
├── inputdata/
│   └── sample_data.ras
├── invoice/
│   └── invoice.json
├── tasksupport/
│   ├── invoice.schema.json
│   └── metadata-def.json
├── structured/                    # ← Your CSV, processed data
│   └── sample.csv
├── meta/                          # ← metadata.json (via Meta class)
│   └── metadata.json
├── raw/                           # ← Copy of original input files
│   └── sample_data.ras
├── main_image/                    # ← Plot images for dataset detail
│   └── image0.png
├── other_image/                   # ← Additional images
│   └── sub_image1.png
├── thumbnail/                     # ← Auto-generated thumbnail
│   └── image.png
├── logs/
│   └── rdesys_YYYYMMDD_HHMMSS.log
└── temp/
    └── invoice_org.json
```

---

## Step 3: Metadata Definition (metadata-def.json)

Define what metadata fields to extract from the input data. Each key maps to a
bilingual name and a JSON Schema type.

### Pattern

```json
{
    "field_key": {
        "name": {
            "ja": "Japanese label",
            "en": "English label"
        },
        "schema": {
            "type": "string"
        }
    }
}
```

### Example: XRD measurement metadata

```json
{
    "sample_name": {
        "name": { "ja": "試料名", "en": "Sample Name" },
        "schema": { "type": "string" }
    },
    "xray_target": {
        "name": { "ja": "X線ターゲット", "en": "X-ray Target" },
        "schema": { "type": "string" }
    },
    "tube_voltage_kv": {
        "name": { "ja": "管電圧 (kV)", "en": "Tube Voltage (kV)" },
        "schema": { "type": "number" }
    },
    "scan_start_angle": {
        "name": { "ja": "測定開始角度", "en": "Scan Start Angle" },
        "schema": { "type": "number" }
    },
    "scan_stop_angle": {
        "name": { "ja": "測定終了角度", "en": "Scan Stop Angle" },
        "schema": { "type": "number" }
    },
    "measurement_date": {
        "name": { "ja": "測定日時", "en": "Measurement Date" },
        "schema": { "type": "string" }
    }
}
```

### Guidelines for choosing metadata fields

- **Measurement conditions**: voltage, current, scan range, speed, mode
- **Sample information**: name, composition, preparation method
- **Temporal/traceability**: measurement date, operator, data point count
- **Equipment**: instrument model, wavelength, focus type

---

## Step 4: Writing Metadata (Meta Class)

This is the REQUIRED pattern for writing metadata to `metadata.json`.
Do NOT write metadata.json manually with json.dump().

```python
from pathlib import Path
from rdetoolkit.models.metadata import Meta


def save_metadata(
    metadata: dict[str, str],
    metadata_def_json_path: str | Path,
    save_path: str | Path,
) -> None:
    """Save metadata based on metadata-def.json field definitions."""
    meta = Meta(metadata_def_json_path)
    meta.assign_vals(metadata)
    meta.writefile(str(save_path))
```

### Usage in dataset function

```python
def dataset(paths: RdeDatasetPaths) -> None:
    # ... parse input data and extract metadata_dict ...

    metadata_dict = {
        "sample_name": "Al2O3",
        "xray_target": "Cu",
        "tube_voltage_kv": "40",
        "scan_start_angle": "10.0",
        "scan_stop_angle": "90.0",
    }

    save_metadata(
        metadata=metadata_dict,
        metadata_def_json_path=paths.tasksupport / "metadata-def.json",
        save_path=paths.meta / "metadata.json",
    )
```

**Important**: All values in the metadata dict MUST be strings, even for numeric fields.
The Meta class handles type conversion based on the schema defined in metadata-def.json.

---

## Step 5: Dataset Function — Complete Pattern with Result Type

The dataset function MUST use Result type for error handling. Do NOT use bare
try/except blocks around the entire function.

### Required imports

```python
from pathlib import Path

from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.models.metadata import Meta
from rdetoolkit.models.result import Result
from rdetoolkit.fileops import read_from_json_file, write_to_json_file
```

### Complete example: XRD RAS file processing

```python
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.models.metadata import Meta
from rdetoolkit.models.result import Result
from rdetoolkit.fileops import read_from_json_file, detect_encoding


# ── Helper: Parse RAS file ──────────────────────────────────────────────

def parse_ras_file(filepath: Path) -> Result[tuple[dict, pd.DataFrame], str]:
    """Parse a Rigaku RAS file and return (metadata_dict, measurement_data)."""
    try:
        encoding = detect_encoding(filepath)
        metadata: dict[str, str] = {}
        data_lines: list[str] = []
        in_data_block = False

        with open(filepath, encoding=encoding) as f:
            for line in f:
                line = line.strip()
                if line == "*RAS_INT_START":
                    in_data_block = True
                    continue
                if line == "*RAS_INT_END":
                    in_data_block = False
                    continue
                if in_data_block:
                    data_lines.append(line)
                elif line.startswith("*") and " " in line:
                    key, _, value = line.partition(" ")
                    metadata[key.lstrip("*")] = value.strip('" ')

        if not data_lines:
            return Result.err("No measurement data found in RAS file")

        rows = [line.split() for line in data_lines]
        df = pd.DataFrame(rows, columns=["angle", "intensity", "attenuation"])
        df = df.astype(float)

        return Result.ok((metadata, df))
    except Exception as e:
        return Result.err(f"Failed to parse RAS file: {e}")


# ── Helper: Save metadata ───────────────────────────────────────────────

def save_metadata(
    metadata: dict[str, str],
    metadata_def_path: Path,
    save_path: Path,
) -> Result[None, str]:
    """Save metadata using the Meta class."""
    try:
        meta = Meta(metadata_def_path)
        meta.assign_vals(metadata)
        meta.writefile(str(save_path))
        return Result.ok(None)
    except Exception as e:
        return Result.err(f"Failed to save metadata: {e}")


# ── Helper: Create structured CSV ────────────────────────────────────────

def create_structured_csv(
    df: pd.DataFrame, output_path: Path
) -> Result[Path, str]:
    """Save processed data as structured CSV."""
    try:
        csv_path = output_path / "xrd_data.csv"
        df[["angle", "intensity"]].to_csv(csv_path, index=False)
        return Result.ok(csv_path)
    except Exception as e:
        return Result.err(f"Failed to create structured CSV: {e}")


# ── Helper: Create plot ──────────────────────────────────────────────────

def create_plot(
    df: pd.DataFrame, output_path: Path
) -> Result[Path, str]:
    """Generate XRD plot and save as image."""
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(df["angle"], df["intensity"], linewidth=0.5)
        ax.set_xlabel("2θ (degree)")
        ax.set_ylabel("Intensity (counts)")
        ax.set_title("XRD Pattern")

        image_path = output_path / "xrd_pattern.png"
        fig.savefig(image_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return Result.ok(image_path)
    except Exception as e:
        return Result.err(f"Failed to create plot: {e}")


# ── Main dataset function ────────────────────────────────────────────────

def dataset(paths: RdeDatasetPaths) -> None:
    """RDE structured processing for XRD RAS files."""
    # Step 1: Find input file
    ras_files = list(paths.inputdata.glob("*.ras"))
    if not ras_files:
        raise FileNotFoundError("No .ras files found in inputdata/")
    input_file = ras_files[0]

    # Step 2: Parse input data (using Result)
    parse_result = parse_ras_file(input_file)
    if parse_result.is_err():
        raise RuntimeError(parse_result.unwrap_err())
    raw_metadata, df = parse_result.unwrap()

    # Step 3: Save metadata
    metadata_dict = {
        "sample_name": raw_metadata.get("FILE_SAMPLE", ""),
        "xray_target": raw_metadata.get("HW_XG_TARGET_NAME", ""),
        "tube_voltage_kv": raw_metadata.get("MEAS_COND_XG_VOLTAGE", ""),
        "scan_start_angle": raw_metadata.get("MEAS_SCAN_START", ""),
        "scan_stop_angle": raw_metadata.get("MEAS_SCAN_STOP", ""),
        "measurement_date": raw_metadata.get("MEAS_SCAN_START_TIME", ""),
    }
    meta_result = save_metadata(
        metadata_dict,
        paths.tasksupport / "metadata-def.json",
        paths.meta / "metadata.json",
    )
    if meta_result.is_err():
        raise RuntimeError(meta_result.unwrap_err())

    # Step 4: Create structured output
    csv_result = create_structured_csv(df, paths.struct)
    if csv_result.is_err():
        raise RuntimeError(csv_result.unwrap_err())

    # Step 5: Create plot image
    plot_result = create_plot(df, paths.main_image)
    if plot_result.is_err():
        raise RuntimeError(plot_result.unwrap_err())
```

### Error handling rules

1. **ALWAYS use `Result` type** for helper functions that can fail
2. **Each helper returns `Result[T, str]`** — Ok with the value, or Err with a message
3. **In the main `dataset()` function**, check each result and raise if error
4. **Do NOT wrap the entire dataset() in a single try/except** — this hides errors
5. **Do NOT use bare `except Exception`** in helpers — convert to Result.err() with context

### Anti-pattern (DO NOT DO THIS)

```python
# ❌ WRONG: Giant try/except hides all errors
def dataset(paths: RdeDatasetPaths) -> None:
    try:
        # ... 100 lines of processing ...
        pass
    except Exception as e:
        print(f"Error: {e}")
```

---

## Step 6: Entry Point (main.py)

```python
import rdetoolkit
from modules.custom_modules import dataset

rdetoolkit.workflows.run(custom_dataset_function=dataset)
```

This is always the same. The entire custom logic lives in the dataset function.

---

## Step 7: Validate and Run

```bash
# 1. Validate templates
rdetoolkit validate all

# 2. Run structured processing
python3 main.py
```

---

## ExcelInvoice / MultiDataTile: divided/ Directory Pattern

For batch processing modes, rdetoolkit creates `data/divided/00xx/` directories.
Use `DirectoryOps` to create and access them:

```python
from rdetoolkit.core import DirectoryOps

dir_ops = DirectoryOps("data")

# Access structured/ for the 2nd data tile
path = dir_ops.structured(2).path   # → data/divided/0002/structured

# Create all directories for data tile 1
paths = dir_ops.all(1)              # → ['data/invoice', ..., 'data/divided/0001/structured', ...]
```

### divided/ naming convention

- Pattern: `data/divided/00xx/` (4-digit zero-padded)
- Each `00xx/` contains the same output directories: `structured/`, `meta/`, `thumbnail/`, etc.
- `inputdata/`, `invoice/`, `tasksupport/` are NOT created inside divided/

---

## Checklist: Complete Structured Processing

Before submitting, verify all of these:

- [ ] `metadata-def.json` defines all fields to extract from input data
- [ ] `invoice.schema.json` defines the registration form schema
- [ ] `invoice.json` conforms to the schema
- [ ] `rdetoolkit validate all` passes
- [ ] `dataset()` function uses `RdeDatasetPaths` (single-argument signature)
- [ ] Metadata is saved via `Meta` class, NOT manual json.dump()
- [ ] File I/O uses `rdetoolkit.fileops` (NOT bare json.load/open)
- [ ] Error handling uses `Result` type in all helper functions
- [ ] Structured output is written to `paths.struct`
- [ ] Plot images are written to `paths.main_image` or `paths.other_image`
- [ ] `main.py` calls `rdetoolkit.workflows.run(custom_dataset_function=dataset)`
- [ ] Processing runs successfully with `python3 main.py`
