from collections.abc import Sequence

import typer

from rdetoolkit.core.node import NodeSpec

app: typer.Typer

def find_duplicate_node_ids(specs: Sequence[NodeSpec]) -> Sequence[str]: ...
def list_nodes(
    as_json: bool = False,
    plugin_only: bool = False,
    modules: list[str] | None = None,
) -> None: ...
def describe(node_id: str, as_json: bool = False, modules: list[str] | None = None) -> None: ...
def lint(modules: list[str] | None = None) -> None: ...
