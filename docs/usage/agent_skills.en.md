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

If you're developing a structured processing project in a separate repository, follow these steps.

#### 1. Copy the canonical source

Place the skill files in `.agents/skills/rdetoolkit-skill/`.

```bash
# Copy skill files from rdetoolkit repository
mkdir -p ./your-project/.agents/skills/rdetoolkit-skill
cp -r /path/to/rdetoolkit/src/rdetoolkit/.agents/* ./your-project/.agents/skills/rdetoolkit-skill/
```

#### 2. Create symlinks for your AI agent(s)

Each AI coding assistant reads skill files from its own dedicated directory. Create symlinks (or copies) for the agents you use.

```bash
# For Claude Code
mkdir -p .claude/skills
ln -s ../../.agents/skills/rdetoolkit-skill .claude/skills/rdetoolkit-skill

# For GitHub Copilot
mkdir -p .github/skills
ln -s ../../.agents/skills/rdetoolkit-skill .github/skills/rdetoolkit-skill

# For Gemini CLI
mkdir -p .gemini/skills
ln -s ../../.agents/skills/rdetoolkit-skill .gemini/skills/rdetoolkit-skill

# For OpenCode
mkdir -p .opencode/skills
ln -s ../../.agents/skills/rdetoolkit-skill .opencode/skills/rdetoolkit-skill

# For Devin
mkdir -p .devin/skills
ln -s ../../.agents/skills/rdetoolkit-skill .devin/skills/rdetoolkit-skill
```

You only need to set up the directories for the agents you actually use.

## Agent Skills structure

When added to your own project, the directory layout looks like this:

```
your-project/
├── .agents/
│   └── skills/
│       └── rdetoolkit-skill/           # ← Canonical source (actual files)
│           ├── SKILL.md                #    Entry point
│           └── references/
│               ├── building-structured-processing.md
│               ├── preferred-apis.md
│               ├── cli-workflow.md
│               ├── config.md
│               └── modes.md
├── .claude/
│   └── skills/
│       └── rdetoolkit-skill/           # For Claude Code (symlink)
├── .github/
│   └── skills/
│       └── rdetoolkit-skill/           # For GitHub Copilot (symlink)
├── .gemini/
│   └── skills/
│       └── rdetoolkit-skill/           # For Gemini CLI (symlink)
├── .opencode/
│   └── skills/
│       └── rdetoolkit-skill/           # For OpenCode (symlink)
└── .devin/
    └── skills/
        └── rdetoolkit-skill/           # For Devin (symlink)
```

`.agents/skills/rdetoolkit-skill/` is the single source of truth. Agent-specific directories contain symlinks pointing back to it. Updating the canonical source automatically propagates changes to all agents.

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
