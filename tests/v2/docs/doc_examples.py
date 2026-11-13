"""Shared parsing for documentation pages whose code fences are executed.

Every fenced block in a page owned by these helpers is preceded by exactly one
marker comment:

* ``<!-- test: NAME -->`` -- the block is executed (or written to disk and
  executed) by a test that names ``NAME`` explicitly;
* ``<!-- illustration: NAME -->`` -- the block shows output, a directory tree
  or an installation command and is deliberately not executed.

A fence without a marker fails :func:`page_examples`, so an example can never
silently drop out of execution.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).parents[3] / "docs"

_MARKED_FENCE_RE = re.compile(
    r"<!-- (?P<kind>test|illustration): (?P<name>[\w-]+) -->\n```(?P<language>\w+)\n(?P<code>.*?)```",
    re.DOTALL,
)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MENTION_RE = re.compile(r"@[A-Za-z]")


@dataclass(frozen=True)
class Example:
    """One marked code fence of a documentation page."""

    kind: str
    language: str
    code: str


def page_examples(doc: Path) -> dict[str, Example]:
    """Return every marked fence of ``doc`` keyed by its marker name.

    Raises:
        AssertionError: If a fence has no marker or a marker name repeats.
    """
    text = doc.read_text(encoding="utf-8")
    matches = list(_MARKED_FENCE_RE.finditer(text))
    names = [match.group("name") for match in matches]
    assert len(names) == len(set(names)), f"{doc.name}: duplicate example names {names}"
    assert text.count("```") == 2 * len(matches), f"{doc.name}: every fenced block needs a test/illustration marker"
    return {match.group("name"): Example(match.group("kind"), match.group("language"), match.group("code")) for match in matches}


def executed_names(doc: Path) -> set[str]:
    """Return the marker names of the executed (``test``) fences of ``doc``."""
    return {name for name, example in page_examples(doc).items() if example.kind == "test"}


def executed_twins(doc: Path) -> dict[str, Example]:
    """Return only the executed fences of ``doc``, for comparing language twins."""
    return {name: example for name, example in page_examples(doc).items() if example.kind == "test"}


def mention_hazards(doc: Path) -> list[str]:
    """Return prose lines that GitHub would render as an ``@`` mention."""
    prose = _FENCE_RE.sub("", doc.read_text(encoding="utf-8"))
    return [line for line in prose.splitlines() if _MENTION_RE.search(line)]


def cli_args(command_line: str) -> list[str]:
    """Strip ``$ python -m rdetoolkit`` from a documented command line."""
    parts = command_line.strip().removeprefix("$ ").split()
    assert parts[:3] == ["python", "-m", "rdetoolkit"], command_line
    return parts[3:]


def command_lines(example: Example) -> list[str]:
    """Return the non-empty ``$``-prefixed lines of a bash example."""
    return [line for line in example.code.splitlines() if line.startswith("$ ")]


@contextmanager
def isolated_modules(*prefixes: str) -> Iterator[None]:
    """Forget project modules imported by an example, before and after it runs.

    Both language twins import modules with the same names from different
    temporary directories; without this the second import would reuse the
    first twin's module object.
    """

    def _forget() -> None:
        for name in list(sys.modules):
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
                del sys.modules[name]

    _forget()
    try:
        yield
    finally:
        _forget()


def scratch_registries(monkeypatch: pytest.MonkeyPatch, *, builtin_only: bool = False) -> None:
    """Give an example throwaway copies of the node, flow and template registries.

    Both language twins register the same fixed node ids, and a second
    registration of a node id is E2001 by design.

    Args:
        monkeypatch: The test's monkeypatch fixture.
        builtin_only: Start from rdetoolkit's own registrations only. Use it
            for examples that run ``nodes lint``, which checks the whole
            process registry: in a full test run that registry also holds the
            deliberately invalid fixtures other tests register.
    """
    from rdetoolkit.core import registry
    from rdetoolkit.templates import registry as template_registry

    def keep(key: str) -> bool:
        return not builtin_only or key.startswith("rdetoolkit.")

    for name in ("_node_specs", "_node_wrappers", "_node_functions", "_flow_specs", "_flow_functions"):
        current = getattr(registry, name)
        monkeypatch.setattr(registry, name, {key: value for key, value in current.items() if keep(key)})
    for name in ("_template_specs", "_template_classes"):
        current = getattr(template_registry, name)
        monkeypatch.setattr(template_registry, name, {key: value for key, value in current.items() if keep(key)})
    concrete = template_registry._concrete_classes
    monkeypatch.setattr(
        template_registry,
        "_concrete_classes",
        [cls for cls in concrete if keep(f"{cls.__module__}.{cls.__qualname__}")],
    )
