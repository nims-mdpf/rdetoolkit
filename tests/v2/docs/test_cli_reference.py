"""The CLI reference page stays in step with the real command tree (#454).

EP table
========

====================  ==========================  ====================================  =====================
Item                  Partition                   Expected                              Test ID
====================  ==========================  ====================================  =====================
commands              every leaf command          exactly one ``### `rdetoolkit ...``` TC-DOC-CLI-EP-001
options / arguments   every documented command    each flag and argument named          TC-DOC-CLI-EP-002
root options          shell completion flags      both named                            TC-DOC-CLI-EP-003
====================  ==========================  ====================================  =====================

BV table
========

====================  ==========================  ====================================  =====================
Item                  Boundary                    Expected                              Test ID
====================  ==========================  ====================================  =====================
headings              command removed or renamed  stale heading fails EP-001            TC-DOC-CLI-BV-001
csv2graph             30+ plotting options        delegated to its own page             TC-DOC-CLI-BV-002
prose outside fences  ``@`` + letter token         none (GitHub mention hazard)          TC-DOC-CLI-BV-003
====================  ==========================  ====================================  =====================

The comparison is two-way: a command added without documentation and a
documented command that no longer exists both fail.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import click
import pytest
import typer

from rdetoolkit.cli.app import app
from tests.v2.docs.doc_examples import DOCS_DIR, mention_hazards, page_examples

DOC_JA = DOCS_DIR / "reference" / "cli.md"
DOC_EN = DOCS_DIR / "reference" / "cli.en.md"
DOCS = pytest.mark.parametrize("doc", [DOC_JA, DOC_EN], ids=["ja", "en"])
HEADING_RE = re.compile(r"^### `rdetoolkit (?P<path>[^`]+)`$", re.MULTILINE)
#: Options documented on a dedicated page instead of the reference table.
DELEGATED = {"csv2graph"}
#: ``validate`` subcommands share one option table under ``validate all``.
SHARED_VALIDATE_SECTION = "validate all"


def _subcommands(command: Any) -> list[str]:
    """Return a group's subcommand names, or ``[]`` for a leaf.

    Duck-typed on purpose: newer typer releases build their command classes
    on a vendored click, so ``isinstance(command, click.Group)`` is False for
    a real typer group.
    """
    list_commands = getattr(command, "list_commands", None)
    return list(list_commands(click.Context(command))) if list_commands is not None else []


def _leaf_commands() -> dict[str, Any]:
    root = typer.main.get_command(app)
    leaves: dict[str, Any] = {}

    def walk(command: Any, path: tuple[str, ...]) -> None:
        # ``graph`` is a group whose callback takes the arguments and that has
        # no subcommands; it is documented and checked as a leaf.
        if names := _subcommands(command):
            for name in names:
                child = command.get_command(click.Context(command), name)
                assert child is not None
                walk(child, (*path, name))
            return
        leaves[" ".join(path)] = command

    walk(root, ())
    return leaves


def _sections(doc: Path) -> dict[str, str]:
    text = doc.read_text(encoding="utf-8")
    matches = list(HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        path = match.group("path")
        assert path not in sections, f"duplicate heading for {path}"
        sections[path] = text[match.end() : end]
    return sections


@DOCS
def test_every_command_has_exactly_one_section__tc_doc_cli_ep_001(doc: Path) -> None:
    """TC-DOC-CLI-EP-001 / BV-001: documented commands equal the real leaf commands."""
    assert set(_sections(doc)) == set(_leaf_commands())


@DOCS
def test_every_option_and_argument_is_named__tc_doc_cli_ep_002(doc: Path) -> None:
    """TC-DOC-CLI-EP-002 / BV-002: each flag and argument appears in its command's section."""
    sections = _sections(doc)
    missing: list[str] = []
    for path, command in _leaf_commands().items():
        if path in DELEGATED:
            continue
        section = sections[path]
        if path.startswith("validate "):
            section += sections[SHARED_VALIDATE_SECTION]
        for param in command.params:
            if param.param_type_name == "option":
                names = [flag for flag in (*param.opts, *param.secondary_opts) if flag.startswith("--")]
                if param.name == "help":
                    continue
                missing.extend(f"{path} {flag}" for flag in names if f"`{flag}`" not in section)
            else:
                metavar = param.name.upper() if param.name else ""
                if f"`{metavar}`" not in section:
                    missing.append(f"{path} {metavar}")
    assert missing == []


@DOCS
def test_root_completion_options_are_named__tc_doc_cli_ep_003(doc: Path) -> None:
    """TC-DOC-CLI-EP-003: the root shell-completion flags are documented."""
    text = doc.read_text(encoding="utf-8")
    assert "`--install-completion`" in text
    assert "`--show-completion`" in text


@DOCS
def test_every_fence_is_an_illustration__tc_doc_cli_fences(doc: Path) -> None:
    """Reference fences are usage illustrations; the commands they show exist."""
    examples = page_examples(doc)
    assert {example.kind for example in examples.values()} == {"illustration"}
    leaves = _leaf_commands()
    for example in examples.values():
        for line in example.code.splitlines():
            words = line.removeprefix("$ ").split()
            assert words[0] == "rdetoolkit"
            assert any(" ".join(words[1 : 1 + size]) in leaves for size in (1, 2)), line


@DOCS
def test_prose_has_no_mention_tokens__tc_doc_cli_bv_003(doc: Path) -> None:
    """TC-DOC-CLI-BV-003: an ``@``-prefixed token may appear only inside a code fence."""
    assert mention_hazards(doc) == []


def test_language_twins_document_the_same_commands() -> None:
    """Both languages carry the same command sections and the same usage fences."""
    assert _sections(DOC_EN).keys() == _sections(DOC_JA).keys()
    assert page_examples(DOC_EN) == page_examples(DOC_JA)
