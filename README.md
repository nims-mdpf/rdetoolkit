![GitHub Release](https://img.shields.io/github/v/release/nims-dpfc/rdetoolkit)
[![python.org](https://img.shields.io/badge/Python-3.9%7C3.10%7C3.11%7C3.12%7C3.13-%233776AB?logo=python)](https://www.python.org/downloads/release/python-3917/)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](https://github.com/nims-dpfc/rdetoolkit/blob/main/LICENSE)
[![Issue](https://img.shields.io/badge/issue_tracking-github-orange)](https://github.com/nims-dpfc/rdetoolkit/issues)
![workflow](https://github.com/nims-dpfc/rdetoolkit/actions/workflows/main.yml/badge.svg)
![coverage](docs/img/coverage.svg)

> [日本語ドキュメント](docs/README_ja.md)

# RDEToolKit

RDEToolKit is a fundamental Python package for creating workflows of RDE-structured programs.
By utilizing various modules provided by RDEToolKit, you can easily build processes for registering research and experimental data into RDE.
Additionally, by combining RDEToolKit with Python modules used in your research or experiments, you can achieve a wide range of tasks, from data registration to processing and visualization.

## Documents

See the [documentation](https://nims-mdpf.github.io/rdetoolkit/) for more details.

## Contributing

If you wish to make changes, please read the following document first:

- [CONTRIBUTING.md](https://github.com/nims-mdpf/rdetoolkit/blob/main/CONTRIBUTING.md)

## Install

To install, run the following command:

```shell
pip install rdetoolkit
```

## Usage

Below is an example of building an RDE-structured program.

### Create a Project

First, prepare the necessary files for the RDE-structured program. Run the following command in your terminal or shell:

```python
python3 -m rdetoolkit init
```

If the command runs successfully, the following files and directories will be generated.

In this example, development proceeds within a directory named `container`.

- **requirements.txt**
  - Add any Python packages you wish to use for building the structured program. Run `pip install` as needed.
- **modules**
  - Store programs you want to use for structured processing here. Details are explained in a later section.
- **main.py**
  - Defines the entry point for the structured program.
- **data/inputdata**
  - Place data files to be processed here.
- **data/invoice**
  - Required even as an empty file for local execution.
- **data/tasksupport**
  - Place supporting files for structured processing here.

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

### Implementing Structured Processing

You can process input data (e.g., data transformation, visualization, creation of CSV files for machine learning) and register the results into RDE. By following the format below, you can incorporate your own processing into the RDE structured workflow.

The recommended signature for the `dataset()` function accepts a single
`RdeDatasetPaths` argument that bundles both input and output locations. The
legacy two-argument style (`RdeInputDirPaths`, `RdeOutputResourcePath`) remains
available for backward compatibility.

```python
from rdetoolkit.models.rde2types import RdeDatasetPaths

def dataset(paths: RdeDatasetPaths) -> None:
    ...
```

In this example, we define a dummy function `display_messsage()` under `modules` to demonstrate how to implement custom structured processing. Create a file named `modules/modules.py` as follows:

```python
# modules/modules.py
from rdetoolkit.models.rde2types import RdeDatasetPaths


def display_messsage(path):
    print(f"Test Message!: {path}")


def dataset(paths: RdeDatasetPaths) -> None:
    display_messsage(paths.inputdata)
    display_messsage(paths.struct)
```

### About the Entry Point

Next, use `rdetoolkit.workflow.run()` to define the entry point. The main tasks performed in the entry point are:

- Checking input files
- Obtaining various directory paths as specified by RDE structure
- Executing user-defined structured processing

```python
import rdetoolkit
from modules.modules import dataset  # User-defined structured processing function

# Pass the user-defined structured processing function as an argument
rdetoolkit.workflows.run(custom_dataset_function=dataset)
```

If you do not wish to pass a custom structured processing function, define as follows:

```python
import rdetoolkit

rdetoolkit.workflows.run()
```

### Running in a Local Environment

To debug or test the RDE structured process in your local environment, simply add the necessary input data to the `data` directory. As long as the `data` directory is placed at the same level as `main.py`, it will work as shown below:

```shell
container/
├── main.py
├── requirements.txt
├── modules/
│   └── modules.py
└── data/
    ├── inputdata/
    │   └── <experimental data to process>
    ├── invoice/
    │   └── invoice.json
    └── tasksupport/
        ├── metadata-def.json
        └── invoice.schema.json
```
