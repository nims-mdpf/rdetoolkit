"""Discover declarative rdetoolkit plugins from package entry points."""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from importlib import metadata
from typing import Any

from rdetoolkit.templates import ProcessingTemplate


@dataclass(frozen=True, slots=True)
class FormatHandler:
    """Declarative description of one plugin-provided file format.

    Attributes:
        name: Human-readable format name.
        extensions: Supported filename extensions, including leading dots.
        target: Qualified ``pkg.mod:attr`` reference shown to users.
    """

    name: str
    extensions: tuple[str, ...]
    target: str


@dataclass(frozen=True, slots=True)
class DiscoveredPlugin:
    """Registry provenance and format declarations for one loaded plugin.

    Attributes:
        name: Entry-point name.
        node_ids: Node identifiers registered while loading the plugin.
        template_ids: Template identifiers registered while loading the plugin.
        format_handlers: Declarative format handlers supplied by the plugin.
    """

    name: str
    node_ids: tuple[str, ...]
    template_ids: tuple[str, ...]
    format_handlers: tuple[FormatHandler, ...]


_discovered: dict[tuple[str, str], DiscoveredPlugin] = {}


def _provider_members(provider: object) -> tuple[object, ...]:
    namespace = getattr(provider, "__dict__", {})
    values = [provider, *namespace.values()]
    if not inspect.isclass(provider):
        values.extend(vars(type(provider)).values())
    unique: dict[int, object] = {}
    for value in values:
        unique.setdefault(id(value), value)
    return tuple(unique.values())


def _provider_node_ids(provider: object) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(spec.id)
            for member in _provider_members(provider)
            if (spec := getattr(member, "__node_spec__", None)) is not None
        ),
    )


def _provider_template_ids(provider: object) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            f"{member.__module__}.{member.__qualname__}"
            for member in _provider_members(provider)
            if inspect.isclass(member)
            and member is not ProcessingTemplate
            and issubclass(member, ProcessingTemplate)
        ),
    )


def _handlers(provider: object) -> tuple[FormatHandler, ...]:
    handlers = getattr(provider, "FORMAT_HANDLERS", ())
    if not isinstance(handlers, tuple) or not all(isinstance(item, FormatHandler) for item in handlers):
        msg = "FORMAT_HANDLERS must be a tuple of rdetoolkit.plugin.FormatHandler values"
        raise TypeError(msg)
    return handlers


def _warning(plugin_name: str, exc: Exception) -> None:
    sys.stderr.write(
        f"Plugin {plugin_name!r} was skipped: {exc}. "
        "Remediation: reinstall or upgrade the plugin, then verify its rdetoolkit.plugins entry point.\n",
    )


def _load_plugin(entry_point: Any) -> DiscoveredPlugin:
    provider = entry_point.load()
    return DiscoveredPlugin(
        name=str(entry_point.name),
        node_ids=_provider_node_ids(provider),
        template_ids=_provider_template_ids(provider),
        format_handlers=_handlers(provider),
    )


def discover_plugins() -> tuple[DiscoveredPlugin, ...]:
    """Load and describe installed ``rdetoolkit.plugins`` entry points.

    A failing or contract-incompatible third-party entry is reported to stderr
    and skipped so inspection commands remain usable.

    Returns:
        Successfully discovered plugins in entry-point order.
    """
    plugins: list[DiscoveredPlugin] = []
    for entry_point in metadata.entry_points(group="rdetoolkit.plugins"):
        key = (str(entry_point.name), str(entry_point.value))
        cached = _discovered.get(key)
        if cached is not None:
            plugins.append(cached)
            continue
        try:
            plugin = _load_plugin(entry_point)
        except Exception as exc:  # noqa: BLE001
            _warning(str(entry_point.name), exc)
            continue
        _discovered[key] = plugin
        plugins.append(plugin)
    return tuple(plugins)
