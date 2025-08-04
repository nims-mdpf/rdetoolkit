# Base Commands API

## Purpose

This module provides base command functionality for RDEToolKit's command-line interface. It defines abstract base classes and common functionality for implementing CLI commands.

## Key Features

### Command Base Classes
- Abstract base classes for CLI commands
- Common command functionality
- Argument parsing and validation

### CLI Framework
- Extensible command architecture
- Error handling and reporting
- Help system integration

---

::: src.rdetoolkit.cmd.command

---

## Practical Usage

### Implementing Custom Commands

```python title="custom_command.py"
from rdetoolkit.cmd.command import BaseCommand
import argparse

class CustomCommand(BaseCommand):
    """Custom command implementation"""

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add command-specific arguments"""
        parser.add_argument('--input', required=True, help='Input file path')
        parser.add_argument('--output', required=True, help='Output file path')

    def handle(self, args):
        """Handle command execution"""
        print(f"Processing: {args.input} -> {args.output}")
        # Custom command logic here
        return {"status": "success"}

# Usage
command = CustomCommand()
# Command would be executed through CLI framework
```
