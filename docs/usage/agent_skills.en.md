# Agent Skills for AI Coding Assistants

## What are Agent Skills?

The rdetoolkit source repository includes a development guide (`.agents/SKILL.md`) that AI coding assistants like Claude Code automatically detect and use.

When this file exists in a repository, the AI assistant generates code with awareness of rdetoolkit's API conventions and project structure. For example, it knows to use `rdetoolkit.fileops.read_from_json_file()` instead of the standard `json.load()` for reading JSON files, and applies this knowledge without being told.

## Difference from the Agent Guide API

rdetoolkit ships two separate AI assistant guides. They serve different purposes.

### Agent Guide (`_agent/` directory)

A guide bundled inside the installed package. Accessible via API or CLI after `pip install`.

```python
import rdetoolkit

guide = rdetoolkit.agent_guide()
```

```bash
rdetoolkit agent-guide
```

This is a general-purpose guide available in any environment where rdetoolkit is installed. Use it when you've installed rdetoolkit as a dependency but haven't cloned the source repository.

### Agent Skills (`.agents/` directory)

A guide placed in the source repository. Claude Code loads it automatically when opening the project and uses it as contextual guidance throughout the development session.

Agent Skills go deeper than the Agent Guide. They include a processing mode selection flowchart, correct CLI operation order, configuration file specs, common mistakes with fixes, and a complete pattern for building structured processing from scratch.

## Setup

### Using with the rdetoolkit source repository

If you've cloned the rdetoolkit repository, Agent Skills work out of the box. No additional configuration needed.

```bash
git clone https://github.com/nims-mdpf/rdetoolkit.git
cd rdetoolkit
# Launch Claude Code — .agents/SKILL.md is automatically detected
```

### Adding to your own project

If you're developing a structured processing project in a separate repository, copy the `.agents/` directory into your project.

```bash
# Copy .agents/ from rdetoolkit into your project
cp -r /path/to/rdetoolkit/src/rdetoolkit/.agents/ ./your-project/.agents/
```

Claude Code auto-detects the skills when `.agents/SKILL.md` exists at the project root or under a src directory.

## Agent Skills structure

```
.agents/
├── SKILL.md                    # Entry point
└── references/
    ├── building-structured-processing.md  # Structured processing build pattern
    ├── preferred-apis.md                  # fileops & csv2graph API
    ├── cli-workflow.md                    # CLI execution order guide
    ├── config.md                          # Configuration file spec
    └── modes.md                           # Processing mode details
```

### SKILL.md

The main entry point. YAML frontmatter defines activation triggers — the skill activates when rdetoolkit import statements, RDE-related keywords, or specific CLI commands are detected.

Covers the following:

- Quick start from project initialization to dataset function implementation
- Encoding-safe file I/O with `rdetoolkit.fileops`
- Metadata writing via the `Meta` class
- Error handling pattern using the Result type
- Processing mode selection table and flowchart
- Correct execution order for CLI template editing and validation
- Step-by-step guide for building structured processing autonomously
- Common mistakes and fixes

### references/building-structured-processing.md

The complete implementation pattern for building a structured processing program from scratch. Includes the standard dataset function layout, metadata-def.json format, Meta class usage, Result-type error handling, directory specifications, and a submission checklist.

### references/preferred-apis.md

Detailed coverage of `rdetoolkit.fileops` and `rdetoolkit.csv2graph` APIs. Explains why standard Python file operations must not be used — with code examples and anti-patterns showing how to handle legacy Japanese encodings like Shift_JIS, EUC-JP, and CP932.

### references/modes.md

A detailed reference for all five processing modes (Invoice, ExcelInvoice, SmartTableInvoice, MultiDataTile, RDEFormat). Each mode includes configuration examples, use cases, directory layouts, and a comparison table.

### references/cli-workflow.md

Complete CLI command reference. Covers the correct order for template file editing, validation execution sequence, CI/CD integration examples, and a validation error troubleshooting table.

### references/config.md

Configuration file specification for both `rdeconfig.yaml` and `pyproject.toml` formats. Includes per-mode configuration examples, field reference table, magic variables, and common configuration mistakes.

## Rules the AI assistant enforces automatically

When Agent Skills are active, the AI assistant applies the following rules without being asked:

- Uses `rdetoolkit.fileops` for all JSON file reads and writes (never `json.load()`)
- Uses the `Meta` class for writing metadata.json (never manual JSON construction)
- Uses the Result type for error handling in helper functions
- Uses `RdeDatasetPaths` attributes instead of hardcoded paths
- Edits template files in the correct order: schema, then metadata-def, then invoice
- Runs validation in the correct order: schema, then invoice, then metadata-def

These rules are defined in the "Critical Rules" section of SKILL.md. To add project-specific rules, edit SKILL.md directly or add them to `CLAUDE.md` at the project root.
