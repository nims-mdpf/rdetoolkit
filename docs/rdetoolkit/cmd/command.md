# Command Module

The `rdetoolkit.cmd.command` module provides command-line interface functionality for RDE (Research Data Exchange) project initialization and management. This module includes commands for project setup, version display, and file generation utilities for structured RDE development environments.

## Overview

The command module offers comprehensive project initialization and management capabilities:

- **Project Initialization**: Create complete RDE project structures with necessary directories and files
- **Version Management**: Display current toolkit version information
- **File Generation**: Automated creation of configuration files, scripts, and templates
- **Container Support**: Generate Docker and containerization files for reproducible environments

## Classes

### Command

Extended Click command class for custom command functionality.

#### Constructor

```python
Command(name: str, **attrs: Any)
```

**Parameters:**
- `name` (str): The name of the command
- `**attrs` (Any): Additional attributes passed to the parent Click command

**Inherits from:** `click.Command`

### InitCommand

Command class for initializing RDE project structures with all necessary files and directories.

#### Constructor

```python
InitCommand()
```

#### Class Attributes

##### default_dirs

```python
default_dirs: list[Path] = [
    Path("container/modules"),
    Path("container/data/inputdata"),
    Path("container/data/invoice"),
    Path("container/data/tasksupport"),
    Path("input/invoice"),
    Path("input/inputdata"),
    Path("templates/tasksupport"),
]
```

List of default directories created during project initialization.

#### Methods

##### invoke()

Execute the complete project initialization process.

```python
def invoke() -> None
```

**Raises:**
- `click.Abort`: If any step in the initialization process fails

**Example:**
```python
from rdetoolkit.cmd.command import InitCommand

# Initialize a new RDE project
init_cmd = InitCommand()
init_cmd.invoke()
```

##### Private Methods

The class includes several private methods for specific file generation tasks:

- `_info_msg(msg: str) -> None`: Display information messages
- `_success_msg(msg: str) -> None`: Display success messages in green
- `_error_msg(msg: str) -> None`: Display error messages in red

### VersionCommand

Command class for displaying the current toolkit version.

#### Constructor

```python
VersionCommand()
```

#### Methods

##### invoke()

Display the current RDEToolkit version.

```python
def invoke() -> None
```

**Example:**
```python
from rdetoolkit.cmd.command import VersionCommand

# Display version information
version_cmd = VersionCommand()
version_cmd.invoke()  # Prints the current version
```

### DockerfileGenerator

Generator class for creating Dockerfile configurations.

#### Constructor

```python
DockerfileGenerator(path: str | Path = "Dockerfile")
```

**Parameters:**
- `path` (str | Path): Path where the Dockerfile will be created. Defaults to "Dockerfile"

#### Attributes

- `path` (str | Path): The target path for the generated Dockerfile

#### Methods

##### generate()

Generate a Dockerfile with standard RDE configuration.

```python
def generate() -> list[str]
```

**Returns:**
- `list[str]`: List of strings representing the Dockerfile content

**Example:**
```python
from rdetoolkit.cmd.command import DockerfileGenerator
from pathlib import Path

# Generate Dockerfile in custom location
generator = DockerfileGenerator(Path("docker/Dockerfile"))
content = generator.generate()
print("Generated Dockerfile with", len(content), "lines")
```

### RequirementsTxtGenerator

Generator class for creating requirements.txt files with RDEToolkit dependencies.

#### Constructor

```python
RequirementsTxtGenerator(path: str | Path = "requirements.txt")
```

**Parameters:**
- `path` (str | Path): Path where the requirements.txt will be created. Defaults to "requirements.txt"

#### Attributes

- `path` (str | Path): The target path for the generated requirements.txt

#### Methods

##### generate()

Generate a requirements.txt file with RDEToolkit dependency.

```python
def generate() -> list[str]
```

**Returns:**
- `list[str]`: List of strings representing the requirements.txt content

**Example:**
```python
from rdetoolkit.cmd.command import RequirementsTxtGenerator

# Generate requirements.txt
generator = RequirementsTxtGenerator("container/requirements.txt")
content = generator.generate()
```

### InvoiceSchemaJsonGenerator

Generator class for creating invoice schema JSON files.

#### Constructor

```python
InvoiceSchemaJsonGenerator(path: str | Path = "invoice.schema.json")
```

**Parameters:**
- `path` (str | Path): Path where the schema file will be created. Defaults to "invoice.schema.json"

#### Attributes

- `path` (str | Path): The target path for the generated schema file

#### Methods

##### generate()

Generate an invoice schema JSON file based on RDE specifications.

```python
def generate() -> dict[str, Any]
```

**Returns:**
- `dict[str, Any]`: Dictionary containing the generated schema structure

**Example:**
```python
from rdetoolkit.cmd.command import InvoiceSchemaJsonGenerator

# Generate invoice schema
generator = InvoiceSchemaJsonGenerator("schemas/invoice.schema.json")
schema = generator.generate()
print(f"Generated schema with {len(schema)} top-level keys")
```

### MetadataDefJsonGenerator

Generator class for creating metadata definition JSON files.

#### Constructor

```python
MetadataDefJsonGenerator(path: str | Path = "metadata-def.json")
```

**Parameters:**
- `path` (str | Path): Path where the metadata definition will be created. Defaults to "metadata-def.json"

#### Attributes

- `path` (str | Path): The target path for the generated metadata definition

#### Methods

##### generate()

Generate a metadata definition JSON file.

```python
def generate() -> dict[str, Any]
```

**Returns:**
- `dict[str, Any]`: Dictionary containing the metadata definition (initially empty)

**Example:**
```python
from rdetoolkit.cmd.command import MetadataDefJsonGenerator

# Generate metadata definition
generator = MetadataDefJsonGenerator("config/metadata-def.json")
metadata = generator.generate()
```

### InvoiceJsonGenerator

Generator class for creating invoice JSON files.

#### Constructor

```python
InvoiceJsonGenerator(path: str | Path = "invoice.json")
```

**Parameters:**
- `path` (str | Path): Path where the invoice file will be created. Defaults to "invoice.json"

#### Attributes

- `path` (str | Path): The target path for the generated invoice file

#### Methods

##### generate()

Generate an invoice JSON file with default RDE structure.

```python
def generate() -> dict[str, Any]
```

**Returns:**
- `dict[str, Any]`: Dictionary containing the generated invoice data

**Example:**
```python
from rdetoolkit.cmd.command import InvoiceJsonGenerator

# Generate invoice file
generator = InvoiceJsonGenerator("data/invoice.json")
invoice_data = generator.generate()
```

### MainScriptGenerator

Generator class for creating main Python script templates.

#### Constructor

```python
MainScriptGenerator(path: str | Path)
```

**Parameters:**
- `path` (str | Path): Path where the main script will be created

#### Attributes

- `path` (str | Path): The target path for the generated main script

#### Methods

##### generate()

Generate a main Python script template for RDE workflows.

```python
def generate() -> list[str]
```

**Returns:**
- `list[str]`: List of strings representing the script content

**Example:**
```python
from rdetoolkit.cmd.command import MainScriptGenerator

# Generate main script
generator = MainScriptGenerator("container/main.py")
script_lines = generator.generate()
```

## Complete Usage Examples

### Basic Project Initialization

```python
from rdetoolkit.cmd.command import InitCommand

# Initialize a complete RDE project
def setup_new_project():
    """Set up a new RDE project with all necessary files."""
    try:
        init_command = InitCommand()
        init_command.invoke()
        print("Project initialized successfully!")
    except Exception as e:
        print(f"Initialization failed: {e}")

setup_new_project()
```

### Custom File Generation

```python
from pathlib import Path
from rdetoolkit.cmd.command import (
    DockerfileGenerator,
    RequirementsTxtGenerator,
    MainScriptGenerator
)

def create_custom_project_structure(base_path: str):
    """Create a custom project structure with generated files."""

    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)

    # Generate Dockerfile
    dockerfile_gen = DockerfileGenerator(base / "Dockerfile")
    dockerfile_gen.generate()
    print(f"Created Dockerfile at {base / 'Dockerfile'}")

    # Generate requirements.txt
    req_gen = RequirementsTxtGenerator(base / "requirements.txt")
    req_gen.generate()
    print(f"Created requirements.txt at {base / 'requirements.txt'}")

    # Generate main script
    main_gen = MainScriptGenerator(base / "main.py")
    main_gen.generate()
    print(f"Created main.py at {base / 'main.py'}")

# Usage
create_custom_project_structure("my_rde_project")
```

### Batch File Generation for Multiple Environments

```python
from pathlib import Path
from rdetoolkit.cmd.command import (
    DockerfileGenerator,
    RequirementsTxtGenerator,
    InvoiceSchemaJsonGenerator,
    MetadataDefJsonGenerator,
    InvoiceJsonGenerator
)

def setup_multiple_environments(environments: list[str], base_dir: str):
    """Set up multiple RDE environments with generated files."""

    base_path = Path(base_dir)

    for env in environments:
        env_path = base_path / env
        env_path.mkdir(parents=True, exist_ok=True)

        print(f"Setting up environment: {env}")

        # Create container files
        container_path = env_path / "container"
        container_path.mkdir(exist_ok=True)

        # Generate Docker files
        DockerfileGenerator(container_path / "Dockerfile").generate()
        RequirementsTxtGenerator(container_path / "requirements.txt").generate()

        # Create data directories and files
        data_path = container_path / "data"
        invoice_path = data_path / "invoice"
        tasksupport_path = data_path / "tasksupport"

        invoice_path.mkdir(parents=True, exist_ok=True)
        tasksupport_path.mkdir(parents=True, exist_ok=True)

        # Generate JSON files
        InvoiceJsonGenerator(invoice_path / "invoice.json").generate()
        InvoiceSchemaJsonGenerator(tasksupport_path / "invoice.schema.json").generate()
        MetadataDefJsonGenerator(tasksupport_path / "metadata-def.json").generate()

        print(f"✅ Environment {env} setup complete")

# Usage
environments = ["development", "testing", "production"]
setup_multiple_environments(environments, "rde_environments")
```

### Advanced Project Template Creation

```python
from pathlib import Path
from rdetoolkit.cmd.command import InitCommand
import shutil

class CustomRDEProject:
    """Custom RDE project creator with additional features."""

    def __init__(self, project_name: str, base_dir: str = "."):
        self.project_name = project_name
        self.base_dir = Path(base_dir)
        self.project_path = self.base_dir / project_name

    def create_project(self, include_samples: bool = True):
        """Create a complete RDE project with optional sample data."""

        # Create project directory
        self.project_path.mkdir(parents=True, exist_ok=True)

        # Change to project directory and initialize
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(self.project_path)

            # Initialize standard RDE structure
            init_cmd = InitCommand()
            init_cmd.invoke()

            if include_samples:
                self._create_sample_data()

            self._create_readme()

        finally:
            os.chdir(original_cwd)

        print(f"Project '{self.project_name}' created successfully at {self.project_path}")

    def _create_sample_data(self):
        """Create sample data files for development."""
        sample_data = {
            "input/inputdata/sample.csv": "id,name,value\n1,Sample,100\n2,Test,200\n",
            "container/modules/sample_module.py": (
                "# Sample module for RDE processing\n\n"
                "def process_data(data):\n"
                "    \"\"\"Process input data.\"\"\"\n"
                "    return data\n"
            )
        }

        for file_path, content in sample_data.items():
            full_path = Path(file_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

    def _create_readme(self):
        """Create a README file with project information."""
        readme_content = f"""# {self.project_name}

RDE (Research Data Exchange) Project

## Structure

- `container/`: Main application container
- `input/`: Input data and configurations
- `templates/`: Template files for data processing

## Getting Started

1. Install dependencies:
   ```bash
   cd container
   pip install -r requirements.txt
   ```

2. Run the main script:
   ```bash
   python main.py
   ```

## Generated with RDEToolkit

This project was generated using RDEToolkit command utilities.
"""
        (Path("README.md")).write_text(readme_content, encoding="utf-8")

# Usage
project = CustomRDEProject("my_research_project")
project.create_project(include_samples=True)
```

### Version Management Integration

```python
from rdetoolkit.cmd.command import VersionCommand
import subprocess
import sys

def check_toolkit_version():
    """Check and display toolkit version information."""

    print("RDEToolkit Version Information:")
    print("=" * 40)

    # Display current version
    version_cmd = VersionCommand()
    print("Current version: ", end="")
    version_cmd.invoke()

    # Check if updates are available (conceptual)
    try:
        # This would typically check against a package repository
        print("\nChecking for updates...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "list", "--outdated"
        ], capture_output=True, text=True)

        if "rdetoolkit" in result.stdout:
            print("⚠️  Update available!")
        else:
            print("✅ You're using the latest version")

    except Exception as e:
        print(f"Could not check for updates: {e}")

# Usage
check_toolkit_version()
```

## Error Handling

### Common Exceptions

The command module operations may raise the following exceptions:

#### click.Abort
Raised when command execution is aborted due to errors:

```python
from rdetoolkit.cmd.command import InitCommand

try:
    init_cmd = InitCommand()
    init_cmd.invoke()
except click.Abort:
    print("Command execution was aborted")
    # Check console output for specific error details
```

#### FileExistsError
May be raised when files already exist and cannot be overwritten:

```python
from pathlib import Path
from rdetoolkit.cmd.command import DockerfileGenerator

# Check if file exists before generation
dockerfile_path = Path("Dockerfile")
if dockerfile_path.exists():
    response = input(f"{dockerfile_path} exists. Overwrite? (y/N): ")
    if response.lower() != 'y':
        print("Generation cancelled")
    else:
        generator = DockerfileGenerator(dockerfile_path)
        generator.generate()
```

#### PermissionError
May be raised if there are insufficient permissions to create files or directories:

```python
try:
    init_cmd = InitCommand()
    init_cmd.invoke()
except PermissionError as e:
    print(f"Permission denied: {e}")
    print("Check write permissions for the current directory")
```

### Best Practices

1. **Check directory permissions before initialization**:
   ```python
   import os
   from pathlib import Path

   def check_permissions(path: Path) -> bool:
       """Check if directory is writable."""
       try:
           test_file = path / ".test_write"
           test_file.touch()
           test_file.unlink()
           return True
       except (OSError, PermissionError):
           return False

   if check_permissions(Path.cwd()):
       init_cmd = InitCommand()
       init_cmd.invoke()
   else:
       print("Insufficient permissions to create project files")
   ```

2. **Backup existing files before overwriting**:
   ```python
   from pathlib import Path
   import shutil

   def safe_generate_file(generator, target_path: Path):
       """Safely generate file with backup."""
       if target_path.exists():
           backup_path = target_path.with_suffix(f"{target_path.suffix}.backup")
           shutil.copy2(target_path, backup_path)
           print(f"Backed up existing file to {backup_path}")

       generator.generate()
   ```

3. **Validate project structure after initialization**:
   ```python
   def validate_project_structure():
       """Validate that all required files were created."""
       required_files = [
           "container/main.py",
           "container/Dockerfile",
           "container/requirements.txt",
           "input/invoice/invoice.json"
       ]

       missing_files = []
       for file_path in required_files:
           if not Path(file_path).exists():
               missing_files.append(file_path)

       if missing_files:
           print("Warning: Missing files:")
           for file in missing_files:
               print(f"  - {file}")
       else:
           print("✅ All required files created successfully")
   ```

## Performance Notes

- File generation operations are lightweight and typically complete in milliseconds
- Directory creation is optimized with `parents=True` and `exist_ok=True` options
- JSON file generation uses efficient encoding with `ensure_ascii=False` for international character support
- The initialization process creates files sequentially; for large projects, consider parallel generation
- Memory usage is minimal as files are written directly to disk without buffering large content

## Integration with Other Modules

### Logging Integration

The command module integrates with the RDE logging system:

```python
from rdetoolkit.rdelogger import get_logger

# Used internally for error logging and debugging
logger = get_logger(__name__)
```

### Schema Integration

Commands use schema models for structured data generation:

```python
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson, Properties
from rdetoolkit.cmd.default import INVOICE_JSON, PROPATIES

# Used for generating valid invoice schemas and data
```

### Version Integration

Version information is automatically included in generated files:

```python
from rdetoolkit import __version__

# Automatically included in requirements.txt and other generated files
```

## See Also

- [Default Configuration](default.md) - For default values and templates
- [Invoice Schema Models](models/invoice_schema.md) - For schema data structures
- [RDE Logger](rdelogger.md) - For logging functionality
- [Workflows Module](workflows.md) - For processing workflows integration
