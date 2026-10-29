"""V2 RunContext — reserved types available at the flow boundary.

RunContext holds Runner reserved types (InputPaths, OutputContext, etc.)
that can be injected at the flow boundary (Design §4.3; flow-boundary DI
itself is implemented in Phase C).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig


def _build_reserved() -> dict[str, type]:
    """Build the reserved name-to-type mapping (lazy to avoid circular imports)."""
    from rdetoolkit.types import (  # noqa: PLC0415
        InputPaths,
        InvoiceData,
        IterationInfo,
        OutputContext,
        RdeConfig,
    )

    return {
        "paths": InputPaths,
        "out": OutputContext,
        "config": RdeConfig,
        "invoice": InvoiceData,
        "iteration": IterationInfo,
    }


# Populated on first access via _get_reserved().
_RESERVED: dict[str, type] | None = None


def _get_reserved() -> dict[str, type]:
    global _RESERVED  # noqa: PLW0603
    if _RESERVED is None:
        _RESERVED = _build_reserved()
    return _RESERVED


def get_reserved_mapping() -> dict[str, type]:
    """Return the reserved param-name → type mapping.

    This is the public API for accessing the RESERVED constant.
    """
    # Defensive copy: callers must not be able to mutate DI behavior globally.
    return dict(_get_reserved())


# Module-level RESERVED for direct import.
# We use __getattr__ so the lazy import works at module level.
def __getattr__(name: str) -> Any:
    if name == "RESERVED":
        return _get_reserved()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


class RunContext:
    """Runtime context providing Runner reserved types for DI resolution.

    Attributes:
        paths: Input directory paths (if available).
        out: Output directory context (if available).
        config: Strict v2 config (if available).
        invoice: Parsed invoice data (if available).
        iteration: Current iteration info (if available).
    """

    __slots__ = ("config", "invoice", "iteration", "out", "paths")

    def __init__(
        self,
        *,
        paths: InputPaths | None = None,
        out: OutputContext | None = None,
        config: RdeConfig | None = None,
        input_paths: InputPaths | None = None,
        output_context: OutputContext | None = None,
        invoice: InvoiceData | None = None,
        iteration: IterationInfo | None = None,
    ) -> None:
        self.paths = paths if paths is not None else input_paths
        self.out = out if out is not None else output_context
        self.config = config
        self.invoice = invoice
        self.iteration = iteration

    @property
    def input_paths(self) -> InputPaths | None:
        """Backward-compatible alias for the canonical ``paths`` slot."""
        return self.paths

    @property
    def output_context(self) -> OutputContext | None:
        """Backward-compatible alias for the canonical ``out`` slot."""
        return self.out

    def reserved_values(self) -> dict[str, Any]:
        """Return a mapping of reserved param-name -> value.

        Returns:
            Dict with reserved parameter names as keys and their instances as
            values. ``None``-valued entries are excluded.
        """
        mapping: dict[str, Any] = {}
        if self.paths is not None:
            mapping["paths"] = self.paths
        if self.out is not None:
            mapping["out"] = self.out
        if self.config is not None:
            mapping["config"] = self.config
        if self.invoice is not None:
            mapping["invoice"] = self.invoice
        if self.iteration is not None:
            mapping["iteration"] = self.iteration
        return mapping
