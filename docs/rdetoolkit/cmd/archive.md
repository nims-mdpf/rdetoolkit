# Archive Module

The `rdetoolkit.cmd.archive` module provides functionality for creating project archives with automated security scanning and report generation. This module is designed to package Python projects into compressed archives while analyzing code for potential security vulnerabilities and external dependencies.

## Overview

The archive module offers comprehensive project archiving capabilities with built-in analysis features:

- **Project Archiving**: Create compressed archives of Python projects with configurable exclusion patterns
- **Security Scanning**: Automated vulnerability detection and external connection analysis
- **Report Generation**: Markdown reports with scan results and project metadata
- **File Detection**: Automatic detection of important project files (Dockerfile, requirements.txt)

## Classes

### CreateArtifactCommand

A command class that orchestrates the complete artifact creation process, including archiving, scanning, and report generation.

#### Constructor

```python
CreateArtifactCommand(source_dir: pathlib.Path, *, output_archive_path: pathlib.Path | None = None, exclude_patterns: list[str] | None = None)
```

**Parameters:**
- `source_dir` (pathlib.Path): Source directory containing the project to archive
- `output_archive_path` (pathlib.Path | None): Output path for the archive file. If None, generates a default filename with timestamp and UUID
- `exclude_patterns` (list[str] | None): List of patterns to exclude from archiving. Defaults to `['.*', 'venv', '.venv', 'site-packages']`

#### Class Constants

The class defines several emoji markers for output formatting:

- `MARK_SUCCESS` = "✅": Success operations
- `MARK_WARNING` = "⚠️": Warning messages
- `MARK_ERROR` = "🔥": Error conditions
- `MARK_INFO` = "📌": Information messages
- `MARK_SCAN` = "🔍": Scanning operations
- `MARK_ARCHIVE` = "📦": Archive operations

#### Attributes

- `source_dir` (pathlib.Path): The source directory to archive
- `output_archive_path` (pathlib.Path): Path where the archive will be created
- `exclude_patterns` (list[str]): Patterns to exclude during archiving
- `template_report_generator` (TemplateMarkdownReportGenerator): Report generator instance

#### Methods

##### invoke()

Execute the complete artifact creation process.

```python
def invoke() -> None
```

**Raises:**
- `click.Abort`: If any step in the process fails

**Example:**
```python
import pathlib
from rdetoolkit.cmd.archive import CreateArtifactCommand

# Create an artifact with default settings
source = pathlib.Path("/path/to/project")
command = CreateArtifactCommand(source)
command.invoke()
```

##### \_check\_file(target_filename, *, logo=None)

Check for the existence of a specific file in the project directory.

```python
def _check_file(target_filename: str, *, logo: str | None = None) -> str
```

**Parameters:**
- `target_filename` (str): Name of the file to search for
- `logo` (str | None): Optional emoji or symbol to display with the filename

**Returns:**
- `str`: Relative path to the file if found, or "{filename} not found" if not found

**Example:**
```python
# Check for Dockerfile
dockerfile_path = command._check_file("Dockerfile", logo="🐳")
```

##### \_check\_extention\_type()

Validate the output archive file extension.

```python
def _check_extention_type() -> str
```

**Returns:**
- `str`: The file extension without the leading dot

**Raises:**
- `click.Abort`: If the extension is not .zip

##### \_archive\_target\_dir(fmt)

Create the archive file using the specified format.

```python
def _archive_target_dir(fmt: str) -> list[pathlib.Path] | None
```

**Parameters:**
- `fmt` (str): Archive format (currently supports "zip")

**Returns:**
- `list[pathlib.Path] | None`: List of directories included in the archive

**Raises:**
- `click.Abort`: If archiving fails

##### \_scan\_external\_conn()

Scan the project for external connection references.

```python
def _scan_external_conn() -> list[CodeSnippet]
```

**Returns:**
- `list[CodeSnippet]`: List of code snippets containing external connections

**Raises:**
- `click.Abort`: If scanning fails

##### \_scan\_code\_security()

Scan the project for potential security vulnerabilities.

```python
def _scan_code_security() -> list[CodeSnippet]
```

**Returns:**
- `list[CodeSnippet]`: List of code snippets with potential security issues

**Raises:**
- `click.Abort`: If scanning fails

##### \_generate\_report(item)

Generate a markdown report with scan results and project information.

```python
def _generate_report(item: ReportItem) -> None
```

**Parameters:**
- `item` (ReportItem): Report data containing scan results and metadata

**Raises:**
- `click.Abort`: If report generation fails

##### \_safe\_relative(p)

Safely convert a path to a relative path string.

```python
def _safe_relative(p: pathlib.Path) -> str
```

**Parameters:**
- `p` (pathlib.Path): Path to convert

**Returns:**
- `str`: Relative path string or absolute path string if conversion fails

## Complete Usage Examples

### Basic Project Archiving

```python
import pathlib
from rdetoolkit.cmd.archive import CreateArtifactCommand

# Archive a project with default settings
project_dir = pathlib.Path("/path/to/my_project")
command = CreateArtifactCommand(project_dir)
command.invoke()

# This will create:
# - An archive file with timestamp and UUID in the filename
# - A markdown report with the same base name
# - Security and external connection scan results
```

### Custom Archive Configuration

```python
import pathlib
from rdetoolkit.cmd.archive import CreateArtifactCommand

# Custom archive path and exclusion patterns
source_dir = pathlib.Path("/path/to/project")
output_path = pathlib.Path("/output/my_project_archive.zip")
exclude_patterns = [
    ".*",           # Hidden files
    "venv",         # Virtual environment
    "__pycache__",  # Python cache
    "node_modules", # Node.js modules
    "*.log",        # Log files
]

command = CreateArtifactCommand(
    source_dir,
    output_archive_path=output_path,
    exclude_patterns=exclude_patterns
)

command.invoke()
```

### Programmatic Archive Creation

```python
import pathlib
from datetime import datetime
from rdetoolkit.cmd.archive import CreateArtifactCommand

def create_project_backup(project_path: str, backup_dir: str) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a project backup with timestamp."""

    source = pathlib.Path(project_path)
    backup_base = pathlib.Path(backup_dir)

    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = source.name
    archive_name = f"{project_name}_{timestamp}_backup.zip"

    output_path = backup_base / archive_name

    # Create the archive
    command = CreateArtifactCommand(
        source,
        output_archive_path=output_path,
        exclude_patterns=[
            ".*",
            "venv",
            ".venv",
            "__pycache__",
            "*.pyc",
            ".git"
        ]
    )

    try:
        command.invoke()
        return output_path, output_path.with_suffix(".md")
    except Exception as e:
        print(f"Backup failed: {e}")
        raise

# Usage
archive_path, report_path = create_project_backup(
    "/path/to/project",
    "/backups"
)
print(f"Archive created: {archive_path}")
print(f"Report created: {report_path}")
```

### Batch Project Archiving

```python
import pathlib
from rdetoolkit.cmd.archive import CreateArtifactCommand

def archive_multiple_projects(projects_dir: str, output_dir: str):
    """Archive multiple projects in a directory."""

    projects_path = pathlib.Path(projects_dir)
    output_path = pathlib.Path(output_dir)

    # Ensure output directory exists
    output_path.mkdir(parents=True, exist_ok=True)

    # Find all project directories (containing Python files)
    for project_dir in projects_path.iterdir():
        if not project_dir.is_dir():
            continue

        # Check if directory contains Python files
        python_files = list(project_dir.rglob("*.py"))
        if not python_files:
            continue

        print(f"Archiving project: {project_dir.name}")

        # Create archive for this project
        archive_name = f"{project_dir.name}_archive.zip"
        archive_path = output_path / archive_name

        try:
            command = CreateArtifactCommand(
                project_dir,
                output_archive_path=archive_path
            )
            command.invoke()
            print(f"✅ Successfully archived: {project_dir.name}")

        except Exception as e:
            print(f"❌ Failed to archive {project_dir.name}: {e}")

# Usage
archive_multiple_projects("/path/to/projects", "/path/to/archives")
```

## Error Handling

### Common Exceptions

The archive module operations may raise the following exceptions:

#### click.Abort
Raised when critical errors occur during the archiving process:

```python
try:
    command = CreateArtifactCommand(source_dir)
    command.invoke()
except click.Abort:
    print("Archive creation was aborted due to an error")
    # Check console output for specific error details
```

#### FileNotFoundError
May be raised if the source directory doesn't exist:

```python
import pathlib
from rdetoolkit.cmd.archive import CreateArtifactCommand

source_dir = pathlib.Path("/nonexistent/path")

if not source_dir.exists():
    print(f"Source directory does not exist: {source_dir}")
else:
    command = CreateArtifactCommand(source_dir)
    command.invoke()
```

#### PermissionError
May be raised if there are insufficient permissions:

```python
try:
    command = CreateArtifactCommand(source_dir, output_archive_path=output_path)
    command.invoke()
except PermissionError as e:
    print(f"Permission denied: {e}")
    print("Check write permissions for the output directory")
```

### Best Practices

1. **Validate paths before archiving**:
   ```python
   if not source_dir.exists():
       raise ValueError(f"Source directory does not exist: {source_dir}")
   if not source_dir.is_dir():
       raise ValueError(f"Source path is not a directory: {source_dir}")
   ```

2. **Ensure output directory exists**:
   ```python
   output_path.parent.mkdir(parents=True, exist_ok=True)
   ```

3. **Handle large projects gracefully**:
   ```python
   # Add more exclusion patterns for large projects
   exclude_patterns = [
       ".*",
       "venv", ".venv",
       "node_modules",
       "__pycache__", "*.pyc",
       "*.log", "*.tmp",
       ".git", ".svn",
       "build", "dist"
   ]
   ```

4. **Monitor disk space**:
   ```python
   import shutil

   # Check available disk space before archiving
   free_space = shutil.disk_usage(output_path.parent).free
   if free_space < 1_000_000_000:  # Less than 1GB
       print("Warning: Low disk space available")
   ```

## Performance Notes

- The archiving process is optimized for typical Python project structures
- Large projects with many files may take significant time to scan and archive
- Exclude patterns are applied during directory traversal to improve performance
- Security scanning performance depends on the size and complexity of the codebase
- Memory usage scales with the number of files and the complexity of scan patterns

## Integration with Other Modules

### Report Generation

The archive module integrates with the report generation system:

```python
from rdetoolkit.artifact.report import TemplateMarkdownReportGenerator
from rdetoolkit.models.reports import ReportItem

# The CreateArtifactCommand uses these internally
# but you can also use them directly for custom reporting
```

### Compression Support

Archives are created using the compressed controller:

```python
from rdetoolkit.impl.compressed_controller import get_artifact_archiver

# This is used internally by CreateArtifactCommand
# Currently supports ZIP format only
```

### Code Scanning

Security and external connection scanning is performed by:

```python
from rdetoolkit.artifact.report import get_scanner

# Used internally for vulnerability and external connection analysis
scanner_vuln = get_scanner('vulnerability', source_dir)
scanner_ext = get_scanner('external', source_dir)
```

## See Also

- [Artifact Report Module](artifact/report.md) - For custom report generation
- [Models Module](models/reports.md) - For report data structures
- [Compressed Controller](impl/compressed_controller.md) - For archive creation
- [Configuration Guide](../config.md) - For project configuration options
