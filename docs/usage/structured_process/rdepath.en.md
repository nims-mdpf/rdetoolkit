# Directory Path Retrieval Methods

## Purpose

This document explains how to retrieve directory paths necessary for file read/write operations in RDE structured processing. You will learn efficient path management using `RdeInputDirPaths` and `RdeOutputResourcePath`.

## Prerequisites

- Understanding of basic RDEToolKit usage
- Basic knowledge of Python file operations
- Understanding of structured processing directory structure

## Steps

### 1. Retrieve Input Paths

Use `RdeInputDirPaths` to retrieve input data path information:

```python title="Input Path Retrieval"
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Input data directory
    input_dir = srcpaths.inputdata
    print(f"Input data directory: {input_dir}")
    
    # Invoice directory
    invoice_dir = srcpaths.invoice
    print(f"Invoice directory: {invoice_dir}")
    
    # Task support directory
    tasksupport_dir = srcpaths.tasksupport
    print(f"Task support directory: {tasksupport_dir}")
```

### 2. Retrieve Output Paths

Use `RdeOutputResourcePath` to retrieve output destination path information:

```python title="Output Path Retrieval"
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Structured data directory
    structured_dir = resource_paths.struct
    print(f"Structured data directory: {structured_dir}")
    
    # Metadata directory
    meta_dir = resource_paths.meta
    print(f"Metadata directory: {meta_dir}")
    
    # Raw data directory
    raw_dir = resource_paths.raw
    print(f"Raw data directory: {raw_dir}")
    
    # Image directories
    main_image_dir = resource_paths.main_image
    other_image_dir = resource_paths.other_image
    thumbnail_dir = resource_paths.thumbnail
    
    print(f"Main image directory: {main_image_dir}")
    print(f"Other image directory: {other_image_dir}")
    print(f"Thumbnail directory: {thumbnail_dir}")
```

### 3. Read Files

Use the retrieved paths to read files:

```python title="File Reading"
import os
import pandas as pd
from pathlib import Path

def read_input_files(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Get file list from input directory
    input_files = os.listdir(srcpaths.inputdata)
    print(f"Input files: {input_files}")
    
    # Read CSV files
    for file in input_files:
        if file.endswith('.csv'):
            file_path = Path(srcpaths.inputdata) / file
            df = pd.read_csv(file_path)
            print(f"Loaded {file}: {df.shape}")
            
            # Process data
            processed_df = process_dataframe(df)
            
            # Save as structured data
            output_path = Path(resource_paths.struct) / f"processed_{file}"
            processed_df.to_csv(output_path, index=False)
```

### 4. Save Files

Save processing results to appropriate directories:

```python title="File Saving"
import json
from pathlib import Path

def save_processing_results(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Processing result data
    results = {
        "status": "completed",
        "processed_files": 5,
        "timestamp": "2023-01-01T12:00:00Z"
    }
    
    # Save as structured data
    structured_file = Path(resource_paths.struct) / "results.json"
    with open(structured_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Save as metadata
    metadata = {
        "processing_version": "1.0",
        "input_file_count": len(os.listdir(srcpaths.inputdata)),
        "processing_date": "2023-01-01"
    }
    
    meta_file = Path(resource_paths.meta) / "metadata.json"
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
```

## Verification

Verify that path retrieval and operations were performed correctly:

### File Operation Verification

```python title="Operation Result Verification"
def verify_file_operations(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Check input file count
    input_count = len(os.listdir(srcpaths.inputdata))
    print(f"Input file count: {input_count}")
    
    # Check output file count
    output_dirs = {
        "structured": resource_paths.struct,
        "meta": resource_paths.meta,
        "raw": resource_paths.raw,
        "main_image": resource_paths.main_image
    }
    
    for name, path in output_dirs.items():
        if Path(path).exists():
            file_count = len(os.listdir(path))
            print(f"{name} directory file count: {file_count}")
        else:
            print(f"⚠️ {name} directory does not exist")
```

## Related Information

To learn more about directory path retrieval, refer to the following documents:

- Understand processing flows where paths are used in [Structured Processing Concepts](structured.en.md)
- Check the role of each directory in [Directory Structure Specification](directory.en.md)
- Learn how to handle path-related errors in [Error Handling](errorhandling.en.md)
