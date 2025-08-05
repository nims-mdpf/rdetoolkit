# Result Models API

## Purpose

This module defines result models for RDEToolKit operations. It provides structured result representations, status tracking, and error reporting for various processing operations.

## Key Features

### Result Structure Models
- Standardized result format definitions
- Status and error tracking
- Operation outcome representation

### Error Reporting
- Detailed error information
- Success/failure status tracking
- Result metadata management

---

::: src.rdetoolkit.models.result

---

## Practical Usage

### Basic Result Handling

```python title="result_handling.py"
from rdetoolkit.models.result import ProcessingResult

# Create processing result
result = ProcessingResult(
    status="success",
    message="Processing completed successfully",
    data={"processed_files": 10, "errors": 0}
)

print(f"Status: {result.status}")
print(f"Message: {result.message}")
print(f"Data: {result.data}")
```
