# Report Generation API

## Purpose

This module provides report generation functionality for RDEToolKit. It creates comprehensive reports from structured processing results, including data summaries, visualizations, and analysis outputs.

## Key Features

### Report Generation
- Comprehensive processing result reports
- Data visualization and charts
- Customizable report templates

### Output Formats
- Support for multiple output formats
- PDF and HTML report generation
- Integration with processing workflows

---

::: src.rdetoolkit.artifact.report

---

## Practical Usage

### Basic Report Generation

```python title="report_generation.py"
from rdetoolkit.artifact.report import generate_report
from pathlib import Path

# Generate processing report
processing_results = {
    "processed_files": 10,
    "errors": 0,
    "warnings": 2,
    "processing_time": "00:05:30"
}

output_path = Path("data/reports/processing_report.html")
result = generate_report(processing_results, output_path)

print(f"Report generation result: {result}")
```
