# What are Data Registration Modes

## Purpose

This document explains the five data registration modes in RDE structured processing. You will understand the characteristics, use cases, and configuration methods of each mode to select the appropriate mode.

## Challenges and Background

Research data registration had diverse needs such as:

- **Single Dataset**: Register one experimental result
- **Batch Registration**: Efficiently register multiple related experiments
- **Integrated Management**: Manage related data as one dataset
- **Data Migration**: Migrate existing RDE format data

Five data registration modes were developed to address these diverse needs.

## Key Concepts

### Mode Selection Mechanism

```mermaid
flowchart TD
    A[Start Structured Processing] --> B{Check Input Files}
    B -->|*_excel_invoice.xlsx exists| C[ExcelInvoice Mode]
    B -->|smarttable_*.{xlsx,csv,tsv} exists| D[SmartTableInvoice Mode]
    B -->|Normal files| E{Check Configuration File}
    E -->|extended_mode: MultiDataTile| F[MultiDataTile Mode]
    E -->|extended_mode: rdeformat| G[RDEFormat Mode]
    E -->|No setting| H[Invoice Mode]
```

### Five Mode Overview

| Mode | Purpose | Activation Condition | Multiple Data Support |
|------|---------|---------------------|----------------------|
| **Invoice** | Single dataset registration | Default | ✗ |
| **ExcelInvoice** | Batch registration | `*_excel_invoice.xlsx` exists | ✓ |
| **SmartTableInvoice** | Automatic metadata generation | `smarttable_*.{xlsx,csv,tsv}` exists | ✓ |
| **MultiDataTile** | Integrated management | Configuration file specification | ✓ |
| **RDEFormat** | Data migration | Configuration file specification | ✓ |

## Mode Details

### 1. Invoice Mode (Standard Mode)

**Overview**: The most basic data registration mode for registering single datasets.

**Activation Condition**: Activated by default.

**Features**:
- Single dataset registration
- Simple configuration
- Recommended for beginners

**Directory Structure**:
```
data/
├── inputdata/          # Input data
├── invoice/            # Invoice data
│   └── invoice.json
└── tasksupport/        # Support files
    ├── invoice.schema.json
    └── metadata-def.json
```

### 2. ExcelInvoice Mode

**Overview**: Mode for batch registration of multiple datasets using Excel files.

**Activation Condition**: Automatically activated when files with `*_excel_invoice.xlsx` naming convention exist in input files.

**Features**:
- Batch registration of multiple datasets
- Efficient management via Excel files
- Suitable for batch processing

**Directory Structure**:
```
data/
├── inputdata/
│   └── experiment_excel_invoice.xlsx  # Excel invoice file
├── invoice/
└── tasksupport/
```

### 3. SmartTableInvoice Mode

**Overview**: Mode that reads metadata from table files (Excel/CSV/TSV) and automatically generates invoice.json files.

**Activation Condition**: Automatically activated when files with `smarttable_*.{xlsx,csv,tsv}` naming convention exist in input files.

**Features**:
- **Multi-format support**: Reads Excel (.xlsx), CSV, and TSV files
- **2-row header format**: Display names in row 1, mapping keys in row 2
- **Automatic metadata mapping**: Structured data generation with `basic/`, `custom/`, `sample/` prefixes
- **Array data support**: Proper mapping to `generalAttributes` and `specificAttributes`
- **ZIP file integration**: Automatic association between data files in ZIP and table files

**Table File Format**:
```csv
# Row 1: Display names (user descriptions)
Data Name,Input File 1,Cycle,Thickness,Temperature,Sample Name,Sample ID,General Item

# Row 2: Mapping keys (used in actual processing)
basic/dataName,inputdata1,custom/cycle,custom/thickness,custom/temperature,sample/names,sample/sampleId,sample/generalAttributes.3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e

# Row 3 onwards: Data
Experiment1,file1.txt,1,2mm,25,sample001,S001,value1
Experiment2,file2.txt,2,3mm,30,sample002,S002,value2
```

**Mapping Key Specifications**:
- `basic/xxxx`: Maps to `xxxx` key in `basic` object of invoice.json
- `custom/xxxx`: Maps to `xxxx` key in `custom` object of invoice.json
- `sample/xxxx`: Maps to `xxxx` key in `sample` object of invoice.json
- `sample/generalAttributes.<termId>`: Maps to `value` of corresponding `termId` in `generalAttributes` array
- `sample/specificAttributes.<classId>.<termId>`: Maps to `value` of corresponding `classId` and `termId` in `specificAttributes` array
- `inputdataX`: Specifies file path in ZIP file (X=1,2,3...)

**Configuration Options**:
```yaml
smarttable:
  save_table_file: true  # Save SmartTable file if true
```

`save_table_file` option:
- `false` (default): SmartTable file is not saved to raw/nonshared_raw directory
- `true`: Original SmartTable file is saved to raw/nonshared_raw directory

**Directory Structure**:
```
data/
├── inputdata/
│   ├── smarttable_experiment.xlsx
│   └── data.zip
├── divided/
│   ├── 0001/
│   │   ├── invoice/
│   │   │   └── invoice.json  # Generated from row 1 of smarttable
│   │   └── raw/
│   │       └── file1.txt
│   └── 0002/
│       ├── invoice/
│       │   └── invoice.json  # Generated from row 2 of smarttable
│       └── raw/
│           └── file2.txt
└── temp/
    ├── fsmarttable_experiment_0001.csv
    └── fsmarttable_experiment_0002.csv
```

### 4. MultiDataTile Mode

**Overview**: Mode for integrated management of multiple related data tiles as one dataset.

**Activation Condition**: Must specify `extended_mode: 'MultiDataTile'` in configuration file.

**Configuration Example**:
```yaml
system:
    extended_mode: 'MultiDataTile'
```

**Features**:
- Integrated management of multiple data tiles
- Maintains relationships between data
- Suitable for large-scale datasets

### 5. RDEFormat Mode

**Overview**: Mode for migrating existing RDE format data or creating mocks.

**Activation Condition**: Must specify `extended_mode: 'rdeformat'` in configuration file.

**Configuration Example**:
```yaml
system:
    extended_mode: 'rdeformat'
```

**Features**:
- Migration of existing data
- Mock creation of RDE format data
- Data conversion processing

## Mode Comparison

| Mode | Multiple Data | Configuration Required | Use Case | Difficulty |
|------|---------------|----------------------|----------|------------|
| Invoice | ✗ | ✗ | Single dataset | Beginner |
| ExcelInvoice | ✓ | ✗ | Batch registration | Intermediate |
| SmartTableInvoice | ✓ | ✗ | Flexible metadata mapping | Intermediate |
| MultiDataTile | ✓ | ✓ | Integrated management | Advanced |
| RDEFormat | ✓ | ✓ | Data migration | Advanced |

## Implementation Examples

### Invoice Mode

```python
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Process single dataset
    input_file = list(srcpaths.inputdata.glob("*.csv"))[0]
    df = pd.read_csv(input_file)
    
    # Save processing results
    output_path = resource_paths.structured / "processed_data.csv"
    df.to_csv(output_path, index=False)
```

### MultiDataTile Mode

```python
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Process multiple files
    input_files = list(srcpaths.inputdata.glob("*.csv"))
    
    for i, file in enumerate(input_files):
        df = pd.read_csv(file)
        
        # Save to directory for each tile
        tile_dir = resource_paths.structured / f"tile_{i+1:04d}"
        tile_dir.mkdir(exist_ok=True)
        
        output_path = tile_dir / f"processed_{file.name}"
        df.to_csv(output_path, index=False)
```

## Configuration File Mode Specification

### rdeconfig.yaml

```yaml
system:
    # Standard mode (default)
    extended_mode: null
    
    # MultiDataTile mode
    extended_mode: 'MultiDataTile'
    
    # RDEFormat mode
    extended_mode: 'rdeformat'
```

### pyproject.toml

```toml
[tool.rdetoolkit.system]
extended_mode = "MultiDataTile"
```

## Troubleshooting

### Common Problems

1. **Unintended mode activation**
   - Check input file names (existence of `*_excel_invoice.xlsx`)
   - Check `extended_mode` in configuration file

2. **MultiDataTile mode not activating**
   - Verify `extended_mode: 'MultiDataTile'` is written in configuration file
   - Check if configuration file YAML format is correct

3. **Divided directory not created**
   - Verify MultiDataTile mode or ExcelInvoice mode is correctly activated
   - Check if multiple input data exist

## Related Information

To learn more about data registration modes, refer to the following documents:

- Learn configuration methods in [Configuration Files](config.en.md)
- Check directory roles in [Directory Structure](../structured_process/directory.en.md)
- Understand processing flows in [Structured Processing Concepts](../structured_process/structured.en.md)
