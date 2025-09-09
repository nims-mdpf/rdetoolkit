# Experience RDEToolKit

## Purpose

This tutorial will help you execute your first structured processing using RDEToolKit and experience the basic workflow. The estimated time is approximately 15 minutes.

Upon completion, you will be able to:
- Understand the basic structure of RDE projects
- Create custom structured processing functions
- Execute structured processing and verify results

## 1. Create a Project

### Purpose
Create a project directory for RDE structured processing and prepare the necessary file structure.

### Code to Execute

=== "Unix/macOS"
    ```bash title="terminal"
    # Create project directory
    mkdir my-rde-project
    cd my-rde-project

    # Create necessary directories
    mkdir -p data/inputdata
    mkdir -p tasksupport
    mkdir -p modules
    ```

=== "Windows"
    ```cmd title="command_prompt"
    # Create project directory
    mkdir my-rde-project
    cd my-rde-project

    # Create necessary directories
    mkdir data\inputdata
    mkdir tasksupport
    mkdir modules
    ```

### Expected Result
The following directory structure will be created:
```
my-rde-project/
├── data/
│   └── inputdata/
├── tasksupport/
└── modules/
```

## 2. Define Dependencies

### Purpose
Define the Python packages to be used in the project.

### Code to Execute

```text title="requirements.txt"
rdetoolkit>=1.0.0
```

### Expected Result
The `requirements.txt` file is created with RDEToolKit dependencies defined.

## 3. Create Custom Structured Processing

### Purpose
Create a custom function containing data processing logic.

### Code to Execute

```python title="modules/process.py"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
import json
import os

def display_message(message):
    """Helper function to display messages"""
    print(f"[INFO] {message}")

def create_sample_metadata(resource_paths):
    """Create sample metadata"""
    metadata = {
        "title": "Sample Dataset",
        "description": "RDEToolKit tutorial sample",
        "created_at": "2024-01-01",
        "status": "processed"
    }

    # Save metadata file
    metadata_path = os.path.join(resource_paths.tasksupport, "sample_metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    display_message(f"Metadata saved: {metadata_path}")

def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    """
    Main structured processing function

    Args:
        srcpaths: Input file path information
        resource_paths: Output resource path information
    """
    display_message("Starting structured processing")

    # Display input path information
    display_message(f"Input data directory: {srcpaths.inputdata}")
    display_message(f"Output resource directory: {resource_paths.root}")

    # Create sample metadata
    create_sample_metadata(resource_paths)

    # Display list of input files
    if os.path.exists(srcpaths.inputdata):
        files = os.listdir(srcpaths.inputdata)
        display_message(f"Number of input files: {len(files)}")
        for file in files:
            display_message(f"  - {file}")

    display_message("Structured processing completed")
```

### Expected Result
The `modules/process.py` file is created with structured processing logic defined.

## 4. Create Main Script

### Purpose
Create an entry point to launch the RDEToolKit workflow.

### Code to Execute

```python title="main.py"
import rdetoolkit

from modules import process

def main():
    """Main execution function"""
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

### Expected Result
The `main.py` file is created and ready to execute structured processing.

## 5. Prepare Sample Data

### Purpose
Create sample data to test the structured processing.

### Code to Execute

```text title="data/inputdata/sample_data.txt"
Sample Research Data
====================

This is a sample data file for RDEToolKit tutorial.
Created: 2024-01-01
Type: Text Data
Status: Ready for processing
```

### Expected Result
The `data/inputdata/sample_data.txt` file is created with sample data ready for processing.

## 6. Execute Structured Processing

### Purpose
Execute RDE structured processing with the created project and verify its operation.

### Code to Execute

```bash title="terminal"
# Install dependencies
pip install -r requirements.txt

# Execute structured processing
python main.py
```

### Expected Result

Output similar to the following will be displayed:

```
=== RDEToolKit Tutorial ===
[INFO] Starting structured processing
[INFO] Input data directory: /path/to/my-rde-project/data/inputdata
[INFO] Output resource directory: /path/to/my-rde-project
[INFO] Metadata saved: /path/to/my-rde-project/tasksupport/sample_metadata.json
[INFO] Number of input files: 1
[INFO]   - sample_data.txt
[INFO] Structured processing completed

=== Processing Results ===
Execution status: {'statuses': [{'run_id': '0000', 'title': 'sample-dataset', 'status': 'success', ...}]}
```

## 7. Verify Results

### Purpose
Verify the execution results and file generation of structured processing.

### Code to Execute

```bash title="terminal"
# Check generated file structure
find . -type f -name "*.json" | head -10
```

### Expected Result

You can verify that files like the following have been generated:
- `tasksupport/sample_metadata.json` - Created metadata file
- `raw/` or `nonshared_raw/` - Copy of input files (depending on configuration)

## Congratulations!

You have completed your first structured processing using RDEToolKit.

### What You Accomplished

✅ Created basic RDE project structure
✅ Implemented custom structured processing function
✅ Executed structured processing workflow
✅ Learned how to verify processing results

### Important Concepts Learned

- **Project Structure**: Roles of `data/inputdata/`, `tasksupport/`, `modules/`
- **Custom Functions**: How to use `RdeInputDirPaths` and `RdeOutputResourcePath`
- **Workflow Execution**: Basic usage of `rdetoolkit.workflows.run()`

## Next Steps

To learn more in detail:

1. [Structured Processing Concepts](user-guide/structured-processing.en.md) - Detailed understanding of processing flow
2. [Configuration File](user-guide/config.en.md) - How to customize behavior
3. [API Reference](api/index.en.md) - Check all available features

!!! tip "Next Practice"
    Try more complex structured processing using actual research data. It's important to select the appropriate processing mode based on the type of data.
