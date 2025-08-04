# RDE2Types API

## Purpose

This module defines various data classes and custom types used in RDEToolKit. It provides type-safe data structures used in structured processing, including input paths, output resource paths, and data classes.

## Key Features

### Path Management
- Structuring of input directory paths
- Management of output resource paths
- Type safety for file paths

### Data Structures
- Data classes for RDE processing
- Format flags and metadata definitions
- Value and unit pair management

---

::: src.rdetoolkit.models.rde2types.RdeFormatFlags

---

::: src.rdetoolkit.models.rde2types.RdeInputDirPaths

---

::: src.rdetoolkit.models.rde2types.RdeOutputResourcePath

---

::: src.rdetoolkit.models.rde2types.Name

---

::: src.rdetoolkit.models.rde2types.Schema

---

::: src.rdetoolkit.models.rde2types.MetadataDefJson

---

::: src.rdetoolkit.models.rde2types.ValueUnitPair

---

## Practical Usage

### Input Path Configuration

```python title="input_paths.py"
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

# Create input directory paths
input_paths = RdeInputDirPaths(
    inputdata=Path("data/input"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

print(f"Input data: {input_paths.inputdata}")
print(f"Invoice: {input_paths.invoice}")
print(f"Task support: {input_paths.tasksupport}")

# Check path existence
for path_name, path_value in input_paths.__dict__.items():
    if path_value.exists():
        print(f"✓ {path_name}: {path_value} (exists)")
    else:
        print(f"✗ {path_name}: {path_value} (does not exist)")
```

### Output Resource Path Management

```python title="output_paths.py"
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from pathlib import Path

# Create output resource paths
output_paths = RdeOutputResourcePath(
    rawfiles=Path("output/rawfiles"),
    thumbnail=Path("output/thumbnail"),
    meta=Path("output/meta"),
    invoice=Path("output/invoice")
)

print(f"Raw data: {output_paths.rawfiles}")
print(f"Thumbnail: {output_paths.thumbnail}")
print(f"Metadata: {output_paths.meta}")
print(f"Invoice: {output_paths.invoice}")

# Create directories
for path_name, path_value in output_paths.__dict__.items():
    path_value.mkdir(parents=True, exist_ok=True)
    print(f"✓ Directory created: {path_value}")
```

### Value and Unit Pair Management

```python title="value_unit_pairs.py"
from rdetoolkit.models.rde2types import ValueUnitPair

# Create value and unit pairs
temperature = ValueUnitPair(value=25.0, unit="℃")
pressure = ValueUnitPair(value=1013.25, unit="hPa")
humidity = ValueUnitPair(value=60, unit="%")

print(f"Temperature: {temperature.value} {temperature.unit}")
print(f"Pressure: {pressure.value} {pressure.unit}")
print(f"Humidity: {humidity.value} {humidity.unit}")

# Manage measurement data
measurements = [
    ValueUnitPair(value=25.0, unit="℃"),
    ValueUnitPair(value=1013.25, unit="hPa"),
    ValueUnitPair(value=60, unit="%")
]

for measurement in measurements:
    print(f"Measurement: {measurement.value} {measurement.unit}")
```
