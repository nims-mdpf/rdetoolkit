# Preferred APIs Reference

This document covers the rdetoolkit APIs that MUST be used instead of standard Python
equivalents. These APIs handle encoding detection, legacy file format quirks, and
RDE-specific conventions automatically.

## rdetoolkit.fileops — Encoding-Safe File Operations

### Why this matters

Research data files from scientific instruments are often encoded in Shift_JIS, EUC-JP,
CP932, or other legacy Japanese encodings. Python's default `open()` assumes UTF-8 and
will crash on these files. The fileops module detects encoding automatically.

### Core functions

#### `read_from_json_file(path) -> dict`

Reads a JSON file with automatic encoding detection.

```python
from rdetoolkit.fileops import read_from_json_file

# Handles UTF-8, Shift_JIS, EUC-JP, CP932 transparently
data = read_from_json_file(Path("data/invoice/invoice.json"))
```

#### `write_to_json_file(path, data) -> None`

Writes a dictionary to a JSON file with proper encoding (UTF-8 with ensure_ascii=False).

```python
from rdetoolkit.fileops import write_to_json_file

result = {"measurement": "XRD", "peak_angle": 28.4}
write_to_json_file(Path("output/result.json"), result)
```

#### `detect_encoding(path) -> str`

Detects the character encoding of a file.

```python
from rdetoolkit.fileops import detect_encoding

encoding = detect_encoding(Path("data/inputdata/old_data.csv"))
# Returns e.g. "Shift_JIS", "UTF-8", "EUC-JP"
```

### Patterns for CSV reading with encoding detection

```python
from rdetoolkit.fileops import detect_encoding
import pandas as pd

csv_path = paths.inputdata / "measurement.csv"
encoding = detect_encoding(csv_path)
df = pd.read_csv(csv_path, encoding=encoding)
```

### Common mistakes

```python
# ❌ WRONG: Will fail on Shift_JIS files
import json
with open("data.json") as f:
    data = json.load(f)

# ❌ WRONG: Will fail on non-UTF-8 CSV
df = pd.read_csv("data.csv")

# ❌ WRONG: Using chardet directly (inconsistent with rdetoolkit internals)
import chardet
with open("data.csv", "rb") as f:
    result = chardet.detect(f.read())
```

---

## rdetoolkit.csv2graph — CSV to Graph Generation

### Overview

The csv2graph module generates XY-axis line graphs directly from CSV files. For simple
2-axis plots, always try csv2graph before writing custom matplotlib code.

### Basic usage

```python
from rdetoolkit.csv2graph import csv_to_graph

# Generates an XY line graph and saves it as an image
csv_to_graph(
    csv_path=paths.inputdata / "spectrum.csv",
    output_dir=paths.struct
)
```

### When to use csv2graph vs custom matplotlib

| Scenario | Use |
|----------|-----|
| Simple XY line graph from CSV | `csv2graph` |
| Multi-panel or overlay plots | Custom matplotlib |
| Specialized scientific plots (contour, 3D) | Custom matplotlib |
| Quick visualization during development | `csv2graph` |

### Integration with dataset function

```python
from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.csv2graph import csv_to_graph

def dataset(paths: RdeDatasetPaths) -> None:
    # Process input data
    csv_files = list(paths.inputdata.glob("*.csv"))
    for csv_file in csv_files:
        csv_to_graph(csv_file, paths.struct)
```

### Graph output location

csv2graph writes output images to the specified output directory. When used in a
dataset function, always write to `paths.struct` — this is where RDE expects
structured output files.

---

## General Rules

1. **Always import from `rdetoolkit.fileops`** for any file read/write in structured processing
2. **Always use `detect_encoding()`** before reading non-UTF-8 text files with pandas or other libraries
3. **Try `csv2graph` first** for any CSV visualization task — it's optimized for research data patterns
4. **Never hardcode file paths** — use `RdeDatasetPaths` attributes
5. **Never assume UTF-8** — scientific instruments produce files in various encodings
