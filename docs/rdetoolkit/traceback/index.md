# Traceback API

## Purpose

This module provides LLM/AI-friendly stacktrace formatting functionality for RDEToolkit. It enables automated error analysis, fix suggestions, bug report generation, and other automation scenarios by generating structured, machine-readable traceback information optimized for consumption by Large Language Models and AI agents.

## Key Features

### Dual Output Format System
- **Compact Format**: Structured, machine-readable format optimized for LLMs and AI agents
- **Python Format**: Traditional human-readable format for developers  
- **Duplex Mode**: Both formats simultaneously for maximum compatibility

### Security and Privacy
- Automatic masking of sensitive information (passwords, tokens, keys)
- Configurable sensitive pattern detection
- Size limits for variable output to prevent information leakage

### Flexible Configuration
- Environment variable control (TRACE_VERBOSE, TRACE_FORMAT)
- Programmatic configuration via Config objects
- Multiple disable options for production environments

---

## Modules

- [formatter](./formatter.md): Core compact trace formatting functionality
- [masking](./masking.md): Sensitive information masking and security features

---

## Core Classes

::: src.rdetoolkit.models.config.TracebackSettings

---

## Environment Integration

::: src.rdetoolkit.config.get_traceback_settings_from_env

---

## Error Handling Integration

::: src.rdetoolkit.errors.handle_exception

---

## Practical Usage

### Basic Activation

```python title="basic_activation.py"
import os
from rdetoolkit.errors import handle_exception

# Activate via environment variables
os.environ['TRACE_VERBOSE'] = 'context,locals'
os.environ['TRACE_FORMAT'] = 'duplex'

try:
    # Your code that might raise an exception
    risky_operation()
except Exception as e:
    structured_error = handle_exception(e)
    print(structured_error.traceback_info)
```

### Programmatic Configuration

```python title="programmatic_config.py"
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.errors import handle_exception

# Create AI-optimized configuration
ai_config = Config(
    traceback=TracebackSettings(
        enabled=True,
        format="compact",           # Machine-readable only
        include_context=True,       # Show error line code
        include_locals=False,       # Privacy protection
        include_env=False,          # Minimal info
        max_locals_size=256
    )
)

try:
    process_data()
except Exception as e:
    structured_error = handle_exception(e, config=ai_config)
    # Send to AI agent
    ai_response = analyze_with_ai(structured_error.traceback_info)
```

### AI Agent Integration

```python title="ai_agent_integration.py"
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.errors import handle_exception

def create_ai_error_handler():
    """Create error handler optimized for AI analysis."""
    return Config(
        traceback=TracebackSettings(
            enabled=True,
            format="compact",
            include_context=True,
            include_locals=False,  # Security first
            include_env=False,
            sensitive_patterns=[   # Custom masking
                "database_url",
                "private_key", 
                "connection_string"
            ]
        )
    )

def handle_error_with_ai(exception, custom_message=None):
    """Handle errors with AI-friendly output."""
    config = create_ai_error_handler()
    structured_error = handle_exception(exception, config=config, custom_error_message=custom_message)
    
    # Structured prompt for AI
    ai_prompt = f"""
    Error Analysis Request:
    
    Structured Traceback:
    {structured_error.traceback_info}
    
    Please analyze this error and provide:
    1. Root cause identification
    2. Suggested fix
    3. Prevention strategies
    """
    
    return send_to_llm(ai_prompt)

# Usage example
try:
    complex_operation()
except ValueError as e:
    suggestion = handle_error_with_ai(e, "Data validation failed")
    print(f"AI Suggestion: {suggestion}")
```

### Production Monitoring

```python title="production_monitoring.py"
import os
from rdetoolkit.errors import handle_exception
from rdetoolkit.models.config import Config, TracebackSettings

class ProductionErrorMonitor:
    """Production-safe error monitoring with AI integration."""
    
    def __init__(self, enable_ai_analysis=False):
        self.enable_ai_analysis = enable_ai_analysis
        
        # Production-safe configuration
        self.config = Config(
            traceback=TracebackSettings(
                enabled=enable_ai_analysis,
                format="compact" if enable_ai_analysis else "python",
                include_context=True,
                include_locals=False,     # Never in production
                include_env=False,        # Minimal info leak
                max_locals_size=0         # No local variables
            )
        )
    
    def handle_production_error(self, exception, operation_context=None):
        """Handle production errors safely."""
        structured_error = handle_exception(
            exception, 
            config=self.config,
            custom_error_message=f"Production error in {operation_context}"
        )
        
        # Log for monitoring
        self.log_error(structured_error)
        
        # Optional AI analysis (if enabled)
        if self.enable_ai_analysis:
            return self.analyze_with_ai(structured_error.traceback_info)
        
        return structured_error.traceback_info
    
    def log_error(self, structured_error):
        """Log error to monitoring system."""
        # Implementation depends on your logging system
        print(f"[PRODUCTION ERROR] {structured_error.emsg}")
        print(structured_error.traceback_info)
    
    def analyze_with_ai(self, traceback_info):
        """Send to AI for analysis (production-safe)."""
        # Implementation depends on your AI service
        return f"AI analysis of: {traceback_info[:100]}..."

# Usage
monitor = ProductionErrorMonitor(enable_ai_analysis=True)

try:
    critical_operation()
except Exception as e:
    monitor.handle_production_error(e, "user_data_processing")
```

### Custom Masking Configuration

```python title="custom_masking.py"
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.errors import handle_exception

# Configure custom sensitive patterns
config = Config(
    traceback=TracebackSettings(
        enabled=True,
        format="duplex",
        include_context=True,
        include_locals=True,
        sensitive_patterns=[
            "database_url",
            "private_key",
            "connection_string",
            "encryption_key",
            "wallet_address",
            "personal_info"
        ],
        max_locals_size=512
    )
)

def demo_with_sensitive_data():
    """Function with sensitive data for masking demo."""
    database_url = "postgresql://user:password@host/db"
    private_key = "-----BEGIN PRIVATE KEY-----"
    wallet_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    normal_data = "This is safe to display"
    
    # This will raise an error to demonstrate masking
    raise ValueError("Demo error with sensitive context")

try:
    demo_with_sensitive_data()
except Exception as e:
    structured_error = handle_exception(e, config=config)
    print(structured_error.traceback_info)
    # Sensitive values will be masked as ***
```

### Batch Error Processing

```python title="batch_processing.py"
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.errors import handle_exception
from pathlib import Path

def batch_process_with_error_collection():
    """Process multiple items with comprehensive error collection."""
    
    config = Config(
        traceback=TracebackSettings(
            enabled=True,
            format="compact",
            include_context=True,
            include_locals=False,
            include_env=True
        )
    )
    
    items = ["item1", "item2", "broken_item", "item4"]
    results = []
    errors = []
    
    for item in items:
        try:
            result = process_single_item(item)
            results.append({"item": item, "status": "success", "result": result})
            
        except Exception as e:
            structured_error = handle_exception(e, config=config)
            
            error_info = {
                "item": item,
                "status": "error", 
                "error_message": structured_error.emsg,
                "structured_trace": structured_error.traceback_info
            }
            
            errors.append(error_info)
    
    return {
        "successful_items": len(results),
        "failed_items": len(errors),
        "results": results,
        "errors": errors
    }

def process_single_item(item):
    """Process a single item (may fail)."""
    if item == "broken_item":
        raise RuntimeError(f"Processing failed for {item}")
    return f"processed_{item}"

# Execute batch processing
batch_result = batch_process_with_error_collection()
print(f"Processed {batch_result['successful_items']} items successfully")
print(f"Failed on {batch_result['failed_items']} items")

# Send all errors to AI for analysis
if batch_result['errors']:
    for error in batch_result['errors']:
        print(f"\nError in {error['item']}:")
        print(error['structured_trace'])
```