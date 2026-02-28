# Processing Modes — Detailed Reference

RDEToolKit provides five processing modes. Each mode determines how input files are
mapped to data tiles (registration units) and how metadata is associated.

## Mode Overview

```
                    ┌─────────────────────────────────────────┐
                    │         How many files?                 │
                    └──────────┬──────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │     One file         │──────► Invoice Mode (default)
                    └──────────┬──────────┘
                               │ Multiple
                    ┌──────────▼──────────────────────────┐
                    │ Different metadata per file?         │
                    └──────┬──────────────────────┬───────┘
                           │ Yes                  │ No
                    ┌──────▼──────┐      ┌───────▼────────┐
                    │ Tabular     │      │ MultiDataTile  │
                    │ metadata?   │      │ Mode           │
                    └──┬──────┬──┘      └────────────────┘
                       │Yes   │No
              ┌────────▼──┐ ┌─▼──────────────────┐
              │ExcelInvoice│ │SmartTableInvoice   │
              │Mode        │ │Mode                │
              └────────────┘ └────────────────────┘

              Already in RDE format? ──────► RDEFormat Mode
```

---

## Invoice Mode (Default)

**Config**: No configuration needed (default behavior)

**Use when**: Registering a single data file with its metadata.

**How it works**:
- One input file in `data/inputdata/` → one data tile
- Metadata comes from `data/invoice/invoice.json`
- Simplest mode for getting started

**Directory layout**:
```
data/
├── inputdata/
│   └── measurement.csv          # Single input file
├── invoice/
│   └── invoice.json             # Metadata for this file
└── tasksupport/
    ├── invoice.schema.json
    └── metadata-def.json
```

---

## ExcelInvoice Mode

**Config**:
```yaml
system:
  extended_mode: 'ExcelInvoice'
```

**Use when**: Batch-registering multiple files where each file has different metadata
described in an Excel spreadsheet.

**How it works**:
- Multiple input files in `data/inputdata/`
- Each row in the Excel invoice maps to one data tile
- Per-file metadata is defined in Excel columns

**Key features**:
- Excel file serves as both invoice and metadata source
- Each row corresponds to one data file
- Column headers map to metadata fields

---

## SmartTableInvoice Mode

**Config**:
```yaml
system:
  extended_mode: 'SmartTableInvoice'
```

**Use when**: Similar to ExcelInvoice but with support for Excel (xlsx), CSV, and TSV
metadata formats, and the ability to associate multiple files with each registration.

**How it works**:
- Metadata can be in Excel, CSV, or TSV format
- Supports linking multiple related files per data tile
- More flexible than ExcelInvoice

---

## MultiDataTile Mode

**Config**:
```yaml
system:
  extended_mode: 'MultiDataTile'
```

**Use when**: Registering multiple files that share the same metadata (e.g., same
experimental conditions, same sample).

**How it works**:
- Multiple input files in `data/inputdata/`
- All files share the single `invoice.json` metadata
- One data tile is created per input file, all with identical metadata

**Example use case**:
- 100 XRD measurements on the same sample under the same conditions
- A series of images from the same microscope session

**Key config options**:
```yaml
system:
  extended_mode: 'MultiDataTile'
  save_raw: true                 # Keep original files
  magic_variable: true           # Enable magic variable substitution
  save_thumbnail_image: true     # Auto-generate thumbnails
```

---

## RDEFormat Mode

**Config**:
```yaml
system:
  extended_mode: 'RDEFormat'
```

**Use when**: Data is already formatted in RDE's standard structure, typically for:
- System-to-system integration
- Re-processing existing RDE data
- Registering only structured processing results (without raw data)
- Handling large files that shouldn't be uploaded to RDE

**How it works**:
- Input must follow RDE's predefined directory structure
- Minimal processing — mainly validation and registration

---

## Mode Comparison Table

| Feature | Invoice | ExcelInvoice | SmartTableInvoice | MultiDataTile | RDEFormat |
|---------|---------|-------------|-------------------|---------------|-----------|
| Files per registration | 1 | Many | Many | Many | Many |
| Metadata source | invoice.json | Excel file | Excel/CSV/TSV | invoice.json (shared) | Pre-formatted |
| Per-file metadata | N/A | Yes (rows) | Yes (rows) | No (shared) | Pre-set |
| Config required | No | Yes | Yes | Yes | Yes |
| Typical use case | Single measurement | Batch with varied metadata | Flexible batch | Batch with same conditions | System integration |

---

## Switching Modes

To switch modes, update `rdeconfig.yaml`:

```yaml
# Before: Invoice mode (default)
system: {}

# After: Switch to MultiDataTile
system:
  extended_mode: 'MultiDataTile'
```

The mode value must be an exact match (case-sensitive):
- `ExcelInvoice` ✅
- `excelinvoice` ❌
- `MultiDataTile` ✅
- `multi_data_tile` ❌
