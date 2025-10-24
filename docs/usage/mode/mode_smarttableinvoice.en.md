# What is SmartTableInvoice Mode?

## Purpose

A mode that reads metadata from table files (Excel/CSV/TSV) and automatically generates an `invoice.json` file.

## Features

- Multi-format support: reads Excel (.xlsx), CSV, and TSV files
- Two-row header format: row 1 for display names, row 2 for mapping keys
- Automatic metadata mapping: generates structured data using the `basic/`, `custom/`, and `sample/` prefixes
- ZIP integration: automatically associates a ZIP that contains data files with the table file

## When to Use

- When you want to register multiple data items by linking multiple files

## How to Configure

No changes to the configuration file are required. However, you must place Excel/CSV/TSV files whose names begin with the `smarttable_` prefix in the input data.

- `smarttable_tabledata.xlsx`
- `smarttable_imagedata.csv`
- `smarttable_20250101.tsv`

## Table Data Format

### Overview

```csv
# Row 1: Display names (user-facing descriptions)
データ名,入力ファイル1,サイクル,厚さ,温度,試料名,試料ID,一般項目

# Row 2: Mapping keys (used in actual processing)
basic/dataName,inputdata1,custom/cycle,custom/thickness,custom/temperature,sample/names,sample/sampleId,sample/generalAttributes.3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e

# Row 3 and onward: Data
実験1,file1.txt,1,2mm,25,sample001,S001,value1
実験2,file2.txt,2,3mm,30,sample002,S002,value2
```

![smarttable_excel_sample](../../img/smarttable_excel_sample.png)

### Row 1: Display Names (User-Facing Descriptions)

This row is not used for data registration; it is for making the table easier to understand when managing it.

```csv
データ名,入力ファイル1,サイクル,厚さ,温度,試料名,試料ID,一般項目
```

### Row 2: Mapping Keys

#### Metadata Mapping and Expansion

This row is read and automatically mapped to `invoice.json` and metadata. The mapping rules are as follows:

- `basic/<key in invoice.json>`: mapped to the `basic` section of `invoice.json`.
- `custom/<key in invoice.json>`: mapped to the `custom` section of `invoice.json`.
- `sample/<key in invoice.json>`: mapped to the `sample` section of `invoice.json`.
- `sample/generalAttributes.<termId>`: mapped to the `value` of the matching `termId` in the `generalAttributes` array.
- `sample/specificAttributes.<classId>.<termId>`: mapped to the `value` of the matching `classId` and `termId` in the `specificAttributes` array.
- `meta/<metadata-def key>`: written to the `constant` section of `metadata.json` according to `metadata-def.json` (values are cast using `schema.type`, and `unit` is copied when provided). Entries marked with `variable` are not supported at this time. If `metadata-def.json` is absent, the meta columns are skipped as before.
- `inputdataX`: specifies a file path inside the ZIP file (X = 1, 2, 3, …).

> Currently, table data is automatically expanded into `invoice.json` and `metadata.json` (for `meta/` columns). Other data is exposed so it can be used by the structured processing.

#### About Input File Handling

The key `inputdata[number]` is for entering the file paths you want to include in a single data tile. Specify paths inside the ZIP file.

- For example, if you put `data1/file1.txt` in `inputdata1`, `file1.txt` must exist inside the ZIP file.
- If you put `data1/file1.txt` in `inputdata1` and `data1/file2.txt` in `inputdata2`, they will be grouped so that both files can be read within the structured processing.

### Row 3 and Onward

Enter the actual data to register. Each row is registered as one data tile.

```csv
実験1,file1.txt,1,2mm,25,sample001,S001,value1
実験2,file2.txt,2,3mm,30,sample002,S002,value2
```

### File Extensions

The table data file must have one of the following extensions: `.csv`, `.xlsx`, or `.tsv`.

## About the Input Files

SmartTableInvoice mode requires specific input files: an Excel/CSV/TSV file containing the table data and a ZIP file containing the related data files.

- `smarttable_imagedata.csv`
- `inputdata.zip`

## Directory Structure

Place the Excel file and the ZIP file in the `inputdata` directory.

```bash
data/
├── inputdata/
│   ├── inputdata.zip
│   └── smarttable_imagedata.csv
├── invoice/
├── tasksupport/
```

```bash
data/
├── inputdata/
│   ├── smarttable_imagedata.csv
│   └── inputdata.zip
├── invoice/
├── tasksupport/
├── divided/
│   ├── 0001/
│   │   ├── invoice/
│   │   │   └── invoice.json  # generated from smarttable row 1
│   │   ├── raw/
│   │   │   ├── file1.txt
│   │   │   └── file2.txt
│   │   └── (other standard folders)
│   └── 0002/
│       ├── invoice/
│       │   └── invoice.json  # generated from smarttable row 2
│       └── (other standard folders)
└── temp/
    ├── fsmarttable_experiment_0001.csv
    └── fsmarttable_experiment_0002.csv
```

## Retrieving a Single Row of Table Data in Structured Processing

If you define the structured processing as shown below, you can obtain the CSV path from `RdeOutputResourcePath.rawfiles`. In the example directory structure above, this would be `temp/fsmarttable_experiment_0001.csv`, etc.

```python
def custom_module(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Execute structured text processing, metadata extraction, and visualization.

    It handles structured text processing, metadata extraction, and graphing.
    Other processing required for structuring may be implemented as needed.

    Args:
        srcpaths (RdeInputDirPaths): Paths to input resources for processing.
        resource_paths (RdeOutputResourcePath): Paths to output resources for saving results.

    Returns:
        None

    Note:
        The actual function names and processing details may vary depending on the project.
    """
    ...
```

## Registering the Table Data File with RDE

By default, the table data used by SmartTableInvoice mode is --not-- registered in RDE. You can register the table data in RDE by adding the following setting to the `rdeconfig.yml` configuration file.

```yaml
smarttable:
    save_table_file: true
```
