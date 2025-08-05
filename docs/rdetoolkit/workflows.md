# Workflows API

## Purpose

This module provides core functionality for executing structured processing workflows in RDEToolKit. It manages data classification, folder path generation, and structured processing execution.

## Key Features

### File Classification and Validation
- Determines appropriateness of input file patterns
- Supports Invoice, ExcelInvoice, RDEFormat, and MultiFile modes
- Automatic detection of file mode (single file) and folder mode (multiple files)

### Workflow Execution
- Integration of custom dataset processing functions
- Configuration file-based behavior control
- Error handling and execution status tracking

---

::: src.rdetoolkit.workflows.check_files

---

::: src.rdetoolkit.workflows.generate_folder_paths_iterator

---

::: src.rdetoolkit.workflows.run

---

## Practical Usage

### Basic Workflow Execution

```python title="basic_workflow.py"
from rdetoolkit import workflows
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def my_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    """Custom data processing function"""
    # Set metadata
    metadata = {
        "experiment_date": "2024-01-01",
        "researcher": "John Doe",
        "status": "completed"
    }
    
    # Create metadata file
    import json
    with open(resource_paths.meta / "metadata.json", "w") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

# Execute workflow
result = workflows.run(custom_dataset_function=my_dataset_function)
print(f"Execution result: {result}")
```

### Configuration-based Workflow

```python title="config_workflow.py"
from rdetoolkit import workflows
from rdetoolkit.config import Config, SystemSettings

# Create configuration
config = Config(
    system=SystemSettings(
        save_raw=True,
        save_thumbnail_image=True,
        extended_mode="MultiDataTile"
    )
)

# Execute workflow with configuration
result = workflows.run(
    custom_dataset_function=my_dataset_function,
    config=config
)
```

### File Classification Verification

```python title="file_classification.py"
from rdetoolkit.workflows import check_files
from rdetoolkit.models.rde2types import RdeInputDirPaths
from rdetoolkit.rde2util import StorageDir

# Set input paths
srcpaths = RdeInputDirPaths(
    inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
    invoice=StorageDir.get_specific_outputdir(False, "invoice"),
    tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
)

# Execute file classification
raw_files, excel_invoice = check_files(srcpaths, mode="Invoice")

print(f"Classified files: {raw_files}")
print(f"Excel invoice: {excel_invoice}")
```
