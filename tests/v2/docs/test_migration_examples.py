"""Executed examples for the v1-to-v2 migration guide.

EP table
========

====================  ======================  =============================  ====================
Example               Partition               Expected                       Test ID
====================  ======================  =============================  ====================
migration commands    check and dry-run apply commands accepted by CLI       TC-DOC-MIG-EP-001
``as_node`` bridge    legacy handler method  callable node preserves result TC-DOC-MIG-EP-002
====================  ======================  =============================  ====================

BV table
========

====================  ======================  =============================  ====================
Example               Boundary                Expected                       Test ID
====================  ======================  =============================  ====================
documentation fences  every fenced example   marker and execution coverage TC-DOC-MIG-BV-001
prose outside fences  ``@`` + letter token     none (GitHub mention hazard)   TC-DOC-MIG-BV-002
language twins        ja vs en fences         identical names and code       TC-DOC-MIG-BV-003
====================  ======================  =============================  ====================

Every test runs for both the Japanese guide and its English twin (Session
K4-5): the fence execution contract is per language, so an example that only
exists, or only runs, in one language is caught.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.core import registry

DOCS_DIR = Path(__file__).parents[3] / "docs"
DOC_JA = DOCS_DIR / "migration_v1_to_v2.md"
DOC_EN = DOCS_DIR / "migration_v1_to_v2.en.md"
DOCS = pytest.mark.parametrize("doc", [DOC_JA, DOC_EN], ids=["ja", "en"])
EXAMPLE_RE = re.compile(r"<!-- test: (?P<name>[\w-]+) -->\n```(?P<language>\w+)\n(?P<code>.*?)```", re.DOTALL)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
MENTION_RE = re.compile(r"@[A-Za-z]")


def _examples(doc: Path) -> dict[str, tuple[str, str]]:
    text = doc.read_text(encoding="utf-8")
    examples = {
        match.group("name"): (match.group("language"), match.group("code"))
        for match in EXAMPLE_RE.finditer(text)
    }
    assert text.count("```") == 2 * len(examples), "Every fenced example must have a test marker"
    return examples


@DOCS
def test_migration_cli_commands_execute__tc_doc_mig_ep_001(doc: Path, tmp_path: Path, monkeypatch) -> None:
    """TC-DOC-MIG-EP-001: documented migration commands execute through the public CLI."""
    # Given: the documented legacy source and command sequence
    examples = _examples(doc)
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "legacy.py"
    source.write_text(examples["legacy-source"][1], encoding="utf-8")
    commands = [line.removeprefix("$ ").split() for line in examples["migration-commands"][1].splitlines()]
    # When: each documented python -m rdetoolkit command is invoked
    results = [CliRunner().invoke(app, command[3:]) for command in commands]
    # Then: check and the default dry-run apply both succeed without writing output
    assert all(result.exit_code == 0 for result in results), [result.output for result in results]
    assert not source.with_name("legacy_migrated").exists()


@pytest.fixture
def scratch_node_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the example a throwaway copy of the node registry.

    The bridge example registers a fixed node id; both language twins run it,
    and a second registration of the same id is E2001 by design.
    """
    for name in ("_node_specs", "_node_wrappers", "_node_functions"):
        monkeypatch.setattr(registry, name, dict(getattr(registry, name)))


@DOCS
@pytest.mark.usefixtures("scratch_node_registry")
def test_as_node_bridge_executes__tc_doc_mig_ep_002(doc: Path) -> None:
    """TC-DOC-MIG-EP-002: the migration-only as_node bridge example is executable."""
    # Given: the complete documented bridge example
    namespace: dict[str, object] = {}
    # When: executing it as ordinary Python
    exec(_examples(doc)["as-node-bridge"][1], namespace)  # noqa: S102
    # Then: the example's own assertion ran and produced the documented value
    assert namespace["result"] == "SAMPLE.TXT"


@DOCS
def test_every_migration_fence_is_executed__tc_doc_mig_bv_001(doc: Path) -> None:
    """TC-DOC-MIG-BV-001: no unmarked migration-guide code fence can bypass execution."""
    # Given: all fenced examples in the migration guide
    examples = _examples(doc)
    # When: comparing their stable marker names with this module's executed set
    executed = {"legacy-source", "migration-commands", "as-node-bridge"}
    # Then: every example is explicitly owned by an execution test
    assert set(examples) == executed


@DOCS
def test_prose_has_no_mention_tokens__tc_doc_mig_bv_002(doc: Path) -> None:
    """TC-DOC-MIG-BV-002: an ``@``-prefixed token may appear only inside a code fence."""
    # Given: the guide with every fenced block removed
    prose = FENCE_RE.sub("", doc.read_text(encoding="utf-8"))
    # When: searching the prose and headings for ``@`` followed by a letter
    hits = [line for line in prose.splitlines() if MENTION_RE.search(line)]
    # Then: nothing would render as a GitHub mention
    assert hits == []


def test_language_twins_carry_identical_examples__tc_doc_mig_bv_003() -> None:
    """TC-DOC-MIG-BV-003: the Japanese and English guides execute the same code."""
    # Given: the fenced examples of both language versions
    # When: comparing them by marker name
    # Then: names, languages and code are identical, so neither twin drifts
    assert _examples(DOC_EN) == _examples(DOC_JA)
