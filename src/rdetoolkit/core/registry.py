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


def get_node_function(node_id: str) -> Any:
    """Return a registered node's undecorated callable.

    Raises:
        KeyError: If ``node_id`` is not registered.
    """
    return _node_functions[node_id]


def find_unstable_node_ids() -> tuple[str, ...]:
    """Return registered node ids whose qualname contains ``<locals>``."""
    return tuple(node_id for node_id in _node_specs if "<locals>" in node_id)


def _duplicate_flow_error(registered: FlowSpec, rejected: FlowSpec) -> RdeRegistryError:
    error_def = ERROR_CATALOG[2007]
    error_cls: Any = RdeRegistryError
    return error_cls(
        code=2007,
        name=error_def.name,
        message=error_def.message_template.format(
            flow_id=registered.id,
            registered_source_location=registered.source_location,
            rejected_source_location=rejected.source_location,
        ),
        detail={
            "flow_id": registered.id,
            "registered_source_location": registered.source_location,
            "rejected_source_location": rejected.source_location,
            "remediation": error_def.remediation,
        },
    )


def register_flow(spec: FlowSpec, fn: Any) -> None:
    """Register a flow spec and callable under ``spec.id``.

    Re-registering the exact same callable object with an equal spec is a
    no-op. Any other registration under a used id is rejected: a source
    location is not proof of identity (``importlib.reload`` builds a new
    function object at the same location), and keeping the first entry
    silently would let the registry and the decorated function disagree.

    Raises:
        RdeRegistryError: Code 2007 (``DuplicateFlowId``) if ``spec.id`` is
            already owned by a different callable or a different spec. The
            registry is left unchanged.
    """
    registered = _flow_specs.get(spec.id)
    if registered is not None:
        if _flow_functions[spec.id] is fn and registered == spec:
            return
        raise _duplicate_flow_error(registered, spec)
    # Both maps are written only after the check, so they always agree.
    _flow_specs[spec.id] = spec
    _flow_functions[spec.id] = fn


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
