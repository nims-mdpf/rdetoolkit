# How to Install RDEToolKit

## Purpose

This guide explains the procedures for installing RDEToolKit in your Python environment. We provide multiple installation methods for both development and production environments.

## Prerequisites

Before installing RDEToolKit, ensure that the following requirements are met:

- **Python**: Version 3.9 or higher
- **pip**: Latest version recommended
- **Internet Connection**: Required for downloading packages from PyPI

!!! tip "Checking Python Environment"
    To check your current Python environment, run the following commands:
    ```bash
    python --version
    pip --version
    ```

## Steps

### 1. Standard Installation

The most common installation method. Install the stable version from PyPI.

=== "Unix/macOS"
    ```bash title="terminal"
    pip install rdetoolkit
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install rdetoolkit
    ```

### 2. Installation with MinIO Support

If you plan to use object storage (MinIO) functionality, install additional dependencies.

=== "Unix/macOS"
    ```bash title="terminal"
    pip install rdetoolkit[minio]
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install rdetoolkit[minio]
    ```

### 3. Development Version Installation

To use the latest development version, install directly from the GitHub repository.

=== "Unix/macOS"
    ```bash title="terminal"
    pip install git+https://github.com/nims-mdpf/rdetoolkit.git
    ```

=== "Windows"
    ```cmd title="command_prompt"
    pip install git+https://github.com/nims-mdpf/rdetoolkit.git
    ```

!!! warning "Development Version Notice"
    Development versions may be unstable. We recommend using stable versions in production environments.

### 4. Installation in Virtual Environment

Steps for creating an isolated environment for each project.

=== "Using venv"
    ```bash title="terminal"
    # Create virtual environment
    python -m venv rde_env

    # Activate virtual environment
    source rde_env/bin/activate  # Unix/macOS
    # rde_env\Scripts\activate  # Windows

    # Install RDEToolKit
    pip install rdetoolkit
    ```

=== "Using conda"
    ```bash title="terminal"
    # Create new environment
    conda create -n rde_env python=3.9

    # Activate environment
    conda activate rde_env

    # Install RDEToolKit
    pip install rdetoolkit
    ```

## Verification

Verify that the installation completed successfully.

### Installation Check

```python title="python_console"
import rdetoolkit
print(rdetoolkit.__version__)
```

Expected output example:
```
1.2.3
```

### Basic Functionality Test

```python title="test_installation.py"
from rdetoolkit import workflows
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

# Verify that basic imports succeed
print("RDEToolKit installation successful!")
```

## Troubleshooting

### Common Issues and Solutions

#### Permission Error

```bash
ERROR: Could not install packages due to an EnvironmentError
```

**Solution**: Install at user level
```bash title="terminal"
pip install --user rdetoolkit
```

#### Dependency Conflicts

```bash
ERROR: pip's dependency resolver does not currently take into account all the packages
```

**Solution**: Use a virtual environment
```bash title="terminal"
python -m venv clean_env
source clean_env/bin/activate
pip install rdetoolkit
```

#### Python Version Incompatibility

```bash
ERROR: Package 'rdetoolkit' requires a different Python
```

**Solution**: Upgrade to Python 3.9 or higher

!!! note "Support Information"
    If installation issues persist, please report them on [GitHub Issues](https://github.com/nims-mdpf/rdetoolkit/issues).

## Related Information

Next steps after installation completion:

- [Quick Start](quick-start.en.md) - Execute your first structured processing
- [Configuration File](user-guide/config.en.md) - Customize behavior settings
- [API Reference](api/index.en.md) - Detailed feature descriptions
