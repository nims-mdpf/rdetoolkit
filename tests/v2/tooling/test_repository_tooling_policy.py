"""Repository tooling retirement guards for #674 and #675.

EP table (written before implementation):

| Partition | Expected | Test ID |
| --- | --- | --- |
| retired PR-Agent workflow/config present | reject | TC-TOOL-EP-001 |
| retired index producer/artifact/workflow present | reject | TC-TOOL-EP-002 |
| provider action or credential in any workflow | reject | TC-TOOL-EP-003 |
| command/docs/agent reference to retired index | reject | TC-TOOL-EP-004 |
| supported MkDocs search | native plugin retained | TC-TOOL-EP-005 |

BV table:

| Boundary | Expected | Test ID |
| --- | --- | --- |
| zero external AI credentials | no PR-Agent dependency in any CI job | TC-TOOL-BV-001 |

These are repository-state guards; no workflow is executed and no provider is called.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "docs/development/tooling-policy.md"
RETIRED = (
    ".github/workflows/pr-agent.yaml",
    ".pr_agent.toml",
    ".github/workflows/build-index.yml",
    "tools/build_index.py",
    "docs/search/rdetoolkit_code_index.jsonl",
)
INDEX_TOKENS = ("build_index.py", "rdetoolkit_code_index.jsonl", "build-index.yml")


@pytest.mark.parametrize("relative", RETIRED)
def test_retired_tooling_is_absent(relative: str) -> None:
    """TC-TOOL-EP-001/002: obsolete tooling cannot silently return."""
    # Given: the maintained retirement policy for PR-Agent and the unconsumed index
    # When: checking each retired producer, configuration, workflow and output
    path = ROOT / relative
    # Then: none remains in the source or release input tree
    assert not path.exists(), relative


@pytest.mark.parametrize("token", ("qodo-ai/pr-agent", "OPENAI_KEY", ".pr_agent.toml", "pr_agent_job"))
def test_all_workflows_are_independent_of_pr_agent(token: str) -> None:
    """TC-TOOL-EP-003/BV-001: renamed workflows cannot restore provider access."""
    # Given: every checked-in workflow, including PR/comment/manual event handlers
    workflows = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
    assert workflows
    # When: inspecting their action references, environment and scripts
    matches = [str(path.relative_to(ROOT)) for path in workflows if token.lower() in path.read_text(encoding="utf-8").lower()]
    # Then: CI requires no PR-Agent action, configuration or external AI credential
    assert matches == [], matches


@pytest.mark.parametrize("token", INDEX_TOKENS)
def test_no_supported_consumer_points_to_retired_index(token: str) -> None:
    """TC-TOOL-EP-004: user commands, agent guides and documentation stay usable."""
    # Given: maintained code, commands, documentation, agent instructions and build inputs
    roots = ("src", "tools", "scripts", "docs", ".github", ".agents")
    paths = [path for name in roots for path in (ROOT / name).rglob("*") if path.is_file()]
    paths.extend(ROOT / name for name in ("AGENTS.md", "CLAUDE.md", "README.md", "pyproject.toml", "mkdocs.yml"))
    text_suffixes = {".py", ".md", ".yml", ".yaml", ".toml", ".json", ".jsonl", ".txt"}
    # When: looking for references outside the explicit historical retirement policy
    matches = [
        str(path.relative_to(ROOT))
        for path in paths
        if path.exists()
        and path != POLICY
        and path.suffix in text_suffixes
        and "__pycache__" not in path.parts
        and token in path.read_text(encoding="utf-8")
    ]
    # Then: no supported command or page tells users to invoke missing tooling
    assert matches == [], matches


def test_native_documentation_search_is_retained() -> None:
    """TC-TOOL-EP-005: removing the JSONL file preserves the real search consumer."""
    # Given: MkDocs has always used its native documentation search plugin
    import yaml

    # When: parsing YAML without interpreting MkDocs' Python object tags
    config = yaml.load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)  # noqa: S506 -- BaseLoader builds only scalars/containers, never Python objects.
    # Then: the supported search plugin remains enabled
    assert any(plugin == "search" or isinstance(plugin, dict) and "search" in plugin for plugin in config["plugins"])
