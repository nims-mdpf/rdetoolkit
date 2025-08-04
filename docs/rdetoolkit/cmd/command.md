# Command API

## Purpose

This module defines the base classes and various commands for RDEToolKit's command-line interface. It provides common functionality including command execution, argument validation, log configuration, and error handling.

## Key Features

### Command Base Classes
- Unified interface for command execution
- Initialization and version display commands
- Various generator commands

### File Generation Functionality
- Automatic Dockerfile generation
- requirements.txt generation
- Configuration file generation

---

::: src.rdetoolkit.cmd.command.Command

---

::: src.rdetoolkit.cmd.command.InitCommand

---

::: src.rdetoolkit.cmd.command.VersionCommand

---

::: src.rdetoolkit.cmd.command.DockerfileGenerator

---

::: src.rdetoolkit.cmd.command.RequirementsTxtGenerator

---

::: src.rdetoolkit.cmd.command.InvoiceSchemaJsonGenerator

---

::: src.rdetoolkit.cmd.command.MetadataDefJsonGenerator

---

::: src.rdetoolkit.cmd.command.InvoiceJsonGenerator

---

::: src.rdetoolkit.cmd.command.MainScriptGenerator

---

## Practical Usage

### Basic Command Execution

```python title="basic_command_execution.py"
from rdetoolkit.cmd.command import InitCommand, VersionCommand

# Execute initialization command
init_command = InitCommand()
try:
    result = init_command.invoke()
    print(f"✓ Initialization completed: {result}")
except Exception as e:
    print(f"✗ Initialization error: {e}")

# Execute version display command
version_command = VersionCommand()
try:
    version_info = version_command.invoke()
    print(f"RDEToolKit version: {version_info}")
except Exception as e:
    print(f"✗ Version retrieval error: {e}")
```

### Using File Generation Commands

```python title="file_generation_commands.py"
from rdetoolkit.cmd.command import (
    DockerfileGenerator, RequirementsTxtGenerator,
    InvoiceSchemaJsonGenerator, MetadataDefJsonGenerator
)
from pathlib import Path

# Prepare output directory
output_dir = Path("generated_files")
output_dir.mkdir(exist_ok=True)

# Generate Dockerfile
dockerfile_gen = DockerfileGenerator()
try:
    dockerfile_content = dockerfile_gen.generate()
    dockerfile_path = output_dir / "Dockerfile"
    
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)
    
    print(f"✓ Dockerfile generation completed: {dockerfile_path}")
except Exception as e:
    print(f"✗ Dockerfile generation error: {e}")

# Generate requirements.txt
requirements_gen = RequirementsTxtGenerator()
try:
    requirements_content = requirements_gen.generate()
    requirements_path = output_dir / "requirements.txt"
    
    with open(requirements_path, 'w') as f:
        f.write(requirements_content)
    
    print(f"✓ requirements.txt generation completed: {requirements_path}")
except Exception as e:
    print(f"✗ requirements.txt generation error: {e}")

# Generate Invoice schema JSON
invoice_schema_gen = InvoiceSchemaJsonGenerator()
try:
    schema_content = invoice_schema_gen.generate()
    schema_path = output_dir / "invoice.schema.json"
    
    with open(schema_path, 'w') as f:
        f.write(schema_content)
    
    print(f"✓ Invoice schema generation completed: {schema_path}")
except Exception as e:
    print(f"✗ Invoice schema generation error: {e}")

# Generate metadata definition JSON
metadata_def_gen = MetadataDefJsonGenerator()
try:
    metadata_content = metadata_def_gen.generate()
    metadata_path = output_dir / "metadata_def.json"
    
    with open(metadata_path, 'w') as f:
        f.write(metadata_content)
    
    print(f"✓ Metadata definition generation completed: {metadata_path}")
except Exception as e:
    print(f"✗ Metadata definition generation error: {e}")
```

### Project Initialization System

```python title="project_initialization.py"
from rdetoolkit.cmd.command import (
    InitCommand, DockerfileGenerator, RequirementsTxtGenerator,
    InvoiceJsonGenerator, MainScriptGenerator
)
from pathlib import Path

class ProjectInitializer:
    """Project initialization system"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.generators = {
            "dockerfile": DockerfileGenerator(),
            "requirements": RequirementsTxtGenerator(),
            "invoice": InvoiceJsonGenerator(),
            "main_script": MainScriptGenerator()
        }
    
    def initialize_project(self) -> dict:
        """Initialize project"""
        
        # Create project directory
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            "project_dir": str(self.project_dir),
            "generated_files": [],
            "failed_files": [],
            "status": "success"
        }
        
        # Execute initialization command
        init_command = InitCommand()
        try:
            init_result = init_command.invoke()
            print(f"✓ Project initialization: {init_result}")
        except Exception as e:
            print(f"✗ Initialization error: {e}")
            results["status"] = "partial_failure"
        
        # Generate various files
        file_configs = {
            "dockerfile": {"filename": "Dockerfile", "generator": "dockerfile"},
            "requirements": {"filename": "requirements.txt", "generator": "requirements"},
            "invoice": {"filename": "invoice_template.json", "generator": "invoice"},
            "main_script": {"filename": "main.py", "generator": "main_script"}
        }
        
        for file_type, config in file_configs.items():
            try:
                generator = self.generators[config["generator"]]
                content = generator.generate()
                
                file_path = self.project_dir / config["filename"]
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                results["generated_files"].append({
                    "type": file_type,
                    "filename": config["filename"],
                    "path": str(file_path)
                })
                
                print(f"✓ {config['filename']} generation completed")
                
            except Exception as e:
                results["failed_files"].append({
                    "type": file_type,
                    "filename": config["filename"],
                    "error": str(e)
                })
                
                print(f"✗ {config['filename']} generation failed: {e}")
                results["status"] = "partial_failure"
        
        return results
    
    def create_directory_structure(self):
        """Create directory structure"""
        
        directories = [
            "data/input",
            "data/output",
            "data/invoice",
            "data/tasksupport",
            "config",
            "scripts",
            "logs"
        ]
        
        for dir_path in directories:
            full_path = self.project_dir / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"✓ Directory created: {dir_path}")
    
    def generate_readme(self):
        """Generate README.md"""
        
        readme_content = f"""# RDEToolKit Project

This project was created using RDEToolKit.

## Directory Structure

```
{self.project_dir.name}/
├── data/
│   ├── input/          # Input data
│   ├── output/         # Output data
│   ├── invoice/        # Invoice files
│   └── tasksupport/    # Task support files
├── config/             # Configuration files
├── scripts/            # Script files
├── logs/               # Log files
├── Dockerfile          # Docker configuration
├── requirements.txt    # Python dependencies
├── main.py            # Main script
└── README.md          # This file
```

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run main script:
   ```bash
   python main.py
   ```

3. Run with Docker:
   ```bash
   docker build -t rdetoolkit-project .
   docker run rdetoolkit-project
   ```
"""
        
        readme_path = self.project_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"✓ README.md generation completed: {readme_path}")

# Usage example
project_name = "my_rde_project"
project_path = Path(f"projects/{project_name}")

initializer = ProjectInitializer(project_path)

print(f"=== {project_name} Project Initialization ===")

# Initialize project
init_results = initializer.initialize_project()

# Create directory structure
initializer.create_directory_structure()

# Generate README.md
initializer.generate_readme()

# Results summary
print(f"\n=== Initialization Results ===")
print(f"Project directory: {init_results['project_dir']}")
print(f"Generated files: {len(init_results['generated_files'])}")
print(f"Failed files: {len(init_results['failed_files'])}")
print(f"Status: {init_results['status']}")

if init_results["failed_files"]:
    print("\nFailed files:")
    for failed_file in init_results["failed_files"]:
        print(f"  - {failed_file['filename']}: {failed_file['error']}")
```
