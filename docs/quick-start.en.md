# RDEToolKit Quick Start

## Purpose

This tutorial walks you through running your first structured processing job with RDEToolKit and experiencing the core workflow. The entire exercise takes about 15 minutes.

By the end you will be able to:

- Understand the basic structure of an RDE project
- Build a custom structured processing function
- Execute the structured processing flow and review the results

## 1. Create a Project

### Purpose

Create a project directory for RDE structured processing.

### Code to Execute

=== "Unix/macOS"
    ```bash title="terminal"
    # Create the project directory
    mkdir my-rde-project
    cd my-rde-project
    ```

=== "Windows"
    ```cmd title="command_prompt"
    # Create the project directory
    mkdir my-rde-project
    cd my-rde-project
    ```

## 2. Define Dependencies

### Purpose
Declare the Python packages required for the project.

### Install RDEToolKit

=== "Unix/macOS"
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install "rdetoolkit>=1.4.0"
    ```

=== "Windows"
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install "rdetoolkit>=1.4.0"
    ```

### Expected Result

Run `pip list` to confirm that `rdetoolkit` is installed.

```bash
$ pip list
Package                   Version
------------------------- -----------------
rdetoolkit                1.4.0
```

## 3. Create the Project Structure

### Purpose

Generate the scaffolded directory layout for structured processing.

### Code to Execute

```bash
rdetoolkit init
```

### Expected Result

```bash
Ready to develop a structured program for RDE.
Created: /Users/user1/my-rde-project/my-rde-project/container/requirements.txt
Created: /Users/user1/my-rde-project/my-rde-project/container/Dockerfile
Created: /Users/user1/my-rde-project/my-rde-project/container/data/invoice/invoice.json
Created: /Users/user1/my-rde-project/my-rde-project/container/data/tasksupport/invoice.schema.json
Created: /Users/user1/my-rde-project/my-rde-project/container/data/tasksupport/metadata-def.json
Created: /Users/user1/my-rde-project/my-rde-project/templates/tasksupport/invoice.schema.json
Created: /Users/user1/my-rde-project/my-rde-project/templates/tasksupport/metadata-def.json
Created: /Users/user1/my-rde-project/my-rde-project/input/invoice/invoice.json

Check the folder: /Users/user1/my-rde-project/my-rde-project
```

## 4. Create Custom Structured Processing

### Purpose

Implement a custom function that contains your data processing logic.

### File to Create

Create `container/modules/process.py` with the following content.

```python title="container/modules/process.py"
from pathlib import Path
import json
import os

from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


def display_message(message: str) -> None:
    """Helper function to display messages."""
    print(f"[INFO] {message}")


def create_sample_metadata(srcpaths: RdeInputDirPaths) -> None:
    """Create sample metadata."""
    metadata = {
        "title": "Sample Dataset",
        "description": "RDEToolKit tutorial sample",
        "created_at": "2024-01-01",
        "status": "processed",
    }

    # Save metadata file
    metadata_path = Path(srcpaths.tasksupport) / "sample_metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    display_message(f"Metadata saved: {metadata_path}")


def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """
    Main structured processing function.

    Args:
        srcpaths: Input file path information.
        resource_paths: Output resource path information.
    """
    display_message("Starting structured processing")

    # Display input path information
    display_message(f"Input data directory: {srcpaths.inputdata}")
    display_message(f"Structured data output directory: {resource_paths.struct}")
    display_message(f"Metadata output directory: {resource_paths.meta}")

    # Create sample metadata
    create_sample_metadata(srcpaths)

    # Display list of input files
    if os.path.exists(srcpaths.inputdata):
        files = os.listdir(srcpaths.inputdata)
        display_message(f"Number of input files: {len(files)}")
        for file in files:
            display_message(f"  - {file}")

    display_message("Structured processing completed")
```

## 5. Create the Main Script

### Purpose

Provide the entry point that launches the RDEToolKit workflow.

### File to Update

Replace the contents of `container/main.py` with the following.

```python title="main.py"
import rdetoolkit

from modules import process


def main() -> str:
    """Main execution function."""
    print("=== RDEToolKit Tutorial ===")

    # Execute RDE structured processing
    result = rdetoolkit.workflows.run(custom_dataset_function=process.dataset)

    # Display results
    print("\n=== Processing Results ===")
    print(f"Execution status: {result}")

    return result


if __name__ == "__main__":
    main()
```

## 6. Prepare Sample Data

### Purpose

Create sample data (`data/inputdata/sample_data.txt`) to test the structured processing workflow.

### File to Create

```text title="container/data/inputdata/sample_data.txt"
Sample Research Data
====================

This is a sample data file for the RDEToolKit tutorial.
Created: 2024-01-01
Type: Text Data
Status: Ready for processing
```

## 7. Run Structured Processing

### Purpose
Execute the structured processing workflow and verify that the project works correctly.

### Code to Execute

Move into the same directory as `data` and run `main.py`.

```bash title="terminal"
# Run structured processing
cd container
python main.py
```

### Expected Result

The execution prints output similar to the following:

```
=== RDEToolKit Tutorial ===
[INFO] Starting structured processing
[INFO] Input data directory: data/inputdata
[INFO] Structured data output directory: data/structured
[INFO] Metadata output directory: data/meta
[INFO] Metadata saved: data/tasksupport/sample_metadata.json
[INFO] Number of input files: 1
[INFO]   - sample_data.txt
[INFO] Structured processing completed

=== Processing Results ===
Execution status: {
  "statuses": [
    {
      "run_id": "0000",
      "title": "toy dataset",
      "status": "success",
      "mode": "invoice",
      "error_code": null,
      "error_message": null,
      "target": "data/inputdata",
      "stacktrace": null
    }
  ]
}
```

## 8. Review the Results

Inspect the `data` directory.

```bash
data
├── attachment
├── inputdata
│   └── sample_data.txt
├── invoice
│   └── invoice.json
├── invoice_patch
├── logs
│   └── rdesys.log
├── main_image
├── meta
├── nonshared_raw
│   └── sample_data.txt
├── other_image
├── raw
├── structured
├── tasksupport
│   ├── invoice.schema.json
│   ├── metadata-def.json
│   └── sample_metadata.json
├── temp
└── thumbnail
```

## Congratulations!

You have successfully completed your first structured processing flow with RDEToolKit.

### What You Accomplished

✅ Created the basic structure of an RDE project
✅ Implemented a custom structured processing function
✅ Ran the structured processing workflow
✅ Learned how to validate the processing results

### Key Concepts Learned

- **Project Structure**: Roles of `data/inputdata/`, `data/tasksupport/`, and `modules/`
- **Custom Functions**: How to use `RdeInputDirPaths` and `RdeOutputResourcePath`
- **Workflow Execution**: Basic usage of `rdetoolkit.workflows.run()`

## Next Steps

Deepen your understanding with the following resources:

1. [Structuring Processing Concepts](user-guide/structured-processing.en.md) – Learn the detailed flow
2. [Configuration Guide](user-guide/config.en.md) – Customize runtime behavior
3. [API Reference](api/index.en.md) – Explore the full feature set

!!! tip "Next Practice"
    Try processing real research data to explore more advanced scenarios. Choose the processing mode that best fits your data type.
