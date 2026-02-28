---
name: rdetoolkit
description: >
  Guide development of RDE (Research Data Express) structured programs using
  rdetoolkit — a Python framework by NIMS for research data registration workflows.
  Covers project scaffolding, dataset function implementation, processing mode
  selection (Invoice / ExcelInvoice / MultiDataTile / RDEFormat), template editing,
  schema & metadata validation via CLI, encoding-safe file I/O with rdetoolkit.fileops,
  and CSV-to-graph generation with rdetoolkit.csv2graph.
  MUST be used whenever code imports rdetoolkit, calls workflows.run(), reads/writes
  JSON in research-data contexts, processes CSV for graphing, edits invoice.schema.json
  or metadata-def.json, or runs `rdetoolkit validate` or `rdetoolkit init` commands.
  Also activate when the user mentions RDE, structured processing, NIMS, materials data,
  research data registration, or any rdetoolkit module.
license: MIT
metadata:
  author: nims-mdpf
  version: "1.0"
  docs: https://nims-mdpf.github.io/rdetoolkit/
  repository: https://github.com/nims-mdpf/rdetoolkit
---

# RDEToolKit — Structured Program Development Guide

RDEToolKit is a Python framework by NIMS (National Institute for Materials Science) that
automates research data registration into RDE. It handles directory scaffolding, file
validation, metadata extraction, thumbnail generation, and graph creation — so you only
write the domain-specific data transformation logic.

Docs: https://nims-mdpf.github.io/rdetoolkit/
Repo: https://github.com/nims-mdpf/rdetoolkit

## Quick Start

### 1. Initialize a project

```bash
pip install rdetoolkit
python3 -m rdetoolkit init
```

This generates the standard layout:

```
container/
├── main.py
├── requirements.txt
├── modules/
└── data/
    ├── inputdata/          # Place experimental data here
    ├── invoice/
    │   └── invoice.json
    └── tasksupport/
        ├── invoice.schema.json
        └── metadata-def.json
```

### 2. Write a dataset function (recommended signature)

```python
from rdetoolkit.models.rde2types import RdeDatasetPaths

def dataset(paths: RdeDatasetPaths) -> None:
    # Read input from  paths.inputdata
    # Write outputs to paths.struct
    ...
```

### 3. Wire the entry point

```python
import rdetoolkit
from modules.my_module import dataset

rdetoolkit.workflows.run(custom_dataset_function=dataset)
```

### 4. Run locally

```bash
python3 main.py
```

---

## Critical Rules — Always Follow These

### Use rdetoolkit APIs, Do NOT Reinvent

Research data files often use legacy encodings (Shift_JIS, EUC-JP, CP932).
Standard Python `open()` / `json.load()` will crash on these files.
Always use rdetoolkit's encoding-aware functions.

#### File I/O (rdetoolkit.fileops)

| Task | ✅ Use this | ❌ Never do this |
|------|-----------|-----------------|
| Read JSON | `rdetoolkit.fileops.read_from_json_file(path)` | `json.load(open(path))` |
| Write JSON | `rdetoolkit.fileops.write_to_json_file(path, data)` | `json.dump(data, open(path, 'w'))` |
| Detect encoding | `rdetoolkit.fileops.detect_encoding(path)` | Raw `chardet.detect()` |

```python
# ✅ CORRECT — handles Shift_JIS, EUC-JP, CP932 transparently
from rdetoolkit.fileops import read_from_json_file, write_to_json_file

metadata = read_from_json_file(paths.meta / "metadata.json")
write_to_json_file(paths.struct / "output.json", result)
```

```python
# ❌ WRONG — will raise UnicodeDecodeError on legacy-encoded files
import json
with open(paths.meta / "metadata.json") as f:
    metadata = json.load(f)
```

#### CSV-to-Graph (rdetoolkit.graph)

For simple XY-axis graphs from CSV data, use csv2graph before writing matplotlib code.
It generates publication-ready plots in one call.

```python
from rdetoolkit.graph import csv2graph

# Generates XY line graph from CSV and saves to output directory
csv2graph(csv_path, output_dir)
```

See [references/preferred-apis.md](references/preferred-apis.md) for full options and examples.

### Dataset Function Signature

```python
# ✅ RECOMMENDED — single-argument style (v1.4+)
from rdetoolkit.models.rde2types import RdeDatasetPaths

def dataset(paths: RdeDatasetPaths) -> None:
    ...
```

```python
# ⚠️ LEGACY — two-argument style (still works, but do not use for new code)
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def dataset(inputdata: RdeInputDirPaths, output: RdeOutputResourcePath) -> None:
    ...
```

### Path Access

Use the `RdeDatasetPaths` attributes. Do NOT hardcode paths.

| Attribute | Purpose |
|-----------|---------|
| `paths.inputdata` | Input data directory |
| `paths.struct` | Structured output directory |
| `paths.meta` | Metadata directory |
| `paths.thumbnail` | Thumbnail output directory |
| `paths.raw` | Raw file copy destination |
| `paths.invoice` | Invoice file path |
| `paths.tasksupport` | Task support files directory |

---

## Processing Modes

Choose the mode that matches your data registration scenario.
Set it in `rdeconfig.yaml` under `system.extended_mode`.

| Mode | Config value | When to use |
|------|-------------|-------------|
| **Invoice** | _(default, no config needed)_ | Single data file, basic registration |
| **ExcelInvoice** | `ExcelInvoice` | Batch registration with per-item metadata in Excel |
| **SmartTableInvoice** | `SmartTableInvoice` | Batch registration with metadata in Excel/CSV/TSV, multiple files per registration |
| **MultiDataTile** | `MultiDataTile` | Multiple files sharing the same metadata |
| **RDEFormat** | `RDEFormat` | Pre-formatted RDE data, system integration |

### Mode selection flowchart

```
How many files per registration?
├── One file → Invoice mode (default)
└── Multiple files
    ├── Each file needs different metadata?
    │   ├── Yes (Excel only) → ExcelInvoice mode
    │   ├── Yes (Excel/CSV/TSV, multiple files per registration) → SmartTableInvoice mode
    │   └── No (shared metadata) → MultiDataTile mode
    └── Data already in RDE format? → RDEFormat mode
```

### Configuration example

```yaml
# rdeconfig.yaml
system:
  extended_mode: 'MultiDataTile'   # or 'ExcelInvoice', 'RDEFormat'
  save_raw: true
  magic_variable: true
  save_thumbnail_image: true
```

See [references/modes.md](references/modes.md) for detailed mode descriptions and examples.

---

## CLI Workflow — Correct Order Matters

Template editing and validation MUST follow this sequence.
Running them out of order causes confusing validation errors.

### Step 1: Edit templates (in this order)

1. **`data/tasksupport/invoice.schema.json`** — Define the schema first
2. **`data/tasksupport/metadata-def.json`** — Configure metadata definitions
3. **`data/invoice/invoice.json`** — Fill in values conforming to the schema

### Step 2: Validate (in this order)

```bash
# 1. Check schema syntax itself
rdetoolkit validate invoice-schema data/tasksupport/invoice.schema.json

# 2. Check invoice conforms to schema
rdetoolkit validate invoice data/invoice/invoice.json \
  --schema data/tasksupport/invoice.schema.json

# 3. Check metadata definition
rdetoolkit validate metadata-def data/tasksupport/metadata-def.json

# 4. Full project validation (all of the above at once)
rdetoolkit validate all
```

### Step 3: Run structured processing

```bash
python3 main.py
```

See [references/cli-workflow.md](references/cli-workflow.md) for all CLI commands and CI/CD integration.

---

## Project Structure Reference

```
container/
├── main.py                          # Entry point: calls workflows.run()
├── requirements.txt                 # Additional Python dependencies
├── modules/
│   └── my_module.py                 # Your dataset() function lives here
├── rdeconfig.yaml                   # Optional: mode & behavior config
└── data/
    ├── inputdata/
    │   └── <your experimental data>
    ├── invoice/
    │   └── invoice.json             # Data registration metadata
    └── tasksupport/
        ├── invoice.schema.json      # JSON Schema for invoice validation
        └── metadata-def.json        # Metadata field definitions
```

---

## Common Mistakes and Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `UnicodeDecodeError` reading JSON | Using `json.load()` directly | Use `rdetoolkit.fileops.read_from_json_file()` |
| Validation error on `invoice.json` | Edited invoice before defining schema | Edit `invoice.schema.json` first, then `invoice.json` |
| `extended_mode` not recognized | Typo in config value | Must be exactly `ExcelInvoice`, `MultiDataTile`, or `RDEFormat` |
| Missing output files after run | Writing to wrong directory | Use `paths.struct` from `RdeDatasetPaths`, not hardcoded paths |
| Graph not generated | Using matplotlib manually for simple XY | Try `rdetoolkit.graph.csv2graph()` first |

---

## References

- **Full documentation**: https://nims-mdpf.github.io/rdetoolkit/
- **API reference**: https://nims-mdpf.github.io/rdetoolkit/en/api/
- **Repository**: https://github.com/nims-mdpf/rdetoolkit
- **Contributing guide**: https://github.com/nims-mdpf/rdetoolkit/blob/main/CONTRIBUTING.md
- **5-mode templates**: https://github.com/nims-mdpf/RDE_rdetoolkit_5mode_templates

### Reference files in this skill

- [references/preferred-apis.md](references/preferred-apis.md) — Detailed fileops and csv2graph usage patterns
- [references/modes.md](references/modes.md) — Deep dive into each processing mode
- [references/cli-workflow.md](references/cli-workflow.md) — Complete CLI reference and CI/CD integration
- [references/config.md](references/config.md) — Configuration file specification (rdeconfig.yaml, pyproject.toml)
