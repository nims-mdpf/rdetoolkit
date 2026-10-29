from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class FormatHandler:
    name: str
    extensions: tuple[str, ...]
    target: str

@dataclass(frozen=True, slots=True)
class DiscoveredPlugin:
    name: str
    node_ids: tuple[str, ...]
    template_ids: tuple[str, ...]
    format_handlers: tuple[FormatHandler, ...]

def discover_plugins() -> tuple[DiscoveredPlugin, ...]: ...
