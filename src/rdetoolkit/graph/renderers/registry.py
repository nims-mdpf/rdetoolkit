"""Renderer registries and capability-based selection (GE-07).

A ``RendererRegistry`` is a plain, caller-owned value: nothing is registered at import
time and there is no process-global registry. ``builtin_renderers()`` builds a fresh
registry with fresh renderer instances on every call, so renderer state never outlives
one graph operation. Selection is "first registered renderer whose capabilities cover
the request"; a request nobody covers, and a missing optional module, are typed errors
raised while artifacts are planned, before any output file is touched.
"""

from __future__ import annotations

import importlib.util
import inspect
from collections.abc import Iterable

from rdetoolkit.graph.exceptions import RendererUnavailableError, UnsupportedFormatError
from rdetoolkit.graph.renderers.base import GraphRenderer
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer


class RendererRegistry:
    """An explicit, ordered set of graph renderers keyed by ``renderer_id``."""

    def __init__(self, renderers: Iterable[GraphRenderer] = ()) -> None:
        """Create a registry holding ``renderers`` in the given order.

        Args:
            renderers: Renderers to register; earlier ones win selection.

        Raises:
            TypeError: If an item is not a ``GraphRenderer`` instance.
            ValueError: If two renderers share an id.
        """
        self._renderers: dict[str, GraphRenderer] = {}
        for renderer in renderers:
            self.register(renderer)

    def register(self, renderer: GraphRenderer, *, replace: bool = False) -> None:
        """Add ``renderer`` after the registered ones.

        Args:
            renderer: The renderer instance.
            replace: Replace the renderer with the same id, keeping its position,
                instead of failing.

        Raises:
            TypeError: If ``renderer`` is not a ``GraphRenderer`` instance.
            ValueError: If the id is registered already and ``replace`` is false.
        """
        if inspect.isclass(renderer) or not isinstance(renderer, GraphRenderer):
            msg = f"Expected a GraphRenderer instance (capabilities, render, export, close), got {renderer!r}"
            raise TypeError(msg)
        renderer_id = renderer.capabilities.renderer_id
        if renderer_id in self._renderers and not replace:
            msg = f"Renderer id {renderer_id!r} is already registered; pass replace=True to replace it"
            raise ValueError(msg)
        self._renderers[renderer_id] = renderer

    def ids(self) -> tuple[str, ...]:
        """Return the registered ids in selection order."""
        return tuple(self._renderers)

    def for_format(self, fmt: str, kind: str) -> GraphRenderer:
        """Return the first registered renderer producing ``fmt`` for figures of ``kind``.

        Args:
            fmt: Output format (case-insensitive), for example ``"png"``.
            kind: ``"overlay"`` or ``"individual"``.

        Returns:
            The selected renderer.

        Raises:
            UnsupportedFormatError: If no registered renderer covers the request.
        """
        for renderer in self._renderers.values():
            if renderer.capabilities.supports(fmt, kind):
                return renderer
        raise UnsupportedFormatError(self._unsupported_message(fmt.lower(), kind))

    def for_kind(self, kind: str) -> GraphRenderer:
        """Return the first registered renderer drawing figures of ``kind`` (any format).

        Used for in-memory output, where nothing is exported.

        Args:
            kind: ``"overlay"`` or ``"individual"``.

        Returns:
            The selected renderer.

        Raises:
            UnsupportedFormatError: If no registered renderer draws ``kind`` figures.
        """
        for renderer in self._renderers.values():
            if kind in renderer.capabilities.figure_kinds:
                return renderer
        if not self._renderers:
            msg = f"Cannot render {kind} figures: no renderer is registered"
            raise UnsupportedFormatError(msg)
        msg = f"No registered renderer draws {kind} figures; registered: {self._describe()}"
        raise UnsupportedFormatError(msg)

    def _unsupported_message(self, fmt: str, kind: str) -> str:
        if not self._renderers:
            return f"Unsupported output format {fmt!r}: no renderer is registered"
        formats = sorted({name for renderer in self._renderers.values() for name in renderer.capabilities.formats})
        if fmt not in formats:
            return f"Unsupported output format {fmt!r}; supported formats: {formats} ({self._describe()})"
        return (
            f"Output format {fmt!r} is not supported for {kind} figures ({self._describe()}); "
            f"use layout='overlay' for {fmt!r} or choose another format"
        )

    def _describe(self) -> str:
        parts = []
        for renderer in self._renderers.values():
            caps = renderer.capabilities
            parts.append(f"{caps.renderer_id}: {sorted(caps.formats)} for {sorted(caps.figure_kinds)}")
        return "; ".join(parts)


def builtin_renderers() -> RendererRegistry:
    """Return a new registry with new builtin renderer instances: Matplotlib, then Plotly.

    Returns:
        A registry owned by the caller; nothing is shared between calls.
    """
    return RendererRegistry([MatplotlibRenderer(), PlotlyRenderer()])


def check_requirements(renderer: GraphRenderer) -> None:
    """Fail when a module the renderer declares in ``requires`` cannot be imported.

    The check uses ``importlib.util.find_spec`` and imports nothing.

    Args:
        renderer: The selected renderer.

    Raises:
        RendererUnavailableError: Naming the missing modules and the renderer's install hint.
    """
    caps = renderer.capabilities
    missing = [name for name in caps.requires if not _importable(name)]
    if missing:
        hint = f"; install it with: {caps.install_hint}" if caps.install_hint else ""
        msg = f"Renderer {caps.renderer_id!r} needs the optional module(s) {missing}, which are not installed{hint}"
        raise RendererUnavailableError(msg)


def _importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ImportError:
        # A dotted name whose parent package is missing.
        return False
    except ValueError:
        # Already imported, but without a module spec (for example created at run time).
        return True
