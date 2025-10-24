# Config Generator Command

## Purpose

This module provides the implementation of the `gen-config` CLI command. It creates validated `rdeconfig.yaml` files using predefined templates or an interactive questionnaire so new projects can start with consistent defaults.

## Key Features

### Template Generation
- Minimal, full, MultiDataTile, RDEFormat, and SmartTable presets
- Prompts before overwriting unless the `--overwrite` flag forces replacement
- Structured YAML output that matches `rdetoolkit` configuration models

### Interactive Workflow
- Guided prompts for each configuration option
- English or Japanese question set switching via `--lang`
- Automatic serialization of boolean and extended mode selections

---

::: src.rdetoolkit.cmd.gen_config.GenerateConfigCommand

---

## Practical Usage

### Generate the Minimal Template

```python title="generate_minimal_config.py"
from pathlib import Path
from rdetoolkit.cmd.gen_config import GenerateConfigCommand

command = GenerateConfigCommand(
    output_dir=Path("./project"),
    template="minimal",
    overwrite=False,
    lang="en",
)

command.invoke()
print("Minimal config generated under ./project/rdeconfig.yaml")
```

### Interactive Japanese Prompts with Overwrite

```python title="interactive_config_generation.py"
from pathlib import Path
from rdetoolkit.cmd.gen_config import GenerateConfigCommand

command = GenerateConfigCommand(
    output_dir=Path("./project"),
    template="interactive",
    overwrite=True,
    lang="ja",
)

# The command uses click to ask questions; invoke() should be run inside a CLI context.
command.invoke()
```
