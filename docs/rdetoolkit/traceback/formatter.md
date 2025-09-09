# Formatter API

## Purpose

The formatter module provides the core compact trace formatting functionality for converting Python tracebacks into structured, machine-readable format optimized for LLM and AI agent consumption. It implements the complete compact trace protocol with CFG, E, T, F, and RC line types.

## Key Features

### Structured Output Format
- **CFG Line**: Configuration and capabilities reporting
- **E Line**: Exception information with timestamp and type
- **T Line**: Optional execution timing information
- **F Lines**: Frame-by-frame call stack with context
- **RC Line**: Root cause identification with hints

### Intelligent Frame Detection
- Automatic application vs dependency code classification (`in_app` detection)
- Dynamic root cause frame identification for exception chains
- Context line extraction from source code
- Module path normalization and cleanup

### Security Integration
- Automatic sensitive information masking for local variables
- Configurable masking patterns and size limits
- Safe handling of potentially large variable dumps

---

## Core Classes

::: src.rdetoolkit.traceback.formatter.CompactTraceFormatter

---

## Practical Usage

### Basic Formatter Usage

```python title="basic_formatter.py"
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.traceback.masking import SecretsSanitizer
from rdetoolkit.models.config import TracebackSettings
import traceback

def demonstrate_basic_formatting():
    """Demonstrate basic compact trace formatting."""

    # Create formatter with basic settings
    settings = TracebackSettings(
        enabled=True,
        format="compact",
        include_context=True,
        include_locals=False,
        include_env=True
    )

    masker = SecretsSanitizer()
    formatter = CompactTraceFormatter(settings, masker)

    try:
        # Create a multi-level call stack
        level_one()
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        compact_trace = formatter.format(e, tb)
        print(compact_trace)

def level_one():
    """First level function."""
    level_two()

def level_two():
    """Second level function."""
    level_three()

def level_three():
    """Third level function that raises an error."""
    data = {"user": "test", "password": "secret123"}
    raise ValueError("Invalid data format")

# Run demonstration
demonstrate_basic_formatting()
```

### Advanced Configuration

```python title="advanced_formatter.py"
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.traceback.masking import SecretsSanitizer
from rdetoolkit.models.config import TracebackSettings
import traceback

def create_ai_optimized_formatter():
    """Create formatter optimized for AI analysis."""

    settings = TracebackSettings(
        enabled=True,
        format="compact",
        include_context=True,
        include_locals=True,          # Include for AI analysis
        include_env=True,
        max_locals_size=1024,         # Larger limit for AI
        sensitive_patterns=[          # Custom patterns
            "database_url",
            "private_key",
            "connection_string"
        ]
    )

    # Create masker with custom patterns
    masker = SecretsSanitizer(
        additional_patterns=settings.sensitive_patterns,
        max_size=settings.max_locals_size
    )

    return CompactTraceFormatter(settings, masker)

def demonstrate_with_locals():
    """Demonstrate formatting with local variables."""

    formatter = create_ai_optimized_formatter()

    try:
        process_user_data()
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)

        # Format with local variables
        compact_trace = formatter.format(e, tb)
        print("=== Compact Trace with Locals ===")
        print(compact_trace)

def process_user_data():
    """Function with various local variables."""
    user_id = 12345
    username = "john_doe"
    email = "john@example.com"
    password = "secret_password_123"  # Will be masked
    api_key = "sk-1234567890abcdef"    # Will be masked
    database_url = "postgresql://user:pass@host/db"  # Custom pattern

    # Simulate processing
    user_data = {
        "id": user_id,
        "username": username,
        "email": email,
        "config": {
            "theme": "dark",
            "notifications": True
        }
    }

    if not user_data.get("id"):
        raise ValueError("User ID is required")

# Run demonstration
demonstrate_with_locals()
```

### Exception Chain Analysis

```python title="exception_chain_analysis.py"
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.traceback.masking import SecretsSanitizer
from rdetoolkit.models.config import TracebackSettings
import traceback

def demonstrate_exception_chains():
    """Demonstrate handling of exception chains (__cause__ and __context__)."""

    settings = TracebackSettings(
        enabled=True,
        format="compact",
        include_context=True,
        include_locals=False,
        include_env=False
    )

    formatter = CompactTraceFormatter(settings, SecretsSanitizer())

    try:
        outer_operation()
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        compact_trace = formatter.format(e, tb)

        print("=== Exception Chain Analysis ===")
        print(compact_trace)
        print("\nNote: RC line shows the actual root cause frame,")
        print("not necessarily F0 in complex exception chains.")

def outer_operation():
    """Outer operation that catches and re-raises."""
    try:
        middle_operation()
    except ValueError as e:
        # Re-raise with context
        raise RuntimeError("Operation failed in outer layer") from e

def middle_operation():
    """Middle operation that calls inner operation."""
    try:
        inner_operation()
    except Exception as e:
        # Add context and re-raise
        raise ValueError("Validation failed in middle layer") from e

def inner_operation():
    """Inner operation where the actual error occurs."""
    data = None
    if data is None:
        raise TypeError("Data cannot be None")  # Root cause

# Run demonstration
demonstrate_exception_chains()
```

### Custom Module Detection

```python title="custom_module_detection.py"
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.traceback.masking import SecretsSanitizer
from rdetoolkit.models.config import TracebackSettings
import traceback

class CustomCompactFormatter(CompactTraceFormatter):
    """Custom formatter with enhanced module detection."""

    def _is_application_code(self, filename: str, module_name: str) -> bool:
        """Enhanced application code detection."""
        # Call parent method first
        is_app = super()._is_application_code(filename, module_name)

        # Add custom logic for your organization
        custom_app_indicators = [
            'mycompany',
            'internal_tools',
            'custom_processors'
        ]

        # Check if any custom indicators are in the module path
        for indicator in custom_app_indicators:
            if indicator in module_name or indicator in filename:
                return True

        return is_app

    def _extract_module_name(self, filename: str) -> str:
        """Enhanced module name extraction."""
        module_name = super()._extract_module_name(filename)

        # Clean up internal module names
        if module_name.startswith('mycompany.internal.'):
            # Simplify internal module names
            parts = module_name.split('.')
            if len(parts) > 3:
                return f"internal.{'.'.join(parts[2:])}"

        return module_name

def demonstrate_custom_detection():
    """Demonstrate custom module detection."""

    settings = TracebackSettings(
        enabled=True,
        format="compact",
        include_context=True,
        include_locals=False,
        include_env=False
    )

    # Use custom formatter
    formatter = CustomCompactFormatter(settings, SecretsSanitizer())

    try:
        # Simulate code from different modules
        simulate_mixed_stack()
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        compact_trace = formatter.format(e, tb)

        print("=== Custom Module Detection ===")
        print(compact_trace)
        print("\nNote: in_app=1 indicates application code,")
        print("in_app=0 indicates dependency/library code")

def simulate_mixed_stack():
    """Simulate a call stack with mixed internal/external code."""
    # This would normally be in mycompany.internal.processor
    internal_processor()

def internal_processor():
    """Simulate internal company code."""
    # This would normally be external library code
    external_library_call()

def external_library_call():
    """Simulate external library that fails."""
    raise ConnectionError("Failed to connect to external service")

# Run demonstration
demonstrate_custom_detection()
```

### Performance Optimization

```python title="performance_optimization.py"
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.traceback.masking import SecretsSanitizer
from rdetoolkit.models.config import TracebackSettings
import traceback
import time

def benchmark_formatter_performance():
    """Benchmark formatter performance with different configurations."""

    configurations = [
        ("minimal", TracebackSettings(
            enabled=True,
            format="compact",
            include_context=False,
            include_locals=False,
            include_env=False
        )),
        ("context_only", TracebackSettings(
            enabled=True,
            format="compact",
            include_context=True,
            include_locals=False,
            include_env=False
        )),
        ("full_featured", TracebackSettings(
            enabled=True,
            format="compact",
            include_context=True,
            include_locals=True,
            include_env=True,
            max_locals_size=1024
        ))
    ]

    for config_name, settings in configurations:
        formatter = CompactTraceFormatter(settings, SecretsSanitizer())

        # Benchmark formatting time
        start_time = time.time()

        for _ in range(100):  # Format same error 100 times
            try:
                create_deep_stack(10)  # 10-level deep stack
            except Exception as e:
                tb = traceback.extract_tb(e.__traceback__)
                formatter.format(e, tb)

        end_time = time.time()
        avg_time = (end_time - start_time) / 100 * 1000  # ms per format

        print(f"{config_name:15}: {avg_time:.2f}ms per format")

def create_deep_stack(depth: int):
    """Create a deep call stack for benchmarking."""
    if depth <= 0:
        # Create local variables for testing
        data = {"key": "value", "number": 42}
        secret_key = "sk-secret123"
        user_info = {"name": "test", "password": "hidden"}
        raise RuntimeError("Deep stack error")

    create_deep_stack(depth - 1)

# Run benchmark
print("Formatter Performance Benchmark:")
benchmark_formatter_performance()
```

### Integration with Error Reporting

```python title="error_reporting_integration.py"
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.traceback.masking import SecretsSanitizer
from rdetoolkit.models.config import TracebackSettings
import traceback
import json
from datetime import datetime

class ErrorReportingSystem:
    """Error reporting system with compact trace integration."""

    def __init__(self):
        self.settings = TracebackSettings(
            enabled=True,
            format="compact",
            include_context=True,
            include_locals=True,
            include_env=True,
            max_locals_size=512
        )

        self.formatter = CompactTraceFormatter(self.settings, SecretsSanitizer())

    def create_error_report(self, exception, context_info=None):
        """Create comprehensive error report."""
        tb = traceback.extract_tb(exception.__traceback__)
        compact_trace = self.formatter.format(exception, tb)

        report = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "compact_trace": compact_trace,
            "context": context_info or {},
            "report_version": "1.0"
        }

        return report

    def send_to_monitoring(self, report):
        """Send report to monitoring system."""
        # Implementation would depend on your monitoring system
        print("=== Error Report ===")
        print(json.dumps(report, indent=2))
        print("\n=== Compact Trace ===")
        print(report["compact_trace"])

def demonstrate_error_reporting():
    """Demonstrate error reporting system."""

    reporting_system = ErrorReportingSystem()

    try:
        business_logic_operation()
    except Exception as e:
        # Create report with context
        report = reporting_system.create_error_report(
            e,
            context_info={
                "user_id": "user123",
                "operation": "data_processing",
                "batch_id": "batch456"
            }
        )

        # Send to monitoring
        reporting_system.send_to_monitoring(report)

def business_logic_operation():
    """Business logic that might fail."""
    config = {
        "max_retries": 3,
        "timeout": 30,
        "api_key": "secret_key_123"  # Will be masked
    }

    data = {"items": [1, 2, 3]}

    if len(data["items"]) < 5:
        raise ValueError("Insufficient data items for processing")

# Run demonstration
demonstrate_error_reporting()
```
