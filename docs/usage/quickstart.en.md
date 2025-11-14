# Experience RDEToolKit

## Purpose

This tutorial walks you through creating and running your first RDE-structured processing project with RDEToolKit. You can experience the entire basic workflow in about 15 minutes.

## Prerequisites

- Python 3.9 or later
- Basic knowledge of Python programming
- Basic understanding of command-line operations

## 1. Initialize the Project

Start by creating a new project with RDEToolKit.

```bash
mkdir sample_project
cd sample_project
python3 -m rdetoolkit init
```

After the command finishes, the following directory structure is created:

```
sample_project/
├── container
│   ├── data
│   │   ├── inputdata
│   │   ├── invoice
│   │   │   └── invoice.json
│   │   └── tasksupport
│   │       ├── invoice.schema.json
│   │       └── metadata-def.json
│   ├── Dockerfile
│   ├── main.py
│   ├── modules
│   └── requirements.txt
├── input
│   ├── inputdata
│   └── invoice
│       └── invoice.json
└── templates
    └── tasksupport
        ├── invoice.schema.json
        └── metadata-def.json
```

## 2. Implement Custom Processing

Open the `sample_project/container/modules/process.py` file and implement your custom processing as shown below:

```python title="modules/process.py"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    """
    Custom data processing function.

    Args:
        srcpaths: Input directory paths.
        resource_paths: Output resource paths.
    """
    # Inspect the input data.
    print(f"Input data directory: {srcpaths.inputdata}")
    print(f"Invoice directory: {srcpaths.invoice}")

    # Simple example of file processing.
    import shutil
    from pathlib import Path
    import pdb; pdb.set_trace()

    # Copy input files into the structured directory.
    input_files = list(srcpaths.inputdata.glob("*"))
    for file_path in input_files:
        if file_path.is_file():
            dest_path = resource_paths.struct / file_path.name
            shutil.copy2(file_path, dest_path)
            print(f"Copied file: {file_path.name}")

    print("Custom processing is complete")
    return 0
```

Next, edit the `main.py` file so that it calls the custom processing function:

```python title="main.py"
# The following script is a template for the source code.

import rdetoolkit
from modules.process import dataset

rdetoolkit.workflows.run(custom_dataset_function=dataset)
```

## 3. Prepare Sample Data

Place sample files in the `data/inputdata/` directory:

```bash
# Create sample text files
echo "This is sample data." > sample_project/container/data/inputdata/sample.txt
echo "Experiment data: Temperature 25°C, humidity 60%" > sample_project/container/data/inputdata/experiment_data.txt
```

## 4. Run the Structured Processing

Move to the project directory and run the structured processing:

```bash
cd sample_project/container
python main.py
```

When the execution succeeds, you will see output similar to the following:

```
Input data directory: data/inputdata
Invoice directory: data/invoice
Copied file: experiment_data.txt
Copied file: sample.txt
Custom processing is complete
```

## 5. Check the Results

After the processing finishes, the directory structure looks like this:

```
sample_project/container
├── data
│   ├── attachment
│   ├── inputdata
│   │   ├── experiment_data.txt
│   │   └── sample.txt
│   ├── invoice
│   │   └── invoice.json
│   ├── invoice_patch
│   ├── job.failed
│   ├── logs
│   │   └── rdesys.log
│   ├── main_image
│   ├── meta
│   │   └── processing_metadata.json
│   ├── nonshared_raw
│   │   ├── experiment_data.txt
│   │   └── sample.txt
│   ├── other_image
│   ├── raw
│   ├── structured
│   │   ├── experiment_data.txt
│   │   └── sample.txt
│   ├── tasksupport
│   │   ├── invoice.schema.json
│   │   └── metadata-def.json
│   ├── temp
│   └── thumbnail
├── Dockerfile
├── main.py
├── modules
│   └── process.py
└── requirements.txt
```

## Congratulations!

Your first RDE structured processing project is complete. In this tutorial you learned how to:

- **Initialize a project**: Create the project structure with `rdetoolkit init`
- **Implement custom processing**: Define the data-processing logic in the `dataset()` function
- **Handle files**: Arrange input data inside the structured directory
- **Manage metadata**: Record processing results as JSON files
- **Run and verify**: Execute the structured processing and review the results

## Next Steps

Now that you have experienced the basic flow, continue with the following topics:

- Understand how to implement structured processing with real data in [Development Guide](../usage/structured_process/development_guide.en.md)
- Explore the available [Configuration Options](../user-guide/config.en.md)
- Review advanced commands in the [CLI Reference](cli.en.md)
