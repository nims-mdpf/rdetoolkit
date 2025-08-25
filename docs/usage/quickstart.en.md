# Experience RDEToolKit

## Purpose

This tutorial will guide you through creating and running your first RDE structured processing project using RDEToolKit. You can experience the basic structured processing workflow in approximately 15 minutes.

## Prerequisites

- Python 3.9 or higher
- Basic Python programming knowledge
- Basic understanding of command-line operations

## 1. Initialize the Project

Create a new RDE structured processing project:

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit init
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit init
    ```

This command creates the following directory structure:

```shell
container
├── data
│   ├── inputdata
│   ├── invoice
│   │   └── invoice.json
│   └── tasksupport
│       ├── invoice.schema.json
│       └── metadata-def.json
├── main.py
├── modules
└── requirements.txt
```

### Description of Generated Files

- **requirements.txt**: Python dependencies for your structured processing
- **modules/**: Directory for custom processing modules
- **main.py**: Entry point for the structured processing program
- **data/inputdata/**: Place input data files here
- **data/invoice/**: Contains invoice.json (required for local execution)
- **data/tasksupport/**: Schema and metadata definition files

!!! tip "File Overwriting"
    Existing files will not be overwritten. You can run this command safely.

## 2. Implement Custom Processing

Edit the `main.py` file to implement your custom structured processing function:

```python title="main.py"
import rdetoolkit.workflows as workflows

def my_dataset(rde):
    """
    Custom dataset processing function
    
    Args:
        rde: RDE processing context object
    """
    # Write your custom processing logic here
    print("Processing dataset...")
    
    # Example: Set metadata
    rde.set_metadata({
        "processing_status": "completed",
        "timestamp": "2023-01-01T00:00:00Z"
    })
    
    return 0

if __name__ == "__main__":
    # Execute the structured processing workflow
    workflows.run(my_dataset)
```

## 3. Add Input Data

Place your data files in the `data/inputdata/` directory:

```shell title="Example: Copy Data File"
# Example: Copy your data file
cp your_data_file.csv container/data/inputdata/
```

## 4. Execute Structured Processing

Run the structured processing:

=== "Unix/macOS"

    ```shell
    cd container
    python3 main.py
    ```

=== "Windows"

    ```powershell
    cd container
    py main.py
    ```

During execution, you will see output similar to:

```shell
Processing dataset...
Structured processing completed successfully
```

## 5. Verify Results

After successful execution, the following output structure will be generated:

```shell
container/data/
├── inputdata/
│   └── your_data_file.csv
├── invoice/
│   └── invoice.json
├── logs/
│   └── rdesys.log
├── main_image/
├── meta/
├── other_image/
├── raw/
│   └── your_data_file.csv
├── structured/
├── tasksupport/
│   ├── invoice.schema.json
│   └── metadata-def.json
├── temp/
└── thumbnail/
```

!!! note "Output Directory Descriptions"
    - **raw/**: Copy of input data
    - **structured/**: Processed data
    - **meta/**: Metadata files
    - **logs/**: Execution logs

## Congratulations!

You have successfully completed your first structured processing project using RDEToolKit. You have achieved the following:

- ✅ Project initialization
- ✅ Custom processing function implementation
- ✅ Structured processing execution
- ✅ Result verification

## Next Steps

Now that you have experienced basic structured processing, learn about the following topics:

- Understand [Structured Processing Concepts](../user-guide/structured-processing.en.md)
- Explore [Configuration Options](config/config.en.md)
- Learn about [Processing Modes](config/mode.en.md)
- Check [CLI Reference](cli.en.md) for advanced commands
