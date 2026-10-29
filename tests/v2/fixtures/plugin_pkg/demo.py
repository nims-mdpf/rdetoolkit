"""Dummy plugin providing the three supported extension kinds."""

from __future__ import annotations

from typing import final

from rdetoolkit import node
from rdetoolkit.plugin import FormatHandler
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths


@node(id="fixture.plugin.read")
def read_fixture(paths: InputPaths) -> str:
    """Return the first fixture filename."""
    return next(iter(paths.inputdata)).name


class FixtureTemplate(ProcessingTemplate):
    """Minimal plugin-provided template skeleton."""

    @slot
    def read(self, paths: InputPaths) -> str: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        self.read(paths)


FORMAT_HANDLERS = (
    FormatHandler(
        name="Fixture format",
        extensions=(".fixture", ".fx"),
        target="tests.v2.fixtures.plugin_pkg.demo:read_fixture",
    ),
)
