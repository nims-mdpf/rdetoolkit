"""Registries for v2 nodes and flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from rdetoolkit.errors import ERROR_CATALOG, RdeRegistryError


class _Spec(Protocol):
    @property
    def id(self) -> str:
        """Registered identifier."""
        ...


@dataclass(frozen=True, slots=True)
class FlowSpec:
    """Serializable flow metadata registered by ``@flow``."""

    id: str
    name: str
    source_location: str


_node_specs: dict[str, _Spec] = {}
_node_wrappers: dict[str, Any] = {}
_node_functions: dict[str, Any] = {}
_flow_specs: dict[str, FlowSpec] = {}
_flow_functions: dict[str, Any] = {}


def _duplicate_node_error(node_id: str) -> RdeRegistryError:
    error_def = ERROR_CATALOG[2001]
    error_cls: Any = RdeRegistryError
    return error_cls(
        code=2001,
        name=error_def.name,
        message=error_def.message_template.format(node_id=node_id),
    )


def register_node(spec: _Spec, wrapper: Any, fn: Any) -> None:
    """Register a node spec and its executable references."""
    if spec.id in _node_specs:
        raise _duplicate_node_error(spec.id)
    _node_specs[spec.id] = spec
    _node_wrappers[spec.id] = wrapper
    _node_functions[spec.id] = fn


def get_node(node_id: str) -> _Spec:
    """Return a registered node spec.

    Raises:
        KeyError: If ``node_id`` is not registered.
    """
    return _node_specs[node_id]


def find_unstable_node_ids() -> tuple[str, ...]:
    """Return registered node ids whose qualname contains ``<locals>``."""
    return tuple(node_id for node_id in _node_specs if "<locals>" in node_id)


def register_flow(spec: FlowSpec, fn: Any) -> None:
    """Register a flow spec and callable."""
    _flow_specs.setdefault(spec.id, spec)
    _flow_functions.setdefault(spec.id, fn)


def get_flow(flow_id: str) -> FlowSpec:
    """Return a registered flow spec.

    Raises:
        KeyError: If ``flow_id`` is not registered.
    """
    return _flow_specs[flow_id]


def list_nodes() -> tuple[_Spec, ...]:
    """Return all registered node specs, in registration order."""
    return tuple(_node_specs.values())


def list_flows() -> tuple[FlowSpec, ...]:
    """Return all registered flow specs, in registration order."""
    return tuple(_flow_specs.values())


def get_flow_function(flow_id: str) -> Any:
    """Return a registered flow's underlying callable.

    Raises:
        KeyError: If ``flow_id`` is not registered.
    """
    return _flow_functions[flow_id]
