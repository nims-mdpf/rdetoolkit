# RDEToolKit

![GitHub Release](https://img.shields.io/github/v/release/nims-mdpf/rdetoolkit)
[![python.org](https://img.shields.io/badge/Python-3.9%7C3.10%7C3.11-%233776AB?logo=python)](https://www.python.org/downloads/release/python-3917/)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](https://github.com/nims-mdpf/rdetoolkit/blob/main/LICENSE)
[![Issue](https://img.shields.io/badge/issue_tracking-github-orange)](https://github.com/nims-mdpf/rdetoolkit/issues)
![workflow](https://github.com/nims-mdpf/rdetoolkit/actions/workflows/main.yml/badge.svg)
![coverage](img/coverage.svg)

RDEToolKit is a fundamental Python package for creating workflows for RDE structured programs. By using various modules of RDEToolKit, you can easily build registration processes for research and experimental data to RDE. Primarily, RDEToolKit supports pre-processing and post-processing of user-defined structured processing. Additionally, by combining with Python modules used for research and experimental data, it enables more diverse processing from data registration to processing and graphing. This allows efficient management of the entire data science workflow, including data cleansing, transformation, aggregation, and visualization.

<br>

![overview_workflow](img/overview_workflow.svg)

## Challenges and Background

Research data management and sharing faced several challenges:

- **Data Format Standardization**: Different data formats and file structures across researchers
- **Metadata Standardization**: Inconsistent metadata descriptions
- **Process Automation**: Manual burden of data conversion and organization tasks
- **Reproducibility**: Difficulty in documenting and standardizing processing procedures

## Key Concepts

### Structured Processing Workflow

RDEToolKit executes "structured processing" to convert research data into standardized RDE format through three phases:

```mermaid
graph LR
    Initialization --> Custom_Processing[Custom Structured Processing]
    Custom_Processing --> Finalization
```

- **Initialization**: Directory creation, file loading, mode detection
- **Custom Structured Processing**: User-defined data transformation and analysis
- **Finalization**: Validation, thumbnail generation, metadata description

### Four Processing Modes

RDEToolKit provides four processing modes based on data type and usage:

| Mode | Purpose | Features |
|------|---------|----------|
| Invoice Mode | Single data file | Default mode, basic structured processing |
| Excel Invoice Mode | Excel format invoices | Automatic processing of Excel invoice files |
| Multi Data Tile | Multiple data files | Batch processing, error skip functionality |
| RDE Format Mode | RDE standard format | Reprocessing of existing RDE data |

### Configuration Files

Processing behavior can be flexibly controlled through configuration files (`rdeconfig.yaml` or `pyproject.toml`):

```yaml
system:
  extended_mode: 'MultiDataTile'
  save_raw: true
  magic_variable: true
  save_thumbnail_image: true
```

## Installation

RDEToolKit is provided as a Python package and can be installed with the following command:

```bash
pip install rdetoolkit
```

## Code Sample

|       Sample1: With User-Defined Structured Processing       |            Sample2: Without User-Defined Structured Processing            |
| :---------------------------------------------: | :-------------------------------------------------------: |
| ![quick-sample-code](img/quick-sample-code.svg) | ![quick-sample-code-none](img/quick-sample-code-none.svg) |

## Key Features

### Automation Features

- **Automatic Directory Structure Generation**: Folder structure compliant with RDE standards
- **Automatic File Format Detection**: Processing mode selection based on input data
- **Automatic Metadata Extraction**: Metadata generation from file information
- **Automatic Thumbnail Creation**: Representative image generation from Main images

### Validation Features

- **Schema Validation**: Data structure validation using JSON Schema
- **File Integrity Check**: Verification of required file existence
- **Metadata Validation**: Consistency check with metadata-def.json

### Extensibility

- **Custom Processing Integration**: Integration of user-defined functions
- **Plugin Functionality**: Addition of custom processing logic
- **Configuration Flexibility**: Detailed settings in YAML/TOML format

## Summary

Key values of RDEToolKit:

- **Efficiency**: Significant time reduction through automation of manual tasks
- **Standardization**: Unified conversion processing to RDE format
- **Flexibility**: Support for diverse research data formats
- **Reliability**: Quality assurance through validation features
- **Extensibility**: Easy integration of custom processing

## Next Steps

To get started with RDEToolKit:

1. [Installation Guide](installation.en.md) - Environment setup procedures
2. [Quick Start](quick-start.en.md) - Experience your first structured processing
3. [User Guide](user-guide/index.en.md) - Detailed usage instructions
