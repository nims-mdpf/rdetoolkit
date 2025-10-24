# LLM/AI-Friendly Traceback System

RDEToolkit includes a structured stacktrace formatting system designed for efficient analysis by LLMs and AI agents. This feature enables automated error analysis, fix suggestions, bug report generation, and other automation scenarios.

## Overview

This feature provides a "duplex output" system that can simultaneously generate:

- **Compact Format**: Structured, machine-readable format optimized for LLMs and AI agents
- **Python Format**: Traditional human-readable format for developers

## Basic Usage

### Default Behavior

**Important**: This feature is **disabled by default**. You can enable it using the following methods:

### 1. Environment Variable Control

```bash
# Basic activation
export TRACE_VERBOSE=context,locals,env

# Output format selection
export TRACE_FORMAT=compact    # LLM-optimized only
export TRACE_FORMAT=python     # Traditional format only
export TRACE_FORMAT=duplex     # Both formats (default)

# Disable the feature
export TRACE_VERBOSE=off       # Explicitly disable
export TRACE_VERBOSE=""        # Empty string also disables
```

**Option descriptions**:
- `context`: Display source code line where error occurred
- `locals`: Display local variable values (sensitive info auto-masked)
- `env`: Display runtime environment info (Python version, OS)

### 2. Programmatic Control

```python
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.errors import handle_exception

# Create configuration
config = Config(
    traceback=TracebackSettings(
        enabled=True,
        format="duplex",
        include_context=True,
        include_locals=False,  # OFF for security
        include_env=False
    )
)

# Use in error handling
try:
    # Process
    process_data()
except Exception as e:
    structured_error = handle_exception(e, config=config)
    print(structured_error.traceback_info)
```

## Output Examples

### Compact Format (AI-optimized)

```
<STACKTRACE>
CFG v=1 ctx=1 locals=0 env=0
E ts=2025-09-08T15:30:45Z type="ValueError" msg="Invalid input data"
F0 mod="myapp.processor" fn="validate_data" file="processor.py:45" in_app=1 context="if not data.get('required_field'):"
F1 mod="myapp.main" fn="main" file="main.py:12" in_app=1
RC frame="F0" hint="Invalid input data"
</STACKTRACE>
```

### Duplex Output

Compact format plus traditional Python format simultaneously:

```
<STACKTRACE>
CFG v=1 ctx=1 locals=0 env=0
E ts=2025-09-08T15:30:45Z type="ValueError" msg="Invalid input data"
F0 mod="myapp.processor" fn="validate_data" file="processor.py:45" in_app=1 context="if not data.get('required_field'):"
F1 mod="myapp.main" fn="main" file="main.py:12" in_app=1
RC frame="F0" hint="Invalid input data"
</STACKTRACE>

Traceback (simplified message):
Call Path:
   File: /path/to/myapp/main.py, Line: 12 in main()
    └─ File: /path/to/myapp/processor.py, Line: 45 in validate_data()
        └─> L45: if not data.get('required_field'): 🔥

Exception Type: ValueError
Error: Invalid input data
```

## AI Agent Use Cases

### Automated Error Correction System

```python
from rdetoolkit.models.config import Config, TracebackSettings

# AI agent configuration
ai_config = Config(
    traceback=TracebackSettings(
        enabled=True,
        format="compact",           # Machine-readable format
        include_context=True,       # Error line code
        include_locals=False,       # Privacy protection
        include_env=False,          # Environment info not needed
        max_locals_size=256
    )
)

def handle_error_with_ai(exception):
    structured_error = handle_exception(exception, config=ai_config)
    
    # Message for AI agent
    ai_prompt = f"""
    An error has occurred. Please analyze the following structured trace
    information and suggest a fix:

    {structured_error.traceback_info}
    """
    
    # Send to LLM API, get fix suggestion
    response = call_llm_api(ai_prompt)
    return response

try:
    risky_operation()
except Exception as e:
    suggestion = handle_error_with_ai(e)
    print(f"AI Fix Suggestion: {suggestion}")
```

### Automated Bug Report Generation

```python
def generate_bug_report(exception):
    structured_error = handle_exception(exception, config=ai_config)
    
    # Auto-create GitHub issue
    issue_body = f"""
## Error Overview
{structured_error.emsg}

## Structured Trace Information
```
{structured_error.traceback_info}
```

## AI Analysis Results
{analyze_with_ai(structured_error.traceback_info)}
"""
    
    create_github_issue("Auto-detected Error", issue_body)
```

## Use Cases

### 1. Development & Debugging
```bash
# Detailed output including local variables
export TRACE_VERBOSE=context,locals
export TRACE_FORMAT=duplex
python your_script.py
```

### 2. CI/CD Pipeline
```bash
# Structured error information for efficient log analysis
export TRACE_VERBOSE=context
export TRACE_FORMAT=compact
python your_rde_script.py
```

### 3. Production Monitoring
```bash
# Minimal configuration without sensitive information
export TRACE_VERBOSE=""
export TRACE_FORMAT=compact
```

## Security Features

### Automatic Masking

Variables containing the following keywords are automatically masked with `***`:

- `password`, `passwd`, `pwd`
- `token`, `auth`, `authorization`
- `secret`, `key`, `api_key`
- `cookie`, `session`
- `credential`, `cred`

### Custom Masking

```python
config = Config(
    traceback=TracebackSettings(
        enabled=True,
        sensitive_patterns=[
            "database_url",
            "private_key",
            "connection_string"
        ]
    )
)
```

## Troubleshooting

### Configuration Not Applied

1. Check environment variables
```bash
echo $TRACE_VERBOSE
echo $TRACE_FORMAT
```

2. Verify configuration priority
   - Programmatic settings (highest priority)
   - Configuration files
   - Environment variables
   - Default values (disabled)

### Unexpected Output

1. Check actual settings in `CFG` line
2. Verify application code scope with `in_app=1`
3. Check for information hidden by security masking

### Performance Issues

1. Disable variable output with `include_locals=false`
2. Reduce `max_locals_size` setting
3. Use `format=compact` in production

## Related Documentation

- [Configuration Details](../config/config.en.md)
- [Error Handling](./errorhandling.en.md)
- [API Reference](../../rdetoolkit/traceback/index.md)