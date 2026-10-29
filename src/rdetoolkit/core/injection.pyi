from collections.abc import Callable
from typing import Any

from rdetoolkit.core.context import RunContext

def find_duplicate_reserved_annotations(flow_fn: Callable[..., Any]) -> dict[type, tuple[str, ...]]: ...
def resolve_flow_kwargs(flow_fn: Callable[..., Any], run_context: RunContext) -> dict[str, Any]: ...
