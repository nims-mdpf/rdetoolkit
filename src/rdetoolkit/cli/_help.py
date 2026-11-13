"""Structured ``--help`` text shared by every rdetoolkit CLI command.

Help text is part of the CLI contract (issue #616): each command and group
states what it reads, what it writes, how to call it, and which exit codes it
returns. Commands describe that once as a :class:`CommandHelp`; ``render``
turns it into the Markdown that Typer prints (the root app uses
``rich_markup_mode="markdown"``), and ``tests/v2/cli/test_cli_help_contract.py``
walks the command tree to check that every section is present.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

#: Root ``--help`` panels, in workflow order. Commands are registered in this
#: order so the panels print in it too.
PANEL_SCAFFOLD = "Scaffold"
PANEL_GENERATE = "Generate"
PANEL_VALIDATE = "Validate"
PANEL_RUN = "Run"
PANEL_INSPECT = "Inspect"
PANEL_PACKAGE = "Package"
PANEL_MIGRATE = "Migrate"
PANEL_INFO = "Info"
PANEL_DEPRECATED = "Deprecated (removed in v2.1)"

#: Section headings every rendered help text contains.
SECTION_EXAMPLES = "Examples"
SECTION_EXIT_CODES = "Exit codes"

#: Exit-code descriptions reused across commands, so the same code always
#: reads the same way.
EXIT_OK = (0, "success")
EXIT_V1_FAILED = (1, "the command failed or was aborted (the reason is printed)")
EXIT_CLICK_USAGE = (2, "invalid command line: unknown option, missing argument, or a value the parser rejects")
EXIT_USAGE = (3, "invalid input: a reference, file, or option value the command cannot use")


@dataclass(frozen=True)
class CommandHelp:
    """The help contract of one command or command group.

    Attributes:
        summary: One line stating the action and its result.
        examples: Copy-pasteable invocations, the most common one first.
        exit_codes: ``(code, meaning)`` pairs the command can return.
        inputs: What each argument or key option expects.
        outputs: Files written, default locations, overwrite behaviour, and
            what is printed.
        see_also: Commands that usually come before or after this one.
        details: Optional paragraph printed after the summary.
    """

    summary: str
    examples: Sequence[str]
    exit_codes: Sequence[tuple[int, str]]
    inputs: Sequence[str] = field(default_factory=tuple)
    outputs: Sequence[str] = field(default_factory=tuple)
    see_also: Sequence[str] = field(default_factory=tuple)
    details: str = ""

    def render(self) -> str:
        """Return the help text as Markdown for Typer's ``--help`` output."""
        parts = [self.summary]
        if self.details:
            parts.append(self.details)
        if self.inputs:
            parts.append(_bullets("Inputs", self.inputs))
        if self.outputs:
            parts.append(_bullets("Outputs and side effects", self.outputs))
        parts.append(f"**{SECTION_EXAMPLES}**\n\n```\n" + "\n".join(self.examples) + "\n```")
        parts.append(_bullets(SECTION_EXIT_CODES, [f"`{code}` {meaning}" for code, meaning in self.exit_codes]))
        if self.see_also:
            parts.append("**See also**: " + ", ".join(f"`{name}`" for name in self.see_also))
        return "\n\n".join(parts)


def _bullets(title: str, items: Sequence[str]) -> str:
    return f"**{title}**\n\n" + "\n".join(f"* {item}" for item in items)


def deprecation_message(old: str, new: str) -> str:
    """Return the warning a deprecated v1 command prints before it runs.

    Args:
        old: Deprecated command line, e.g. ``"rdetoolkit gen-config"``.
        new: Replacement command line, e.g. ``"rdetoolkit new config"``.
    """
    return (
        f"Warning: '{old}' is deprecated and will be removed in rdetoolkit v2.1.\n"
        f"Remediation: use '{new}' instead (same behaviour; see '{new} --help')."
    )
