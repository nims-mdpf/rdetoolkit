"""Tests for Phase 1.5: RunContext and DI resolution algorithm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.context import RunContext
from rdetoolkit.core.node import NodeSpec, node
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig


def _dummy_fn() -> None:
    pass


# ── 1.5.1: RunContext construction and field access ─────────────────────


def _make_output_context() -> OutputContext:
    """Build an OutputContext through the mandatory factory (Design §4.2)."""
    from types import SimpleNamespace

    root = Path("/out")
    return OutputContext.from_resource_paths(
        SimpleNamespace(
            struct=root / "struct",
            meta=root / "meta",
            main_image=root / "main",
            other_image=root / "other",
            thumbnail=root / "thumb",
            raw=root / "raw",
            logs=root / "logs",
            attachment=root / "attachment",
            nonshared_raw=root / "nonshared_raw",
            invoice=root / "invoice",
        )
    )


class TestRunContext:
    """Tests for RunContext construction and field access."""

    def test_construction_with_input_paths(self) -> None:
        """RunContext stores InputPaths and makes it accessible."""
        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        ctx = RunContext(input_paths=ip)
        assert ctx.input_paths is ip

    def test_construction_with_output_context(self) -> None:
        """RunContext stores OutputContext and makes it accessible."""
        oc = _make_output_context()
        ctx = RunContext(output_context=oc)
        assert ctx.output_context is oc

    def test_construction_with_both(self) -> None:
        """RunContext accepts both InputPaths and OutputContext."""
        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        oc = _make_output_context()
        ctx = RunContext(input_paths=ip, output_context=oc)
        assert ctx.input_paths is ip
        assert ctx.output_context is oc

    def test_construction_with_none(self) -> None:
        """RunContext can be constructed with no reserved types."""
        ctx = RunContext()
        assert ctx.input_paths is None
        assert ctx.output_context is None

    def test_reserved_values_returns_mapping(self) -> None:
        """reserved_values() returns a dict mapping param names to values."""
        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        ctx = RunContext(input_paths=ip)
        reserved = ctx.reserved_values()
        assert "paths" in reserved
        assert reserved["paths"] is ip

    def test_reserved_values_excludes_none(self) -> None:
        """reserved_values() does not include None-valued entries."""
        ctx = RunContext()
        reserved = ctx.reserved_values()
        assert "paths" not in reserved
        assert "output" not in reserved
        assert "out" not in reserved
        assert "context" not in reserved

    def test_self_reference_in_reserved_values(self) -> None:
        """RunContext itself is not a reserved injectable value."""
        ctx = RunContext()
        reserved = ctx.reserved_values()
        assert "context" not in reserved


# ── 1.5.3: DI resolution algorithm ─────────────────────────────────────


def _make_spec(
    node_id: str,
    input_schema: dict[str, dict[str, object]],
    output_schema: tuple[str, ...] | None = None,
) -> NodeSpec:
    """Helper to build a NodeSpec for testing.

    Signature updated for Session C1: NodeSpec no longer holds `fn` (Design
    v2.1 §3.2, JSON-serializability requirement) and output_schema is now a
    tuple[str, ...] of type-name strings; input_schema entries are the
    JSON-serializable InputSchemaEntry dicts (type_name/has_default/default_repr).
    This helper remains unused within this file (no call sites) — only its
    signature is kept in sync with the new NodeSpec shape so the module still
    collects.
    """
    return NodeSpec(
        id=node_id,
        name=node_id,
        input_schema=input_schema,
        output_schema=output_schema if output_schema is not None else (),
        tags=(),
        version="1.0.0",
        idempotent=False,
        source_location=f"test:{node_id}",
    )


