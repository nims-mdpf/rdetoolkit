# Agent Skills installation verification

Recorded on 2026-11-12 for the `2.0.0rc1` Skills pack built from the same
working tree as the runtime. No model inference or research data was used.

## Automated offline installation contract

`tests/v2/docs/test_skills_distribution.py` builds synthetic versioned packs,
extracts the bundled installer and runs it without the source tree. It verifies
both Codex `.agents/skills/<name>/SKILL.md` and Claude Code
`.claude/skills/<name>/SKILL.md` copy layouts, the complete five-Skill set,
manifest digests, uninstall and rejection of conflicts, version mismatch,
corruption, traversal, symlink destinations, malformed manifests and local edits.
An unrelated contributor Skill is excluded from release packs.

Run: `python -m pytest tests/v2/docs/test_skills_distribution.py -v`.
The deterministic tests require neither installed agent clients nor credentials.
These filesystem assertions alone do not prove a client discovers Skills.

## Actual Codex discovery smoke

Client: `codex-cli 0.167.0-alpha.4`, Debian Linux, x86_64.

1. Built `rdetoolkit-skills-2.0.0rc1.zip` using
   `python scripts/skills_pack.py build --output /tmp/rdetoolkit-skill-dist`.
2. Installed it into an otherwise empty temporary project with the bundled
   installer's `install --agent codex --version 2.0.0rc1` command.
3. Started `codex app-server --stdio` in that project, with analytics disabled
   and `sqlite_home` pointing into a temporary directory. The managed sandbox's
   read-only Codex state initially prevented startup; the same probe succeeded
   with the environment's approved filesystem access. No home variable was
   reassigned and no model turn was started.
4. Sent JSON-RPC `initialize` with client name `rdetoolkit-smoke`, version `1.0`
   and `experimentalApi: true`, followed by `initialized`, then:

   ```json
   {"id": 2, "method": "skills/list", "params": {"cwds": ["<temporary-project>"], "forceReload": true}}
   ```

The response contained each name below with `scope: "repo"`, `enabled: true`,
the matching project-local `SKILL.md` path, and an empty `errors` array:

- `rdetoolkit-flow-authoring`
- `rdetoolkit-metadata`
- `rdetoolkit-debugging`
- `rdetoolkit-testing`
- `rdetoolkit-v1-migration`

The client also listed its unrelated user/system Skills. The smoke asserts
only the five project Skills; it does not assume a clean global agent profile,
verify model activation, or assert symlink portability.

## Actual Claude Code discovery smoke

Client: official `@anthropic-ai/claude-code`, version `2.1.323`, Debian Linux,
x86_64. The CLI was installed into a temporary directory, not the repository
or global environment. Package download required network access; the subsequent
discovery ran locally in the network-restricted sandbox.

1. Installed the same version-matched pack into a second empty temporary
   project with `--agent claude --version 2.0.0rc1`.
2. Started the CLI in that project with isolated `CLAUDE_CONFIG_DIR` and flags:

   ```text
   --print --verbose --input-format stream-json --output-format stream-json
   --no-session-persistence --setting-sources project --strict-mcp-config
   --mcp-config '{"mcpServers":{}}'
   ```

3. Sent only this local SDK control message, keeping stdin open until the
   response arrived; no user prompt or model request was sent:

   ```json
   {"type":"control_request","request_id":"init-smoke","request":{"subtype":"initialize"}}
   ```

4. Received a successful `control_response`. Its `commands` contained all five
   names listed above with each description marked `(project)`.
   `claude_code_version` was `2.1.323`, `account.tokenSource` was `none`, and
   `session_state` was `idle`. No credentials or research inputs were needed.

This verifies the actual client's discovery of project-local Skills, rather
than only reproducing its directory scan in a test. It does not verify model
activation or symlink portability. The `--setting-sources project` option matters:
an empty source list excludes the project's Skills. Do not use a mode that
excludes project customizations when checking discovery. See
[Claude Code's Skills documentation](https://code.claude.com/docs/en/skills).
Other agents remain best effort / unverified.

## Re-run after the CLI command redesign

On 2026-11-13 the pack was rebuilt from the updated Skills, whose CLI examples
use the `rdetoolkit <noun> <verb>` names (`nodes show`, `skeletons list`,
`run <module:flow>`, `migrate apply -o`). Both smokes above were repeated on
macOS (arm64) with `codex-cli 0.167.1` and Claude Code `2.1.323`, using an
isolated `CODEX_HOME` / `CLAUDE_CONFIG_DIR` and the same messages. Codex
`skills/list` returned the five Skills with `scope: "repo"`, `enabled: true`
and `errors: []`; the Claude Code `initialize` response listed the five names
as `(project)` commands with `tokenSource: "none"` and `session_state: "idle"`.
