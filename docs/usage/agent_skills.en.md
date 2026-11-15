# Agent Skills for v2 processing authors

The canonical source is the five `.agents/skills/rdetoolkit-*` directories at the
repository root. These are downstream workflow Skills, separate from the
repository's contributor `AGENTS.md` and `CLAUDE.md`. Neither the runtime wheel
nor its source distribution contains the Skills or retired embedded guidance.

| Skill | Use it for |
| --- | --- |
| `rdetoolkit-flow-authoring` | Create eager v2 flows and explicit-argument nodes |
| `rdetoolkit-metadata` | Build and save metadata with the actual schema |
| `rdetoolkit-debugging` | Inspect failures, repair inputs/code, rerun |
| `rdetoolkit-testing` | Test with isolated fixtures and real outputs |
| `rdetoolkit-v1-migration` | Migrate existing v1 callbacks and compare artifacts |

## Download once, install offline

Use **exactly the installed package version**, including `a`, `b` or `rc` suffix.
A pack from another version is rejected. Determine the runtime version with
`python -c "from importlib.metadata import version; print(version('rdetoolkit'))"`.
The release pipeline attaches `rdetoolkit-skills-<version>.zip` and its
`.zip.sha256` checksum to the GitHub release of that version. Packs exist for
releases built after this pipeline was added; `v2.0.0rc1` has none. Development
checkouts can build the same asset with
`python scripts/skills_pack.py build --output skill-dist`. Downloading does not
require cloning the repository:

```sh
VERSION=$(python -c "from importlib.metadata import version; print(version('rdetoolkit'))")
gh release download "v$VERSION" --repo nims-mdpf/rdetoolkit --pattern "rdetoolkit-skills-$VERSION.zip*"
python -m zipfile -e "rdetoolkit-skills-$VERSION.zip" skills-pack
python skills-pack/install_skills.py install --pack "rdetoolkit-skills-$VERSION.zip" --project ./your-project --agent codex
python skills-pack/install_skills.py install --pack "rdetoolkit-skills-$VERSION.zip" --project ./your-project --agent claude
```

Run the installer with Python **3.10 or newer**, in the environment containing
rdetoolkit. It reads the installed version without importing runtime code.
Alternatively pass `--version <version>` after independently checking that exact
runtime version. The downloaded ZIP includes the standalone installer and a
schema-versioned manifest with SHA-256 hashes of all payload files. The installer
checks those hashes and rejects unsafe paths before writing. A checksum detects
corruption, not publisher identity; obtain both files from the trusted release.
You can verify the ZIP's SHA-256 against the `.sha256` text using
`sha256sum` (Unix) or `Get-FileHash` (PowerShell).

After downloading, extraction, installation and execution need **no network**.
No ordinary rdetoolkit workflow fetches remote instructions. Keep the ZIP for
future offline reinstalls. All file copying is implemented in Python; the same
installer works on Windows without symlinks:

```powershell
$VERSION = py -c "from importlib.metadata import version; print(version('rdetoolkit'))"
py -m zipfile -e "rdetoolkit-skills-$VERSION.zip" skills-pack
py skills-pack/install_skills.py install --pack "rdetoolkit-skills-$VERSION.zip" --project .\your-project --agent claude
```

## Agent discovery and verification

| Agent | Project installation | Verification status |
| --- | --- | --- |
| Codex | `.agents/skills/<name>/SKILL.md` | Copy/install and real `skills/list` discovery smoke described in the [verification record](../development/agent-skills-verification.md) |
| Claude Code | `.claude/skills/<name>/SKILL.md` | Copy/install and actual client SDK initialization discovered all five project Skills; see the [verification record](../development/agent-skills-verification.md) |

Start/restart the agent in `your-project` after installing. Codex should list all
five names in its Skills picker; Claude Code should expose them as slash
commands (for example `/rdetoolkit-flow-authoring`).
Check that each name appears before relying on automatic activation. Their YAML
`name` and `description` define distinct triggers; installing a Skill does not
require sending research inputs or diagnostics to a cloud model.
See the upstream [Codex Skills documentation](https://developers.openai.com/codex/skills/)
and [Claude Code Skills documentation](https://code.claude.com/docs/en/skills).
No claim is made that Claude reads `.agents/SKILL.md` automatically.

Other agents (Copilot, Cursor, Gemini, OpenCode, Devin) are **best effort,
not verified**. Follow their current discovery documentation and copy the
individual Skill directories as needed. Do not assume they discover these paths
or follow symlinks. Symlink installations are intentionally unsupported by the
installer; copying is the portable fallback and the default.

## Upgrade, conflicts and uninstall

The installer never overwrites a Skill or an existing installation receipt.
If any of the five target names exists, it fails before copying any Skill.
Back up or rename conflicting user content first. To upgrade, keep the old
ZIP, preserve local edits, uninstall the old pack, then install the new pack
matching the upgraded runtime:

```sh
python skills-pack/install_skills.py uninstall --project ./your-project --agent codex
```

Use `--agent claude` for Claude Code. Uninstall verifies the installation receipt
and every owned file before removing the five directories. Modified, added,
removed or symlinked files stop uninstall without deleting any Skill: first
back up your changes and restore the old pack's files, then retry. Unrelated
Skills remain untouched. Remove the extracted `skills-pack` directory and ZIP
only when you no longer need offline reinstallation.

## Discovering the installed API

The Skills tell the agent to ask the installed CLI before inventing an API.
Each listing accepts `--json`, and `--module package.module` registers your
project's own declarations first:

```sh
python -m rdetoolkit nodes list --json
python -m rdetoolkit nodes show rdetoolkit.nodes.meta.build_meta --json
python -m rdetoolkit flows list --json
python -m rdetoolkit skeletons list --json
```

## Retired Agent Guide

The package-embedded guide (`rdetoolkit.get_agent_guide()`, the `agent-guide`
command and the package-local `.agents/` directory) was removed before v2 GA.
There is no replacement API in the package; this Skills pack and the commands
above replace it. See the
[v1 to v2 migration guide](../migration_v1_to_v2.en.md) ("What was removed (after 2.0.0rc1, before GA)").
