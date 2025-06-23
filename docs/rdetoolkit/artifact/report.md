# Report Module

The `rdetoolkit.artifact.report` module provides comprehensive report generation and code analysis functionality for RDE (Research Data Exchange) artifact creation. This module offers security scanning, external communication detection, and automated markdown report generation capabilities.

## Overview

The report module offers specialized functionality for artifact analysis and reporting:

- **Security Scanning**: Detection of common security vulnerabilities in Python code
- **External Communication Analysis**: Identification of external network communication patterns
- **Report Generation**: Automated markdown report creation with customizable templates
- **Code Analysis**: Pattern-based code scanning with context extraction
- **Flexible Architecture**: Interface-based design supporting multiple scanner types
- **Logging Integration**: Comprehensive error logging and debugging support

## Classes

### TemplateMarkdownReportGenerator

A report generator that creates markdown reports using customizable templates with data substitution.

#### Constructor

```python
TemplateMarkdownReportGenerator(template_str: str | None = None) -> None
```

**Parameters:**

- `template_str` (str | None): Custom template string (optional, uses default template if None)

**Attributes:**

- `template_str` (str): The template string with placeholder variables
- `template` (Template): Python Template object for variable substitution
- `text` (str): Generated report text after calling generate()

**Default Template Structure:**

- Execution date and status information
- Dockerfile and requirements file status
- Included directories listing
- Code security scan results
- External communication check results

#### TemplateMarkdownReportGenerator Methods

##### generate

Generate a report string based on provided data.

```python
def generate(self, data: ReportItem) -> str
```

**Parameters:**

- `data` (ReportItem): Object containing report data including scan results and metadata

**Returns:**

- `str`: Generated report as markdown string

**Report Components:**

- Dockerfile status (exists/not found with path)
- Requirements file status (exists/not found with path)
- List of included directories/files
- Security vulnerability analysis results
- External communication code snippets

##### save

Save the generated report to a specified file path.

```python
def save(self, output_path: str | Path) -> None
```

**Parameters:**

- `output_path` (str | Path): Path where the report will be saved

**Raises:**

- `FileNotFoundError`: If no report has been generated (text is empty)

**Example:**

```python
from rdetoolkit.artifact.report import TemplateMarkdownReportGenerator
from rdetoolkit.models.reports import ReportItem
from pathlib import Path

# Create generator with default template
generator = TemplateMarkdownReportGenerator()

# Create custom template
custom_template = """
# Security Analysis Report

**Date:** $exec_date

## Infrastructure
- Dockerfile: $dockerfile_status
- Requirements: $requirements_status

## Vulnerabilities
$vuln_results

## External Communications
$ext_comm_results
"""

custom_generator = TemplateMarkdownReportGenerator(custom_template)

# Generate report (assuming report_data is populated)
report_text = generator.generate(report_data)

# Save report
generator.save("reports/security_analysis.md")
```

### CodeSecurityScanner

A security scanner that detects common vulnerabilities in Python code using pattern matching.

#### CodeSecurityScanner Constructor

```python
CodeSecurityScanner(source_dir: str | Path)
```

**Parameters:**

- `source_dir` (str | Path): Directory path to scan for Python files

**Attributes:**

- `source_dir` (Path): Source directory for scanning
- `results` (list[CodeSnippet]): List of detected vulnerability snippets
- `_vuln_patterns` (tuple): Predefined vulnerability patterns to detect

**Vulnerability Patterns Detected:**

- `eval()` usage - Arbitrary code execution risk
- `os.system()` usage - Command injection vulnerabilities
- `subprocess` calls - Command injection risks
- `pickle.load()` usage - Untrusted data deserialization
- `mktemp()` usage - Race condition risks
- SQL injection via string formatting

#### CodeSecurityScanner Methods

##### scan_file

Scan a single file for security vulnerabilities.

```python
def scan_file(self, file_path: Path) -> None
```

**Parameters:**

- `file_path` (Path): Path to the file to scan

**Behavior:**

- Reads file line by line
- Searches for vulnerability patterns using regex
- Extracts code snippets with context (3 lines before, 4 lines after)
- Stores results in internal results list
- Logs errors if file cannot be read

##### scan

Scan the entire source directory for Python files.

```python
def scan(self) -> list[CodeSnippet]
```

**Returns:**

- `list[CodeSnippet]`: List of detected vulnerability code snippets

**Behavior:**

- Recursively traverses source directory
- Excludes "venv" and "site-packages" directories
- Processes only Python (.py) files
- Returns accumulated scan results

##### get_results

Retrieve the current scan results.

```python
def get_results(self) -> list[CodeSnippet]
```

**Returns:**

- `list[CodeSnippet]`: List of detected code snippets

**Example:**

```python
from rdetoolkit.artifact.report import CodeSecurityScanner
from pathlib import Path

# Create scanner
scanner = CodeSecurityScanner("src/myproject")

# Scan all Python files
vulnerabilities = scanner.scan()

# Process results
for vuln in vulnerabilities:
    print(f"Vulnerability in {vuln.file_path}:")
    print(f"Description: {vuln.description}")
    print(f"Code snippet:\n{vuln.snippet}")
    print("-" * 50)

# Scan specific file
scanner.scan_file(Path("src/myproject/utils.py"))
specific_results = scanner.get_results()
```

### ExternalConnScanner

A scanner that detects external communication patterns in Python code.

#### ExternalConnScanner Constructor

```python
ExternalConnScanner(source_dir: str | Path)
```

**Parameters:**

- `source_dir` (str | Path): Directory path to scan for external communication

**Attributes:**

- `source_dir` (Path): Source directory for scanning
- `external_comm_packages` (list[str]): List of packages that indicate external communication

**Monitored Packages:**

- `requests`, `urllib`, `urllib3`
- `httplib`, `http.client`
- `socket`, `ftplib`, `telnetlib`
- `smtplib`, `aiohttp`, `httpx`
- `pycurl`

#### ExternalConnScanner Methods

##### scan_directory

Scan the source directory for external communication patterns.

```python
def scan(self) -> list[CodeSnippet]
```

**Returns:**

- `list[CodeSnippet]`: List of code snippets containing external communication

**Behavior:**

- Builds regex patterns for import statements and package usage
- Scans Python files for pattern matches
- Extracts code snippets with line numbers and context
- Excludes "venv" and "site-packages" directories
- Returns collected code snippets

**Pattern Detection:**

- Import statements (`import requests`)
- From imports (`from urllib import request`)
- Aliased imports (`import requests as req`)
- Package usage (`requests.get()`)

**Example:**

```python
from rdetoolkit.artifact.report import ExternalConnScanner

# Create scanner
ext_scanner = ExternalConnScanner("src/myproject")

# Scan for external communication
external_comms = ext_scanner.scan()

# Process results
for comm in external_comms:
    print(f"External communication found in {comm.file_path}:")
    print(f"Code snippet:\n{comm.snippet}")
    print("-" * 50)

# Check if any external communications were found
if external_comms:
    print(f"Found {len(external_comms)} instances of external communication")
else:
    print("No external communication detected")
```

## Functions

### get_scanner

Factory function to create scanner instances based on type.

```python
def get_scanner(scanner_type: Literal["vulnerability", "external"], source_dir: str | Path) -> ICodeScanner
```

**Parameters:**

- `scanner_type` (Literal["vulnerability", "external"]): Type of scanner to create
- `source_dir` (str | Path): Directory to scan

**Returns:**

- `ICodeScanner`: Instance of the appropriate scanner

**Raises:**

- `ValueError`: If scanner_type is not "vulnerability" or "external"

**Example:**

```python
from rdetoolkit.artifact.report import get_scanner

# Create vulnerability scanner
vuln_scanner = get_scanner("vulnerability", "src/myproject")
vulnerabilities = vuln_scanner.scan()

# Create external communication scanner
ext_scanner = get_scanner("external", "src/myproject")
external_comms = ext_scanner.scan()

# Process both types of results
print(f"Found {len(vulnerabilities)} vulnerabilities")
print(f"Found {len(external_comms)} external communications")
```

## Integrated Analysis Workflow

### Basic Security Analysis

```python
from rdetoolkit.artifact.report import (
    TemplateMarkdownReportGenerator,
    get_scanner
)
from rdetoolkit.models.reports import ReportItem, CodeSnippet
from datetime import datetime
from pathlib import Path

def analyze_project_security(project_dir: str, output_file: str):
    """Perform comprehensive security analysis of a project."""

    project_path = Path(project_dir)

    # Create scanners
    vuln_scanner = get_scanner("vulnerability", project_path)
    ext_scanner = get_scanner("external", project_path)

    # Perform scans
    print("Scanning for vulnerabilities...")
    vulnerabilities = vuln_scanner.scan()

    print("Scanning for external communications...")
    external_comms = ext_scanner.scan()

    # Check for infrastructure files
    dockerfile_path = project_path / "Dockerfile"
    requirements_path = project_path / "requirements.txt"

    # Collect directory information
    include_dirs = [
        str(p.relative_to(project_path))
        for p in project_path.rglob("*")
        if p.is_dir() and not any(exclude in str(p) for exclude in ["__pycache__", ".git", "venv"])
    ]

    # Create report data
    report_data = ReportItem(
        exec_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        dockerfile_path=str(dockerfile_path) if dockerfile_path.exists() else None,
        requirements_path=str(requirements_path) if requirements_path.exists() else None,
        include_dirs=include_dirs,
        code_security_scan_results=vulnerabilities,
        code_ext_requests_scan_results=external_comms
    )

    # Generate report
    generator = TemplateMarkdownReportGenerator()
    report_text = generator.generate(report_data)
    generator.save(output_file)

    print(f"Analysis complete. Report saved to: {output_file}")
    print(f"Vulnerabilities found: {len(vulnerabilities)}")
    print(f"External communications found: {len(external_comms)}")

# Usage
analyze_project_security("src/myproject", "reports/security_analysis.md")
```

### Custom Template Usage

```python
from rdetoolkit.artifact.report import TemplateMarkdownReportGenerator

def create_custom_security_report(data, output_path):
    """Create a security report with custom formatting."""

    custom_template = """
# 🔒 Security Analysis Report

**Analysis Date:** $exec_date

---

## 📋 Project Infrastructure

| Component    | Status               |
| ------------ | -------------------- |
| Dockerfile   | $dockerfile_status   |
| Requirements | $requirements_status |

## 📁 Project Structure

$included_dirs

---

## ⚠️ Security Vulnerabilities

$vuln_results

---

## 🌐 External Communications

$ext_comm_results

---

**Report Generated by RDE Toolkit**
"""

    generator = TemplateMarkdownReportGenerator(custom_template)
    report = generator.generate(data)
    generator.save(output_path)

    return report

# Usage with custom template
# custom_report = create_custom_security_report(report_data, "custom_report.md")
```

### Scanner Configuration and Filtering

```python
from rdetoolkit.artifact.report import CodeSecurityScanner, ExternalConnScanner

def filtered_security_scan(source_dir: str, exclude_patterns: list[str] = None):
    """Perform security scan with file filtering."""

    exclude_patterns = exclude_patterns or ["test_", "_test.py", "tests/"]

    # Create scanner
    scanner = CodeSecurityScanner(source_dir)

    # Get all Python files
    source_path = Path(source_dir)
    python_files = list(source_path.rglob("*.py"))

    # Filter files
    filtered_files = [
        f for f in python_files
        if not any(pattern in str(f) for pattern in exclude_patterns)
    ]

    # Scan filtered files
    for file_path in filtered_files:
        scanner.scan_file(file_path)

    return scanner.get_results()

def analyze_external_dependencies(source_dir: str):
    """Analyze external dependencies and categorize them."""

    ext_scanner = ExternalConnScanner(source_dir)
    external_comms = ext_scanner.scan()

    # Categorize by package type
    categories = {
        "HTTP": ["requests", "urllib", "httplib", "aiohttp", "httpx"],
        "Network": ["socket", "ftplib", "telnetlib"],
        "Email": ["smtplib"],
        "Other": ["pycurl"]
    }

    categorized = {cat: [] for cat in categories}

    for comm in external_comms:
        snippet_lower = comm.snippet.lower()
        categorized_item = False

        for category, packages in categories.items():
            if any(pkg in snippet_lower for pkg in packages):
                categorized[category].append(comm)
                categorized_item = True
                break

        if not categorized_item:
            categorized["Other"].append(comm)

    return categorized

# Usage
vulnerabilities = filtered_security_scan("src/myproject", ["test_", "demo_"])
dependencies = analyze_external_dependencies("src/myproject")
```

## Error Handling

### Scanner Error Management

```python
from rdetoolkit.artifact.report import CodeSecurityScanner
import logging

def robust_security_scan(source_dir: str):
    """Perform security scan with comprehensive error handling."""

    try:
        scanner = CodeSecurityScanner(source_dir)

        # Verify source directory exists
        if not Path(source_dir).exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        # Perform scan
        results = scanner.scan()

        if not results:
            print("No security vulnerabilities detected")
        else:
            print(f"Found {len(results)} potential security issues")

        return results

    except FileNotFoundError as e:
        logging.error(f"Directory error: {e}")
        return []
    except Exception as e:
        logging.error(f"Scan error: {e}")
        return []

def safe_report_generation(data, output_path):
    """Generate report with error handling."""

    try:
        generator = TemplateMarkdownReportGenerator()

        # Validate data
        if not hasattr(data, 'exec_date'):
            raise ValueError("Invalid report data: missing exec_date")

        # Generate and save
        report = generator.generate(data)
        generator.save(output_path)

        return True

    except FileNotFoundError as e:
        logging.error(f"Report generation error: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False

# Usage
results = robust_security_scan("src/myproject")
success = safe_report_generation(report_data, "analysis.md")
```

## Best Practices

### Scanner Usage

```python
# Always verify directory exists before scanning
if Path(source_dir).exists():
    scanner = get_scanner("vulnerability", source_dir)
    results = scanner.scan()

# Handle empty results gracefully
vulnerabilities = vuln_scanner.scan()
if not vulnerabilities:
    print("No vulnerabilities detected")

# Use appropriate scanner for the task
vuln_scanner = get_scanner("vulnerability", source_dir)  # For security issues
ext_scanner = get_scanner("external", source_dir)       # For external communications
```

### Report Generation

```python
# Always generate before saving
generator = TemplateMarkdownReportGenerator()
report_text = generator.generate(data)  # Generate first
generator.save(output_path)             # Then save

# Validate template variables
required_vars = ["exec_date", "dockerfile_status", "requirements_status"]
for var in required_vars:
    if f"${var}" not in generator.template_str:
        print(f"Warning: Template missing variable: {var}")

# Use meaningful output paths
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_path = f"reports/security_analysis_{timestamp}.md"
```

## Integration with RDE Workflows

```python
# Integration with RDE processing
from rdetoolkit.artifact.report import get_scanner, TemplateMarkdownReportGenerator

def integrate_security_analysis(workflow_results):
    """Integrate security analysis into RDE workflow."""

    # Scan processed code
    if workflow_results.get("processed_code_dir"):
        vuln_scanner = get_scanner("vulnerability", workflow_results["processed_code_dir"])
        vulnerabilities = vuln_scanner.scan()

        # Add to workflow results
        workflow_results["security_scan"] = {
            "vulnerabilities_count": len(vulnerabilities),
            "vulnerabilities": vulnerabilities
        }

    return workflow_results
```

## See Also

- [Models - Reports](../models/reports.md) - For ReportItem and CodeSnippet data structures
- [Interfaces - Report](../interfaces/report.md) - For ICodeScanner and IReportGenerator interfaces
- [RDE Logger](../rdelogger.md) - For logging functionality used in scanners
- [Artifact Processing](index.md) - For artifact creation and management workflows
- [Usage - CLI](../../usage/cli.md) - For command-line report generation examples
