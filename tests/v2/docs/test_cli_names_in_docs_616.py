"""The docs and README name only commands the CLI has (#616).

The command list lives in the CLI itself; these documents may quote commands
but must not drift from it. Every ``rdetoolkit <command>`` invocation in a code
block or inline code span must resolve to a registered, non-deprecated command,
and no renamed v1/rc spelling may appear outside the migration mapping tables.

| Test ID | Target | Condition | Expected |
|---|---|---|---|
| TC-616-DOC-001 | docs, guides, skills | every quoted ``rdetoolkit`` invocation | resolves to a current command path |
| TC-616-DOC-002 | docs, guides, skills | every line | no renamed spelling, except mapping-table rows that also give the replacement |
| TC-616-DOC-003 | migration guides (ja/en) | mapping table | every ``COMMAND_RENAMES`` row's old and new command appears |
"""

from __future__ import annotations

import re
from pathlib import Path

import click
import pytest
import typer

from rdetoolkit.cli._renames import COMMAND_RENAMES, find_renamed_commands
from rdetoolkit.cli.app import app

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Release notes describe past versions and legitimately keep old names.
_EXCLUDED = (REPO_ROOT / "docs" / "releases",)

_DEPRECATED_ROOT_COMMANDS = {"gen-config", "gen-invoice", "make-excelinvoice", "csv2graph", "artifact"}

#: A command line that starts with the CLI (optionally behind a ``$`` prompt
#: or a ``python -m`` launcher); Python such as ``from rdetoolkit import x``
#: never matches.
_INVOCATION = re.compile(r"^(?:\$ )?(?:(?:uv run )?python3? -m |py -m )?rdetoolkit((?: +[a-z][a-z0-9-]*){1,2})")


def _documents() -> list[Path]:
    roots = [REPO_ROOT / "docs"]
    files = [REPO_ROOT / "README.md"]
    for root in roots:
        files.extend(sorted(root.rglob("*.md")))
    # The shipped Agent Skills (#664) quote CLI commands for agents to run.
    files.extend(sorted((REPO_ROOT / ".agents" / "skills").glob("rdetoolkit-*/**/*.md")))
    return [path for path in files if not any(path == excluded or excluded in path.parents for excluded in _EXCLUDED)]


def _code_lines(text: str) -> list[tuple[int, str]]:
    """Return (line number, code text) for fenced-block lines and inline code spans."""
    found: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            found.append((number, line.strip()))
        else:
            found.extend((number, span) for span in re.findall(r"`([^`]+)`", line))
    return found


def _root() -> click.Group:
    command = typer.main.get_command(app)
    assert isinstance(command, click.Group)
    return command


def _check_invocation(words: list[str]) -> str | None:
    """Return why ``rdetoolkit <words>`` is not a current command, or None."""
    root = _root()
    head = words[0]
    if head not in root.commands:
        return f"unknown command {head!r}"
    if head in _DEPRECATED_ROOT_COMMANDS:
        return f"deprecated command {head!r}"
    command = root.commands[head]
    if isinstance(command, click.Group) and len(words) > 1 and words[1] not in command.commands:
        return f"unknown subcommand {' '.join(words)!r}"
    return None


@pytest.mark.parametrize("path", _documents(), ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_quoted_invocations_name_current_commands__tc_616_doc_001(path: Path) -> None:
    # Given: the code a reader would copy from one document
    problems = []
    for number, code in _code_lines(path.read_text(encoding="utf-8")):
        if find_renamed_commands(code):
            continue  # reported (or allowed as a mapping row) by the next test
        match = _INVOCATION.match(code)
        if match is None:
            continue
        reason = _check_invocation(match.group(1).split())
        if reason:
            problems.append(f"{path.relative_to(REPO_ROOT)}:{number}: {reason}: {code}")

    # Then: every quoted command exists in the CLI
    assert problems == []


def _is_mapping_row(line: str) -> bool:
    """A table row that pairs an old command with its replacement."""
    return line.lstrip().startswith("|") and line.count("|") >= 3


@pytest.mark.parametrize("path", _documents(), ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_no_renamed_spelling_outside_mapping_tables__tc_616_doc_002(path: Path) -> None:
    problems = [
        f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if find_renamed_commands(line) and not _is_mapping_row(line)
    ]
    assert problems == []


@pytest.mark.parametrize("name", ["migration_v1_to_v2.md", "migration_v1_to_v2.en.md"])
def test_migration_guide_lists_every_rename__tc_616_doc_003(name: str) -> None:
    # Given: the migration guide
    text = (REPO_ROOT / "docs" / name).read_text(encoding="utf-8")

    # Then: each renamed command and its replacement are named in it
    for rename in COMMAND_RENAMES:
        old = " ".join(rename.old.split()[1:3]).split(" [")[0]
        new = " ".join(rename.new.split()[1:3]).split(" [")[0].split("|")[0]
        assert old.split()[0] in text, rename.old
        assert new in text, rename.new
