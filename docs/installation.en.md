# How to Install RDEToolKit

## Purpose

This guide explains the procedures for installing RDEToolKit in your Python environment. Multiple installation methods are provided for both development and production use.

## Prerequisites

Before installing RDEToolKit, confirm the following:

- **Python**: Version 3.9 or higher
- **pip**: Latest version recommended
- **Internet Connection**: Needed to download packages from PyPI

!!! tip "Checking Your Python Environment"
    Run:
    ```bash
    python --version
    pip --version
    ```

## Steps

### 1. Standard Installation

Install the stable release from PyPI.

=== "Unix/macOS"
    ```bash title="terminal"
    pip install rdetoolkit
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install rdetoolkit
    ```

### 2. Installation with MinIO Support

Install extra dependencies if you use object storage (MinIO).

=== "Unix/macOS"
    ```bash title="terminal"
    pip install rdetoolkit[minio]
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install rdetoolkit[minio]
    ```

### 3. Installation with Plotly Support

Plotly is a visualization library that generates interactive graphs and dashboards (operable dynamically in a web browser). Install extras if you need Plotly features in RDEToolKit.

=== "Unix/macOS"
    ```bash title="terminal"
    pip install rdetoolkit[plotly]
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install rdetoolkit[plotly]
    ```

### 4. Development Version Installation

Install the latest development version directly from GitHub.

=== "Unix/macOS"
    ```bash title="terminal"
    pip install git+https://github.com/nims-mdpf/rdetoolkit.git
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install git+https://github.com/nims-mdpf/rdetoolkit.git
    ```

!!! warning "Development Version Notice"
    Development versions may be unstable. Use the stable release in production.

### 5. Installation in a Virtual Environment

Create an isolated environment per project.

=== "Using venv"
    ```bash title="terminal"
    # Create virtual environment
    python -m venv rde_env

    # Activate
    source rde_env/bin/activate  # Unix/macOS
    # rde_env\Scripts\activate   # Windows

    # Install RDEToolKit
    pip install rdetoolkit
    ```

=== "Using conda"
    ```bash title="terminal"
    # Create new environment
    conda create -n rde_env python=3.9

    # Activate
    conda activate rde_env

    # Install RDEToolKit
    pip install rdetoolkit
    ```

## Verification

### Installation Check

```python title="python_console"
import rdetoolkit
print(rdetoolkit.__version__)
```

Expected example:
```
1.2.3
```

### Basic Functionality Test

```python title="test_installation.py"
from rdetoolkit import workflows
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

print("RDEToolKit installation successful!")
```

## Troubleshooting

#### Dependency Conflicts

```bash
ERROR: pip's dependency resolver does not currently take into account all the packages
```

Solution: Use a clean virtual environment
```bash title="terminal"
python -m venv clean_env
source clean_env/bin/activate
pip install rdetoolkit
```

## Related Information

Next steps:

- [Quick Start](quick-start.en.md) - Run your first structured processing
- [Configuration File](user-guide/config.en.md) - Customize behavior settings
- [API Reference](api/index.en.md) - Detailed feature descriptions
